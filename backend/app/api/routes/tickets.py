import asyncio
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import AgentStatus, EventType
from app.core.database import get_db, get_or_404
from app.models.agent import Agent
from app.models.event import AgentEvent
from app.models.ticket import Ticket
from app.models.workspace import Workspace
from app.services.auth import generate_api_key

router = APIRouter()


def _make_criterion(text: str, test_cmd: str | None = None, done: bool = False) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "text": text, "test_cmd": test_cmd, "done": done, "verified": False, "evidence": None}


def _split_description(description: str | None) -> tuple[str | None, list[str]]:
    """Extract `- [ ] ...` lines from description; return (cleaned_description, criteria_texts)."""
    if not description:
        return description, []
    criteria: list[str] = []
    body_lines: list[str] = []
    for line in description.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            text = stripped[5:].strip()
            if text:
                criteria.append(text)
        else:
            body_lines.append(line)
    cleaned = "\n".join(body_lines).strip() or None
    return cleaned, criteria


class CreateTicketRequest(BaseModel):
    workspace_id: str | None = Field(None, examples=["ws-abc123"])
    title: str = Field(..., examples=["Fix login redirect loop"])
    description: str | None = Field(None)
    acceptance_criteria: list[str] = Field(default=[])


class CriterionInput(BaseModel):
    id: str | None = None
    text: str
    test_cmd: str | None = None
    done: bool = False
    verified: bool = False
    evidence: str | None = None


class TicketResponse(BaseModel):
    id: str
    workspace_id: str | None
    source: str
    source_id: str | None
    title: str
    description: str | None
    status: str
    acceptance_criteria: list[dict]
    body: dict

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=TicketResponse)
async def create_ticket(req: CreateTicketRequest, db: AsyncSession = Depends(get_db)):
    cleaned_desc, extracted = _split_description(req.description)
    criteria = [_make_criterion(c) for c in (req.acceptance_criteria or extracted)]
    ticket = Ticket(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        source="custom",
        source_id=None,
        title=req.title,
        description=cleaned_desc,
        status="open",
        body={},
        acceptance_criteria=criteria,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.put("/{ticket_id}/criteria", response_model=TicketResponse)
async def update_criteria(
    ticket_id: str,
    criteria: list[CriterionInput],
    db: AsyncSession = Depends(get_db),
):
    ticket = await get_or_404(db, Ticket, ticket_id)
    ticket.acceptance_criteria = [
        {
            "id": c.id or str(uuid.uuid4()),
            "text": c.text,
            "test_cmd": c.test_cmd,
            "done": c.done,
            "verified": c.verified,
            "evidence": c.evidence,
        }
        for c in criteria
    ]
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/refine", response_model=TicketResponse)
async def refine_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)):
    """Call LLM to propose acceptance criteria + test commands for this ticket."""
    ticket = await get_or_404(db, Ticket, ticket_id)
    if not ticket.description and not ticket.title:
        raise HTTPException(status_code=400, detail="Ticket needs a title or description to refine")

    proposed = await _propose_criteria(ticket.title, ticket.description)

    existing = {c["id"]: c for c in (ticket.acceptance_criteria or [])}
    merged = list(existing.values()) + [c for c in proposed if not any(e["text"] == c["text"] for e in existing.values())]
    ticket.acceptance_criteria = merged
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def _propose_criteria(title: str, description: str | None) -> list[dict[str, Any]]:
    prompt = f"""You are helping define verifiable acceptance criteria for a software ticket.

Title: {title}
Description: {description or "(none)"}

Propose 3–5 acceptance criteria. For each, provide:
- A clear, specific criterion statement
- A shell command to verify it (e.g. pytest test, curl check, file existence check)

Respond with ONLY a JSON array, no explanation:
[
  {{"text": "...", "test_cmd": "..."}},
  ...
]"""

    try:
        if settings.anthropic_api_key:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
        elif settings.openai_api_key:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content.strip()
        else:
            return []

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        items = json.loads(raw)
        return [_make_criterion(item["text"], item.get("test_cmd")) for item in items if "text" in item]
    except Exception:
        return []


class ImplementRequest(BaseModel):
    method: Literal["claude_code", "anthropic"]
    model: str = Field(default="claude-sonnet-5")
    system_prompt: str = Field(default="")
    skip_permissions: bool = Field(default=True)


class ImplementResponse(BaseModel):
    agent_id: str
    agent_name: str


@router.post("/{ticket_id}/implement", response_model=ImplementResponse)
async def implement_ticket(
    ticket_id: str,
    req: ImplementRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.implement import run_anthropic_agent, run_claude_code

    ticket = await get_or_404(db, Ticket, ticket_id)

    workspace: Workspace | None = None
    if ticket.workspace_id:
        workspace = await db.get(Workspace, ticket.workspace_id)

    raw_key, key_hash = generate_api_key()
    agent_name = f"impl-{ticket_id[:8]}"
    agent = Agent(
        id=str(uuid.uuid4()),
        workspace_id=ticket.workspace_id,
        name=agent_name,
        api_key_hash=key_hash,
        status=AgentStatus.WORKING,
        current_ticket_id=ticket_id,
    )
    db.add(agent)
    db.add(AgentEvent(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        ticket_id=ticket_id,
        workspace_id=ticket.workspace_id or "",
        event_type=EventType.TICKET_STARTED,
        payload={"method": req.method, "model": req.model},
    ))
    await db.commit()
    await db.refresh(agent)

    runner = run_claude_code if req.method == "claude_code" else run_anthropic_agent
    kwargs: dict[str, Any] = {"skip_permissions": req.skip_permissions} if req.method == "claude_code" else {}
    asyncio.create_task(runner(agent.id, raw_key, ticket, workspace, req.model, req.system_prompt, **kwargs))

    return ImplementResponse(agent_id=agent.id, agent_name=agent_name)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Ticket, ticket_id)


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)):
    ticket = await get_or_404(db, Ticket, ticket_id)
    await db.delete(ticket)
    await db.commit()


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    workspace_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Ticket)
    if workspace_id is not None:
        query = query.where(Ticket.workspace_id == workspace_id)
    query = query.order_by(Ticket.created_at.desc()).limit(min(limit, 200)).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
