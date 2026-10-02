"""
Migration 0002: Add pr_state and pr_merged_at to patches table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0002"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add PR lifecycle tracking columns to patches table
    op.add_column(
        "patches",
        sa.Column("pr_state", sa.String(50), nullable=True),
    )
    op.add_column(
        "patches",
        sa.Column("pr_merged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patches", "pr_merged_at")
    op.drop_column("patches", "pr_state")
