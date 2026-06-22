"""Tests for GET /health."""
import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_required_fields(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    @pytest.mark.asyncio
    async def test_version_matches_app(self, client):
        from app.main import app
        r = await client.get("/health")
        assert r.json()["version"] == app.version

    @pytest.mark.asyncio
    async def test_db_error_returns_503(self, client):
        with patch("app.main.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
            mock_session_cls.return_value = mock_session

            r = await client.get("/health")

        assert r.status_code == 503
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] == "error"
