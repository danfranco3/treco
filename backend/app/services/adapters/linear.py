from typing import Any

import httpx
from fastapi import HTTPException

from app.services.adapters.base import NormalizedTicket, TicketAdapter

_STATUS_MAP = {
    "Todo": "open",
    "In Progress": "in_progress",
    "Done": "done",
    "Cancelled": "done",
    "Backlog": "open",
}

_QUERY_ISSUE = """
    query($id: String!) {
        issue(id: $id) {
            identifier
            title
            description
            state { name }
        }
    }
"""

_QUERY_ISSUES_BY_TEAM = """
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

_QUERY_ALL_ISSUES = """
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


class LinearAdapter(TicketAdapter):
    def normalize(self, raw: dict[str, Any]) -> NormalizedTicket:
        return NormalizedTicket(
            source="linear",
            source_id=raw["identifier"],
            title=raw.get("title", ""),
            description=raw.get("description"),
            status=self.extract_status(raw),
            body=raw,
        )

    def extract_status(self, raw: dict[str, Any]) -> str:
        state_name = raw.get("state", {}).get("name", "")
        return _STATUS_MAP.get(state_name, "open")

    async def fetch_issue(self, issue_id: str, api_key: str) -> NormalizedTicket:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.linear.app/graphql",
                json={"query": _QUERY_ISSUE, "variables": {"id": issue_id}},
                headers={"Authorization": api_key, "Content-Type": "application/json"},
            )
            r.raise_for_status()
        issue = (r.json().get("data") or {}).get("issue")
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        return self.normalize(issue)

    async def fetch_issues(self, team_key: str | None, token: str, limit: int = 20) -> list[NormalizedTicket]:
        if team_key:
            query = _QUERY_ISSUES_BY_TEAM
            variables: dict[str, Any] = {"teamKey": team_key}
        else:
            query = _QUERY_ALL_ISSUES
            variables = {}

        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.linear.app/graphql",
                json={"query": query, "variables": variables},
                headers={"Authorization": token, "Content-Type": "application/json"},
            )
            r.raise_for_status()

        nodes = ((r.json().get("data") or {}).get("issues") or {}).get("nodes", [])
        return [self.normalize(n) for n in nodes[:limit]]
