"""
Database Models — PatchR

SQLAlchemy async ORM models for all core entities.
Every model includes created_at / updated_at for audit trails.

v2: Added PatchCandidate, Journey, JourneyRun, IncidentMemory, IncidentEvent
    for Patch Arena, Synthetic Journeys, Post-Merge Guard, and Incident Memory.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────


class IncidentStatus(str, enum.Enum):
    # ── Detection ─────────────────────────────────────────────────────────────
    DETECTED = "detected"               # Webhook received; incident record created
    COLLECTING_CONTEXT = "collecting_context"  # Gathering build/runtime/code context

    # ── Analysis ──────────────────────────────────────────────────────────────
    ANALYZING = "analyzing"             # AI root-cause analysis running
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"  # Analysis complete, cause known
    ANALYSIS_FAILED = "analysis_failed" # AI analysis failed (error or low confidence)

    # ── Repair ────────────────────────────────────────────────────────────────
    REPAIR_PROPOSED = "repair_proposed" # AI patch generated, awaiting verification
    VERIFYING = "verifying"             # Sandbox validation running
    VERIFIED = "verified"               # Patch passed verification; ready for owner review
    VERIFICATION_FAILED = "verification_failed"  # Verification/risk check failed

    # ── Human Review ──────────────────────────────────────────────────────────
    NEEDS_REVIEW = "needs_review"       # Low confidence — needs manual inspection
    AWAITING_REVIEW = "awaiting_review" # Awaiting owner approve/reject decision
    AWAITING_APPROVAL = "awaiting_approval"  # Synonym for awaiting_review (spec term)
    HUMAN_REVIEW_REQUIRED = "human_review_required"  # Max retries exhausted — human must act
    MANUAL_REVIEW_REQUIRED = "manual_review_required"  # All candidates failed policy
    REJECTED = "rejected"               # Owner rejected the proposed patch

    # ── Recovery ──────────────────────────────────────────────────────────────
    PR_CREATED = "pr_created"           # Draft PR opened on GitHub
    DEPLOYING_WATCHING = "deploying_watching"  # PR merged; waiting for deployment
    RECOVERY_MONITORING = "recovery_monitoring"  # Deployment healthy; monitoring window
    RESOLVED = "resolved"               # Deployment healthy after patch

    # ── Terminal ──────────────────────────────────────────────────────────────
    DISMISSED = "dismissed"             # Incident dismissed as not actionable
    REOPENED = "reopened"               # Regression — incident re-opened after resolve


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentSource(str, enum.Enum):
    VERCEL_DEPLOYMENT = "vercel_deployment"
    GITHUB_ACTION = "github_action"
    SYNTHETIC_JOURNEY = "synthetic_journey"
    RUNTIME_ERROR = "runtime_error"
    MANUAL = "manual"


class FailureType(str, enum.Enum):
    BUILD_ERROR = "build_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    SYNTAX_ERROR = "syntax_error"
    ENV_VARIABLE = "env_variable"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    FRAMEWORK_ERROR = "framework_error"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN = "unknown"


class PatchStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    APPLIED = "applied"
    PR_CREATED = "pr_created"


class CandidateStatus(str, enum.Enum):
    """Status of a single Patch Arena candidate."""
    GENERATING = "generating"
    GENERATED = "generated"
    SANDBOX_RUNNING = "sandbox_running"
    ELIGIBLE = "eligible"       # Passed all validation gates
    DISCARDED = "discarded"     # Failed a gate
    SELECTED = "selected"       # Chosen candidate for PR
    PR_CREATED = "pr_created"


class CandidateStrategy(str, enum.Enum):
    """The repair strategy for this candidate."""
    MINIMAL_DIFF = "minimal_diff"       # Smallest possible change
    DEFENSIVE = "defensive"             # Add guards/error handling
    DEPENDENCY_UPDATE = "dependency_update"  # Update package version
    REFACTOR = "refactor"               # Clean rewrite of affected section
    CONFIGURATION_FIX = "configuration_fix"  # Fix env/config issue


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class EvidenceLabel(str, enum.Enum):
    """Truthfulness classification for evidence items."""
    OBSERVED = "observed"       # Directly received from external signal
    CORRELATED = "correlated"   # Deterministically linked by IDs/metadata
    INFERRED = "inferred"       # AI/system conclusion from evidence
    SYNTHETIC = "synthetic"     # Generated test input or localized reproduction
    VALIDATED = "validated"     # Result of an executed check


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JourneyStatus(str, enum.Enum):
    HEALTHY = "healthy"
    FAILING = "failing"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class JourneyRunStatus(str, enum.Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class AuditAction(str, enum.Enum):
    # Auth
    USER_LOGGED_IN = "user_logged_in"
    # Incidents
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_DISMISSED = "incident_dismissed"
    INCIDENT_RESOLVED = "incident_resolved"
    INCIDENT_REOPENED = "incident_reopened"
    # Analysis
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    # Patch Arena
    ARENA_STARTED = "arena_started"
    CANDIDATE_GENERATED = "candidate_generated"
    CANDIDATE_SELECTED = "candidate_selected"
    CANDIDATE_DISCARDED = "candidate_discarded"
    # Patch legacy
    PATCH_GENERATED = "patch_generated"
    PATCH_GENERATION_FAILED = "patch_generation_failed"
    PATCH_APPROVED = "patch_approved"
    PATCH_REJECTED = "patch_rejected"
    # Verification
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    VERIFICATION_FAILED = "verification_failed"
    # PR
    PR_CREATED = "pr_created"
    PR_MERGED = "pr_merged"
    # Post-merge
    DEPLOYMENT_WATCH_STARTED = "deployment_watch_started"
    DEPLOYMENT_HEALTHY = "deployment_healthy"
    DEPLOYMENT_FAILED = "deployment_failed"
    # Journey
    JOURNEY_CREATED = "journey_created"
    JOURNEY_RUN_STARTED = "journey_run_started"
    JOURNEY_RUN_COMPLETED = "journey_run_completed"
    JOURNEY_INCIDENT_CREATED = "journey_incident_created"


# ─── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    """A PatchR operator authenticated through GitHub OAuth."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    github_login: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    github_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    github_avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Stored encrypted. Never expose to frontend or model prompts.
    vercel_access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    vercel_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # PatchR remains an owner-operated product.
    is_owner: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ix_users_github_login", "github_login"),
        Index("ix_users_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User github:{self.github_login}>"


class Repository(Base):
    """A connected GitHub repository."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    github_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    private: Mapped[bool] = mapped_column(Boolean, default=False)

    # Vercel project linked to this repo (optional)
    vercel_project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vercel_project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Repository metadata snapshot (package.json, framework, etc.)
    metadata_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Webhook registration tracking
    github_webhook_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    webhook_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Journey base URL for this repo's deployed app (used by journey runner)
    deployment_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    journeys: Mapped[list["Journey"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"


class Deployment(Base):
    """A Vercel/GitHub deployment event."""

    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE")
    )

    # Vercel deployment identifiers
    vercel_deployment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    vercel_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    vercel_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Git context
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    commit_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Deployment state
    state: Mapped[str] = mapped_column(String(50), nullable=False)  # READY, ERROR, CANCELED, etc.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw build logs (fetched from Vercel API)
    build_logs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw payload from webhook
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="deployments")
    incident: Mapped["Incident | None"] = relationship(back_populates="deployment", uselist=False)

    __table_args__ = (Index("ix_deployments_repository_id", "repository_id"),)

    def __repr__(self) -> str:
        return f"<Deployment {self.vercel_deployment_id} state={self.state}>"


class IncidentEvent(Base):
    """
    Normalized event that created or updated an incident.
    Each raw webhook/journey/signal maps to one event record.
    Enables deduplication via idempotency_key.
    """

    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )

    # Event identity
    event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # provider delivery ID
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # github|vercel|journey|internal
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # deployment.failed|runtime.error|...

    # Correlation
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    deployment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Evidence provenance (safe reference, not raw payload)
    evidence_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Safe subset of normalized event data
    normalized: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_incident_events_incident_id", "incident_id"),
        Index("ix_incident_events_idempotency_key", "idempotency_key"),
        Index("ix_incident_events_source", "source"),
    )


class Incident(Base):
    """
    A detected failure event. Central entity in the PatchR system.
    Links deployment → analysis → candidates → verification → audit trail.
    """

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE")
    )
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True
    )

    # Classification
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), default=IncidentStatus.DETECTED
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity), default=IncidentSeverity.MEDIUM
    )
    source: Mapped[IncidentSource] = mapped_column(
        Enum(IncidentSource), default=IncidentSource.VERCEL_DEPLOYMENT
    )
    failure_type: Mapped[FailureType] = mapped_column(
        Enum(FailureType), default=FailureType.UNKNOWN
    )

    # Deduplication / fingerprinting
    fingerprint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False, server_default="1")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Summary (human-readable, populated by AI analysis)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Git context at time of incident
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resolution tracking
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_to_resolve_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Retry tracking — bounded autonomous retry loop
    retry_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, server_default="0")

    # Post-merge guard tracking
    merged_pr_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    watch_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="incidents")
    deployment: Mapped["Deployment | None"] = relationship(back_populates="incident")
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    patches: Mapped[list["Patch"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["PatchCandidate"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    events: Mapped[list["IncidentEvent"]] = relationship(
        "IncidentEvent",
        foreign_keys="[IncidentEvent.incident_id]",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_incidents_repository_id", "repository_id"),
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_created_at", "created_at"),
        Index("ix_incidents_fingerprint", "fingerprint"),
    )

    def __repr__(self) -> str:
        return f"<Incident {self.id} [{self.status}]>"


class Analysis(Base):
    """
    AI root-cause analysis result for an incident.
    Stores the full structured output from the reasoning model.
    Multiple analyses per incident are allowed (re-analysis, different models).
    """

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )

    # AI provider metadata
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Structured analysis output (matches ai/schemas.py AnalysisResult)
    failure_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verification_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw AI response (for debugging and audit — never expose to frontend)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Token usage for cost tracking
    prompt_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="analyses")

    __table_args__ = (Index("ix_analyses_incident_id", "incident_id"),)

    def __repr__(self) -> str:
        return f"<Analysis {self.id} confidence={self.confidence}>"


class PatchCandidate(Base):
    """
    A single Patch Arena candidate.
    Replaces the single-candidate Patch model for new Arena flow.
    2-3 candidates generated concurrently with different strategies.
    Each goes through the same validation policy independently.
    """

    __tablename__ = "patch_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True
    )

    # Candidate identity
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2
    strategy: Mapped[CandidateStrategy] = mapped_column(
        Enum(CandidateStrategy), nullable=False
    )
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.GENERATING
    )

    # AI provider metadata
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Patch content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)  # strategy rationale
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_changes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Confidence and risk
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Validation plan (from AI)
    validation_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Eligibility gate results (set after sandbox run)
    reproduction_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    build_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tests_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    no_new_failures: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Selection metadata
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PR tracking (set when this candidate is approved and PR is created)
    github_pr_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    github_pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pr_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pr_merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Owner decision
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Change surface metrics (for deterministic selection)
    changed_files_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_lines_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="candidates")
    verification_runs: Mapped[list["VerificationRun"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_patch_candidates_incident_id", "incident_id"),
        Index("ix_patch_candidates_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PatchCandidate {self.id} strategy={self.strategy} status={self.status}>"


class Patch(Base):
    """
    Legacy single-candidate patch model.
    Kept for backward compatibility with existing API.
    New code should use PatchCandidate via the Arena flow.
    """

    __tablename__ = "patches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True
    )

    # AI provider metadata
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Patch content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_changes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Confidence and risk (from AI + verification)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[PatchStatus] = mapped_column(
        Enum(PatchStatus), default=PatchStatus.PROPOSED
    )

    # PR tracking
    github_pr_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    github_pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pr_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pr_merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Owner decision
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="patches")
    verification_results: Mapped[list["VerificationResult"]] = relationship(
        back_populates="patch", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_patches_incident_id", "incident_id"),)

    def __repr__(self) -> str:
        return f"<Patch {self.id} [{self.status}]>"


class VerificationRun(Base):
    """
    A single sandbox validation step for a PatchCandidate.
    Stores exact stdout/stderr/exit_code for the Repair Proof.
    Replaces the old VerificationResult model for Arena candidates.
    """

    __tablename__ = "verification_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patch_candidates.id", ondelete="CASCADE")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )

    # What stage of validation
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    # clone | baseline | apply | install | typecheck | build | tests | regression | risk | cleanup

    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.PENDING
    )

    # Evidence label per spec
    evidence_label: Mapped[EvidenceLabel] = mapped_column(
        Enum(EvidenceLabel), default=EvidenceLabel.SYNTHETIC
    )

    # Reproduction level
    reproduction_level: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # exact_replay | localized_synthetic | mechanism_validation | unverified

    # Command executed (safe to log - no secrets)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Results
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Artifact references (paths to log files, not raw content)
    artifact_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Risk scoring
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    candidate: Mapped["PatchCandidate"] = relationship(back_populates="verification_runs")

    __table_args__ = (
        Index("ix_verification_runs_candidate_id", "candidate_id"),
        Index("ix_verification_runs_incident_id", "incident_id"),
    )

    def __repr__(self) -> str:
        return f"<VerificationRun {self.stage} passed={self.passed}>"


class VerificationResult(Base):
    """
    Result of running a proposed patch through a verification pipeline (legacy).
    Kept for backward compat with existing Patch model.
    New code should use VerificationRun for PatchCandidate.
    """

    __tablename__ = "verification_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patches.id", ondelete="CASCADE")
    )

    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.PENDING
    )

    verification_type: Mapped[str] = mapped_column(String(100), nullable=False)

    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    patch: Mapped["Patch"] = relationship(back_populates="verification_results")

    __table_args__ = (Index("ix_verification_results_patch_id", "patch_id"),)

    def __repr__(self) -> str:
        return f"<VerificationResult {self.id} passed={self.passed}>"


class Journey(Base):
    """
    A synthetic user journey definition.
    Reusable backend HTTP flow that tests critical application paths.
    """

    __tablename__ = "journeys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[str] = mapped_column(String(50), default="high")

    # Journey steps: list of {name, method, path, expected_status, body?, headers?}
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Configuration
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=10000)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=2)  # consecutive failures before incident

    # Heartbeat schedule (cron expression, empty = disabled)
    heartbeat_cron: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Current state
    current_status: Mapped[JourneyStatus] = mapped_column(
        Enum(JourneyStatus), default=JourneyStatus.UNKNOWN
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    repository: Mapped["Repository | None"] = relationship(back_populates="journeys")
    runs: Mapped[list["JourneyRun"]] = relationship(
        back_populates="journey", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_journeys_repository_id", "repository_id"),
        Index("ix_journeys_enabled", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<Journey {self.name} status={self.current_status}>"


class JourneyRun(Base):
    """
    A single execution of a Journey.
    Records all step results and final outcome.
    """

    __tablename__ = "journey_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journeys.id", ondelete="CASCADE")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )

    # Trigger type
    trigger: Mapped[str] = mapped_column(String(100), nullable=False)  # heartbeat|deployment|manual|post_merge

    status: Mapped[JourneyRunStatus] = mapped_column(
        Enum(JourneyRunStatus), default=JourneyRunStatus.RUNNING
    )

    # Step results: list of {name, method, path, status_code, passed, duration_ms, error?}
    step_results: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Failing step info
    failing_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failing_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timing
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Base URL used for this run
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Error (timeout, network issue, etc.)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    journey: Mapped["Journey"] = relationship(back_populates="runs")

    __table_args__ = (
        Index("ix_journey_runs_journey_id", "journey_id"),
        Index("ix_journey_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<JourneyRun {self.id} status={self.status}>"


class IncidentMemory(Base):
    """
    Normalized memory of a successfully resolved incident.
    Used as historical context for future similar incidents.
    Never treated as proof — current validation always required.
    """

    __tablename__ = "incident_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE")
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )

    # Normalized fingerprint for similarity matching
    fingerprint: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Context for retrieval
    framework: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_pattern: Mapped[str | None] = mapped_column(String(512), nullable=True)  # normalized message pattern
    affected_route: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # What worked
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    successful_strategy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    successful_diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # NOT raw diff

    # Outcome metadata
    final_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)  # resolved|reopened
    time_to_resolve_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_incident_memory_incident_id", "incident_id"),
        Index("ix_incident_memory_fingerprint", "fingerprint"),
        Index("ix_incident_memory_failure_type", "failure_type"),
    )

    def __repr__(self) -> str:
        return f"<IncidentMemory fingerprint={self.fingerprint}>"


class AuditLog(Base):
    """
    Immutable audit record for every AI action and owner decision.
    Never updated — only inserted. Deletion is disabled at the API level.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )

    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)  # "owner" | "system:ai" | "system:github"
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # What entity was affected
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    incident: Mapped["Incident | None"] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_incident_id", "incident_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor}>"
