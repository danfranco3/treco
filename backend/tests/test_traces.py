"""Tests for the trace tree endpoint."""
import uuid

import pytest

from app.models.trace import Trace
from tests.shared import TestSessionLocal


class TestTicketTraces:
    @pytest.mark.asyncio
    async def test_tree_nests_children_under_parents(self, client):
        ticket_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        async with TestSessionLocal() as db:
            db.add(Trace(
                id=parent_id, agent_id="a1", ticket_id=ticket_id,
                step_type="llm_turn", status="ok", payload={},
            ))
            db.add(Trace(
                id=str(uuid.uuid4()), agent_id="a1", ticket_id=ticket_id,
                parent_trace_id=parent_id, step_type="tool_call",
                tool_name="write_file", status="ok", payload={},
            ))
            await db.commit()

        r = await client.get(f"/api/traces/ticket/{ticket_id}")
        assert r.status_code == 200
        roots = r.json()
        assert len(roots) == 1
        assert roots[0]["step_type"] == "llm_turn"
        assert len(roots[0]["children"]) == 1
        assert roots[0]["children"][0]["tool_name"] == "write_file"

    @pytest.mark.asyncio
    async def test_unknown_ticket_returns_empty_list(self, client):
        r = await client.get("/api/traces/ticket/no-such-ticket")
        assert r.status_code == 200
        assert r.json() == []
