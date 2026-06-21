# Security

Treco uses two separate authentication paths and a workspace-scoped data model. This document covers how they work, what is stored and where, and the threat model for both self-hosted and local deployments.

---

## Authentication model

Treco has two credential types that serve different principals.

### Human users — JWT via GitHub OAuth

Dashboard users authenticate through GitHub OAuth. The flow:

1. `GET /api/auth/github` redirects to `github.com/login/oauth/authorize` with `scope: read:user`.
2. GitHub redirects back to `GET /api/auth/github/callback?code=…`.
3. The backend exchanges the code for a GitHub access token (server-to-server, never exposed to the browser), fetches the user profile, and upserts a `User` row keyed on `github_id`.
4. A signed JWT (`HS256`) is issued and appended to a redirect to the frontend (`/auth/callback?token=…`).
5. The frontend stores the JWT and attaches it as `Authorization: Bearer <token>` on subsequent API calls.

JWT properties:

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Signing secret | `JWT_SECRET` env var (required) |
| Expiry | 7 days (`jwt_expire_minutes = 10080`) |
| Payload | `{ sub: user_id, exp: <unix> }` |

Tokens are validated by `decode_jwt()` in `backend/app/services/auth.py`. Any `JWTError` or missing `sub` returns HTTP 401. A `/api/auth/refresh` endpoint issues a new token from a valid existing one without requiring re-authorization through GitHub.

The GitHub access token is used only during the callback to fetch the user profile. It is never stored.

### Agents — SDK API keys

Autonomous agents authenticate using `X-Agent-Key` header on every request to `/api/events`. The key is issued once at agent creation and never retrievable again.

Key lifecycle:

1. `POST /api/agents` calls `generate_api_key()`, which produces `treco_<32-byte urlsafe token>` via `secrets.token_urlsafe`.
2. SHA-256 of the raw key is stored in `Agent.api_key_hash`. The raw key is returned once in the response.
3. On each request, `resolve_agent()` hashes the incoming key and queries `Agent.api_key_hash`. No timing-safe comparison is needed because the lookup is by hash equality in the DB index, not a direct string compare — but the hash eliminates direct key exposure if the database is compromised.
4. If the hash matches no agent, HTTP 401 is returned with no additional detail.

The raw key is never logged, never included in error responses, and never queryable from the API.

---

## Key and secret storage

### Server-side

| Secret | Where stored | Form |
|--------|-------------|------|
| `JWT_SECRET` | `backend/.env` (local) or environment | Plaintext — never committed |
| Agent API key | `agents.api_key_hash` column | SHA-256 hex digest |
| GitHub OAuth secret | `backend/.env` or environment | Plaintext — never committed |
| LLM API keys | `backend/.env` or environment | Plaintext — never committed |
| GitHub OAuth access token | Not stored | Used in-flight during callback only |

### CLI / SDK client-side

The `treco` CLI writes `~/.treco/config.json` with `chmod 600` on every save. This file contains:

```json
{
  "api_key": "treco_…",
  "base_url": "http://localhost:8001",
  "workspace_id": "…"
}
```

The SDK reads credentials from `~/.treco/config.json` or the `TRECO_API_KEY` / `TRECO_URL` environment variables. The API key is never logged by the SDK.

---

## Workspace isolation

Every multi-tenant boundary in Treco is enforced through `workspace_id`. The invariants:

- `Ticket`, `Agent`, and `AgentEvent` rows all carry a `workspace_id` column with a database index.
- Every query that lists or reads these resources includes `.where(<Model>.workspace_id == workspace_id)`. There are no "list all" queries that cross workspace boundaries.
- `workspace_id` is validated as a non-empty string at the Pydantic request boundary before it reaches the database layer.
- The event stream (`GET /api/events/stream?workspace_id=…`) filters by `workspace_id` before bootstrapping and on every polling tick.

Cross-tenant data leakage is treated as a critical bug. If you add a new route that accesses any of these three tables, the query must filter on `workspace_id`.

---

## Input validation

All HTTP request bodies go through Pydantic models. There is no raw `dict` parsing from `request.body()`.

| Field | Constraint |
|-------|-----------|
| `workspace_id` | Non-empty string, validated in every Pydantic model that accepts it |
| `source` | `Literal["jira", "linear", "asana", "github", "custom"]` — unknowns rejected at parse time |
| `event_type` | `Literal[…]` union in `EventRequest` — unknowns rejected at parse time |
| `team_key` (Linear import) | Regex `[A-Z0-9_-]{1,20}` — validated by `field_validator` |

All database queries use SQLAlchemy ORM or parameterized `select()`. String-interpolated SQL is not permitted.

Ticket `body` and event `payload` are stored as JSONB (Postgres) or JSON (SQLite). They are user-controlled data and must be sanitized before rendering in the frontend to prevent XSS via ticket content.

---

## Known risks and mitigations

### GraphQL query construction — Linear adapter

**Status: remediated.** An earlier version of `LinearAdapter.fetch_issues()` interpolated `team_key` directly into a GraphQL query string. This was replaced with GraphQL variables (`{"teamKey": team_key}`) in commit `07530e0`. The `team_key` field also has a strict allowlist regex validator (`[A-Z0-9_-]{1,20}`) as defense in depth.

Any future work that constructs GraphQL queries must use variables, not string formatting.

### JWT in redirect URL

After GitHub OAuth, the JWT is appended to the frontend redirect URL as a query parameter (`/auth/callback?token=…`). The frontend must immediately move this token out of the URL (into memory or a secure cookie) and not persist it in `localStorage` or `sessionStorage`, which are accessible to any script on the page.

### Agent key exposure window

The raw agent API key is returned exactly once in the `POST /api/agents` response. If this response is lost (network error, terminal clear), the key cannot be recovered and a new agent must be created. Store it immediately in `~/.treco/config.json` or the equivalent.

### Workspace ID is not a secret

`workspace_id` is a non-secret identifier included in API requests. It enforces data isolation but is not an authentication credential. An agent authenticated with a valid API key can read any workspace's public data if it knows the `workspace_id`. In self-hosted deployments, workspace IDs should be treated as internal identifiers rather than shared externally.

---

## Threat model

### What Treco protects

- **Agent impersonation**: SDK keys are hashed at rest. A database dump does not yield working keys.
- **Cross-tenant reads**: `workspace_id` filtering on every query prevents one workspace from reading another's tickets, agents, or events.
- **JWT forgery**: Tokens are signed with `JWT_SECRET`. Without the secret, tokens cannot be forged or extended.
- **Injection via ticket source adapters**: All adapter queries use GraphQL variables or parameterized ORM queries. No user-controlled input reaches a query as a string fragment.

### What Treco does not protect (by design)

- **Unauthenticated dashboard access**: Most read endpoints (ticket lists, event streams, agent lists) accept `workspace_id` as a query parameter with no additional authentication. Treco is designed for internal / self-hosted use. If you expose it publicly, add network-level access control (VPN, firewall, reverse proxy auth).
- **Agent-to-agent isolation**: All agents in a workspace share the same `workspace_id` scope. One agent can read tickets and events belonging to another agent in the same workspace.
- **Rate limiting**: There is no built-in rate limiting on the event ingestion endpoint. A misconfigured agent could flood the database. Add rate limiting at the reverse proxy layer in production.
- **Audit log**: Agent events are append-only but there is no tamper-evident audit trail. Events can be read but the system does not detect if they were modified at the database level.

---

## Self-hosting hardening checklist

- [ ] Set `JWT_SECRET` to at least 32 random bytes (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` from a GitHub OAuth App registered to your domain
- [ ] Set `CORS_ORIGINS` to your frontend's exact origin — do not use `*`
- [ ] Use PostgreSQL in production (`DATABASE_URL` + `DATABASE_MODE=postgres`) — SQLite is not suitable for concurrent write workloads
- [ ] Put the backend behind a reverse proxy (nginx, Caddy) with TLS termination — do not expose port 8001 directly
- [ ] Restrict access to the Treco API to trusted networks if possible (VPN, firewall rule)
- [ ] Rotate agent API keys periodically — delete and recreate agents to issue new keys
- [ ] Never commit `backend/.env` — it is gitignored, keep it that way
