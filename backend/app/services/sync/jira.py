"""Jira REST sync. config: {"base_url", "email"?, "status_map"?: {treco_status: transition_id}}.

Basic auth (email + API token) when email is set, else Bearer (PAT).
Always posts a comment; additionally fires a workflow transition when
status_map has an entry for the new status.
"""
from typing import Any

import httpx


def _auth_kwargs(config: dict[str, Any], token: str) -> dict[str, Any]:
    email = config.get("email")
    if email:
        return {"auth": (email, token)}
    return {"headers": {"Authorization": f"Bearer {token}"}}


async def push_status(
    config: dict[str, Any],
    token: str,
    issue_key: str,
    status: str,
    pr_url: str | None,
) -> None:
    base_url = str(config["base_url"]).rstrip("/")
    kwargs = _auth_kwargs(config, token)
    comment = f"Treco: ticket moved to {status}"
    if pr_url:
        comment += f" — PR: {pr_url}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{base_url}/rest/api/2/issue/{issue_key}/comment",
            json={"body": comment},
            **kwargs,
        )
        resp.raise_for_status()

        transition_id = (config.get("status_map") or {}).get(status)
        if transition_id:
            resp = await client.post(
                f"{base_url}/rest/api/2/issue/{issue_key}/transitions",
                json={"transition": {"id": str(transition_id)}},
                **kwargs,
            )
            resp.raise_for_status()
