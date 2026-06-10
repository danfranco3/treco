from typing import Any

from app.services.adapters.base import NormalizedTicket, TicketAdapter

_STATUS_MAP = {
    "To Do": "open",
    "In Progress": "in_progress",
    "Done": "done",
    "Closed": "done",
}


class JiraAdapter(TicketAdapter):
    def normalize(self, raw: dict[str, Any]) -> NormalizedTicket:
        fields = raw.get("fields", {})
        description = fields.get("description")
        if isinstance(description, dict):
            # Jira Atlassian Document Format — extract plain text
            description = _extract_adf_text(description)

        return NormalizedTicket(
            source="jira",
            source_id=raw["key"],
            title=fields.get("summary", ""),
            description=description,
            status=self.extract_status(raw),
            body=raw,
        )

    def extract_status(self, raw: dict[str, Any]) -> str:
        status_name = raw.get("fields", {}).get("status", {}).get("name", "")
        return _STATUS_MAP.get(status_name, "open")


def _extract_adf_text(node: dict[str, Any]) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if node.get("type") == "text":
        return node.get("text", "")
    children = node.get("content", [])
    return "".join(_extract_adf_text(child) for child in children).strip()
