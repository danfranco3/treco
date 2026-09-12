"""Unit tests for the agent runner internals: path sandboxing, tool execution,
criterion marking, registry tool loading, and the no-key failure path."""
import uuid

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.core.constants import EventType
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.models.tool import Tool
from app.services.implement import (
    _build_task,
    _exec_registry_tool,
    _exec_tool,
    _load_workspace_tools,
    _mark_criterion,
    _safe_path,
    is_paused,
    pause_agent,
    resume_agent,
    run_anthropic_agent,
)
from tests.shared import TestSessionLocal


def _ticket(**overrides) -> Ticket:
    defaults = dict(
        id=str(uuid.uuid4()), workspace_id="ws1", source="custom",
        title="Test", status="in_progress", body={},
        acceptance_criteria=[],
    )
    defaults.update(overrides)
    return Ticket(**defaults)


class TestSafePath:
    def test_allows_paths_inside_repo(self, tmp_path):
        resolved = _safe_path(str(tmp_path), "src/main.py")
        assert resolved.startswith(str(tmp_path))

    def test_allows_repo_root_itself(self, tmp_path):
        assert _safe_path(str(tmp_path), ".") == str(tmp_path)

    def test_rejects_parent_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            _safe_path(str(tmp_path), "../outside.txt")

    def test_rejects_deep_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            _safe_path(str(tmp_path), "src/../../etc/passwd")

    def test_rejects_absolute_path_outside_repo(self, tmp_path):
        with pytest.raises(ValueError):
            _safe_path(str(tmp_path), "/etc/passwd")

    def test_rejects_symlink_escape(self, tmp_path):
        repo = tmp_path / "repo"
        outside = tmp_path / "outside"
        repo.mkdir()
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        (repo / "link").symlink_to(outside)
        with pytest.raises(ValueError):
            _safe_path(str(repo), "link/secret.txt")


class TestExecTool:
    @pytest.mark.asyncio
    async def test_read_file_returns_contents(self, tmp_path):
        (tmp_path / "a.txt").write_text("content here")
        result = await _exec_tool("read_file", {"path": "a.txt"},
                                  "agent-1", _ticket(), str(tmp_path))
        assert result == "content here"

    @pytest.mark.asyncio
    async def test_write_file_creates_file(self, tmp_path, service_sessions):
        result = await _exec_tool(
            "write_file", {"path": "new/deep/file.py", "content": "x = 1\n"},
            "agent-1", _ticket(), str(tmp_path),
        )
        assert "Written" in result
        assert (tmp_path / "new" / "deep" / "file.py").read_text() == "x = 1\n"

    @pytest.mark.asyncio
    async def test_write_file_outside_repo_returns_error_string(self, tmp_path, service_sessions):
        result = await _exec_tool(
            "write_file", {"path": "../evil.py", "content": "boom"},
            "agent-1", _ticket(), str(tmp_path),
        )
        assert result.startswith("Error:")
        assert not (tmp_path.parent / "evil.py").exists()

    @pytest.mark.asyncio
    async def test_run_command_returns_output_and_emits_log(self, tmp_path, service_sessions):
        ticket = _ticket()
        result = await _exec_tool(
            "run_command", {"command": "echo tool-ran"},
            "agent-1", ticket, str(tmp_path),
        )
        assert "tool-ran" in result
        async with TestSessionLocal() as db:
            events = (await db.execute(
                select(AgentEvent).where(AgentEvent.ticket_id == ticket.id)
            )).scalars().all()
        assert any("tool-ran" in e.payload.get("message", "") for e in events)

    @pytest.mark.asyncio
    async def test_unknown_tool_reports_error(self, tmp_path):
        result = await _exec_tool("teleport", {}, "agent-1", _ticket(), str(tmp_path))
        assert result == "Unknown tool: teleport"

    @pytest.mark.asyncio
    async def test_finish_returns_summary(self, tmp_path):
        result = await _exec_tool("finish", {"summary": "all done"},
                                  "agent-1", _ticket(), str(tmp_path))
        assert result == "all done"


class TestMarkCriterion:
    @pytest.mark.asyncio
    async def test_marks_criterion_done_and_emits_event(self, service_sessions):
        crit_id = str(uuid.uuid4())
        ticket = _ticket(acceptance_criteria=[
            {"id": crit_id, "text": "do it", "done": False},
        ])
        async with TestSessionLocal() as db:
            db.add(ticket)
            await db.commit()

        await _mark_criterion("agent-1", ticket, crit_id,
                              file_path="src/x.py", notes="did it")

        async with TestSessionLocal() as db:
            refreshed = await db.get(Ticket, ticket.id)
            crit = refreshed.acceptance_criteria[0]
            assert crit["done"] is True
            assert crit["file_path"] == "src/x.py"
            events = (await db.execute(
                select(AgentEvent).where(
                    AgentEvent.ticket_id == ticket.id,
                    AgentEvent.event_type == EventType.CRITERION_CHECKED,
                )
            )).scalars().all()
        assert len(events) == 1
        assert events[0].criterion_id == crit_id

    @pytest.mark.asyncio
    async def test_unknown_criterion_id_leaves_others_untouched(self, service_sessions):
        crit_id = str(uuid.uuid4())
        ticket = _ticket(acceptance_criteria=[
            {"id": crit_id, "text": "real", "done": False},
        ])
        async with TestSessionLocal() as db:
            db.add(ticket)
            await db.commit()

        await _mark_criterion("agent-1", ticket, "no-such-criterion")

        async with TestSessionLocal() as db:
            refreshed = await db.get(Ticket, ticket.id)
        assert refreshed.acceptance_criteria[0]["done"] is False


class TestWorkspaceToolLoading:
    async def _seed_tool(self, name: str, safety_flag: str, definition: dict | None = None):
        async with TestSessionLocal() as db:
            db.add(Tool(
                id=str(uuid.uuid4()), name=name, kind="openapi", source="local",
                definition=definition if definition is not None else {
                    "description": "d",
                    "input_schema": {"type": "object", "properties": {}},
                },
                safety_flag=safety_flag, checksum="c" * 64, workspace_id="ws1",
            ))
            await db.commit()

    @pytest.mark.asyncio
    async def test_high_risk_tools_excluded_from_agent_loop(self, service_sessions):
        await self._seed_tool("safe_tool", "unverified")
        await self._seed_tool("net_tool", "high_risk_network")
        await self._seed_tool("fs_tool", "high_risk_fs")
        tools = await _load_workspace_tools("ws1")
        names = {t["name"] for t in tools}
        assert names == {"safe_tool"}

    @pytest.mark.asyncio
    async def test_tools_without_input_schema_skipped(self, service_sessions):
        await self._seed_tool("schemaless", "unverified", definition={"description": "no schema"})
        tools = await _load_workspace_tools("ws1")
        assert tools == []

    @pytest.mark.asyncio
    async def test_no_workspace_returns_no_tools(self, service_sessions):
        assert await _load_workspace_tools(None) == []


class TestRegistryToolExecution:
    @pytest.mark.asyncio
    async def test_non_openapi_kinds_are_not_executable(self):
        tool = {"_registry": {"kind": "python", "definition": {}}}
        result = await _exec_registry_tool(tool, {})
        assert "not executable" in result

    @pytest.mark.asyncio
    async def test_openapi_missing_url_reports_error(self):
        tool = {"_registry": {"kind": "openapi", "definition": {}}}
        result = await _exec_registry_tool(tool, {})
        assert result.startswith("Error:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_openapi_get_passes_inputs_as_params(self):
        route = respx.get("https://api.example.com/run").mock(
            return_value=Response(200, text="ok-result")
        )
        tool = {"_registry": {"kind": "openapi", "definition": {
            "url": "https://api.example.com/run", "method": "GET",
        }}}
        result = await _exec_registry_tool(tool, {"q": "hello"})
        assert result == "ok-result"
        assert route.calls[0].request.url.params["q"] == "hello"


class TestPauseResumeFlags:
    def test_pause_resume_roundtrip(self):
        agent_id = str(uuid.uuid4())
        assert is_paused(agent_id) is False
        pause_agent(agent_id)
        assert is_paused(agent_id) is True
        assert resume_agent(agent_id) is True
        assert is_paused(agent_id) is False

    def test_resume_unpaused_agent_returns_false(self):
        assert resume_agent(str(uuid.uuid4())) is False


class TestBuildTask:
    def test_includes_criterion_ids_and_mark_instruction(self):
        crit_id = str(uuid.uuid4())
        ticket = _ticket(acceptance_criteria=[
            {"id": crit_id, "text": "add endpoint", "done": False, "test_cmd": "pytest -k endpoint"},
        ])
        task = _build_task(ticket, "Be careful.", method="anthropic")
        assert f"ID:{crit_id}" in task
        assert "pytest -k endpoint" in task
        assert "mark_criterion_done" in task
        assert task.startswith("Be careful.")

    def test_done_criteria_rendered_checked(self):
        ticket = _ticket(acceptance_criteria=[
            {"id": "c1", "text": "done one", "done": True},
        ])
        assert "[x] ID:c1" in _build_task(ticket, "")


class TestRunAnthropicAgentWithoutKey:
    @pytest.mark.asyncio
    async def test_missing_api_key_blocks_ticket_and_errors_agent(
        self, service_sessions, monkeypatch
    ):
        from app.core.config import settings
        monkeypatch.setattr(settings, "anthropic_api_key", None)

        ticket = _ticket()
        agent = Agent(
            id=str(uuid.uuid4()), workspace_id="ws1", name="no-key-agent",
            api_key_hash=uuid.uuid4().hex, status="working",
            current_ticket_id=ticket.id,
        )
        async with TestSessionLocal() as db:
            db.add_all([ticket, agent])
            await db.commit()

        await run_anthropic_agent(agent.id, "treco_key", ticket, None, "", "")

        async with TestSessionLocal() as db:
            assert (await db.get(Ticket, ticket.id)).status == "blocked"
            assert (await db.get(Agent, agent.id)).status == "error"
            errors = (await db.execute(
                select(AgentEvent).where(
                    AgentEvent.ticket_id == ticket.id,
                    AgentEvent.event_type == EventType.ERROR,
                )
            )).scalars().all()
        assert any("ANTHROPIC_API_KEY" in e.payload.get("message", "") for e in errors)
