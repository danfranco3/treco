"""workspaces

Revision ID: a1c3e9f02b7d
Revises: 2d54e54c9557
Create Date: 2026-06-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e9f02b7d"
down_revision: Union[str, Sequence[str], None] = "2d54e54c9557"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = inspector.get_table_names()
    if "workspaces" not in existing_tables:
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("repo_path", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    agent_cols = {c["name"] for c in inspector.get_columns("agents")}
    if "repo_path" in agent_cols:
        with op.batch_alter_table("agents") as batch_op:
            batch_op.drop_column("repo_path")

    # SQLite batch mode rebuilds the table, making workspace_id nullable
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.alter_column("workspace_id", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.alter_column("workspace_id", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(sa.Column("repo_path", sa.String(), nullable=True))
    op.drop_table("workspaces")
