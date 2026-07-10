"""
Agent implementation runners — spawned as asyncio background tasks.
Both runners create their own DB sessions (one per event emit) since they
outlive the request session.
"""
import asyncio
import json as _json
import os
from typing import Any

from app.core.constants import AgentStatus, EventType
from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.models.workspace import Workspace


async def _emit(
    agent_id: str,
    ticket_id: str,
    workspace_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    import uuid
    async with AsyncSessionLocal() as db:
        db.add(AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket_id,
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
        ))
        await db.commit()


async def _finish_agent(agent_id: str, status: str) -> None:
    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if agent:
            agent.status = status
            agent.current_ticket_id = None
            db.add(agent)
            await db.commit()


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
        db.add(AgentEvent(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            ticket_id=ticket.id,
            workspace_id=ticket.workspace_id or "",
            event_type=EventType.CRITERION_CHECKED,
            criterion_id=criterion_id,
            payload={"file_path": file_path, "notes": notes},
        ))
        await db.commit()


def _build_task(ticket: Ticket, system_prompt: str, method: str = "anthropic") -> str:
    criteria = "\n".join(
        f"- [{('x' if c.get('done') else ' ')}] ID:{c['id']} {c['text']}"
        + (f"  (verify: {c['test_cmd']})" if c.get("test_cmd") else "")
        for c in (ticket.acceptance_criteria or [])
    )
    base = system_prompt.strip() + "\n\n" if system_prompt.strip() else ""

    if method == "claude_code":
        mark_instruction = (
            "IMPORTANT: after completing each criterion, run this bash command:\n"
            "  treco check <criterion_id> --file <repo_relative_path> --notes \"<one sentence>\"\n"
            "Example:\n"
            "  treco check d8a7e9a2-... --file src/components/Foo.tsx --notes \"Removed badge from TopBar\"\n"
            "Always include --file (the main file you changed) and --notes (what you did). "
            "Do NOT just mention the ID in text — run the command."
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
) -> None:
    ws_id = ticket.workspace_id or ""
    repo_path = (workspace.repo_path if workspace and workspace.repo_path else None) or os.getcwd()
    task = _build_task(ticket, system_prompt, method="claude_code")

    env = {
        **os.environ,
        "TRECO_API_KEY": api_key,
        "TRECO_URL": "http://localhost:8001",
        "TRECO_TICKET_ID": ticket.id,
    }

    try:
        args = [
            "claude", "--dangerously-skip-permissions",
            "-p", task,
            "--output-format", "stream-json",
            "--verbose",
        ]
        if model:
            args += ["--model", model]

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=repo_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Accumulate tool_use input across content_block_delta events (verbose streaming format)
        _partial_tool: dict[str, Any] = {}

        async def _drain_stdout() -> None:
            assert proc.stdout
            async for raw in proc.stdout:
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
                        _partial_tool.clear()

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
        await proc.wait()

        if proc.returncode == 0:
            await _emit(agent_id, ticket.id, ws_id, EventType.DONE, {"exit_code": 0})
            await _finish_agent(agent_id, AgentStatus.IDLE)
        else:
            await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"exit_code": proc.returncode})
            await _finish_agent(agent_id, "error")

    except FileNotFoundError:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {
            "message": "claude CLI not found — install with: npm i -g @anthropic-ai/claude-code"
        })
        await _finish_agent(agent_id, "error")
    except Exception as e:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"message": str(e)})
        await _finish_agent(agent_id, "error")


# ── Anthropic tool-use loop ───────────────────────────────────────────────────

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


async def _exec_tool(
    name: str,
    inputs: dict[str, Any],
    agent_id: str,
    ticket: Ticket,
    repo_path: str,
) -> str:
    ws_id = ticket.workspace_id or ""
    try:
        if name == "read_file":
            path = os.path.join(repo_path, inputs["path"])
            with open(path) as f:
                return f.read()

        if name == "write_file":
            path = os.path.join(repo_path, inputs["path"])
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w") as f:
                f.write(inputs["content"])
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
    repo_path = (workspace.repo_path if workspace and workspace.repo_path else None) or os.getcwd()

    if not settings.anthropic_api_key:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {
            "message": "ANTHROPIC_API_KEY not set"
        })
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

        for _ in range(30):
            response = await client.messages.create(
                model=model or "claude-sonnet-5",
                max_tokens=4096,
                system=system,
                tools=_TOOLS,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            messages.append({"role": "assistant", "content": response.content})

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
                result = await _exec_tool(block.name, inp, agent_id, ticket, repo_path)
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

        await _emit(agent_id, ticket.id, ws_id, EventType.DONE, {})
        await _finish_agent(agent_id, AgentStatus.IDLE)

    except Exception as e:
        await _emit(agent_id, ticket.id, ws_id, EventType.ERROR, {"message": str(e)})
        await _finish_agent(agent_id, "error")
