# Linear Integration

Import Linear issues into Treco individually or in bulk. Treco fetches from the Linear GraphQL
API directly — you provide an API key and Treco does the rest.

---

## Prerequisites

- A Linear API key: Settings → API → Personal API keys
- Treco running locally or self-hosted (see [self-hosting.md](../self-hosting.md))

---

## Fetch a single issue

```bash
curl -s -X POST http://localhost:8001/api/tickets/fetch/linear \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "issue_id": "TEAM-42",
    "api_key": "lin_api_..."
  }'
```

`issue_id` is the Linear issue identifier (e.g. `ENG-12`). The response is a Treco ticket with
normalized fields and extracted acceptance criteria.

---

## Bulk import by team

Import up to 50 open issues from a Linear team at once:

```bash
curl -s -X POST http://localhost:8001/api/tickets/fetch/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "source": "linear",
    "token": "lin_api_...",
    "team_key": "ENG",
    "limit": 20
  }'
```

`team_key` is the short uppercase key shown in your Linear team settings (e.g. `ENG`, `MOBILE`).
Must match `[A-Z0-9_-]{1,20}`. If omitted, Treco imports from all teams (first 50 issues).

`limit` defaults to 20, max 50.

---

## Field mapping

| Treco field | Linear source |
|-------------|---------------|
| `source_id` | `issue.identifier` (e.g. `ENG-12`) |
| `title` | `issue.title` |
| `description` | `issue.description` (Markdown) |
| `status` | `issue.state.name` — see status map below |
| `body` | Full raw issue object |

### Status map

| Linear state name | Treco status |
|-------------------|--------------|
| `Backlog` | `open` |
| `Todo` | `open` |
| `In Progress` | `in_progress` |
| `Done` | `done` |
| `Cancelled` | `done` |
| anything else | `open` |

---

## Manual import (raw payload)

If you already have the Linear issue payload, POST it directly:

```bash
curl -s -X POST http://localhost:8001/api/tickets/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "linear",
    "workspace_id": "your-workspace",
    "raw": {
      "identifier": "ENG-42",
      "title": "Add dark mode",
      "description": "Users want a dark theme...",
      "state": { "name": "In Progress" }
    }
  }'
```

The `raw` object must contain at minimum `identifier`, `title`, and `state.name`.

---

## Scripting with the SDK

```python
import asyncio
from treco import TrecoClient

async def sync_linear_team(workspace_id: str, team_key: str, treco_api_key: str, linear_token: str):
    async with TrecoClient(api_key=treco_api_key) as treco:
        tickets = await treco.bulk_import(
            source="linear",
            workspace_id=workspace_id,
            token=linear_token,
            team_key=team_key,
            limit=20,
        )
    print(f"Imported {len(tickets)} tickets")

asyncio.run(sync_linear_team("your-workspace", "ENG", "treco_...", "lin_api_..."))
```

---

## Re-importing

Tickets are upserted on `source` + `source_id`. Calling fetch again updates title, description,
and status. Acceptance criteria are not re-extracted — only derived on first import.

---

## Security note

Linear API keys have broad read access to your workspace. Store them in `~/.treco/config.json`
(chmod 600) or as an environment variable. Never commit them to source control.

---

## Troubleshooting

**404 Issue not found** — `issue_id` must be the Linear identifier (e.g. `ENG-42`), not the
internal UUID.

**team_key validation error** — must be uppercase alphanumeric, 1–20 characters. Check your
team's key in Linear → Settings → Team.

**Empty bulk import** — if no issues are returned, verify the team has open issues and the API
key has access to that team's workspace.
