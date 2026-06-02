"""Unit tests for auth dependencies — no DB required."""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import _decode_jwt, require_admin_jwt, require_api_key, require_jwt


# ---------------------------------------------------------------------------
# _decode_jwt (pure function — no I/O)
# ---------------------------------------------------------------------------

def _make_token(payload: dict, secret: str = "test-secret", algorithm: str = "HS256") -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def test_decode_valid_jwt(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.jwt_secret", "test-secret")
    monkeypatch.setattr("app.middleware.auth.settings.jwt_algorithm", "HS256")

    token = _make_token({"sub": "user1", "role": "user"}, secret="test-secret")
    claims = _decode_jwt(token)
    assert claims["sub"] == "user1"


def test_decode_expired_jwt(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr("app.middleware.auth.settings.jwt_secret", "test-secret")
    monkeypatch.setattr("app.middleware.auth.settings.jwt_algorithm", "HS256")

    expired = _make_token(
        {"sub": "u1", "exp": int(time.time()) - 10},
        secret="test-secret",
    )
    with pytest.raises(HTTPException) as exc_info:
        _decode_jwt(expired)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_decode_invalid_signature(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr("app.middleware.auth.settings.jwt_secret", "correct-secret")
    monkeypatch.setattr("app.middleware.auth.settings.jwt_algorithm", "HS256")

    token = _make_token({"sub": "u1"}, secret="wrong-secret")
    with pytest.raises(HTTPException) as exc_info:
        _decode_jwt(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# require_api_key via test app
# ---------------------------------------------------------------------------

_test_app = FastAPI()


@_test_app.get("/protected")
async def _protected(_auth=None):
    return {"ok": True}


# Attach the dependency directly so we can test it in isolation
from fastapi import Depends, Security  # noqa: E402

_key_app = FastAPI()


@_key_app.get("/ok")
async def _key_route(_auth: None = Security(require_api_key)):
    return {"ok": True}


def test_api_key_missing_returns_401(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.api_key", "secret-key")
    client = TestClient(_key_app, raise_server_exceptions=False)
    resp = client.get("/ok")
    assert resp.status_code == 401


def test_api_key_wrong_returns_401(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.api_key", "secret-key")
    client = TestClient(_key_app, raise_server_exceptions=False)
    resp = client.get("/ok", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_api_key_correct_returns_200(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.api_key", "secret-key")
    client = TestClient(_key_app, raise_server_exceptions=False)
    resp = client.get("/ok", headers={"X-API-Key": "secret-key"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# require_admin_jwt
# ---------------------------------------------------------------------------

_jwt_app = FastAPI()


@_jwt_app.get("/admin")
async def _admin_route(claims: dict = Depends(require_admin_jwt)):
    return {"role": claims.get("role")}


def test_admin_jwt_non_admin_returns_403(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.jwt_secret", "s")
    monkeypatch.setattr("app.middleware.auth.settings.jwt_algorithm", "HS256")

    token = _make_token({"role": "user"}, secret="s")
    client = TestClient(_jwt_app, raise_server_exceptions=False)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_jwt_admin_returns_200(monkeypatch):
    monkeypatch.setattr("app.middleware.auth.settings.jwt_secret", "s")
    monkeypatch.setattr("app.middleware.auth.settings.jwt_algorithm", "HS256")

    token = _make_token({"role": "admin"}, secret="s")
    client = TestClient(_jwt_app, raise_server_exceptions=False)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
