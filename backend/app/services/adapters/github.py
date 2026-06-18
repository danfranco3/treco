from typing import Any

import httpx
from fastapi import HTTPException

from app.services.adapters.base import NormalizedTicket, TicketAdapter


class GitHubIssueAdapter(TicketAdapter):
    def normalize(self, raw: dict[str, Any]) -> NormalizedTicket:
        return NormalizedTicket(
            source="github",
            source_id=str(raw["number"]),
            title=raw.get("title", ""),
            description=raw.get("body"),
            status=self.extract_status(raw),
            body=raw,
        )

    def extract_status(self, raw: dict[str, Any]) -> str:
        return "done" if raw.get("state") == "closed" else "open"

    async def fetch_issue(self, repo: str, issue_number: int, token: str) -> NormalizedTicket:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="Issue not found")
            r.raise_for_status()
        return self.normalize(r.json())

    async def fetch_issues(self, repo: str, token: str, limit: int = 20) -> list[NormalizedTicket]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/issues",
                params={"state": "open", "per_page": limit},
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            r.raise_for_status()
        return [self.normalize(raw) for raw in r.json()]
