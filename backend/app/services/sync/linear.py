"""Linear GraphQL sync. config: {"status_map"?: {treco_status: linear_state_id}}.

Resolves the issue UUID from its identifier (e.g. ENG-123), posts a comment,
and moves the issue when status_map has a state id for the new status.
"""
from typing import Any

import httpx

LINEAR_API = "https://api.linear.app/graphql"


async def _gql(client: httpx.AsyncClient, token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    resp = await client.post(
        LINEAR_API,
        json={"query": query, "variables": variables},
        headers={"Authorization": token},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"])[:300])
    return data["data"]


async def push_status(
    config: dict[str, Any],
    token: str,
    issue_key: str,
    status: str,
    pr_url: str | None,
) -> None:
    comment = f"Treco: ticket moved to {status}"
    if pr_url:
        comment += f" — PR: {pr_url}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        data = await _gql(
            client, token,
            "query($id: String!) { issue(id: $id) { id } }",
            {"id": issue_key},
        )
        issue_id = data["issue"]["id"]

        await _gql(
            client, token,
            "mutation($input: CommentCreateInput!) { commentCreate(input: $input) { success } }",
            {"input": {"issueId": issue_id, "body": comment}},
        )

        state_id = (config.get("status_map") or {}).get(status)
        if state_id:
            await _gql(
                client, token,
                "mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success } }",
                {"id": issue_id, "input": {"stateId": state_id}},
            )
