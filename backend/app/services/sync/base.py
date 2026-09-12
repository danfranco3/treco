"""Tracker sync core — pushes Treco ticket state out to Jira/Linear.

Runs as fire-and-forget asyncio tasks triggered by ticket status transitions
and pr_opened events. Tokens live in a chmod-600 local file keyed by the
Integration row's opaque credential_ref — never in the database.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.integration import Integration
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path.home() / ".treco" / "credentials.json"


def _read_credentials() -> dict[str, str]:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(CREDENTIALS_FILE.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read credential store: %s", e)
        return {}


def load_credential(credential_ref: str) -> str | None:
    return _read_credentials().get(credential_ref)


def save_credential(token: str, provider: str) -> str:
    """Store a token, return the opaque ref to persist in the Integration row."""
    credential_ref = f"{provider}-{uuid.uuid4().hex[:12]}"
    creds = _read_credentials()
    creds[credential_ref] = token
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    CREDENTIALS_FILE.chmod(0o600)
    return credential_ref


def delete_credential(credential_ref: str) -> None:
    creds = _read_credentials()
    if credential_ref in creds:
        del creds[credential_ref]
        CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
        CREDENTIALS_FILE.chmod(0o600)


async def sync_ticket_to_tracker(ticket_id: str, status: str, pr_url: str | None = None) -> None:
    """Push a status transition (and optional PR link) to the linked tracker.

    No-op for tickets without an external_ref or workspaces without an
    enabled integration for that provider. Sync outcome is written back to
    ticket.external_ref.sync_status — errors are recorded, never raised.
    """
    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket_id)
        if not ticket or not ticket.external_ref or not ticket.workspace_id:
            return
        provider = ticket.external_ref.get("provider")
        issue_key = ticket.external_ref.get("issue_key")
        if not provider or not issue_key:
            return

        result = await db.execute(
            select(Integration).where(
                Integration.workspace_id == ticket.workspace_id,
                Integration.provider == provider,
                Integration.enabled,
            )
        )
        integration = result.scalars().first()
        if not integration:
            return

        token = load_credential(integration.credential_ref)
        sync_error: str | None = None
        if not token:
            sync_error = "credential missing from local store"
        else:
            try:
                if provider == "jira":
                    from app.services.sync.jira import push_status
                else:
                    from app.services.sync.linear import push_status
                await push_status(integration.config, token, issue_key, status, pr_url)
            except Exception as e:
                sync_error = str(e)[:300]
                logger.warning("Tracker sync failed for ticket %s: %s", ticket_id, sync_error)

        now = datetime.utcnow()
        ticket.external_ref = {
            **ticket.external_ref,
            "last_synced_at": now.isoformat(),
            "sync_status": "error" if sync_error else "ok",
            "sync_error": sync_error,
        }
        integration.last_sync_at = now
        integration.last_sync_status = "error" if sync_error else "ok"
        db.add(ticket)
        db.add(integration)
        await db.commit()
