"""Tests for ticket CRUD, import, and workspace assignment endpoints."""
import uuid

import pytest
import pytest_asyncio

from app.models.ticket import Ticket
from app.models.user_workspace import UserWorkspace
from app.models.workspace import Workspace
from tests.shared import TestSessionLocal


@pytest_asyncio.fixture
async def workspace():
    async with TestSessionLocal() as db:
        ws = Workspace(id="ws-test", name="test-ws", repo_path=None)
        db.add(ws)
        await db.commit()
        await db.refresh(ws)
        return ws


@pytest_asyncio.fixture
async def workspace_with_member(workspace, user_with_token):
    """Add test user as owner of the 'ws-test' workspace."""
    user, _ = user_with_token
    async with TestSessionLocal() as db:
        db.add(UserWorkspace(user_id=user.id, workspace_id=workspace.id, role="owner"))
        await db.commit()
    return workspace


@pytest_asyncio.fixture
async def ws1_membership(user_with_token):
    """Create UserWorkspace membership for 'ws1' (no actual Workspace row needed for import)."""
    user, _ = user_with_token
    async with TestSessionLocal() as db:
        db.add(UserWorkspace(user_id=user.id, workspace_id="ws1", role="member"))
        await db.commit()


class TestCreateTicket:
    @pytest.mark.asyncio
    async def test_create_minimal_ticket(self, client):
        r = await client.post("/api/tickets/", json={"title": "Fix bug", "workspace_id": "ws1"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Fix bug"
        assert data["source"] == "custom"
        assert data["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_with_acceptance_criteria(self, client):
        r = await client.post("/api/tickets/", json={
            "title": "Add feature",
            "workspace_id": "ws1",
            "acceptance_criteria": ["User can click button", "UI updates"],
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["acceptance_criteria"]) == 2
        texts = [c["text"] for c in data["acceptance_criteria"]]
        assert "User can click button" in texts
        assert "UI updates" in texts

    @pytest.mark.asyncio
    async def test_criteria_have_ids_and_done_false(self, client):
        r = await client.post("/api/tickets/", json={
            "title": "Test",
            "acceptance_criteria": ["Do X"],
        })
        c = r.json()["acceptance_criteria"][0]
        assert "id" in c
        assert c["done"] is False

    @pytest.mark.asyncio
    async def test_create_without_workspace_id(self, client):
        r = await client.post("/api/tickets/", json={"title": "Orphan ticket"})
        assert r.status_code == 200
        assert r.json()["workspace_id"] is None

    @pytest.mark.asyncio
    async def test_missing_title_returns_422(self, client):
        r = await client.post("/api/tickets/", json={"workspace_id": "ws1"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_body_is_empty_dict_for_custom(self, client):
        r = await client.post("/api/tickets/", json={"title": "T"})
        assert r.json()["body"] == {}


class TestGetTicket:
    @pytest.mark.asyncio
    async def test_get_existing_ticket(self, client, ticket):
        r = await client.get(f"/api/tickets/{ticket.id}")
        assert r.status_code == 200
        assert r.json()["id"] == ticket.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client):
        r = await client.get(f"/api/tickets/{uuid.uuid4()}")
        assert r.status_code == 404


class TestListTickets:
    @pytest.mark.asyncio
    async def test_list_by_workspace(self, client):
        async with TestSessionLocal() as db:
            for i in range(3):
                db.add(Ticket(
                    id=str(uuid.uuid4()),
                    workspace_id="list-ws",
                    source="custom",
                    title=f"T{i}",
                    status="open",
                    body={},
                    acceptance_criteria=[],
                ))
            await db.commit()

        r = await client.get("/api/tickets/?workspace_id=list-ws")
        assert r.status_code == 200
        assert len(r.json()) == 3

    @pytest.mark.asyncio
    async def test_list_all_no_filter(self, client, ticket):
        r = await client.get("/api/tickets/")
        assert r.status_code == 200
        assert any(t["id"] == ticket.id for t in r.json())

    @pytest.mark.asyncio
    async def test_workspace_isolation(self, client):
        async with TestSessionLocal() as db:
            db.add(Ticket(
                id=str(uuid.uuid4()),
                workspace_id="isolated-ws",
                source="custom",
                title="Isolated",
                status="open",
                body={},
                acceptance_criteria=[],
            ))
            await db.commit()

        r = await client.get("/api/tickets/?workspace_id=other-ws-xyz")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_default_limit_50(self, client):
        async with TestSessionLocal() as db:
            for i in range(55):
                db.add(Ticket(
                    id=str(uuid.uuid4()),
                    workspace_id="big-ws",
                    source="custom",
                    title=f"T{i}",
                    status="open",
                    body={},
                    acceptance_criteria=[],
                ))
            await db.commit()

        r = await client.get("/api/tickets/?workspace_id=big-ws")
        assert len(r.json()) == 50


class TestImportTicket:
    @pytest.mark.asyncio
    async def test_import_jira_ticket(self, authed_client, ws1_membership):
        client, _ = authed_client
        raw = {
            "key": "PROJ-10",
            "fields": {"summary": "Fix login", "status": {"name": "In Progress"}, "description": None},
        }
        r = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Fix login"
        assert data["source"] == "jira"
        assert data["source_id"] == "PROJ-10"

    @pytest.mark.asyncio
    async def test_import_github_ticket(self, authed_client, ws1_membership):
        client, _ = authed_client
        raw = {"number": 42, "title": "Bug in parser", "state": "open", "body": "Steps..."}
        r = await client.post("/api/tickets/import", json={"source": "github", "workspace_id": "ws1", "raw": raw})
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "github"
        assert data["source_id"] == "42"

    @pytest.mark.asyncio
    async def test_import_linear_ticket(self, authed_client, ws1_membership):
        client, _ = authed_client
        raw = {"identifier": "ENG-7", "title": "Dark mode", "state": {"name": "Backlog"}, "description": ""}
        r = await client.post("/api/tickets/import", json={"source": "linear", "workspace_id": "ws1", "raw": raw})
        assert r.status_code == 200
        assert r.json()["source"] == "linear"

    @pytest.mark.asyncio
    async def test_import_unknown_source_returns_422(self, authed_client, ws1_membership):
        client, _ = authed_client
        r = await client.post("/api/tickets/import", json={
            "source": "notion",
            "workspace_id": "ws1",
            "raw": {},
        })
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_import_dedup_returns_same_id(self, authed_client, ws1_membership):
        client, _ = authed_client
        raw = {"key": "DUP-1", "fields": {"summary": "Dup", "status": {"name": "Done"}, "description": None}}
        r1 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        r2 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        assert r1.json()["id"] == r2.json()["id"]

    @pytest.mark.asyncio
    async def test_import_updates_title_on_reimport(self, authed_client, ws1_membership):
        client, _ = authed_client
        raw = {"key": "UPD-1", "fields": {"summary": "Old title", "status": {"name": "Done"}, "description": None}}
        r1 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})

        raw["fields"]["summary"] = "New title"
        r2 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["title"] == "New title"

    @pytest.mark.asyncio
    async def test_import_without_membership_returns_403(self, authed_client):
        client, _ = authed_client
        raw = {"key": "X-1", "fields": {"summary": "T", "status": {"name": "Done"}, "description": None}}
        r = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "no-membership", "raw": raw})
        assert r.status_code == 403


class TestAssignTicketWorkspace:
    @pytest.mark.asyncio
    async def test_assign_workspace(self, authed_client, ticket, workspace_with_member):
        client, _ = authed_client
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": workspace_with_member.id})
        assert r.status_code == 200
        assert r.json()["workspace_id"] == workspace_with_member.id

    @pytest.mark.asyncio
    async def test_clear_workspace(self, authed_client, ticket, workspace_with_member):
        client, _ = authed_client
        await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": workspace_with_member.id})
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": None})
        assert r.status_code == 200
        assert r.json()["workspace_id"] is None

    @pytest.mark.asyncio
    async def test_assign_nonexistent_workspace_returns_404(self, authed_client, ticket):
        client, _ = authed_client
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": "ghost-ws"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_nonexistent_ticket_returns_404(self, authed_client, workspace_with_member):
        client, _ = authed_client
        r = await client.patch(f"/api/tickets/{uuid.uuid4()}/workspace", json={"workspace_id": workspace_with_member.id})
        assert r.status_code == 404
