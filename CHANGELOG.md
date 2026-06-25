# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-22

### Engineering

#### Added
- Initial FastAPI scaffold with SQLAlchemy async, PostgreSQL/SQLite dual support via `AnyJSON` type alias
- Ticket workflow: create, import, connect agent context, inject per-ticket context
- Full event stream: append-only `agent_events` table with cost aggregation at read time via `func.sum()`
- GitHub OAuth2 login flow with auth guard, user avatar, and session persistence
- `UserWorkspace` membership table; all workspace-scoped routes enforce membership
- Rate limiting: 100 req/min per IP, 1000 req/min per API key via middleware
- Request ID middleware and structured JSON logging
- JWT secret minimum-length check on startup
- `GET /health` endpoint with db ping and version fields (required for Render health checks)
- Settings page: workspace rename, delete, quick-start snippet

#### Changed
- Removed all JWT/user auth from OSS build — agent routes use `X-Agent-Key` only
- Extracted shared route helpers, deduplicated validators, split health monitor into its own module

#### Fixed
- Criteria extractor crash on malformed LLM response (falls back to `_parse_checkboxes`)
- Criterion mutation bug — acceptance criteria are now derived-only, never hand-set
- Broken API connections between frontend and backend
- Trailing slash routing inconsistency across all route modules
- `seed_demo.py` JWT auth so the script works against a live server

### Security

#### Added
- SHA-256 hashing for all agent API keys — raw key returned once on creation, never stored or logged
- Workspace isolation enforced on every DB query; cross-tenant leakage treated as critical bug

#### Fixed
- Eliminated f-string GraphQL query construction in `LinearAdapter` — replaced with parameterized variables (was a known injection risk at `tickets.py:226`)

### Performance

#### Added
- Cost aggregation uses `func.sum()` in SQL — never persisted as a derived field
- Agent marked offline after 5-minute heartbeat silence (event-driven, no polling table scan)

### SDK / CLI

#### Added
- `TrecoClient` async Python client (`backend/sdk/python/treco/client.py`) — published to PyPI as `treco`
- Full CLI: `init`, `new`, `start`, `check`, `done`, `inject`, `server`, `hook` subcommands
- Daemon server management (`server.py`)
- Claude Code hook integration for automatic agent reporting
- Demo seeder (`scripts/seed_demo.py`) for local development

### Frontend

#### Added
- Mission control dashboard with agent kanban and ticket detail views
- Landing page with outcome-led hero copy and CSS `fadeUp` animation (no Framer dependency)
- Full UI design system: paper/green theme, Lucide icons, design tokens
- Empty states on all list views — agents, tickets, ticket not found
- Improved error states for agent offline and ticket not found
- WCAG 2.1 AA accessibility audit pass on all dashboard components

#### Fixed
- SSR hydration warning and empty pagination label
- Color token references and text/background contrast ratios
- Landing page animation replaced Framer `whileInView` with pure CSS to remove runtime dependency

### Docs

#### Added
- `docs/quickstart.md` — zero to first agent reporting, end-to-end verified
- `docs/concepts.md` — workspaces, tickets, agents, events, acceptance criteria
- `docs/sdk-reference.md` — `TrecoClient` API with typed examples for all methods
- `docs/integrations/` — setup guides for Jira, Linear, GitHub, and Asana
- `docs/security.md` — auth model, key storage, workspace isolation, threat model
- `docs/contributing.md` — dev setup, test standards, PR process
- `docs/architecture.md` — system diagram, data model, design decisions
- `docs/deployment.md` — deployment guide for Railway, Render, Fly.io, and bare VPS
- `docs/faq.md` — agents, data storage, Postgres, cost tracking, criteria extraction
- `docs/cli-reference.md` and `docs/self-hosting.md` (in progress)

#### Fixed
- Stale config key, wrong port, and misleading `init` comment in quickstart
- Quickstart rewritten to work end-to-end without external dependencies

### Tests

#### Added
- Backend integration test suite (`backend/tests/`) with pytest + pytest-asyncio
- SDK tests (`backend/sdk/python/tests/`) with pytest + respx HTTP mocking
- GitHub adapter tests covering `fetch_issue` and `fetch_issues` async paths
- OAuth tests: happy path, 401 rejection, token expiry

### DevOps / CI

#### Added
- GitHub Actions CI workflow: lint, type-check, test on every push
- Docker Compose one-command startup (`docker compose up`)
- Python minimum version lowered to 3.11 (was pinned too high)

#### Fixed
- Docker Compose startup failures — service ordering and health check timing

[0.1.0]: https://github.com/your-org/treco/releases/tag/v0.1.0
