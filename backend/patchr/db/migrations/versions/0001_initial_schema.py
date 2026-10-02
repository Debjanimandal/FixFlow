"""Initial schema — all core PatchR tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Repositories ──────────────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("private", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vercel_project_id", sa.String(255), nullable=True),
        sa.Column("vercel_project_name", sa.String(255), nullable=True),
        sa.Column("metadata_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("github_webhook_id", sa.BigInteger(), nullable=True),
        sa.Column("webhook_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
        sa.UniqueConstraint("github_id"),
    )

    # ── Deployments ──────────────────────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vercel_deployment_id", sa.String(255), nullable=False),
        sa.Column("vercel_url", sa.String(1024), nullable=True),
        sa.Column("vercel_team_id", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("commit_author", sa.String(255), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("build_logs", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vercel_deployment_id"),
    )
    op.create_index("ix_deployments_repository_id", "deployments", ["repository_id"])

    # ── Incidents ─────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "detected", "analyzing", "patch_ready", "verified",
                "needs_review", "resolved", "dismissed",
                name="incidentstatus",
            ),
            nullable=False,
            server_default="detected",
        ),
        sa.Column(
            "severity",
            sa.Enum("critical", "high", "medium", "low", name="incidentseverity"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "source",
            sa.Enum("vercel_deployment", "github_action", "manual", name="incidentsource"),
            nullable=False,
            server_default="vercel_deployment",
        ),
        sa.Column(
            "failure_type",
            sa.Enum(
                "build_error", "import_error", "type_error", "syntax_error",
                "env_variable", "dependency_conflict", "framework_error",
                "runtime_error", "unknown",
                name="failuretype",
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_to_resolve_seconds", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_repository_id", "incidents", ["repository_id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])

    # ── Analyses ──────────────────────────────────────────────────────────
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("failure_type", sa.String(100), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("affected_files", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(50), nullable=True),
        sa.Column("verification_plan", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_response", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=True),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyses_incident_id", "analyses", ["incident_id"])

    # ── Patches ───────────────────────────────────────────────────────────
    op.create_table(
        "patches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("diff", sa.Text(), nullable=True),
        sa.Column("file_changes", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "proposed", "verifying", "verified", "rejected", "applied", "pr_created",
                name="patchstatus",
            ),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("github_pr_number", sa.BigInteger(), nullable=True),
        sa.Column("github_pr_url", sa.String(1024), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patches_incident_id", "patches", ["incident_id"])

    # ── Verification Results ──────────────────────────────────────────────
    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "passed", "failed", "error", name="verificationstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("verification_type", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error_output", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_explanation", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patch_id"], ["patches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verification_results_patch_id", "verification_results", ["patch_id"])

    # ── Audit Logs ────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "incident_created", "analysis_started", "analysis_completed",
                "patch_generated", "patch_approved", "patch_rejected",
                "verification_started", "verification_completed",
                "pr_created", "incident_resolved", "incident_dismissed",
                name="auditaction",
            ),
            nullable=False,
        ),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_incident_id", "audit_logs", ["incident_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("verification_results")
    op.drop_table("patches")
    op.drop_table("analyses")
    op.drop_table("incidents")
    op.drop_table("deployments")
    op.drop_table("repositories")

    # Drop enums
    for enum_name in [
        "incidentstatus", "incidentseverity", "incidentsource",
        "failuretype", "patchstatus", "verificationstatus",
        "risklevel", "auditaction",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
