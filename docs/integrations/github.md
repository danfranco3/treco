# GitHub Issues Integration

Import GitHub issues into Treco by URL, by repo + issue number, or in bulk. Public repos work
without authentication. Private repos require a personal access token.

---

## Prerequisites

- A GitHub repository with issues enabled
- For private repos: a GitHub PAT with `repo` scope
  (Settings → Developer settings → Personal access tokens)
- Treco running locally or self-hosted (see [self-hosting.md](../self-hosting.md))

---

## Import by URL (quickest)

Paste a GitHub issue URL and Treco fetches it automatically:

```bash
curl -s -X POST http://localhost:8001/api/tickets/fetch/url \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "url": "https://github.com/owner/repo/issues/42"
  }'
```

Only public issue URLs are supported via this endpoint. For private repos use the
repo + issue number endpoint below.

---

## Import by repo + issue number

```bash
curl -s -X POST http://localhost:8001/api/tickets/fetch/github \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "repo": "owner/repo",
    "issue_number": 42,
    "token": "ghp_..."
  }'
```

`token` is optional for public repos. For private repos it must have `repo` read scope.

---

## Bulk import

Import open issues from a repo (up to the specified limit):

```bash
curl -s -X POST http://localhost:8001/api/tickets/fetch/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "source": "github",
    "token": "ghp_...",
    "repo": "owner/repo",
    "limit": 20
  }'
```

`limit` defaults to 20. Treco fetches open issues only, ordered by GitHub's default (most
recently updated first).

---

## Field mapping

| Treco field | GitHub source |
|-------------|---------------|
| `source_id` | `issue.number` (as string) |
| `title` | `issue.title` |
| `description` | `issue.body` (Markdown) |
| `status` | `issue.state` — see status map below |
| `body` | Full raw issue object from GitHub API v3 |

### Status map

| GitHub state | Treco status |
|--------------|--------------|
| `open` | `open` |
| `closed` | `done` |

---

## Manual import (raw payload)

If you already have the GitHub API response, POST it directly:

```bash
curl -s -X POST http://localhost:8001/api/tickets/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "github",
    "workspace_id": "your-workspace",
    "raw": {
      "number": 42,
      "title": "Fix login redirect loop",
      "body": "After OAuth callback, users are redirected back to /login.",
      "state": "open"
    }
  }'
```

The `raw` object must contain `number`, `title`, and `state` at minimum.

---

## Scripting with the SDK

```python
import asyncio
from treco import TrecoClient

async def sync_github_issues(workspace_id: str, repo: str, treco_api_key: str, github_token: str):
    async with TrecoClient(api_key=treco_api_key) as treco:
        tickets = await treco.bulk_import(
            source="github",
            workspace_id=workspace_id,
            token=github_token,
            repo=repo,
            limit=20,
        )
    print(f"Imported {len(tickets)} tickets from {repo}")

asyncio.run(sync_github_issues("your-workspace", "owner/repo", "treco_...", "ghp_..."))
```

---

## Re-importing

Tickets are upserted on `source` + `source_id` (the issue number). Calling fetch again updates
title, body, and state. Acceptance criteria are not re-extracted after the first import.

---

## Security note

Store GitHub tokens in `~/.treco/config.json` (chmod 600) or as `GITHUB_TOKEN` in your
environment. Never commit tokens to source control. For read-only syncing, generate a
fine-grained PAT scoped to specific repos with Issues: Read permission.

---

## Troubleshooting

**404 Issue not found** — verify `repo` is `owner/repo` format and the issue number exists.
For private repos, confirm the token has `repo` read access.

**URL not supported** — `/fetch/url` only accepts `https://github.com/owner/repo/issues/N`
format. Pull request URLs and other GitHub URLs are not supported.

**Empty bulk import** — the endpoint fetches open issues only. If all issues are closed, the
response will be an empty list.

**Rate limiting** — unauthenticated GitHub API requests are limited to 60/hour per IP.
Authenticated requests are 5,000/hour. Use a token for any bulk syncing.
