"""Tests for LinearAdapter fetch methods using respx HTTP mocking."""
import pytest
import respx
import httpx

from app.services.adapters.linear import LinearAdapter

LINEAR_URL = "https://api.linear.app/graphql"


class TestLinearAdapterNormalize:
    def test_normalize_basic(self):
        raw = {
            "identifier": "ENG-1",
            "title": "Fix the bug",
            "description": "Details here",
            "state": {"name": "In Progress"},
        }
        result = LinearAdapter().normalize(raw)
        assert result.source == "linear"
        assert result.source_id == "ENG-1"
        assert result.title == "Fix the bug"
        assert result.status == "in_progress"

    def test_normalize_maps_all_statuses(self):
        adapter = LinearAdapter()
        mapping = {
            "Todo": "open",
            "In Progress": "in_progress",
            "Done": "done",
            "Cancelled": "done",
            "Backlog": "open",
            "Unknown": "open",
        }
        for state_name, expected in mapping.items():
            raw = {"identifier": "X-1", "title": "T", "state": {"name": state_name}}
            assert adapter.normalize(raw).status == expected

    def test_normalize_missing_description(self):
        raw = {"identifier": "ENG-2", "title": "T", "state": {"name": "Todo"}}
        result = LinearAdapter().normalize(raw)
        assert result.description is None


class TestLinearAdapterFetchIssue:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issue_returns_normalized(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={
            "data": {
                "issue": {
                    "identifier": "ENG-7",
                    "title": "Dark mode",
                    "description": "Add dark mode",
                    "state": {"name": "Backlog"},
                }
            }
        }))
        result = await LinearAdapter().fetch_issue("ENG-7", "lin_api_key")
        assert result.source_id == "ENG-7"
        assert result.title == "Dark mode"
        assert result.status == "open"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issue_not_found_raises_404(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={"data": {"issue": None}}))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await LinearAdapter().fetch_issue("MISSING-1", "key")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issue_http_error_raises(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(401))
        with pytest.raises(httpx.HTTPStatusError):
            await LinearAdapter().fetch_issue("ENG-1", "bad-key")


class TestLinearAdapterFetchIssues:
    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issues_with_team_key(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={
            "data": {
                "issues": {
                    "nodes": [
                        {"identifier": "ENG-1", "title": "Task A", "description": None, "state": {"name": "Todo"}},
                        {"identifier": "ENG-2", "title": "Task B", "description": None, "state": {"name": "Done"}},
                    ]
                }
            }
        }))
        results = await LinearAdapter().fetch_issues("ENG", "token", limit=20)
        assert len(results) == 2
        assert results[0].source_id == "ENG-1"
        assert results[1].status == "done"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issues_without_team_key(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={
            "data": {"issues": {"nodes": [
                {"identifier": "ALL-1", "title": "Global", "description": None, "state": {"name": "Backlog"}},
            ]}}
        }))
        results = await LinearAdapter().fetch_issues(None, "token")
        assert len(results) == 1
        assert results[0].source_id == "ALL-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issues_respects_limit(self):
        nodes = [
            {"identifier": f"ENG-{i}", "title": f"Task {i}", "description": None, "state": {"name": "Todo"}}
            for i in range(10)
        ]
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={
            "data": {"issues": {"nodes": nodes}}
        }))
        results = await LinearAdapter().fetch_issues("ENG", "token", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_issues_empty_response(self):
        respx.post(LINEAR_URL).mock(return_value=httpx.Response(200, json={
            "data": {"issues": {"nodes": []}}
        }))
        results = await LinearAdapter().fetch_issues("ENG", "token")
        assert results == []
