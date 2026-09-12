"""traces, tools, telemetry, integrations, ticket/agent lifecycle fields

Revision ID: 7f8a1b3c9d02
Revises: 2d54e54c9557
Create Date: 2026-09-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7f8a1b3c9d02"
down_revision: Union[str, Sequence[str], None] = "a1c3e9f02b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("git_branch", sa.String(), nullable=True))
    op.add_column("tickets", sa.Column("worktree_path", sa.String(), nullable=True))
    op.add_column("tickets", sa.Column("external_ref", sa.JSON(), nullable=True))
    op.create_index("ix_tickets_worktree_path", "tickets", ["worktree_path"])

    op.add_column("agents", sa.Column("worktree_id", sa.String(), nullable=True))
    op.add_column("agents", sa.Column("execution_mode", sa.String(), nullable=False, server_default="local"))
    op.add_column("agents", sa.Column("cloud_session_id", sa.String(), nullable=True))
    op.create_index("ix_agents_worktree_id", "agents", ["worktree_id"])

    op.create_table(
        "traces",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("parent_trace_id", sa.String(), nullable=True),
        sa.Column("event_id", sa.String(), nullable=True),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traces_agent_id", "traces", ["agent_id"])
    op.create_index("ix_traces_ticket_id", "traces", ["ticket_id"])
    op.create_index("ix_traces_parent_trace_id", "traces", ["parent_trace_id"])
    op.create_index("ix_traces_event_id", "traces", ["event_id"])
    op.create_index("ix_traces_step_type", "traces", ["step_type"])
    op.create_index("ix_traces_created_at", "traces", ["created_at"])

    op.create_table(
        "tools",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="local"),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("safety_flag", sa.String(), nullable=False, server_default="unverified"),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("installed_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tools_name", "tools", ["name"])
    op.create_index("ix_tools_workspace_id", "tools", ["workspace_id"])

    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("dims", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telemetry_events_workspace_id", "telemetry_events", ["workspace_id"])
    op.create_index("ix_telemetry_events_ticket_id", "telemetry_events", ["ticket_id"])
    op.create_index("ix_telemetry_events_agent_id", "telemetry_events", ["agent_id"])
    op.create_index("ix_telemetry_events_metric", "telemetry_events", ["metric"])
    op.create_index("ix_telemetry_events_created_at", "telemetry_events", ["created_at"])

    op.create_table(
        "integrations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("credential_ref", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integrations_workspace_id", "integrations", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_integrations_workspace_id", "integrations")
    op.drop_table("integrations")
    op.drop_index("ix_telemetry_events_created_at", "telemetry_events")
    op.drop_index("ix_telemetry_events_metric", "telemetry_events")
    op.drop_index("ix_telemetry_events_agent_id", "telemetry_events")
    op.drop_index("ix_telemetry_events_ticket_id", "telemetry_events")
    op.drop_index("ix_telemetry_events_workspace_id", "telemetry_events")
    op.drop_table("telemetry_events")
    op.drop_index("ix_tools_workspace_id", "tools")
    op.drop_index("ix_tools_name", "tools")
    op.drop_table("tools")
    op.drop_index("ix_traces_created_at", "traces")
    op.drop_index("ix_traces_step_type", "traces")
    op.drop_index("ix_traces_event_id", "traces")
    op.drop_index("ix_traces_parent_trace_id", "traces")
    op.drop_index("ix_traces_ticket_id", "traces")
    op.drop_index("ix_traces_agent_id", "traces")
    op.drop_table("traces")
    op.drop_index("ix_agents_worktree_id", "agents")
    op.drop_column("agents", "cloud_session_id")
    op.drop_column("agents", "execution_mode")
    op.drop_column("agents", "worktree_id")
    op.drop_index("ix_tickets_worktree_path", "tickets")
    op.drop_column("tickets", "external_ref")
    op.drop_column("tickets", "worktree_path")
    op.drop_column("tickets", "git_branch")
