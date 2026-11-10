# ---------------------------------------------------------------------------
# Test database isolation — MUST run before any backend.app import.
# The suite is PostgreSQL-native, so the supported strategy is a disposable
# same-server PostgreSQL copy of the live database (create -> pg_dump ->
# pg_restore), dropped at session end. The live database is never opened by
# tests; DATABASE_URL is rewritten before the engine is constructed.
# ---------------------------------------------------------------------------
import os
import json

os.environ.setdefault("ENVIRONMENT", "test")
# Relax fork rate limits enough for the full suite; production defaults stay as configured.
os.environ.setdefault("RATE_LIMIT_SCALE", "200")

from backend.app.config import settings as _settings
from backend.app.testing import fork_lifecycle as _fork_lifecycle
from backend.app.testing.db_guard import (
    assert_disposable_pg_url,
)

_PRODUCTION_URL = os.environ.get("DATABASE_URL")

# Critical A (CI mode): create the synthetic database BEFORE any backend.app.database
# import, so nothing can bind to the production-like DATABASE_URL at module scope.
_SCHEMA_ONLY = os.environ.get("CAREEROS_TEST_SCHEMA_ONLY") == "1"
_EXPLICIT_TEST_URL = os.environ.get("CAREEROS_TEST_DATABASE_URL")
_CI_SYNTHETIC = os.environ.get("CAREEROS_CI_SYNTHETIC") == "1"
_LIFECYCLE_FORK = None
_SETTINGS_IMPORT = False

if _CI_SYNTHETIC:
    _SERVICE_URL = os.environ.get("CAREEROS_CI_DATABASE_URL")
    if not _SERVICE_URL:
        raise RuntimeError(
            "CAREEROS_CI_SYNTHETIC=1 requires CAREEROS_CI_DATABASE_URL (a disposable CI "
            "maintenance URL, e.g. the CI postgres service). Never falls back to a live database."
        )
    from backend.app.testing import synthetic_fixture as _synthetic_fixture
    from backend.app.testing import fork_lifecycle as _fork_lifecycle

    _TEST_URL = _synthetic_fixture.create_synthetic_test_database(_SERVICE_URL)
    os.environ["DATABASE_URL"] = _TEST_URL
    _settings.ORIGINAL_DATABASE_URL = _SERVICE_URL  # forks are created on this CI server only
    _LIFECYCLE_FORK = _fork_lifecycle.OwnedFork(_TEST_URL, _TEST_URL.rsplit("/", 1)[-1], _fork_lifecycle.parse_pg_url(_SERVICE_URL))
else:
    from backend.app.config import settings as _settings

    _PRODUCTION_URL = _settings.DATABASE_URL
    _SETTINGS_IMPORT = True
    # Capture the authoritative production URL before any rewrite so tests can prove isolation.
    _settings.ORIGINAL_DATABASE_URL = _PRODUCTION_URL

    # Critical: two mechanisms, both required.
    # (1) os.environ rewrite — spawned worker processes import from scratch and pick it up.
    # (2) settings.DATABASE_URL rewrite — this process already imported config; the cached
    #     object is what every downstream module binds against.
    if _EXPLICIT_TEST_URL:
        assert_disposable_pg_url(_EXPLICIT_TEST_URL, _PRODUCTION_URL)
        _TEST_URL = _EXPLICIT_TEST_URL
    else:
        from backend.app.testing import fork_lifecycle as _fork_lifecycle

        _LIFECYCLE_FORK = _fork_lifecycle.provision(_PRODUCTION_URL, schema_only=_SCHEMA_ONLY)
        _TEST_URL = _LIFECYCLE_FORK.url
os.environ["DATABASE_URL"] = _TEST_URL
_settings.DATABASE_URL = _TEST_URL

import pytest

from backend.app.main import app
from backend.app.core.auth import get_current_user_id
from backend.app.database import engine as _engine

assert _settings.DATABASE_URL != _PRODUCTION_URL, (
    "FATAL: settings still bind production DATABASE_URL; test isolation is broken. "
    "Refusing to run."
)

# Engine fingerprint guard: the engine must point at the disposable fork.
_probe = _engine.url
assert _probe.database and _probe.database.startswith("careeros_test_"), (
    f"FATAL: backend engine bound to non-test database {_probe.database!r}; refusing to run."
)


@pytest.fixture(scope="session", autouse=True)
def _disposable_fork_lifecycle_guard():
    """
    Deterministic teardown of the disposable fork at session end. Failure is loud:
    it aborts the session with a non-zero exit and a recovery instruction.
    """
    yield
    if _LIFECYCLE_FORK is not None:
        report = _LIFECYCLE_FORK.cleanup(reason="pytest session end")
        if not report["success"]:
            raise RuntimeError(
                "disposable fork cleanup FAILED and a fork was left behind: "
                + json.dumps(
                    {k: report[k] for k in ("database", "remaining_connections", "error", "recovery")},
                    default=str,
                )
            )


@pytest.fixture(autouse=True)
def default_test_authentication(request):
    """
    Provides explicit test authentication dependency override for non-security test suites,
    ensuring legacy functional tests execute with an authenticated test user (user_id=1).
    Security tests in test_resume_studio_security explicitly test live 401/403 filters and
    are exempt from this override.
    """
    exempt_suites = [
        "test_resume_studio_security",
        "test_resume_studio_iteration1_2",
        "test_groq_live_integration",
        "test_resume_parser",
        "test_token_security",
        "test_structured_resume_editing",
        "test_legacy_preservation_and_concurrency",
        "test_migration_and_pdf_safety",
        "test_pdf_page_budgeting",
        "test_page_size_and_metadata_integrity",
        "test_post_promotion_recovery",
        "test_github_project_intelligence",
        "test_github_intelligence_trust_and_security",
        "test_github_adversarial_and_race_safety",
        "test_job_matching_intelligence",
        "test_matching_jd_evaluation_benchmark",
        "test_matching_adversarial_and_hardening",
        "test_candidate_match_isolation",
        "test_candidate_aware_discovery",
        "test_discovery_ranking_and_scale",
        "test_pagination_concurrency_and_audit",
        "test_distributed_snapshots_and_stale_writes",
        "test_iteration_2_6_frontend_integration",
        "test_iteration_2_7_security_and_tenant_isolation",
        "test_iteration_2_8_onboarding_and_profile_readiness",
        "test_iteration_2_8_1_production_verification_audit",
        "test_security_remediation"
    ]
    if any(s in request.node.nodeid for s in exempt_suites):
        yield
        return

    # Apply explicit test authentication override
    app.dependency_overrides[get_current_user_id] = lambda: 1
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def cleanup_ephemeral_test_data(request):
    # Only run database cleanup if running suites that insert multi-user test entities
    multi_user_suites = [
        "test_resume_studio_security",
        "test_resume_studio_iteration1_2",
        "test_groq_live_integration",
        "test_resume_parser",
        "test_token_security",
        "test_structured_resume_editing",
        "test_legacy_preservation_and_concurrency",
        "test_migration_and_pdf_safety",
        "test_pdf_page_budgeting",
        "test_page_size_and_metadata_integrity",
        "test_post_promotion_recovery",
        "test_github_project_intelligence",
        "test_github_intelligence_trust_and_security",
        "test_github_adversarial_and_race_safety",
        "test_job_matching_intelligence",
        "test_matching_jd_evaluation_benchmark",
        "test_matching_adversarial_and_hardening",
        "test_candidate_match_isolation",
        "test_candidate_aware_discovery",
        "test_discovery_ranking_and_scale",
        "test_pagination_concurrency_and_audit",
        "test_distributed_snapshots_and_stale_writes",
        "test_iteration_2_6_frontend_integration",
        "test_iteration_2_7_security_and_tenant_isolation",
        "test_iteration_2_8_onboarding_and_profile_readiness",
        "test_iteration_2_8_1_production_verification_audit",
        "test_security_remediation"
    ]
    is_multi_user = any(s in request.node.nodeid for s in multi_user_suites)
    if is_multi_user:
        from backend.app.database import SessionLocal
        from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
        from backend.app.services.discovery_snapshot_manager import snapshot_manager

        _db = SessionLocal()
        try:
            _db.query(DiscoveryRankingSnapshot).filter(DiscoveryRankingSnapshot.user_id >= 1000).delete(synchronize_session=False)
            _db.commit()
            snapshot_manager.l1_cache.clear()
        except Exception:
            _db.rollback()
        finally:
            _db.close()

    yield

    if is_multi_user:
        from backend.app.database import SessionLocal
        from backend.app.models.candidate import CandidateProfile
        from backend.app.models.opportunity import Opportunity
        from backend.app.models.resume import ResumeDocument
        from backend.app.models.resume_version import ResumeVersion
        from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
        from backend.app.services.discovery_snapshot_manager import snapshot_manager

        db = SessionLocal()
        try:
            test_resumes = db.query(ResumeDocument).filter(ResumeDocument.user_id >= 1000).all()
            for r in test_resumes:
                db.query(ResumeVersion).filter(ResumeVersion.resume_id == r.id).delete()
                db.delete(r)
            db.query(CandidateProfile).filter(CandidateProfile.user_id >= 1000).delete()
            db.query(Opportunity).filter(Opportunity.user_id >= 1000).delete()
            db.query(DiscoveryRankingSnapshot).filter(DiscoveryRankingSnapshot.user_id >= 1000).delete(synchronize_session=False)
            db.commit()
            snapshot_manager.l1_cache.clear()
        except Exception:
            db.rollback()
        finally:
            db.close()
