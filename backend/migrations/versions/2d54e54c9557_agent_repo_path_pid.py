"""agent_repo_path_pid

Revision ID: 2d54e54c9557
Revises: 933bfa2574e2
Create Date: 2026-06-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2d54e54c9557"
down_revision: Union[str, Sequence[str], None] = "933bfa2574e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("repo_path", sa.String(), nullable=True))
    op.add_column("agents", sa.Column("pid", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "pid")
    op.drop_column("agents", "repo_path")
