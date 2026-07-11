"""Tests for request ID middleware and JWT secret validation."""
import uuid

import pytest


@pytest.mark.asyncio
async def test_response_includes_request_id_header(client):
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    # Must be a valid UUID
    uuid.UUID(response.headers["x-request-id"])


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_echoed(client):
    custom_id = str(uuid.uuid4())
    response = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_each_request_gets_unique_id(client):
    r1 = await client.get("/health")
    r2 = await client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


def test_jwt_secret_validation_rejects_short_custom_secret():
    from app.main import _validate_jwt_secret
    from app.core import config as cfg_mod

    original = cfg_mod.settings.jwt_secret
    try:
        cfg_mod.settings.jwt_secret = "tooshort"
        with pytest.raises(RuntimeError, match="32 bytes"):
            _validate_jwt_secret()
    finally:
        cfg_mod.settings.jwt_secret = original


def test_jwt_secret_validation_allows_dev_default():
    from app.main import _validate_jwt_secret, _DEV_JWT_SECRET
    from app.core import config as cfg_mod

    original = cfg_mod.settings.jwt_secret
    try:
        cfg_mod.settings.jwt_secret = _DEV_JWT_SECRET
        _validate_jwt_secret()  # must not raise
    finally:
        cfg_mod.settings.jwt_secret = original


def test_jwt_secret_validation_accepts_long_secret():
    from app.main import _validate_jwt_secret
    from app.core import config as cfg_mod

    original = cfg_mod.settings.jwt_secret
    try:
        cfg_mod.settings.jwt_secret = "a" * 32
        _validate_jwt_secret()  # must not raise
    finally:
        cfg_mod.settings.jwt_secret = original
