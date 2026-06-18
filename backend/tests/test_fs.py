"""Tests for the filesystem browse endpoint, including localhost-only enforcement."""
import pytest


class TestFsBrowseAuth:
    @pytest.mark.asyncio
    async def test_localhost_allowed(self, local_client, tmp_path):
        r = await local_client.get(f"/api/fs/browse?path={tmp_path}")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_external_ip_blocked(self, remote_client, tmp_path):
        r = await remote_client.get(f"/api/fs/browse?path={tmp_path}")
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_path_returns_400(self, local_client):
        r = await local_client.get("/api/fs/browse?path=/nonexistent/xyz/path")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_default_path_returns_home(self, local_client):
        r = await local_client.get("/api/fs/browse")
        assert r.status_code == 200
        data = r.json()
        assert "path" in data
        assert "entries" in data

    @pytest.mark.asyncio
    async def test_browse_returns_directory_entries(self, local_client, tmp_path):
        (tmp_path / "subdir").mkdir()
        r = await local_client.get(f"/api/fs/browse?path={tmp_path}")
        assert r.status_code == 200
        data = r.json()
        names = [e["name"] for e in data["entries"]]
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_git_repo_flagged(self, local_client, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / ".git").mkdir()
        r = await local_client.get(f"/api/fs/browse?path={tmp_path}")
        assert r.status_code == 200
        entries = r.json()["entries"]
        repo_entry = next(e for e in entries if e["name"] == "myrepo")
        assert repo_entry["is_git_repo"] is True
