"""Tests for ticket CRUD, import, and workspace assignment endpoints."""
import uuid

import pytest
import pytest_asyncio

from app.models.ticket import Ticket
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


class TestCreateTicket:
    @pytest.mark.asyncio
    async def test_create_minimal_ticket(self, client):
        r = await client.post("/api/tickets", json={"title": "Fix bug", "workspace_id": "ws1"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Fix bug"
        assert data["source"] == "custom"
        assert data["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_with_acceptance_criteria(self, client):
        r = await client.post("/api/tickets", json={
            "title": "Add feature",
            "workspace_id": "ws1",
            "acceptance_criteria": ["User can click button", "UI updates"],
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["acceptance_criteria"]) == 2
        texts = [c["text"] for c in data["acceptance_criteria"]]
        assert "User can click button" in texts

    @pytest.mark.asyncio
    async def test_criteria_have_ids_and_done_false(self, client):
        r = await client.post("/api/tickets", json={"title": "Test", "acceptance_criteria": ["Do X"]})
        c = r.json()["acceptance_criteria"][0]
        assert "id" in c
        assert c["done"] is False

    @pytest.mark.asyncio
    async def test_create_without_workspace_id(self, client):
        r = await client.post("/api/tickets", json={"title": "Orphan ticket"})
        assert r.status_code == 200
        assert r.json()["workspace_id"] is None

    @pytest.mark.asyncio
    async def test_missing_title_returns_422(self, client):
        r = await client.post("/api/tickets", json={"workspace_id": "ws1"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_body_is_empty_dict_for_custom(self, client):
        r = await client.post("/api/tickets", json={"title": "T"})
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

        r = await client.get("/api/tickets?workspace_id=list-ws")
        assert r.status_code == 200
        assert len(r.json()) == 3

    @pytest.mark.asyncio
    async def test_list_all_no_filter(self, client, ticket):
        r = await client.get("/api/tickets")
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

        r = await client.get("/api/tickets?workspace_id=other-ws-xyz")
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

        r = await client.get("/api/tickets?workspace_id=big-ws")
        assert len(r.json()) == 50


class _RemovedImportTicket:
    @pytest.mark.asyncio
    async def test_import_jira_ticket(self, client):
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
    async def test_import_github_ticket(self, client):
        raw = {"number": 42, "title": "Bug in parser", "state": "open", "body": "Steps..."}
        r = await client.post("/api/tickets/import", json={"source": "github", "workspace_id": "ws1", "raw": raw})
        assert r.status_code == 200
        assert r.json()["source"] == "github"
        assert r.json()["source_id"] == "42"

    @pytest.mark.asyncio
    async def test_import_linear_ticket(self, client):
        raw = {"identifier": "ENG-7", "title": "Dark mode", "state": {"name": "Backlog"}, "description": ""}
        r = await client.post("/api/tickets/import", json={"source": "linear", "workspace_id": "ws1", "raw": raw})
        assert r.status_code == 200
        assert r.json()["source"] == "linear"

    @pytest.mark.asyncio
    async def test_import_unknown_source_returns_422(self, client):
        r = await client.post("/api/tickets/import", json={"source": "notion", "workspace_id": "ws1", "raw": {}})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_import_dedup_returns_same_id(self, client):
        raw = {"key": "DUP-1", "fields": {"summary": "Dup", "status": {"name": "Done"}, "description": None}}
        r1 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        r2 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        assert r1.json()["id"] == r2.json()["id"]

    @pytest.mark.asyncio
    async def test_import_updates_title_on_reimport(self, client):
        raw = {"key": "UPD-1", "fields": {"summary": "Old title", "status": {"name": "Done"}, "description": None}}
        r1 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        raw["fields"]["summary"] = "New title"
        r2 = await client.post("/api/tickets/import", json={"source": "jira", "workspace_id": "ws1", "raw": raw})
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["title"] == "New title"


class _RemovedAssignTicketWorkspace:
    @pytest.mark.asyncio
    async def test_assign_workspace(self, client, ticket, workspace):
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": workspace.id})
        assert r.status_code == 200
        assert r.json()["workspace_id"] == workspace.id

    @pytest.mark.asyncio
    async def test_clear_workspace(self, client, ticket, workspace):
        await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": workspace.id})
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": None})
        assert r.status_code == 200
        assert r.json()["workspace_id"] is None

    @pytest.mark.asyncio
    async def test_assign_nonexistent_workspace_returns_404(self, client, ticket):
        r = await client.patch(f"/api/tickets/{ticket.id}/workspace", json={"workspace_id": "ghost-ws"})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_nonexistent_ticket_returns_404(self, client, workspace):
        r = await client.patch(f"/api/tickets/{uuid.uuid4()}/workspace", json={"workspace_id": workspace.id})
        assert r.status_code == 404


class TestDeleteTicket:
    @pytest.mark.asyncio
    async def test_delete_returns_204_and_ticket_gone(self, client, ticket):
        assert (await client.delete(f"/api/tickets/{ticket.id}")).status_code == 204
        assert (await client.get(f"/api/tickets/{ticket.id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_delete_unknown_ticket_returns_404(self, client):
        assert (await client.delete(f"/api/tickets/{uuid.uuid4()}")).status_code == 404


class TestCriteriaExtractionFromDescription:
    @pytest.mark.asyncio
    async def test_checkbox_lines_become_criteria(self, client):
        r = await client.post("/api/tickets", json={
            "workspace_id": "ws1", "title": "With checkboxes",
            "description": "Some context\n- [ ] first thing\n- [ ] second thing\nMore text",
        })
        data = r.json()
        texts = [c["text"] for c in data["acceptance_criteria"]]
        assert texts == ["first thing", "second thing"]
        assert "- [ ]" not in (data["description"] or "")
        assert "Some context" in data["description"]

    @pytest.mark.asyncio
    async def test_explicit_criteria_take_precedence_over_extraction(self, client):
        r = await client.post("/api/tickets", json={
            "workspace_id": "ws1", "title": "Explicit wins",
            "description": "- [ ] extracted",
            "acceptance_criteria": ["explicit"],
        })
        texts = [c["text"] for c in r.json()["acceptance_criteria"]]
        assert texts == ["explicit"]


class TestUpdateCriteria:
    @pytest.mark.asyncio
    async def test_replaces_criteria_and_generates_ids(self, client, ticket):
        r = await client.put(f"/api/tickets/{ticket.id}/criteria", json=[
            {"text": "new criterion"},
            {"text": "another", "test_cmd": "pytest -k x", "done": True},
        ])
        assert r.status_code == 200
        criteria = r.json()["acceptance_criteria"]
        assert len(criteria) == 2
        assert all(c["id"] for c in criteria)
        assert criteria[1]["test_cmd"] == "pytest -k x"
        assert criteria[1]["done"] is True

    @pytest.mark.asyncio
    async def test_existing_ids_preserved(self, client, ticket):
        existing_id = ticket.acceptance_criteria[0]["id"]
        r = await client.put(f"/api/tickets/{ticket.id}/criteria", json=[
            {"id": existing_id, "text": "kept id", "done": False},
        ])
        assert r.json()["acceptance_criteria"][0]["id"] == existing_id

    @pytest.mark.asyncio
    async def test_unknown_ticket_returns_404(self, client):
        r = await client.put(f"/api/tickets/{uuid.uuid4()}/criteria", json=[])
        assert r.status_code == 404


class TestRefineTicket:
    @pytest.mark.asyncio
    async def test_refine_unknown_ticket_returns_404(self, client):
        assert (await client.post(f"/api/tickets/{uuid.uuid4()}/refine")).status_code == 404

    @pytest.mark.asyncio
    async def test_refine_without_title_or_description_returns_400(self, client):
        async with TestSessionLocal() as db:
            t = Ticket(id=str(uuid.uuid4()), workspace_id="ws1", source="custom",
                       title="", description=None, status="open", body={},
                       acceptance_criteria=[])
            db.add(t)
            await db.commit()
            ticket_id = t.id
        assert (await client.post(f"/api/tickets/{ticket_id}/refine")).status_code == 400

    @pytest.mark.asyncio
    async def test_refine_without_llm_key_leaves_criteria_unchanged(
        self, client, ticket, monkeypatch
    ):
        from app.core.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", None)
        monkeypatch.setattr(settings, "openai_api_key", None)
        before = [c["text"] for c in ticket.acceptance_criteria]
        r = await client.post(f"/api/tickets/{ticket.id}/refine")
        assert r.status_code == 200
        assert [c["text"] for c in r.json()["acceptance_criteria"]] == before

    @pytest.mark.asyncio
    async def test_refine_merges_proposals_and_dedupes_by_text(
        self, client, ticket, monkeypatch
    ):
        # The LLM call is mocked: _propose_criteria is the provider boundary and
        # its real implementation needs a live API key. Shapes match production.
        import app.api.routes.tickets as tickets_route

        existing_text = ticket.acceptance_criteria[0]["text"]

        async def fake_propose(title, description):
            return [
                tickets_route._make_criterion(existing_text, "echo dup"),
                tickets_route._make_criterion("brand new criterion", "pytest -k new"),
            ]

        monkeypatch.setattr(tickets_route, "_propose_criteria", fake_propose)
        r = await client.post(f"/api/tickets/{ticket.id}/refine")
        assert r.status_code == 200
        texts = [c["text"] for c in r.json()["acceptance_criteria"]]
        assert texts.count(existing_text) == 1
        assert "brand new criterion" in texts
