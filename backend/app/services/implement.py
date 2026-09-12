"""
Agent implementation runners — spawned as asyncio background tasks.
Both runners create their own DB sessions (one per event emit) since they
outlive the request session.
"""
import asyncio
import json as _json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.constants import AgentStatus, EventType, TicketStatus
from app.core.database import AsyncSessionLocal
from app.core.pubsub import (
    agent_channel,
    agent_to_dict,
    bus,
    event_channel,
    event_to_dict,
    trace_channel,
    trace_to_dict,
)
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.models.trace import Trace
from app.models.workspace import Workspace

# Maps agent_id → active subprocess so the permission_response endpoint
# can write to stdin without needing to hold a reference elsewhere.
_active_procs: dict[str, asyncio.subprocess.Process] = {}

# Agents paused via POST /agents/{id}/pause — checked between loop iterations.
_paused_agents: set[str] = set()


def pause_agent(agent_id: str) -> None:
    _paused_agents.add(agent_id)


def resume_agent(agent_id: str) -> bool:
    if agent_id in _paused_agents:
        _paused_agents.discard(agent_id)
        return True
    return False


def is_paused(agent_id: str) -> bool:
    return agent_id in _paused_agents


async def _wait_if_paused(agent_id: str) -> None:
    while agent_id in _paused_agents:
        await asyncio.sleep(0.5)


async def _emit(
    agent_id: str,
    ticket_id: str,
    workspace_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    import uuid
    async with AsyncSessionLocal() as db:
        event = AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket_id,
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
        )
        db.add(event)
        await db.commit()
        bus.publish(event_channel(workspace_id), event_to_dict(event))


async def _finish_agent(agent_id: str, status: str) -> None:
    _active_procs.pop(agent_id, None)
    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if agent:
            agent.status = status
            agent.current_ticket_id = None
            db.add(agent)
            await db.commit()
            bus.publish(agent_channel(agent.workspace_id), agent_to_dict(agent))


async def _trace(
    agent_id: str,
    ticket_id: str,
    workspace_id: str,
    step_type: str,
    *,
    tool_name: str | None = None,
    status: str = "ok",
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
    parent_trace_id: str | None = None,
    event_id: str | None = None,
) -> str:
    import uuid
    async with AsyncSessionLocal() as db:
        trace = Trace(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket_id,
            parent_trace_id=parent_trace_id,
            event_id=event_id,
            step_type=step_type,
            tool_name=tool_name,
            status=status,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            payload=payload or {},
        )
        db.add(trace)
        await db.commit()
        bus.publish(trace_channel(workspace_id), trace_to_dict(trace))
    return trace.id


async def _set_ticket_status(ticket_id: str, status: str) -> None:
    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket_id)
        if ticket:
            ticket.status = status
            db.add(ticket)
            await db.commit()


async def _cleanup_worktree(ticket: Ticket, workspace: Workspace | None, error: bool) -> None:
    from app.core.config import settings
    from app.services.worktree import remove_worktree

    if not ticket.worktree_path or not workspace or not workspace.repo_path:
        return
    if error and settings.keep_worktree_on_error:
        return
    await remove_worktree(workspace.repo_path, ticket.worktree_path)
    async with AsyncSessionLocal() as db:
        t = await db.get(Ticket, ticket.id)
        if t:
            t.worktree_path = None
            db.add(t)
            await db.commit()


async def respond_permission(agent_id: str, response: str) -> bool:
    """Write a y/n response to the waiting subprocess stdin. Returns False if no proc."""
    proc = _active_procs.get(agent_id)
    if not proc or not proc.stdin:
        return False
    try:
        proc.stdin.write((response.strip() + "\n").encode())
        await proc.stdin.drain()
        return True
    except Exception:
        return False


async def _mark_criterion(
    agent_id: str,
    ticket: Ticket,
    criterion_id: str,
    file_path: str | None = None,
    notes: str | None = None,
) -> None:
    import uuid
    async with AsyncSessionLocal() as db:
        t = await db.get(Ticket, ticket.id)
        if not t:
            return
        updated = [
            {**c, "done": True, "file_path": file_path, "notes": notes} if c["id"] == criterion_id else c
            for c in (t.acceptance_criteria or [])
        ]
        t.acceptance_criteria = updated
        db.add(t)
        event = AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket.id,
            workspace_id=ticket.workspace_id or "",
            event_type=EventType.CRITERION_CHECKED,
            criterion_id=criterion_id,
            payload={"file_path": file_path, "notes": notes},
        )
        db.add(event)
        await db.commit()
        bus.publish(event_channel(ticket.workspace_id or ""), event_to_dict(event))
    await _trace(
        agent_id, ticket.id, ticket.workspace_id or "", "criterion_check",
        event_id=event.id, payload={"criterion_id": criterion_id},
    )


def _build_task(ticket: Ticket, system_prompt: str, method: str = "anthropic") -> str:
    criteria = "\n".join(
        f"- [{('x' if c.get('done') else ' ')}] ID:{c['id']} {c['text']}"
        + (f"  (verify: {c['test_cmd']})" if c.get("test_cmd") else "")
        for c in (ticket.acceptance_criteria or [])
    )
    base = system_prompt.strip() + "\n\n" if system_prompt.strip() else ""

    if method == "claude_code":
        mark_instruction = (
            "IMPORTANT: after completing each criterion, call the `mark_criterion_done` MCP tool "
            "with its exact ID, the repo-relative path of the main file you changed, and a one-sentence note. "
            "Do NOT just mention the ID in text — call the tool."
        )
    else:
        mark_instruction = (
            "IMPORTANT: after completing each criterion, call the "
            "`mark_criterion_done` tool with its exact ID string. "
            "Do not just mention the ID in text — call the tool. "
            "Only call `finish` after all criteria are marked done."
        )

    return (
        f"{base}Implement the following ticket:\n\n"
        f"**{ticket.title}**\n"
        f"{ticket.description or ''}\n\n"
        f"Acceptance criteria (each has an ID):\n{criteria or '(none)'}\n\n"
        f"{mark_instruction}"
    )


# ── Claude Code subprocess ────────────────────────────────────────────────────

async def run_claude_code(
    agent_id: str,
    api_key: str,
    ticket: Ticket,
    workspace: Workspace | None,
    model: str,
    system_prompt: str,
    skip_permissions: bool = True,
) -> None:
    ws_id = ticket.workspace_id or ""
    repo_path = (
        ticket.worktree_path
        or (workspace.repo_path if workspace and workspace.repo_path else None)
        or os.getcwd()
    )
    task = _build_task(ticket, system_prompt, method="claude_code")

    env = {
        **os.environ,
        "TRECO_API_KEY": api_key,
        "TRECO_URL": "http://localhost:8001",
        "TRECO_TICKET_ID": ticket.id,
    }

    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    mcp_config = {
        "mcpServers": {
            "treco": {
                "command": "python3",
                "args": [str(mcp_server_path)],
                "env": {
                    "TRECO_API_KEY": env["TRECO_API_KEY"],
                    "TRECO_URL": env["TRECO_URL"],
                    "TRECO_TICKET_ID": env["TRECO_TICKET_ID"],
                },
            }
        }
    }

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as mcp_cfg_file:
            _json.dump(mcp_config, mcp_cfg_file)
            mcp_cfg_path = mcp_cfg_file.name

        args = ["claude"]
        if skip_permissions:
            args.append("--dangerously-skip-permissions")
        args += [
            "-p", task,
            "--output-format", "stream-json",
            "--verbose",
            "--mcp-config", mcp_cfg_path,
        ]
        if model:
            args += ["--model", model]

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=repo_path,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _active_procs[agent_id] = proc

        # Accumulate tool_use input across content_block_delta events (verbose streaming format)
        _partial_tool: dict[str, Any] = {}

        async def _drain_stdout() -> None:
            assert proc.stdout
            async for raw in proc.stdout:
                await _wait_if_paused(agent_id)
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                except _json.JSONDecodeError:
                    await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": line})
                    continue

                kind = obj.get("type")

                # Standard complete-message format
                if kind == "assistant":
                    msg = obj.get("message", {})
                    for block in msg.get("content", []):
                        btype = block.get("type")
                        if btype == "text" and block.get("text"):
                            await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": block["text"].strip()})
                        elif btype == "tool_use":
                            name = block.get("name", "tool")
                            inp = block.get("input", {})
                            brief = (
                                inp.get("command") or inp.get("file_path") or
                                inp.get("path") or inp.get("criterion_id") or
                                inp.get("summary") or ""
                            )
                            await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {
                                "message": f"→ {name}({brief})" if brief else f"→ {name}"
                            })
                            await _trace(
                                agent_id, ticket.id, ws_id, "tool_call",
                                tool_name=name, payload={"brief": brief},
                            )

                # Streaming content block format (emitted when --verbose or newer SDK)
                elif kind == "content_block_start":
                    cb = obj.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        _partial_tool.clear()
                        _partial_tool["name"] = cb.get("name", "tool")
                        _partial_tool["input_raw"] = ""
                elif kind == "content_block_delta":
                    delta = obj.get("delta", {})
                    if delta.get("type") == "input_json_delta" and "input_raw" in _partial_tool:
                        _partial_tool["input_raw"] = _partial_tool.get("input_raw", "") + delta.get("partial_json", "")
                    elif delta.get("type") == "text_delta" and delta.get("text"):
                        await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": delta["text"]})
                elif kind == "content_block_stop":
                    if "name" in _partial_tool:
                        name = _partial_tool.get("name", "tool")
                        try:
                            inp = _json.loads(_partial_tool.get("input_raw") or "{}")
                        except _json.JSONDecodeError:
                            inp = {}
                        brief = (
                            inp.get("command") or inp.get("file_path") or
                            inp.get("path") or inp.get("criterion_id") or
                            inp.get("summary") or ""
                        )
                        await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {
                            "message": f"→ {name}({brief})" if brief else f"→ {name}"
                        })
                        await _trace(
                            agent_id, ticket.id, ws_id, "tool_call",
                            tool_name=name, payload={"brief": brief},
                        )
                        _partial_tool.clear()

                elif kind == "input_required":
                    prompt = obj.get("prompt") or obj.get("message") or "Permission required"
                    request_id = obj.get("request_id") or obj.get("id") or ""
                    await _emit(agent_id, ticket.id, ws_id, EventType.PERMISSION_REQUESTED, {
                        "prompt": prompt,
                        "request_id": request_id,
                    })
                    await _trace(
                        agent_id, ticket.id, ws_id, "permission_gate",
                        payload={"prompt": prompt},
                    )
                    async with AsyncSessionLocal() as db:
                        agent = await db.get(Agent, agent_id)
                        if agent:
                            agent.status = AgentStatus.AWAITING_APPROVAL
                            db.add(agent)
                            await db.commit()
                            bus.publish(agent_channel(agent.workspace_id), agent_to_dict(agent))
                    await _set_ticket_status(ticket.id, TicketStatus.HITL_REVIEW)

                elif kind == "result":
                    result_text = obj.get("result", "")
                    if result_text:
                        await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": result_text.strip()})

        async def _drain_stderr() -> None:
            assert proc.stderr
            lines: list[str] = []
            async for raw in proc.stderr:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    lines.append(line)
            if lines:
                await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": "\n".join(lines)})

        await asyncio.gather(_drain_stdout(), _drain_stderr())
        if proc.stdin:
            proc.stdin.close()
        await proc.wait()

        try:
            os.unlink(mcp_cfg_path)
        except OSError:
            pass

        from app.services.telemetry import record_ticket_final_metrics
        if proc.returncode == 0:
            await _emit(agent_id, ticket.id, ws_id, EventType.DONE, {"exit_code": 0})
            from app.services.deviation import flag_incomplete_criteria
            await record_ticket_final_metrics(ticket.id, ws_id, agent_id)
            await flag_incomplete_criteria(agent_id, ticket.id, ws_id)
            await _set_ticket_status(ticket.id, TicketStatus.DONE)
            await _finish_agent(agent_id, AgentStatus.IDLE)
            await _cleanup_worktree(ticket, workspace, error=False)
        else:
            await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"exit_code": proc.returncode})
            from app.services.deviation import emit_deviation
            await emit_deviation(
                agent_id, ticket.id, ws_id, "process_exited",
                f"claude CLI exited with code {proc.returncode}",
                block=False,
                context={"exit_code": proc.returncode},
            )
            await record_ticket_final_metrics(ticket.id, ws_id, agent_id)
            await _set_ticket_status(ticket.id, TicketStatus.BLOCKED)
            await _finish_agent(agent_id, "error")
            await _cleanup_worktree(ticket, workspace, error=True)

    except FileNotFoundError:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {
            "message": "claude CLI not found — install with: npm i -g @anthropic-ai/claude-code"
        })
        await _set_ticket_status(ticket.id, TicketStatus.BLOCKED)
        await _finish_agent(agent_id, "error")
        await _cleanup_worktree(ticket, workspace, error=True)
    except Exception as e:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"message": str(e)})
        await _set_ticket_status(ticket.id, TicketStatus.BLOCKED)
        await _finish_agent(agent_id, "error")
        await _cleanup_worktree(ticket, workspace, error=True)


# ── Anthropic tool-use loop ───────────────────────────────────────────────────

# Runaway-loop ceiling — loop_utilization_ratio telemetry measures against this.
_MAX_LOOPS = 30

# Context-saturation denominator; the last turn's input_tokens approximates
# the full accumulated context since messages are never trimmed.
_CONTEXT_WINDOW_TOKENS = 200_000

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a file from the repository.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path from repo root"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file in the repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the repo directory. Returns stdout+stderr (max 2000 chars).",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "mark_criterion_done",
        "description": "Mark an acceptance criterion as done by its ID. Include the file you changed and a short note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "criterion_id": {"type": "string"},
                "file_path": {"type": "string", "description": "Repo-relative path of the main file changed"},
                "notes": {"type": "string", "description": "One sentence describing what you did"},
            },
            "required": ["criterion_id"],
        },
    },
    {
        "name": "finish",
        "description": "Signal that the implementation is complete.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


async def _load_workspace_tools(workspace_id: str | None) -> list[dict[str, Any]]:
    """Registry tools exposed to the agent loop. High-risk tools are excluded;
    only openapi tools are executable (python/javascript have no sandbox yet)."""
    if not workspace_id:
        return []
    from sqlalchemy import select
    from app.models.tool import Tool

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tool).where(
                Tool.workspace_id == workspace_id,
                Tool.safety_flag.not_in(["high_risk_network", "high_risk_fs"]),
            )
        )
        rows = result.scalars().all()
    tools = []
    for row in rows:
        definition = row.definition or {}
        if not definition.get("input_schema"):
            continue
        tools.append({
            "name": row.name,
            "description": definition.get("description", ""),
            "input_schema": definition["input_schema"],
            "_registry": {"kind": row.kind, "definition": definition},
        })
    return tools


async def _exec_registry_tool(tool: dict[str, Any], inputs: dict[str, Any]) -> str:
    registry = tool["_registry"]
    if registry["kind"] != "openapi":
        return f"Error: {registry['kind']} tools are not executable yet (no sandbox)"
    import httpx
    definition = registry["definition"]
    url = definition.get("url")
    if not url:
        return "Error: openapi tool definition missing url"
    method = str(definition.get("method", "GET")).upper()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, json=inputs if method != "GET" else None,
                                    params=inputs if method == "GET" else None)
        return resp.text[:2000]


def _safe_path(repo_path: str, rel_path: str) -> str:
    """Resolve a tool-supplied path, rejecting anything that escapes the repo."""
    base = os.path.realpath(repo_path)
    resolved = os.path.realpath(os.path.join(base, rel_path))
    if resolved != base and not resolved.startswith(base + os.sep):
        raise ValueError(f"Path escapes repository: {rel_path}")
    return resolved


async def _exec_tool(
    name: str,
    inputs: dict[str, Any],
    agent_id: str,
    ticket: Ticket,
    repo_path: str,
    registry: dict[str, dict[str, Any]] | None = None,
) -> str:
    ws_id = ticket.workspace_id or ""
    try:
        if name == "read_file":
            path = _safe_path(repo_path, inputs["path"])
            with open(path) as f:
                return f.read()

        if name == "write_file":
            path = _safe_path(repo_path, inputs["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(inputs["content"])
            from app.services.telemetry import record_metric
            await record_metric(
                ws_id, "diff_churn_lines", inputs["content"].count("\n") + 1, "count",
                ticket_id=ticket.id, agent_id=agent_id, dims={"path": inputs["path"]},
            )
            return f"Written {inputs['path']}"

        if name == "run_command":
            proc = await asyncio.create_subprocess_shell(
                inputs["command"],
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode(errors="replace")[:2000]
            await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {
                "message": f"$ {inputs['command']}\n{output}"
            })
            return output

        if name == "mark_criterion_done":
            await _mark_criterion(
                agent_id, ticket, inputs["criterion_id"],
                file_path=inputs.get("file_path"),
                notes=inputs.get("notes"),
            )
            return f"Criterion {inputs['criterion_id']} marked done"

        if name == "finish":
            return inputs.get("summary", "Done")

        if registry and name in registry:
            return await _exec_registry_tool(registry[name], inputs)

        return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error: {e}"


async def run_anthropic_agent(
    agent_id: str,
    api_key: str,  # noqa: ARG001 — Treco key, not Anthropic key
    ticket: Ticket,
    workspace: Workspace | None,
    model: str,
    system_prompt: str,
) -> None:
    from app.core.config import settings

    ws_id = ticket.workspace_id or ""
    repo_path = (
        ticket.worktree_path
        or (workspace.repo_path if workspace and workspace.repo_path else None)
        or os.getcwd()
    )

    if not settings.anthropic_api_key:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {
            "message": "ANTHROPIC_API_KEY not set"
        })
        await _set_ticket_status(ticket.id, TicketStatus.BLOCKED)
        await _finish_agent(agent_id, "error")
        return

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        system = (
            (system_prompt.strip() + "\n\n") if system_prompt.strip() else ""
        ) + (
            "You are an expert software engineer. Implement the requested changes carefully and completely. "
            "After completing each acceptance criterion, call `mark_criterion_done` with its exact ID — "
            "do NOT just mention the ID in text. Call `finish` only after all criteria are marked done."
        )

        user_content = _build_task(ticket, "", method="anthropic")
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        registry_tools = await _load_workspace_tools(ticket.workspace_id)
        registry_by_name = {t["name"]: t for t in registry_tools}
        api_tools = _TOOLS + [
            {k: v for k, v in t.items() if k != "_registry"} for t in registry_tools
        ]

        loops_used = 0
        last_context_tokens = 0
        for _ in range(_MAX_LOOPS):
            await _wait_if_paused(agent_id)
            loops_used += 1
            response = await client.messages.create(
                model=model or "claude-sonnet-5",
                max_tokens=4096,
                system=system,
                tools=api_tools,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            messages.append({"role": "assistant", "content": response.content})
            last_context_tokens = response.usage.input_tokens
            turn_trace_id = await _trace(
                agent_id, ticket.id, ws_id, "llm_turn",
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                payload={"stop_reason": response.stop_reason, "loop": loops_used},
            )

            # Emit any text blocks as log events
            text = "\n".join(b.text for b in response.content if hasattr(b, "text") and b.text)
            if text:
                await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {"message": text})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            done = False
            for block in response.content:
                if block.type != "tool_use":
                    continue
                inp: dict[str, Any] = block.input  # type: ignore[assignment]
                brief = (
                    inp.get("command") or inp.get("path") or
                    inp.get("criterion_id") or inp.get("summary") or ""
                )
                await _emit(agent_id, ticket.id, ws_id, EventType.LOG, {
                    "message": f"→ {block.name}({brief})" if brief else f"→ {block.name}"
                })
                started = asyncio.get_event_loop().time()
                result = await _exec_tool(block.name, inp, agent_id, ticket, repo_path, registry_by_name)
                await _trace(
                    agent_id, ticket.id, ws_id, "tool_call",
                    tool_name=block.name,
                    parent_trace_id=turn_trace_id,
                    status="error" if result.startswith("Error:") else "ok",
                    duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
                    payload={"brief": brief},
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
                if block.name == "finish":
                    done = True

            messages.append({"role": "user", "content": tool_results})
            if done:
                break

        await _emit(agent_id, ticket.id, ws_id, EventType.DONE, {"loops_used": loops_used})
        from app.services.deviation import flag_incomplete_criteria
        from app.services.telemetry import record_metric, record_ticket_final_metrics
        await record_metric(
            ws_id, "loop_count_per_ticket", loops_used, "count",
            ticket_id=ticket.id, agent_id=agent_id,
        )
        await record_metric(
            ws_id, "loop_utilization_ratio", loops_used / _MAX_LOOPS, "ratio",
            ticket_id=ticket.id, agent_id=agent_id,
            dims={"ceiling": _MAX_LOOPS, "runaway": loops_used >= _MAX_LOOPS},
        )
        if last_context_tokens:
            await record_metric(
                ws_id, "context_saturation_ratio",
                last_context_tokens / _CONTEXT_WINDOW_TOKENS, "ratio",
                ticket_id=ticket.id, agent_id=agent_id,
                dims={"context_tokens": last_context_tokens, "window": _CONTEXT_WINDOW_TOKENS},
            )
        await record_ticket_final_metrics(ticket.id, ws_id, agent_id)
        await flag_incomplete_criteria(agent_id, ticket.id, ws_id)
        await _set_ticket_status(ticket.id, TicketStatus.DONE)
        await _finish_agent(agent_id, AgentStatus.IDLE)
        await _cleanup_worktree(ticket, workspace, error=False)

    except Exception as e:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"message": str(e)})
        await _set_ticket_status(ticket.id, TicketStatus.BLOCKED)
        await _finish_agent(agent_id, "error")
        await _cleanup_worktree(ticket, workspace, error=True)
