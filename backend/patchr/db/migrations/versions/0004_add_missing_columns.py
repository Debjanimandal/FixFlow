"""Add missing columns that exist in ORM models but not in DB.

- repositories.is_active (may already exist from init_db)
- incidents.retry_count
- users.vercel_access_token

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in the table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # repositories.is_active
    if not _column_exists("repositories", "is_active"):
        op.add_column(
            "repositories",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # incidents.retry_count
    if not _column_exists("incidents", "retry_count"):
        op.add_column(
            "incidents",
            sa.Column("retry_count", sa.BigInteger(), nullable=False, server_default="0"),
        )

    # users.vercel_access_token
    if not _column_exists("users", "vercel_access_token"):
        op.add_column(
            "users",
            sa.Column("vercel_access_token", sa.String(1024), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("users", "vercel_access_token"):
        op.drop_column("users", "vercel_access_token")
    if _column_exists("incidents", "retry_count"):
        op.drop_column("incidents", "retry_count")
    if _column_exists("repositories", "is_active"):
        op.drop_column("repositories", "is_active")
