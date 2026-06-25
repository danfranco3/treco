"""Tests for agent_runner: mint_agent, spawn_agent_run, _reap."""
import asyncio
import hashlib
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.services import agent_runner
from tests.shared import TestSessionLocal


@pytest_asyncio.fixture
async def db_ticket():
    async with TestSessionLocal() as db:
        t = Ticket(
            id=str(uuid.uuid4()),
            workspace_id="ws1",
            source="custom",
            title="Test ticket",
            status="open",
            body={},
            acceptance_criteria=[],
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t


class TestMintAgent:
    @pytest.mark.asyncio
    async def test_creates_agent_in_db(self):
        async with TestSessionLocal() as db:
            agent, raw_key = await agent_runner.mint_agent("ws1", "test-agent", db)

        assert agent.id
        assert agent.workspace_id == "ws1"
        assert agent.name == "test-agent"
        assert agent.status == "idle"

    @pytest.mark.asyncio
    async def test_returns_raw_key_with_prefix(self):
        async with TestSessionLocal() as db:
            _, raw_key = await agent_runner.mint_agent("ws1", "test-agent", db)
        assert raw_key.startswith("treco_")

    @pytest.mark.asyncio
    async def test_key_stored_hashed(self):
        async with TestSessionLocal() as db:
            agent, raw_key = await agent_runner.mint_agent("ws1", "test-agent", db)
            refreshed = await db.get(Agent, agent.id)
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert refreshed.api_key_hash == expected_hash
        assert refreshed.api_key_hash != raw_key

    @pytest.mark.asyncio
    async def test_each_call_produces_unique_key(self):
        async with TestSessionLocal() as db:
            _, key1 = await agent_runner.mint_agent("ws1", "agent-a", db)
            _, key2 = await agent_runner.mint_agent("ws1", "agent-b", db)
        assert key1 != key2


class TestSpawnAgentRun:
    @pytest.mark.asyncio
    async def test_sets_agent_working_and_emits_event(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, raw_key = await agent_runner.mint_agent("ws1", "spawner", db)

        mock_proc = MagicMock()
        mock_proc.pid = 99999

        mock_open = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("app.services.agent_runner._reap", new_callable=AsyncMock), \
             patch("builtins.open", mock_open):
            async with TestSessionLocal() as db:
                refreshed_agent = await db.get(Agent, agent.id)
                await agent_runner.spawn_agent_run(
                    refreshed_agent, raw_key, ticket, "do the work", "/tmp", db
                )

        async with TestSessionLocal() as db:
            updated = await db.get(Agent, agent.id)
            assert updated.status == "working"
            assert updated.current_ticket_id == ticket.id
            assert updated.pid == 99999

    @pytest.mark.asyncio
    async def test_emits_ticket_started_event(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, raw_key = await agent_runner.mint_agent("ws1", "spawner2", db)

        mock_proc = MagicMock()
        mock_proc.pid = 88888
        mock_open = MagicMock()
        mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("app.services.agent_runner._reap", new_callable=AsyncMock), \
             patch("builtins.open", mock_open):
            async with TestSessionLocal() as db:
                refreshed_agent = await db.get(Agent, agent.id)
                await agent_runner.spawn_agent_run(
                    refreshed_agent, raw_key, ticket, "do the work", "/tmp", db
                )

        async with TestSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(AgentEvent)
                .where(AgentEvent.agent_id == agent.id)
                .where(AgentEvent.event_type == "ticket_started")
            )
            event = result.scalar_one_or_none()
        assert event is not None
        assert event.ticket_id == ticket.id

    @pytest.mark.asyncio
    async def test_config_file_written_with_api_key(self, db_ticket, tmp_path):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, raw_key = await agent_runner.mint_agent("ws1", "cfg-test", db)

        mock_proc = MagicMock()
        mock_proc.pid = 77777

        with patch("app.services.agent_runner.RUNS_DIR", tmp_path), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("app.services.agent_runner._reap", new_callable=AsyncMock):
            async with TestSessionLocal() as db:
                refreshed_agent = await db.get(Agent, agent.id)
                await agent_runner.spawn_agent_run(
                    refreshed_agent, raw_key, ticket, "prompt", "/tmp", db
                )

        config_files = list(tmp_path.rglob("config.json"))
        assert len(config_files) == 1
        import json
        config = json.loads(config_files[0].read_text())
        assert config["api_key"] == raw_key
        assert config["workspace_id"] == "ws1"


class TestReap:
    """_reap uses AsyncSessionLocal directly, so we patch it to use the test DB."""

    @pytest.mark.asyncio
    async def test_reap_emits_deviation_when_no_terminal_event(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, _ = await agent_runner.mint_agent("ws1", "reap-test", db)
            a = await db.get(Agent, agent.id)
            a.status = "working"
            a.current_ticket_id = ticket.id
            db.add(a)
            await db.commit()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        fake_log = Path("/tmp/fake_stdout.log")
        fake_log.write_text("agent completed successfully with exit code 0")

        with patch("app.services.agent_runner.AsyncSessionLocal", TestSessionLocal):
            await agent_runner._reap(agent.id, ticket.id, mock_proc, fake_log)

        async with TestSessionLocal() as db:
            updated = await db.get(Agent, agent.id)
            assert updated.status == "error"
            assert updated.pid is None

            from sqlalchemy import select
            result = await db.execute(
                select(AgentEvent)
                .where(AgentEvent.agent_id == agent.id)
                .where(AgentEvent.event_type == "deviation")
            )
            event = result.scalar_one_or_none()
        assert event is not None
        assert event.payload["deviation_type"] == "process_exited"

    @pytest.mark.asyncio
    async def test_reap_detects_permission_keyword(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, _ = await agent_runner.mint_agent("ws1", "perm-test", db)
            a = await db.get(Agent, agent.id)
            a.status = "working"
            a.current_ticket_id = ticket.id
            db.add(a)
            await db.commit()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        fake_log = Path("/tmp/fake_perm.log")
        fake_log.write_text("Error: permission denied to write file")

        with patch("app.services.agent_runner.AsyncSessionLocal", TestSessionLocal):
            await agent_runner._reap(agent.id, ticket.id, mock_proc, fake_log)

        async with TestSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(AgentEvent)
                .where(AgentEvent.agent_id == agent.id)
                .where(AgentEvent.event_type == "deviation")
            )
            event = result.scalar_one_or_none()
        assert event.payload["deviation_type"] == "awaiting_approval"

    @pytest.mark.asyncio
    async def test_reap_skips_if_terminal_event_exists(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, _ = await agent_runner.mint_agent("ws1", "skip-test", db)
            a = await db.get(Agent, agent.id)
            a.status = "working"
            a.current_ticket_id = ticket.id
            db.add(a)
            db.add(AgentEvent(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                ticket_id=ticket.id,
                workspace_id="ws1",
                event_type="done",
                payload={},
            ))
            await db.commit()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        fake_log = Path("/tmp/fake_done.log")
        fake_log.write_text("")

        with patch("app.services.agent_runner.AsyncSessionLocal", TestSessionLocal):
            await agent_runner._reap(agent.id, ticket.id, mock_proc, fake_log)

        async with TestSessionLocal() as db:
            updated = await db.get(Agent, agent.id)
        assert updated.status == "working"

    @pytest.mark.asyncio
    async def test_reap_skips_if_ticket_changed(self, db_ticket):
        ticket = db_ticket
        async with TestSessionLocal() as db:
            agent, _ = await agent_runner.mint_agent("ws1", "ticket-change-test", db)
            a = await db.get(Agent, agent.id)
            a.status = "working"
            a.current_ticket_id = "different-ticket-id"
            db.add(a)
            await db.commit()

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        fake_log = Path("/tmp/fake_changed.log")
        fake_log.write_text("")

        with patch("app.services.agent_runner.AsyncSessionLocal", TestSessionLocal):
            await agent_runner._reap(agent.id, ticket.id, mock_proc, fake_log)

        async with TestSessionLocal() as db:
            updated = await db.get(Agent, agent.id)
        assert updated.status == "working"
