from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    AWAITING_APPROVAL = "awaiting_approval"
    OFFLINE = "offline"
    BLOCKED = "blocked"
    CLOUD_OFFLOADED = "cloud_offloaded"


class TicketStatus(str, Enum):
    """backlog -> in_progress -> hitl_review -> blocked -> done.
    blocked and hitl_review can return to in_progress. Legacy rows use 'open',
    treated as backlog; unrecognized values normalize to OPEN."""
    BACKLOG = "backlog"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    HITL_REVIEW = "hitl_review"
    BLOCKED = "blocked"
    DONE = "done"

    @classmethod
    def normalize(cls, value: str) -> "TicketStatus":
        try:
            return cls(value)
        except ValueError:
            return cls.OPEN


class EventType(str, Enum):
    TICKET_STARTED = "ticket_started"
    CRITERION_CHECKED = "criterion_checked"
    CRITERION_FAILED = "criterion_failed"
    PR_OPENED = "pr_opened"
    DONE = "done"
    ERROR = "error"
    LOG = "log"
    HEARTBEAT = "heartbeat"
    DEVIATION = "deviation"
    CRITERION_VERIFIED = "criterion_verified"
    PERMISSION_REQUESTED = "permission_requested"
