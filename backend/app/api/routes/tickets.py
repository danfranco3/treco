import re
import uuid
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ticket import Ticket
from app.services.adapters import ADAPTERS
from app.services.criteria_extractor import extract_criteria

router = APIRouter()


class ImportTicketRequest(BaseModel):
    source: Literal["jira", "linear", "asana", "github"]
    workspace_id: str
    raw: dict[str, Any]


class CreateTicketRequest(BaseModel):
    workspace_id: str
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

    @field_validator("team_key")
    @classmethod
    def validate_team_key(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"[A-Z0-9_-]{1,20}", v):
            raise ValueError("team_key must be 1–20 uppercase alphanumeric characters")
        return v


class TicketResponse(BaseModel):
    id: str
    source: str
    source_id: str | None
    title: str
    description: str | None
    status: str
    acceptance_criteria: list[dict]
    body: dict

    model_config = ConfigDict(from_attributes=True)


async def _upsert_ticket(
    db: AsyncSession,
    workspace_id: str,
    source: str,
    source_id: str,
    title: str,
    description: str | None,
    status: str,
    body: dict,
) -> Ticket:
    result = await db.execute(
        select(Ticket).where(
            Ticket.workspace_id == workspace_id,
            Ticket.source == source,
            Ticket.source_id == source_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.title = title
        existing.description = description
        existing.status = status
        existing.body = body
        await db.commit()
        await db.refresh(existing)
        return existing

    criteria = await extract_criteria(title, description)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        source=source,
        source_id=source_id,
        title=title,
        description=description,
        status=status,
        body=body,
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
    criteria = await extract_criteria(normalized.title, normalized.description)

    ticket = Ticket(
        id=str(uuid.uuid4()),
        workspace_id=req.workspace_id,
        source=normalized.source,
        source_id=normalized.source_id,
        title=normalized.title,
        description=normalized.description,
        status=normalized.status,
        body=normalized.body,
        acceptance_criteria=criteria,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/fetch/github", response_model=TicketResponse)
async def fetch_github_issue(req: FetchGitHubIssueRequest, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.github.com/repos/{req.repo}/issues/{req.issue_number}",
            headers={
                "Authorization": f"token {req.token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Issue not found")
        r.raise_for_status()

    raw = r.json()
    adapter = ADAPTERS["github"]
    normalized = adapter.normalize(raw)
    return await _upsert_ticket(
        db,
        req.workspace_id,
        normalized.source,
        normalized.source_id,
        normalized.title,
        normalized.description,
        normalized.status,
        normalized.body,
    )


@router.post("/fetch/linear", response_model=TicketResponse)
async def fetch_linear_issue(req: FetchLinearIssueRequest, db: AsyncSession = Depends(get_db)):
    query = """
        query($id: String!) {
            issue(id: $id) {
                identifier
                title
                description
                state { name }
            }
        }
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.linear.app/graphql",
            json={"query": query, "variables": {"id": req.issue_id}},
            headers={"Authorization": req.api_key, "Content-Type": "application/json"},
        )
        r.raise_for_status()

    data = r.json()
    issue = (data.get("data") or {}).get("issue")
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    adapter = ADAPTERS["linear"]
    normalized = adapter.normalize(issue)
    return await _upsert_ticket(
        db,
        req.workspace_id,
        normalized.source,
        normalized.source_id,
        normalized.title,
        normalized.description,
        normalized.status,
        normalized.body,
    )


@router.post("/fetch/bulk", response_model=list[TicketResponse])
async def bulk_import(req: BulkImportRequest, db: AsyncSession = Depends(get_db)):
    if req.source == "github":
        if not req.repo:
            raise HTTPException(status_code=400, detail="repo is required for GitHub bulk import")
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.github.com/repos/{req.repo}/issues",
                params={"state": "open", "per_page": req.limit},
                headers={
                    "Authorization": f"token {req.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            r.raise_for_status()
        raw_issues = r.json()
        adapter = ADAPTERS["github"]
        normalized_list = [adapter.normalize(raw) for raw in raw_issues]

    else:
        if req.team_key:
            query = """
                query($teamKey: String!) {
                    issues(filter: { team: { key: { eq: $teamKey } } }) {
                        nodes {
                            identifier
                            title
                            description
                            state { name }
                        }
                    }
                }
            """
            variables: dict[str, Any] = {"teamKey": req.team_key}
        else:
            query = """
                query {
                    issues(first: 50) {
                        nodes {
                            identifier
                            title
                            description
                            state { name }
                        }
                    }
                }
            """
            variables = {}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.linear.app/graphql",
                json={"query": query, "variables": variables},
                headers={"Authorization": req.token, "Content-Type": "application/json"},
            )
            r.raise_for_status()
        nodes = ((r.json().get("data") or {}).get("issues") or {}).get("nodes", [])
        nodes = nodes[: req.limit]
        adapter = ADAPTERS["linear"]
        normalized_list = [adapter.normalize(n) for n in nodes]

    tickets: list[Ticket] = []
    for norm in normalized_list:
        ticket = await _upsert_ticket(
            db,
            req.workspace_id,
            norm.source,
            norm.source_id,
            norm.title,
            norm.description,
            norm.status,
            norm.body,
        )
        tickets.append(ticket)
    return tickets


@router.post("/", response_model=TicketResponse)
async def create_ticket(req: CreateTicketRequest, db: AsyncSession = Depends(get_db)):
    criteria = [
        {"id": str(uuid.uuid4()), "text": c, "done": False}
        for c in req.acceptance_criteria
    ]
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
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/")
async def list_tickets(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .where(Ticket.workspace_id == workspace_id)
        .order_by(Ticket.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return result.scalars().all()
