"""Permission gating in the claude_code runner — real subprocess, no HTTP-only mocks.

A fake `claude` CLI on PATH emits an `input_required` line, then blocks on
stdin. It only performs its "tool call" (writing a marker file) after reading
`y`. That makes the pause observable: no marker file ⇒ the subprocess did not
proceed. The only test double is the claude binary itself — everything from
run_claude_code() down to process stdin/stdout is real.
"""
import asyncio
import os
import stat
import textwrap
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.constants import EventType
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services.implement import _active_procs, respond_permission, run_claude_code
from tests.shared import TestSessionLocal

FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys

    marker_dir = os.environ["TRECO_TEST_MARKER_DIR"]
    tid = os.environ.get("TRECO_TICKET_ID", "unknown")
    with open(os.path.join(marker_dir, tid + ".args"), "w") as f:
        f.write(" ".join(sys.argv[1:]))

    if os.environ.get("FAKE_CLAUDE_EXIT_EARLY") == "1":
        sys.exit(0)

    print(json.dumps({"type": "input_required", "prompt": "Run rm -rf build?",
                      "request_id": "req-1"}), flush=True)
    line = sys.stdin.readline().strip()
    if line == "y":
        with open(os.path.join(marker_dir, tid + ".executed"), "w") as f:
            f.write("tool call ran")
        print(json.dumps({"type": "result", "result": "finished"}), flush=True)
        sys.exit(0)
    sys.exit(1)
""")


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    """Install the fake claude CLI on PATH; returns the marker directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("TRECO_TEST_MARKER_DIR", str(marker_dir))
    return marker_dir


@pytest_asyncio.fixture
async def gated_pair(service_sessions):
    """An agent + ticket persisted in the test DB for direct runner invocation."""
    async with TestSessionLocal() as db:
        ticket = Ticket(
            id=str(uuid.uuid4()), workspace_id="ws1", source="custom",
            title="Gated work", status="in_progress", body={},
            acceptance_criteria=[],
        )
        agent = Agent(
            id=str(uuid.uuid4()), workspace_id="ws1", name="gated-agent",
            api_key_hash=uuid.uuid4().hex, status="working",
            current_ticket_id=ticket.id,
        )
        db.add_all([ticket, agent])
        await db.commit()
    return agent, ticket


async def _wait_for(predicate, timeout: float = 8.0, interval: float = 0.05):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = await predicate()
        if result:
            return result
        await asyncio.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s")


async def _events(ticket_id: str, event_type: str) -> list[AgentEvent]:
    async with TestSessionLocal() as db:
        result = await db.execute(
            select(AgentEvent).where(
                AgentEvent.ticket_id == ticket_id,
                AgentEvent.event_type == event_type,
            )
        )
        return list(result.scalars().all())


async def _agent_status(agent_id: str) -> str:
    async with TestSessionLocal() as db:
        return (await db.get(Agent, agent_id)).status


async def _ticket_status(ticket_id: str) -> str:
    async with TestSessionLocal() as db:
        return (await db.get(Ticket, ticket_id)).status


def _run(agent, ticket, skip_permissions=False):
    return asyncio.create_task(run_claude_code(
        agent.id, "treco_fake_key", ticket, None, "", "",
        skip_permissions=skip_permissions,
    ))


class TestPermissionGateBlocksSubprocess:
    @pytest.mark.asyncio
    async def test_subprocess_pauses_on_permission_gate_until_approved(
        self, fake_claude, gated_pair
    ):
        agent, ticket = gated_pair
        marker = fake_claude / f"{ticket.id}.executed"
        task = _run(agent, ticket)

        await _wait_for(lambda: _events(ticket.id, EventType.PERMISSION_REQUESTED))
        assert not marker.exists(), "tool call ran before permission was granted"
        assert agent.id in _active_procs
        assert not task.done()
        assert await _agent_status(agent.id) == "awaiting_approval"
        assert await _ticket_status(ticket.id) == "hitl_review"

        # Still paused after a real wait — the gate is a hard stop, not a delay.
        await asyncio.sleep(0.4)
        assert not marker.exists()
        assert not task.done()

        assert await respond_permission(agent.id, "y") is True
        await asyncio.wait_for(task, timeout=8)
        assert marker.exists()
        assert await _events(ticket.id, EventType.DONE)
        assert await _agent_status(agent.id) == "idle"
        assert await _ticket_status(ticket.id) == "done"

    @pytest.mark.asyncio
    async def test_denied_permission_prevents_tool_call(self, fake_claude, gated_pair):
        agent, ticket = gated_pair
        marker = fake_claude / f"{ticket.id}.executed"
        task = _run(agent, ticket)

        await _wait_for(lambda: _events(ticket.id, EventType.PERMISSION_REQUESTED))
        assert await respond_permission(agent.id, "n") is True
        await asyncio.wait_for(task, timeout=8)

        assert not marker.exists(), "tool call ran despite denial"
        errors = await _events(ticket.id, EventType.ERROR)
        assert errors and errors[0].payload["exit_code"] == 1
        assert await _ticket_status(ticket.id) == "blocked"
        assert await _agent_status(agent.id) == "error"

    @pytest.mark.asyncio
    async def test_permission_gate_records_trace_step(self, fake_claude, gated_pair):
        from app.models.trace import Trace
        agent, ticket = gated_pair
        task = _run(agent, ticket)
        await _wait_for(lambda: _events(ticket.id, EventType.PERMISSION_REQUESTED))

        async with TestSessionLocal() as db:
            result = await db.execute(
                select(Trace).where(
                    Trace.ticket_id == ticket.id,
                    Trace.step_type == "permission_gate",
                )
            )
            assert result.scalars().first() is not None

        await respond_permission(agent.id, "y")
        await asyncio.wait_for(task, timeout=8)


class TestRespondPermissionTargeting:
    @pytest.mark.asyncio
    async def test_respond_permission_unknown_agent_returns_false(self):
        assert await respond_permission(str(uuid.uuid4()), "y") is False

    @pytest.mark.asyncio
    async def test_respond_permission_after_run_finished_returns_false(
        self, fake_claude, gated_pair
    ):
        agent, ticket = gated_pair
        task = _run(agent, ticket)
        await _wait_for(lambda: _events(ticket.id, EventType.PERMISSION_REQUESTED))
        await respond_permission(agent.id, "y")
        await asyncio.wait_for(task, timeout=8)
        assert agent.id not in _active_procs
        assert await respond_permission(agent.id, "y") is False

    @pytest.mark.asyncio
    async def test_response_unblocks_only_the_target_subprocess(
        self, fake_claude, service_sessions
    ):
        pairs = []
        async with TestSessionLocal() as db:
            for name in ("agent-a", "agent-b"):
                ticket = Ticket(
                    id=str(uuid.uuid4()), workspace_id="ws1", source="custom",
                    title=name, status="in_progress", body={},
                    acceptance_criteria=[],
                )
                agent = Agent(
                    id=str(uuid.uuid4()), workspace_id="ws1", name=name,
                    api_key_hash=uuid.uuid4().hex, status="working",
                    current_ticket_id=ticket.id,
                )
                db.add_all([ticket, agent])
                pairs.append((agent, ticket))
            await db.commit()
        (agent_a, ticket_a), (agent_b, ticket_b) = pairs

        task_a = _run(agent_a, ticket_a)
        task_b = _run(agent_b, ticket_b)
        await _wait_for(lambda: _events(ticket_a.id, EventType.PERMISSION_REQUESTED))
        await _wait_for(lambda: _events(ticket_b.id, EventType.PERMISSION_REQUESTED))

        await respond_permission(agent_a.id, "y")
        await asyncio.wait_for(task_a, timeout=8)

        assert (fake_claude / f"{ticket_a.id}.executed").exists()
        assert not (fake_claude / f"{ticket_b.id}.executed").exists(), (
            "responding to agent A unblocked agent B's subprocess"
        )
        assert agent_b.id in _active_procs
        assert not task_b.done()

        await respond_permission(agent_b.id, "y")
        await asyncio.wait_for(task_b, timeout=8)


class TestSkipPermissionsFlag:
    @pytest.mark.asyncio
    async def test_skip_permissions_false_omits_dangerous_flag(
        self, fake_claude, gated_pair, monkeypatch
    ):
        monkeypatch.setenv("FAKE_CLAUDE_EXIT_EARLY", "1")
        agent, ticket = gated_pair
        await asyncio.wait_for(_run(agent, ticket, skip_permissions=False), timeout=8)
        args = (fake_claude / f"{ticket.id}.args").read_text()
        assert "--dangerously-skip-permissions" not in args

    @pytest.mark.asyncio
    async def test_skip_permissions_true_passes_dangerous_flag(
        self, fake_claude, gated_pair, monkeypatch
    ):
        monkeypatch.setenv("FAKE_CLAUDE_EXIT_EARLY", "1")
        agent, ticket = gated_pair
        await asyncio.wait_for(_run(agent, ticket, skip_permissions=True), timeout=8)
        args = (fake_claude / f"{ticket.id}.args").read_text()
        assert "--dangerously-skip-permissions" in args


class TestPermissionResponseRoute:
    @pytest.mark.asyncio
    async def test_route_returns_409_when_no_process_is_waiting(
        self, client, agent_with_key
    ):
        agent, _ = agent_with_key
        r = await client.post(
            f"/api/agents/{agent.id}/permission_response", json={"response": "y"}
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_route_returns_404_for_unknown_agent(self, client):
        r = await client.post(
            f"/api/agents/{uuid.uuid4()}/permission_response", json={"response": "y"}
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_full_flow_implement_pause_approve_via_api(
        self, client, fake_claude, service_sessions, ticket
    ):
        """End to end: POST /implement spawns the real subprocess, the UI-facing
        permission event lands in the stream, POST /permission_response resumes
        exactly that subprocess, and the run completes."""
        r = await client.post(f"/api/tickets/{ticket.id}/implement", json={
            "method": "claude_code", "skip_permissions": False,
        })
        assert r.status_code == 200
        agent_id = r.json()["agent_id"]
        marker = fake_claude / f"{ticket.id}.executed"

        async def _ticket_done():
            return await _ticket_status(ticket.id) == "done"

        perm_events = await _wait_for(
            lambda: _events(ticket.id, EventType.PERMISSION_REQUESTED)
        )
        assert perm_events[0].payload["prompt"] == "Run rm -rf build?"
        assert not marker.exists()
        assert (await client.get(f"/api/agents/{agent_id}")).json()["status"] == "awaiting_approval"
        assert (await client.get(f"/api/tickets/{ticket.id}")).json()["status"] == "hitl_review"

        r = await client.post(
            f"/api/agents/{agent_id}/permission_response", json={"response": "y"}
        )
        assert r.status_code == 200

        await _wait_for(lambda: asyncio.sleep(0, result=marker.exists()))
        await _wait_for(lambda: _events(ticket.id, EventType.DONE))
        # The DONE event lands before the status write — poll for final state.
        await _wait_for(_ticket_done)
