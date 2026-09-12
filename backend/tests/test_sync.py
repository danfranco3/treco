"""Tracker sync — local credential store hygiene and the Jira/Linear push
paths. Outbound HTTP is intercepted with respx against the real request
shapes; nothing else is mocked."""
import json
import uuid

import pytest
import respx
from httpx import Response

import app.services.sync.base as sync_base
from app.models.integration import Integration
from app.models.ticket import Ticket
from app.services.sync.base import (
    delete_credential,
    load_credential,
    save_credential,
    sync_ticket_to_tracker,
)
from app.services.sync.jira import push_status as jira_push
from app.services.sync.linear import push_status as linear_push
from tests.shared import TestSessionLocal


@pytest.fixture(autouse=True)
def credential_store(tmp_path, monkeypatch):
    path = tmp_path / "credentials.json"
    monkeypatch.setattr(sync_base, "CREDENTIALS_FILE", path)
    return path


class TestCredentialStore:
    def test_save_returns_opaque_ref_and_round_trips(self):
        ref = save_credential("secret-token", "jira")
        assert "secret-token" not in ref
        assert ref.startswith("jira-")
        assert load_credential(ref) == "secret-token"

    def test_store_file_is_chmod_600(self, credential_store):
        save_credential("secret", "linear")
        assert (credential_store.stat().st_mode & 0o777) == 0o600

    def test_store_stays_600_after_delete(self, credential_store):
        ref = save_credential("secret", "jira")
        delete_credential(ref)
        assert (credential_store.stat().st_mode & 0o777) == 0o600

    def test_delete_removes_token(self, credential_store):
        ref = save_credential("delete-me", "jira")
        delete_credential(ref)
        assert load_credential(ref) is None
        assert "delete-me" not in credential_store.read_text()

    def test_delete_unknown_ref_is_noop(self):
        delete_credential("jira-nonexistent")

    def test_corrupt_store_returns_empty_not_crash(self, credential_store):
        credential_store.write_text("{not json")
        assert load_credential("any") is None

    def test_multiple_credentials_coexist(self):
        ref_a = save_credential("token-a", "jira")
        ref_b = save_credential("token-b", "linear")
        assert load_credential(ref_a) == "token-a"
        assert load_credential(ref_b) == "token-b"


class TestJiraPush:
    @pytest.mark.asyncio
    @respx.mock
    async def test_posts_comment_with_status_and_pr_url(self):
        comment = respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-1/comment"
        ).mock(return_value=Response(201, json={}))

        await jira_push(
            {"base_url": "https://x.atlassian.net/", "email": "a@b.c"},
            "tok", "PROJ-1", "done", "https://github.com/pr/1",
        )
        body = json.loads(comment.calls[0].request.content)
        assert "done" in body["body"]
        assert "https://github.com/pr/1" in body["body"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_fires_transition_when_status_mapped(self):
        respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-1/comment"
        ).mock(return_value=Response(201, json={}))
        transition = respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-1/transitions"
        ).mock(return_value=Response(204))

        await jira_push(
            {"base_url": "https://x.atlassian.net", "status_map": {"done": 31}},
            "tok", "PROJ-1", "done", None,
        )
        assert transition.called
        body = json.loads(transition.calls[0].request.content)
        assert body["transition"]["id"] == "31"

    @pytest.mark.asyncio
    @respx.mock
    async def test_bearer_auth_used_without_email(self):
        comment = respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-1/comment"
        ).mock(return_value=Response(201, json={}))
        await jira_push({"base_url": "https://x.atlassian.net"}, "pat-token",
                        "PROJ-1", "in_progress", None)
        assert comment.calls[0].request.headers["authorization"] == "Bearer pat-token"


class TestLinearPush:
    @pytest.mark.asyncio
    @respx.mock
    async def test_resolves_issue_comments_and_moves_state(self):
        responses = iter([
            Response(200, json={"data": {"issue": {"id": "uuid-1"}}}),
            Response(200, json={"data": {"commentCreate": {"success": True}}}),
            Response(200, json={"data": {"issueUpdate": {"success": True}}}),
        ])
        route = respx.post("https://api.linear.app/graphql").mock(
            side_effect=lambda request: next(responses)
        )
        await linear_push({"status_map": {"done": "state-42"}}, "lin_tok",
                          "ENG-123", "done", None)
        assert route.call_count == 3
        update_body = json.loads(route.calls[2].request.content)
        assert update_body["variables"]["input"]["stateId"] == "state-42"

    @pytest.mark.asyncio
    @respx.mock
    async def test_graphql_errors_raise(self):
        respx.post("https://api.linear.app/graphql").mock(
            return_value=Response(200, json={"errors": [{"message": "nope"}]})
        )
        with pytest.raises(RuntimeError):
            await linear_push({}, "tok", "ENG-1", "done", None)


class TestSyncTicketToTracker:
    async def _seed(self, external_ref, integration_kwargs=None):
        async with TestSessionLocal() as db:
            ticket = Ticket(
                id=str(uuid.uuid4()), workspace_id="ws1", source="jira",
                title="Synced", status="done", body={},
                acceptance_criteria=[], external_ref=external_ref,
            )
            db.add(ticket)
            if integration_kwargs is not None:
                db.add(Integration(
                    id=str(uuid.uuid4()), workspace_id="ws1", **integration_kwargs,
                ))
            await db.commit()
        return ticket

    @pytest.mark.asyncio
    async def test_ticket_without_external_ref_is_noop(self, service_sessions):
        ticket = await self._seed(external_ref=None)
        await sync_ticket_to_tracker(ticket.id, "done")
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).external_ref is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_sync_records_ok_status(self, service_sessions):
        ref = save_credential("jira-token", "jira")
        respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-9/comment"
        ).mock(return_value=Response(201, json={}))
        ticket = await self._seed(
            external_ref={"provider": "jira", "issue_key": "PROJ-9"},
            integration_kwargs={
                "provider": "jira", "credential_ref": ref, "enabled": True,
                "config": {"base_url": "https://x.atlassian.net"},
            },
        )
        await sync_ticket_to_tracker(ticket.id, "done")
        async with TestSessionLocal() as db:
            refreshed = await db.get(Ticket, ticket.id)
            assert refreshed.external_ref["sync_status"] == "ok"
            assert refreshed.external_ref["sync_error"] is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_provider_failure_recorded_never_raised(self, service_sessions):
        ref = save_credential("jira-token", "jira")
        respx.post(
            "https://x.atlassian.net/rest/api/2/issue/PROJ-9/comment"
        ).mock(return_value=Response(500, text="boom"))
        ticket = await self._seed(
            external_ref={"provider": "jira", "issue_key": "PROJ-9"},
            integration_kwargs={
                "provider": "jira", "credential_ref": ref, "enabled": True,
                "config": {"base_url": "https://x.atlassian.net"},
            },
        )
        await sync_ticket_to_tracker(ticket.id, "done")
        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).external_ref["sync_status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_credential_recorded_as_error(self, service_sessions):
        ticket = await self._seed(
            external_ref={"provider": "jira", "issue_key": "PROJ-9"},
            integration_kwargs={
                "provider": "jira", "credential_ref": "jira-gone", "enabled": True,
                "config": {"base_url": "https://x.atlassian.net"},
            },
        )
        await sync_ticket_to_tracker(ticket.id, "done")
        async with TestSessionLocal() as db:
            refreshed = await db.get(Ticket, ticket.id)
            assert refreshed.external_ref["sync_status"] == "error"
            assert "credential missing" in refreshed.external_ref["sync_error"]

    @pytest.mark.asyncio
    async def test_disabled_integration_is_noop(self, service_sessions):
        ticket = await self._seed(
            external_ref={"provider": "jira", "issue_key": "PROJ-9"},
            integration_kwargs={
                "provider": "jira", "credential_ref": "jira-x", "enabled": False,
                "config": {},
            },
        )
        await sync_ticket_to_tracker(ticket.id, "done")
        async with TestSessionLocal() as db:
            assert "sync_status" not in ((await db.get(Ticket, ticket.id)).external_ref or {})
