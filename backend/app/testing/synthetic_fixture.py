"""
Synthetic CI fixture for CareerOS (Phase 3.0.7).

Creates a brand-new, disposable database, applies the normal schema migrations, and
seeds a small, deterministic, fully synthetic dataset that the test suite needs.
No real candidate data is copied or derived from production.

Requires a maintenance PostgreSQL URL whose role can CREATE DATABASE and run DDL
(e.g. the CI postgres service). Fails closed: any error drops the partially seeded
fork before re-raising.
"""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.testing.db_guard import _fork_database_url, _psql, parse_pg_url
from backend.app.testing import fork_lifecycle


def create_synthetic_test_database(maintenance_url: str) -> str:
    """Create careeros_test_ci_<rand>, migrate it, seed synthetic data; return its URL."""
    parsed = parse_pg_url(maintenance_url)
    name = f"careeros_test_ci_{uuid.uuid4().hex[:10]}"
    _psql(parsed, "postgres", f'CREATE DATABASE "{name}"')
    url = _fork_database_url(parsed, name)

    # Bind any module-level engine (created inside database_migration's import)
    # to the disposable CI database, never to a live configuration.
    from backend.app.config import settings
    settings.DATABASE_URL = url

    engine = create_engine(url)
    try:
        _migrate_and_seed(engine)
    except Exception:
        engine.dispose()
        _psql(parsed, "postgres", f'DROP DATABASE IF EXISTS "{name}"', check=False)
        raise
    finally:
        engine.dispose()

    fork_lifecycle.write_marker(
        name,
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        username=parsed.username or "",
    )
    return url


def seed_existing_database(url: str) -> None:
    """
    Migrate and seed an existing disposable database (e.g. the CI-only service).
    Used by the Docker validation job which boots both app and database inside a
    single `docker compose` project; that database is NEVER the production one.
    """
    from backend.app.config import settings
    settings.DATABASE_URL = url

    engine = create_engine(url)
    try:
        _migrate_and_seed(engine)
    finally:
        engine.dispose()


def _migrate_and_seed(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    from backend.app.services.database_migration import run_database_migrations

    run_database_migrations(engine)
    _seed_synthetic_rows(engine)


def _seed_synthetic_rows(engine) -> None:
    from backend.app.models.application import ApplicationRecord
    from backend.app.models.application_transition import ApplicationStageTransition
    from backend.app.models.candidate import CandidateProfile
    from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
    from backend.app.models.company import Company
    from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
    from backend.app.models.opportunity import Opportunity
    from backend.app.models.preferences import UserPreferences
    from backend.app.models.resume import ResumeDocument
    from backend.app.models.resume_version import ResumeVersion
    from backend.app.models.source import JobSource
    from sqlalchemy.orm import Session
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as db:
        candidate = CandidateProfile(
            user_id=1,
            name="Alex Synthetic Test",
            email="synthetic.candidate1@example.test",
            phone="+90 555 000 0001",
            location="Istanbul, Türkiye",
            degree="B.Tech in Artificial Intelligence & Data Science",
            graduation_year=2027,
            college="Synthetic Institute of Technology",
            bio="Synthetic candidate for CI fixtures; not a real person. Building reliably tested tooling.",
            github_url="https://github.com/synthetic-candidate",
            github_username="synthetic-candidate",
            linkedin_url="https://www.linkedin.com/in/synthetic-candidate",
            onboarding_status="completed",
            onboarding_step=6,
            evidence_version=53,
            skills=[
                {"name": name, "level": "advanced", "category": category}
                for name, category in [
                    ("Python", "Languages"), ("JavaScript", "Languages"), ("TypeScript", "Languages"),
                    ("SQL", "Languages"), ("HTML", "Languages"), ("CSS", "Languages"),
                    ("Dart", "Languages"), ("React", "Frontend"), ("Next.js", "Frontend"),
                    ("Flutter", "Frontend"), ("Vue.js", "Frontend"),
                    ("Node.js", "Backend"), ("Express.js", "Backend"), ("FastAPI", "Backend"),
                    ("Supabase", "Backend"), ("PostgreSQL", "Databases"), ("MongoDB", "Databases"),
                    ("SQLAlchemy", "Databases"), ("Docker", "Tools"), ("Git", "Tools"),
                    ("AWS", "Tools"), ("Kubernetes", "Tools"),
                ]
            ],
            projects=[
                {"title": "Synthetic Ledger", "description": "Synthetic double-entry ledger service handling thousands of daily transactions.", "tech_stack": ["Python", "FastAPI", "PostgreSQL"]},
                {"title": "Synthetic Inbox", "description": "Synthetic message prioritization assistant built to reduce response latency.", "tech_stack": ["TypeScript", "Node.js"]},
                {"title": "Synthetic Scheduler", "description": "Synthetic cron/scheduler dashboard visualizing SLO compliance.", "tech_stack": ["Go", "Kubernetes"]},
                {"title": "Synthetic Profiler", "description": "Synthetic performance profiler UI rendered in React for deep profiling.", "tech_stack": ["React", "JavaScript"]},
                {"title": "Synthetic Mirror", "description": "Synthetic multi-region search replica keeping indexes fresh.", "tech_stack": ["Python", "Redis"]},
                {"title": "Synthetic Gauge", "description": "Synthetic alerting layer for service-level objectives and uptime guarantees.", "tech_stack": ["Python", "AWS"]},
                {"title": "Synthetic Compiler", "description": "Synthetic mini compiler study with optimization passes.", "tech_stack": ["C++", "LLVM"]},
            ],
            experience=[{"title": "Synthetic Intern", "company": "Synthetic Corp", "duration": "2024",
                        "bullets": ["Built a synthetic FastAPI service handling 500 req/s", "Reduced CI runtime by 30%", "Led migration to Go services"]}],
            certifications=[],
            achievements=[],
            career_goals=["AI engineering", "developer tools"],
        )

        preferences = UserPreferences(
            preferred_categories=["AI/ML", "Full Stack"],
            search_priorities=[{"priority": 1, "category": "AI/ML"}],
            preferred_locations=["Remote, India", "Bengaluru"],
            paid_only=True,
            min_stipend=20000.0,
            graduation_year=2027,
        )

        candidate_github = dict(candidate.github_data or {})
        candidate_github["repos"] = [{"name": "synthetic-repo", "stars": 3}]
        candidate.github_data = candidate_github

        source = JobSource(
            name="synthetic-ci",
            source_type="ats",
            integration_method="api",
            connection_status="connected",
            sync_frequency_hours=24,
        )

        companies = [
            Company(name="Cloudaeon Software Technology Private Limited", website="https://cloudaeon.example.test", ats_provider="greenhouse", industry="Software"),
            Company(name="Synth Corp One", website="https://one.example.test", ats_provider="lever", industry="AI"),
            Company(name="Synth Corp Two", website="https://two.example.test", ats_provider="ashby", industry="Data"),
            Company(name="Synth Corp Three", website="https://three.example.test", ats_provider="smartrecruiters", industry="Cloud"),
            Company(name="Synth Corp Four", website="https://four.example.test", ats_provider="custom", industry="Developer Tools"),
        ]

        opportunities = [
            Opportunity(
                id=37,
                user_id=1,
                title="Backend Intern",
                normalized_title="Backend Intern",
                company_name=companies[0].name,
                company_id=None,  # fixed after flush
                location="Bengaluru, India",
                normalized_location="Bengaluru, India",
                workplace_type="onsite",
                internship_type="in-office",
                employment_type="internship",
                internship_category="backend",
                description="Cloudaeon Software Technology Private Limited backend internship. Python FastAPI PostgreSQL Docker required. Work on production-grade services and developer tools.",
                required_skills=["Python", "FastAPI", "PostgreSQL"],
                preferred_skills=["Docker", "Git"],
                stipend_text="INR 30,000/month",
                min_stipend=30000.0,
                is_paid=True,
                status="verified",
                original_url="https://example.test/careers/cloudaeon-backend",
                source_platform="synthetic",
                source_links=[{"source": "synthetic", "url": "https://example.test/careers/cloudaeon-backend"}],
                quality_score=85.0,
                quality_breakdown={
                    "classification_confidence": 18.0,
                    "skill_relevance": 22.0,
                    "company_identification": 14.0,
                    "application_link_quality": 13.0,
                    "freshness_clarity": 12.0,
                    "data_completeness": 6.0,
                    "reasons": ["Synthetic job classified as an internship", "Strong alignment with candidate skills"],
                },
                match_score=80.0,
                match_analysis={"source": "synthetic", "user_id": 1},
            ),
        ] + [
            Opportunity(
                user_id=1,
                title=f"{label} Intern",
                normalized_title=f"{label} Intern",
                company_name=c.name,
                company_id=None,
                location="Remote, India",
                normalized_location="Remote, India",
                workplace_type="remote",
                internship_type="remote",
                employment_type="internship",
                internship_category="backend",
                description=f"Synthetic internship at {c.name}. Python FastAPI PostgreSQL required. Automate workflows and ship developer tools with strong testing culture.",
                required_skills=["Python", "FastAPI", "PostgreSQL"],
                preferred_skills=["Docker"],
                stipend_text="INR 25,000/month",
                min_stipend=25000.0,
                is_paid=True,
                status="verified",
                original_url=f"https://example.test/careers/{token}",
                source_platform="synthetic",
                source_links=[{"source": "synthetic", "url": f"https://example.test/careers/{token}"}],
                quality_score=80.0,
                quality_breakdown={
                    "classification_confidence": 18.0,
                    "skill_relevance": 22.0,
                    "company_identification": 14.0,
                    "application_link_quality": 13.0,
                    "freshness_clarity": 12.0,
                    "data_completeness": 6.0,
                    "reasons": ["Synthetic job classified as an internship", "Strong alignment with candidate skills"],
                },
                match_score=75.0,
                match_analysis={"source": "synthetic", "user_id": 1},
            )
            for label, c, token in zip(
                ["Frontend", "Infrastructure", "Data", "Platform"],
                companies[1:],
                ["one", "two", "three", "four"],
            )
        ]

        db.add_all([candidate, preferences, source, *companies])
        db.flush()
        for opp, company in zip(opportunities, companies):
            opp.company_id = company.id
        db.add_all(opportunities)
        # The explicit id=37 above leaves the serial sequence behind; resync immediately.
        db.execute(text("SELECT setval(pg_get_serial_sequence('opportunities','id'), (SELECT max(id) FROM opportunities))"))
        db.flush()

        resume_master = ResumeDocument(
            user_id=1,
            title="Synthetic Master Resume",
            template_id="ats_modern",
            latex_content=(
                "\\documentclass{article}\n"
                "\\usepackage{hyperref}\n"
                "\\hypersetup{colorlinks=true}\n"
                "\\begin{document}\n"
                "Alex Synthetic Test | synthetic.candidate1@example.test | +90 555 000 0001 | github.com/synthetic-candidate\n\n"
                "\\section*{Education}\n"
                "\\begin{itemize}\n"
                "\\item B.Tech Artificial Intelligence \\& Data Science, 2023-2027\n"
                "\\end{itemize}\n\n"
                "\\section*{Technical Skills}\n"
                "Python, FastAPI, PostgreSQL, SQLAlchemy, React, TypeScript, Docker, Kubernetes, AWS, Git, Linux\n\n"
                "\\section*{Projects}\n"
                "\\begin{itemize}\n"
                "\\item Built a synthetic FastAPI ledger service handling 500 req/s with <50 ms p95 latency\n"
                "\\item Developed a synthetic multi-region search replica keeping 1M document indexes fresh\n"
                "\\item Led a synthetic dashboard migration from jQuery to React, reducing bundle size 40%\n"
                "\\item Reduced synthetic CI runtime by 30% with caching and matrix builds\n"
                "\\end{itemize}\n"
                "\\end{document}"
            ),
            is_master=True,
            version=78,
            pdf_path="/synthetic/artifacts/master_resume.pdf",
            structured_content={
                "personal_info": {"name": "Alex Synthetic Test", "email": "synthetic.candidate1@example.test"},
                "summary": "Synthetic AI engineer with strong Python, FastAPI and PostgreSQL. Seeking an internship to build reliable backend services at scale.",
                "education": [
                    {"degree": "B.Tech in Artificial Intelligence \\& Data Science", "college": "Synthetic Institute of Technology", "graduation_year": 2027},
                ],
                "skills": [{"name": "Python"}, {"name": "FastAPI"}, {"name": "PostgreSQL"}, {"name": "Docker"}, {"name": "React"}, {"name": "SQL"}],
                "experience": [
                    {"title": "Synthetic Intern", "company": "Synthetic Corp", "duration": "2024",
                     "bullets": ["Built a synthetic FastAPI service handling 500 req/s with <50ms p95", "Reduced CI runtime by 30% via caching", "Shipped migrations with zero downtime across two regions"]},
                ],
                "projects": [
                    {"title": "Synthetic Ledger", "description": "Designed a double-entry ledger handling 10k daily transactions", "tech_stack": ["Python", "FastAPI", "PostgreSQL"]},
                    {"title": "Synthetic Inbox", "description": "Message prioritization reducing response latency by 40%", "tech_stack": ["TypeScript", "Node.js"]},
                    {"title": "Synthetic Scheduler", "description": "SLO dashboard visualizing 99.9% uptime", "tech_stack": ["Go", "Kubernetes"]},
                ],
                "certifications": [
                    {"name": "Synthetic Cloud Practitioner", "year": 2025},
                    {"name": "Synthetic ML Foundations", "year": 2025},
                ],
                "achievements": [
                    {"title": "Synthetic national hackathon finalist 2025"},
                    {"title": "Synthetic open-source contributor with 200+ merged PRs"},
                ],
            },
            tailored_insights={"items": ["Python op", "FastAPI op"]},
        )
        resume_tailored = ResumeDocument(
            user_id=1,
            title="Synthetic Tailored Resume",
            template_id="ats_classic",
            latex_content="\\documentclass{article}\\begin{document}Synthetic Tailored Resume\\end{document}",
            version=4,
            pdf_path="/synthetic/artifacts/tailored_resume.pdf",
            structured_content={"skills": {"items": [{"name": "Python"}]}},
        )
        db.add_all([resume_master, resume_tailored])
        db.flush()

        db.add_all([
            ResumeVersion(resume_id=resume_master.id, version_number=78, title="Synthetic Master v78", latex_content=resume_master.latex_content),
            ResumeVersion(resume_id=resume_tailored.id, version_number=4, title="Synthetic Tailored v4", latex_content=resume_tailored.latex_content),
        ])

        apps = []
        stage_map = [
            ("ready_to_apply", "applied"),
            ("applied", "screening"),
            ("applied", "screening"),
            ("applied", "technical_interview"),
            ("screening", "technical_interview"),
            ("applied", "rejected"),
            ("applied", "applied"),
            ("ready_to_apply", "applied"),
        ]
        for i, (opportunity, stage_pair) in enumerate(zip(opportunities, stage_map)):
            rec = ApplicationRecord(
                opportunity_id=opportunity.id,
                company_name=opportunity.company_name,
                job_title=opportunity.title,
                original_url=opportunity.original_url,
                status=stage_pair[-1],
                applied_date=now - timedelta(days=30 - i * 3),
                match_score=75.0 - i,
                resume_id=resume_master.id,
                resume_version_number=78,
                submission_mode="assisted",
                cover_letter_text="Synthetic cover letter payload, deterministic and not a real person.",
                follow_up_date=now + timedelta(days=2),
            )
            apps.append(rec)
        db.add_all(apps)
        db.flush()
        for rec, (from_stage, to_stage) in zip(apps, stage_map):
            db.add(ApplicationStageTransition(
                application_id=rec.id,
                from_stage=from_stage,
                to_stage=to_stage,
                transitioned_at=now - timedelta(days=7),
                notes="synthetic transition",
            ))

        match_analyses = [
            {"user_id": 1, "summary": "synthetic match", "candidate_content_hash": f"cand_hash_{i}", "opportunity_content_hash": f"opp_hash_{i}", "engine_version": "2.0.0"}
            for i in range(6)
        ]
        matches = [
            CandidateOpportunityMatch(
                user_id=1,
                candidate_id=candidate.id,
                opportunity_id=opportunities[i].id,
                match_score=72.0 + i,
                eligibility_status="eligible",
                match_analysis=match_analyses[i],
                candidate_content_hash=f"cand_hash_{i}_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                opportunity_content_hash=f"opp_hash_{i}_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                engine_version="2.0.0",
                engine_generation=2,
            )
            for i in range(len(opportunities))
        ]
        db.add_all(matches)

        expires = now + timedelta(days=1)
        snapshot = DiscoveryRankingSnapshot(
            snapshot_key="synthetic-ci-snapshot",
            snapshot_id="synthetic-ci-snapshot-1",
            user_id=1,
            signature="synthetic-signature",
            candidate_evidence_version="v1",
            total_count=len(opportunities),
            snapshot_ids=[o.id for o in opportunities],
            expires_at=expires,
        )

        # Bulk-seed additional opportunities to satisfy market-scale tests (>=50).
        bulk_specs = [
            ("Backend Intern", "Python", "FastAPI", "PostgreSQL"),
            ("Frontend Intern", "React", "TypeScript", "Next.js"),
            ("Data Intern", "Python", "SQL", "PostgreSQL"),
            ("Infra Intern", "Kubernetes", "Docker", "AWS"),
            ("ML Intern", "Python", "PyTorch", "scikit-learn"),
        ]
        bulk_opps = []
        for i in range(55):
            title_word, s1, s2, s3 = bulk_specs[i % len(bulk_specs)]
            company_index = i % len(companies)
            company = companies[company_index]
            bulk_opps.append(Opportunity(
                user_id=1,
                title=f"{title_word} {i + 1}",
                normalized_title=title_word,
                company_name=company.name,
                company_id=company.id,
                location="Remote, India",
                normalized_location="Remote, India",
                workplace_type="remote",
                internship_type="remote",
                employment_type="internship",
                internship_category="backend",
                description=f"Synthetic internship at {company.name}. Required skills include {s1}, {s2}, {s3}. Duties include testing and shipping features.",
                required_skills=[s1, s2, s3],
                preferred_skills=["Git", "Docker"],
                stipend_text="INR 20,000/month",
                min_stipend=20000.0,
                is_paid=True,
                status="verified",
                original_url=f"https://example.test/careers/bulk-{i:03d}",
                source_platform="synthetic",
                source_links=[{"source": "synthetic", "url": f"https://example.test/careers/bulk-{i:03d}"}],
                quality_score=75.0,
                quality_breakdown={
                    "classification_confidence": 18.0,
                    "skill_relevance": 20.0,
                    "company_identification": 12.0,
                    "application_link_quality": 12.0,
                    "freshness_clarity": 10.0,
                    "data_completeness": 3.0,
                    "reasons": ["Synthetic internship", "Bulk-seeded for market-scale tests"],
                },
                match_score=float(55 + (i % 40)),
                match_analysis={"source": "synthetic", "user_id": 1},
            ))
        db.add_all(bulk_opps)

        db.add(snapshot)
        db.commit()
