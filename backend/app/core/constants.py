from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    AWAITING_APPROVAL = "awaiting_approval"


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
