# Jira Integration

Import Jira issues into Treco so agents can report progress against them.

---

## How it works

Treco does not connect to Jira directly. You fetch the raw issue payload from the Jira REST API
and POST it to Treco's `/tickets/import` endpoint. Treco normalizes the payload using the
`JiraAdapter` — extracting title, description, and status — then runs LLM-based criteria
extraction and stores the ticket.

This keeps Treco stateless with respect to Jira auth. Your agent or CI pipeline owns the
credential and decides when to sync.

---

## Prerequisites

- Jira Cloud or Jira Server (REST API v3)
- An API token: [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
- Treco running locally or self-hosted (see [self-hosting.md](../self-hosting.md))

---

## Step 1 — Fetch the issue from Jira

```bash
curl -u your@email.com:YOUR_API_TOKEN \
  "https://your-domain.atlassian.net/rest/api/3/issue/PROJ-42" \
  | jq . > issue.json
```

The full response JSON is what you pass to Treco — do not strip fields. Treco preserves the
raw payload in `body` and derives normalized fields from it.

---

## Step 2 — Import into Treco

```bash
curl -s -X POST http://localhost:8001/api/tickets/import \
  -H "Content-Type: application/json" \
  -d "{
    \"source\": \"jira\",
    \"workspace_id\": \"your-workspace\",
    \"raw\": $(cat issue.json)
  }"
```

Response includes the Treco ticket ID, normalized title, description, status, and extracted
acceptance criteria.

---

## Field mapping

| Treco field | Jira source |
|-------------|-------------|
| `source_id` | `issue.key` (e.g. `PROJ-42`) |
| `title` | `fields.summary` |
| `description` | `fields.description` — ADF converted to plain text |
| `status` | `fields.status.name` — see status map below |
| `body` | Full raw JSON, preserved as-is |

### Status map

| Jira status name | Treco status |
|------------------|--------------|
| `To Do` | `open` |
| `In Progress` | `in_progress` |
| `Done` | `done` |
| `Closed` | `done` |
| anything else | `open` |

---

## Description format (ADF)

Jira Cloud returns descriptions in [Atlassian Document Format](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/).
Treco's adapter recursively extracts plain text from the ADF tree. Jira Server may return plain
text strings — both formats are handled.

---

## Scripting with the SDK

```python
import asyncio
import httpx
from treco import TrecoClient

JIRA_URL = "https://your-domain.atlassian.net"
JIRA_AUTH = ("your@email.com", "YOUR_API_TOKEN")

async def sync_issue(issue_key: str, workspace_id: str, treco_api_key: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{JIRA_URL}/rest/api/3/issue/{issue_key}",
            auth=JIRA_AUTH,
        )
        r.raise_for_status()
        raw = r.json()

    async with TrecoClient(api_key=treco_api_key) as treco:
        await treco.import_ticket(
            source="jira",
            workspace_id=workspace_id,
            raw=raw,
        )

asyncio.run(sync_issue("PROJ-42", "your-workspace", "treco_..."))
```

---

## Re-importing

Calling `/tickets/import` with the same `source` + `source_id` upserts the ticket: title,
description, and status are updated, but acceptance criteria are **not** re-extracted (criteria
are derived only on first import). This is intentional — criteria extraction is an LLM call and
you likely curated criteria after initial import.

---

## Troubleshooting

**400 Unsupported source** — the `source` field must be exactly `"jira"`.

**Missing title** — check that `fields.summary` is present in the raw payload.

**Description is empty** — Jira may omit `fields.description` for issues with no description.
Treco treats `null` as an empty description; criteria extraction falls back to the title only.

**Status shows `open` unexpectedly** — custom Jira workflow states not in the status map default
to `open`. This is expected; Treco does not know your workflow configuration.
