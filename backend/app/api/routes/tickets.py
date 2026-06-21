import re
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_or_404
from app.models.ticket import Ticket
from app.models.workspace import Workspace
from app.services import agent_runner
from app.services.adapters import ADAPTERS
from app.services.adapters.base import NormalizedTicket
from app.services.criteria_extractor import create_criterion, extract_criteria

router = APIRouter()


def _require_workspace_id(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("workspace_id is required")
    return v


class ImportTicketRequest(BaseModel):
    source: Literal["jira", "linear", "asana", "github"]
    workspace_id: str
    raw: dict[str, Any]

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str) -> str:
        return _require_workspace_id(v)


class CreateTicketRequest(BaseModel):
    workspace_id: str | None = None
    title: str
    description: str | None = None
    acceptance_criteria: list[str] = []


class FetchGitHubIssueRequest(BaseModel):
    workspace_id: str
    repo: str
    issue_number: int
    token: str


class FetchLinearIssueRequest(BaseModel):
    workspace_id: str
    issue_id: str
    api_key: str


class BulkImportRequest(BaseModel):
    workspace_id: str
    source: Literal["github", "linear"]
    token: str
    repo: str | None = None
    team_key: str | None = None
    limit: int = 20

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str) -> str:
        return _require_workspace_id(v)

    @field_validator("team_key")
    @classmethod
    def validate_team_key(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[A-Z0-9_-]{1,20}", v):
            raise ValueError("team_key must be 1–20 uppercase alphanumeric characters")
        return v


class FetchUrlRequest(BaseModel):
    workspace_id: str
    url: str

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str) -> str:
        return _require_workspace_id(v)


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


class ImplementTicketRequest(BaseModel):
    prompt: str
    agent_name: str | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt is required")
        return v


class ImplementTicketResponse(BaseModel):
    agent_id: str
    agent_name: str

    model_config = ConfigDict(from_attributes=True)


class AssignTicketWorkspaceRequest(BaseModel):
    workspace_id: str | None = None


_GITHUB_ISSUE_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)"
)


async def _upsert_ticket(db: AsyncSession, workspace_id: str, norm: NormalizedTicket) -> Ticket:
    result = await db.execute(
        select(Ticket).where(
            Ticket.workspace_id == workspace_id,
            Ticket.source == norm.source,
            Ticket.source_id == norm.source_id,
        )
    )
    existing = result.scalars().first()
    if existing:
        existing.title = norm.title
        existing.description = norm.description
        existing.status = norm.status
        existing.body = norm.body
        await db.commit()
        await db.refresh(existing)
        return existing

    criteria = await extract_criteria(norm.title, norm.description)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        source=norm.source,
        source_id=norm.source_id,
        title=norm.title,
        description=norm.description,
        status=norm.status,
        body=norm.body,
        acceptance_criteria=criteria,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/import", response_model=TicketResponse)
async def import_ticket(req: ImportTicketRequest, db: AsyncSession = Depends(get_db)):
    adapter = ADAPTERS.get(req.source)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {req.source}")
    normalized = adapter.normalize(req.raw)
    return await _upsert_ticket(db, req.workspace_id, normalized)


@router.post("/fetch/github", response_model=TicketResponse)
async def fetch_github_issue(req: FetchGitHubIssueRequest, db: AsyncSession = Depends(get_db)):
    adapter = ADAPTERS["github"]
    normalized = await adapter.fetch_issue(req.repo, req.issue_number, req.token)
    return await _upsert_ticket(db, req.workspace_id, normalized)


@router.post("/fetch/linear", response_model=TicketResponse)
async def fetch_linear_issue(req: FetchLinearIssueRequest, db: AsyncSession = Depends(get_db)):
    adapter = ADAPTERS["linear"]
    normalized = await adapter.fetch_issue(req.issue_id, req.api_key)
    return await _upsert_ticket(db, req.workspace_id, normalized)


@router.post("/fetch/bulk", response_model=list[TicketResponse])
async def bulk_import(req: BulkImportRequest, db: AsyncSession = Depends(get_db)):
    if req.source == "github":
        if not req.repo:
            raise HTTPException(status_code=400, detail="repo is required for GitHub bulk import")
        adapter = ADAPTERS["github"]
        normalized_list = await adapter.fetch_issues(req.repo, req.token, req.limit)
    else:
        adapter = ADAPTERS["linear"]
        normalized_list = await adapter.fetch_issues(req.team_key, req.token, req.limit)
    return [await _upsert_ticket(db, req.workspace_id, n) for n in normalized_list]


@router.post("/fetch/url", response_model=TicketResponse)
async def fetch_url(req: FetchUrlRequest, db: AsyncSession = Depends(get_db)):
    m = _GITHUB_ISSUE_RE.match(req.url.strip())
    if m:
        owner, repo, issue_number = m.groups()
        adapter = ADAPTERS["github"]
        normalized = await adapter.fetch_issue(f"{owner}/{repo}", int(issue_number))
        return await _upsert_ticket(db, req.workspace_id, normalized)
    raise HTTPException(
        status_code=400,
        detail="Unsupported URL. Only public GitHub issue URLs are supported.",
    )


@router.post("", response_model=TicketResponse)
async def create_ticket(req: CreateTicketRequest, db: AsyncSession = Depends(get_db)):
    criteria = [create_criterion(c) for c in req.acceptance_criteria]
    if not criteria and req.description:
        criteria = await extract_criteria(req.title, req.description)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        source="custom",
        source_id=None,
        title=req.title,
        description=req.description,
        status="open",
        body={},
        acceptance_criteria=criteria,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Ticket, ticket_id)


@router.post("/{ticket_id}/implement", response_model=ImplementTicketResponse)
async def implement_ticket(
    ticket_id: str,
    req: ImplementTicketRequest,
    db: AsyncSession = Depends(get_db),
):
    ticket = await get_or_404(db, Ticket, ticket_id)
    if not ticket.workspace_id:
        raise HTTPException(status_code=400, detail="Assign this ticket to a workspace first")
    workspace = await get_or_404(db, Workspace, ticket.workspace_id)
    if not workspace.repo_path:
        raise HTTPException(status_code=400, detail="Workspace has no repo path configured")
    agent_name = req.agent_name or f"agent-{ticket.title[:24]}"
    agent, raw_key = await agent_runner.mint_agent(
        workspace_id=ticket.workspace_id,
        name=agent_name,
        db=db,
    )
    await agent_runner.spawn_agent_run(agent, raw_key, ticket, req.prompt, workspace.repo_path, db)
    return ImplementTicketResponse(agent_id=agent.id, agent_name=agent.name)


@router.patch("/{ticket_id}/workspace", response_model=TicketResponse)
async def assign_ticket_workspace(
    ticket_id: str,
    req: AssignTicketWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    ticket = await get_or_404(db, Ticket, ticket_id)
    if req.workspace_id is not None:
        await get_or_404(db, Workspace, req.workspace_id)
    ticket.workspace_id = req.workspace_id
    await db.commit()
    await db.refresh(ticket)
    return ticket


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
