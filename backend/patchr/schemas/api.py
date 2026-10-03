"""
API Request/Response Schemas (Pydantic)

These are the shapes of data going in and out of the FastAPI endpoints.
Separate from DB models — never expose raw ORM objects to the API layer.
"""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


def _as_utc_iso(dt: datetime | None) -> str | None:
    """
    Serialize a datetime as a UTC-aware ISO string (with a '+00:00' offset).

    The DB (SQLite) returns naive datetimes even though the app always stores
    UTC. Without a timezone marker the frontend parses the string as *local*
    time, which skews the displayed time and the "x ago" value. Stamping naive
    values as UTC fixes that.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ─── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Repository ────────────────────────────────────────────────────────────────


class RepositoryCreate(BaseModel):
    full_name: str = Field(..., description="GitHub full name, e.g. 'acme/my-app'")
    vercel_project_id: str | None = None
    vercel_project_name: str | None = None


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    full_name: str
    github_id: int
    default_branch: str
    private: bool
    vercel_project_id: str | None
    vercel_project_name: str | None
    github_webhook_id: int | None = None
    webhook_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Incident ──────────────────────────────────────────────────────────────────


class IncidentListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    severity: str
    source: str
    failure_type: str
    summary: str | None
    commit_sha: str | None
    repository_full_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, dt: datetime) -> str | None:
        return _as_utc_iso(dt)


class IncidentDetail(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    severity: str
    source: str
    failure_type: str
    summary: str | None
    commit_sha: str | None
    commit_message: str | None
    repository_id: uuid.UUID
    deployment_id: uuid.UUID | None
    resolved_at: datetime | None
    time_to_resolve_seconds: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at", "resolved_at")
    def _ser_dt(self, dt: datetime | None) -> str | None:
        return _as_utc_iso(dt)


class IncidentUpdate(BaseModel):
    status: str | None = None
    severity: str | None = None


# ─── Analysis ──────────────────────────────────────────────────────────────────


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    model_provider: str
    model_name: str
    failure_type: str | None
    root_cause: str | None
    affected_files: list | None
    evidence: list | None
    confidence: float | None
    risk_level: str | None
    verification_plan: list | None
    prompt_tokens: int | None
    completion_tokens: int | None
    repository_full_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Patch ─────────────────────────────────────────────────────────────────────


class PatchResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    analysis_id: uuid.UUID | None
    model_provider: str
    model_name: str
    description: str | None
    diff: str | None
    file_changes: list | None
    confidence: float | None
    risk_level: str | None
    status: str
    github_pr_number: int | None
    github_pr_url: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatchApproveRequest(BaseModel):
    create_pr: bool = True


class PatchRejectRequest(BaseModel):
    reason: str | None = None


# ─── Verification ──────────────────────────────────────────────────────────────


class VerificationResultResponse(BaseModel):
    id: uuid.UUID
    patch_id: uuid.UUID
    status: str
    verification_type: str
    passed: bool | None
    output: str | None
    error_output: str | None
    duration_seconds: float | None
    risk_score: float | None
    risk_explanation: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Deployment Status ─────────────────────────────────────────────────────────


class DeploymentStatusItem(BaseModel):
    id: str
    state: str  # READY, ERROR, BUILDING, QUEUED, CANCELED
    url: str | None
    branch: str | None
    commit_sha: str | None
    commit_message: str | None
    created_at: int  # unix ms
    error_message: str | None


class DeploymentStatusResponse(BaseModel):
    linked: bool
    latest_state: str | None
    vercel_project_name: str | None
    deployments: list[DeploymentStatusItem]


class BuildLogEntry(BaseModel):
    text: str
    type: str  # stdout, stderr, command, event
    is_error: bool
    created_at: int


class DeploymentLogsResponse(BaseModel):
    deployment_id: str
    log_count: int
    logs: list[BuildLogEntry]


# ─── Webhooks ──────────────────────────────────────────────────────────────────


class WebhookAckResponse(BaseModel):
    received: bool = True
    message: str = "Webhook received"


# ─── Audit Log ─────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID | None
    action: str
    actor: str
    details: dict | None
    entity_type: str | None
    entity_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
