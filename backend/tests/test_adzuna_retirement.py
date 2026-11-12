"""Adzuna retirement regression tests (v3.1.0).

The optional Adzuna integration was removed; the remaining discovery providers
must keep working, and the app must start with no Adzuna credentials present.
"""

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.sources import DEFAULT_SOURCES, ensure_default_sources_seeded
from backend.app.config import Settings
from backend.app.database import SessionLocal
from backend.app.main import app
from backend.app.models.source import JobSource
from backend.app.services import seed_data

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_connector_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.app.connectors.adzuna")


def test_no_adzuna_configuration_remains():
    assert "ADZUNA_APP_ID" not in Settings.model_fields
    assert "ADZUNA_APP_KEY" not in Settings.model_fields
    for rel in (".env.example", "docker-compose.yml", "backend/app/config.py"):
        assert "ADZUNA" not in (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_adzuna_absent_from_seeded_sources():
    assert all(s["name"].lower() != "adzuna" for s in DEFAULT_SOURCES)
    assert all(s["name"].lower() != "adzuna" for s in seed_data.INITIAL_SOURCES)


def test_shared_discovery_providers_preserved():
    names = {s["name"] for s in DEFAULT_SOURCES}
    assert {
        "Internshala",
        "Greenhouse",
        "Lever",
        "Ashby",
        "SmartRecruiters",
        "Y Combinator",
        "Remotive",
        "Remote OK",
        "LinkedIn Jobs",
        "RSS Feeds",
        "Manual Import",
    } <= names


def test_legacy_adzuna_row_is_marked_unsupported():
    db = SessionLocal()
    try:
        row = db.query(JobSource).filter(JobSource.name == "Adzuna").first()
        if row is None:
            row = JobSource(
                name="Adzuna",
                source_type="api",
                integration_method="api",
                connection_status="not_configured",
                sync_frequency_hours=12,
                config_data={},
            )
            db.add(row)
            db.commit()

        ensure_default_sources_seeded(db)
        db.refresh(row)
        assert row.connection_status == "unsupported"
        assert "retired" in (row.last_error_message or "").lower()

        response = client.get("/api/sources")
        assert response.status_code == 200
        assert all(s["name"] != "Adzuna" or s["connection_status"] == "unsupported" for s in response.json())
    finally:
        db.query(JobSource).filter(JobSource.name == "Adzuna").delete()
        db.commit()
        db.close()
