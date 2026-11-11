"""First-run bootstrap window for production token minting.

A fresh self-hosted instance has no candidate profile, so the installer must be
able to mint a user_id=1 token to reach the onboarding flow. Once a profile has
completed onboarding the window closes and arbitrary minting is refused unless a
trusted internal gateway presents the shared secret.
"""

import pytest
from fastapi import HTTPException

import backend.app.database as database
from backend.app.api.auth import TokenRequest, obtain_access_token
from backend.app.config import settings


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Session:
    def __init__(self, row):
        self._row = row

    def execute(self, *args, **kwargs):
        return _Result(self._row)

    def close(self):
        pass


def _fake_profiles(monkeypatch, total, completed):
    monkeypatch.setattr(database, "SessionLocal", lambda: _Session((total, completed)))


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "INTERNAL_GATEWAY_SECRET", "")
    return settings


@pytest.mark.parametrize("total,completed", [(0, 0), (1, 0)])
def test_bootstrap_allows_unclaimed_instance(monkeypatch, production, total, completed):
    _fake_profiles(monkeypatch, total, completed)
    token = obtain_access_token(TokenRequest(user_id=1, ttl_seconds=60), None)
    assert token.user_id == 1
    assert token.mode == "production"


@pytest.mark.parametrize("total,completed", [(1, 1), (2, 0), (2, 1)])
def test_bootstrap_closed_after_claim(monkeypatch, production, total, completed):
    _fake_profiles(monkeypatch, total, completed)
    with pytest.raises(HTTPException) as exc:
        obtain_access_token(TokenRequest(user_id=1, ttl_seconds=60), None)
    assert exc.value.status_code == 403


def test_trusted_gateway_bypasses_profile_check(monkeypatch, production):
    monkeypatch.setattr(settings, "INTERNAL_GATEWAY_SECRET", "gateway-secret")

    def _no_db():
        raise AssertionError("profile check must not run for a trusted gateway")

    monkeypatch.setattr(database, "SessionLocal", _no_db)
    token = obtain_access_token(TokenRequest(user_id=1, ttl_seconds=60), "gateway-secret")
    assert token.user_id == 1


def test_development_mode_unaffected(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    token = obtain_access_token(TokenRequest(user_id=1, ttl_seconds=60), None)
    assert token.mode == "development"
