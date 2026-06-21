# Asana Integration

> **Status: not yet implemented.** The Asana adapter is planned but not built. The `source`
> field accepts `"asana"` in the schema, but importing will return a 400 error until the adapter
> ships. Track progress in issue [#TODO].

---

## Planned behavior

When implemented, the Asana integration will let you import tasks from any Asana project into
Treco via the Asana REST API. The adapter will normalize Asana task payloads into Treco's
unified ticket schema (title, description, status, acceptance criteria).

Planned field mapping:

| Treco field | Asana source |
|-------------|--------------|
| `source_id` | `task.gid` |
| `title` | `task.name` |
| `description` | `task.notes` |
| `status` | derived from `task.completed` |
| `body` | Full raw task object |

Planned status map:

| Asana state | Treco status |
|-------------|--------------|
| `completed: false` | `open` |
| `completed: true` | `done` |

---

## Workaround — custom import

Until the adapter ships, you can import Asana tasks using the `"custom"` source and the
`/tickets/create` endpoint:

```bash
curl -s -X POST http://localhost:8001/api/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "your-workspace",
    "title": "Your Asana task title",
    "description": "Task description from Asana",
    "acceptance_criteria": [
      "Criterion one",
      "Criterion two"
    ]
  }'
```

This creates a custom ticket with the criteria you specify. Acceptance criteria will not be
re-extracted via LLM — what you provide is what gets stored.

---

## Contributing

To add Asana support:

1. Create `backend/app/services/adapters/asana.py` implementing `TicketAdapter`.
2. Register `"asana": AsanaAdapter()` in `backend/app/services/adapters/__init__.py`.
3. Add tests in `backend/tests/test_adapters.py` (happy path, missing fields, status mapping).
4. Optionally add `/tickets/fetch/asana` and `/tickets/fetch/bulk` support.

See [jira.py](../../backend/app/services/adapters/jira.py) as the reference implementation.
The Asana REST API reference: [developers.asana.com/reference/gettask](https://developers.asana.com/reference/gettask).
