"""
Incident Service — Business Logic Layer

Handles incident creation, status transitions, and AI analysis orchestration.
Called by webhook handlers and API routes.
No HTTP concerns here — pure business logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.ai.provider import get_ai_provider, IncidentContext
from patchr.config import get_settings
from patchr.db.models import (
    AuditAction,
    AuditLog,
    Analysis,
    Deployment,
    FailureType,
    Incident,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    Journey,
    JourneyRun,
    Repository,
)
from patchr.services.log_parser import parse_build_log

logger = structlog.get_logger(__name__)


# ─── Incident Creation ────────────────────────────────────────────────────────


async def create_incident_from_github_deployment(
    db: AsyncSession,
    *,
    repository_full_name: str,
    commit_sha: str,
    commit_message: str | None,
    deployment_vercel_id: str | None,
    error_description: str,
    build_logs: str | None,
    environment: str = "production",
) -> Incident | None:
    """
    Create an Incident record when a GitHub deployment_status failure is received.

    Returns None if the repository is not registered (ignore the event).
    Returns existing open incident if one already exists for this commit+repo.
    """
    settings = get_settings()

    # Find the registered repository
    result = await db.execute(
        select(Repository).where(Repository.full_name == repository_full_name)
    )
    repo = result.scalar_one_or_none()

    if repo is None:
        logger.info(
            "incident_create_skipped_unknown_repo",
            full_name=repository_full_name,
        )
        return None

    # Deduplicate: don't create duplicate incidents for the same commit
    existing = await db.execute(
        select(Incident).where(
            Incident.repository_id == repo.id,
            Incident.commit_sha == commit_sha,
            Incident.status.notin_(["resolved", "dismissed"]),
        )
    )
    if existing.scalars().first():
        logger.info(
            "incident_create_skipped_duplicate",
            repo=repository_full_name,
            sha=commit_sha[:8],
        )
        return None

    # Parse build logs for structured error info
    parsed_log = parse_build_log(build_logs) if build_logs else None

    # Determine severity from environment and error description
    severity = _infer_severity(environment, error_description)
    failure_type = (
        parsed_log.failure_type
        if parsed_log and parsed_log.failure_type != "unknown"
        else _infer_failure_type(error_description, build_logs)
    )


    # Create or update the deployment record
    deployment = None
    if deployment_vercel_id:
        dep_result = await db.execute(
            select(Deployment).where(
                Deployment.vercel_deployment_id == deployment_vercel_id
            )
        )
        deployment = dep_result.scalar_one_or_none()

        if deployment is None:
            deployment = Deployment(
                id=uuid.uuid4(),
                repository_id=repo.id,
                vercel_deployment_id=deployment_vercel_id,
                commit_sha=commit_sha,
                commit_message=commit_message,
                state="error",
                error_message=error_description,
                build_logs=build_logs,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(deployment)
            await db.flush()
        else:
            deployment.state = "error"
            deployment.error_message = error_description
            if build_logs:
                deployment.build_logs = build_logs
            deployment.updated_at = datetime.now(timezone.utc)

    # Create the incident
    title = _generate_incident_title(error_description, failure_type, commit_sha)

    incident = Incident(
        id=uuid.uuid4(),
        repository_id=repo.id,
        deployment_id=deployment.id if deployment else None,
        title=title,
        status="detected",
        severity=severity,
        source="vercel_deployment",
        failure_type=failure_type,
        commit_sha=commit_sha,
        commit_message=commit_message,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(incident)

    # Audit log entry
    audit = AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action="incident_created",
        actor="system:webhook",
        details={
            "repo": repository_full_name,
            "sha": commit_sha,
            "environment": environment,
            "error": error_description[:500],
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(incident)

    logger.info(
        "incident_created",
        incident_id=str(incident.id),
        repo=repository_full_name,
        sha=commit_sha[:8],
        severity=severity,
        failure_type=failure_type,
    )

    return incident


# ─── Analysis Pipeline ────────────────────────────────────────────────────────


async def trigger_analysis(
    db: AsyncSession,
    *,
    incident: Incident,
    commit_diff: str | None = None,
    build_logs: str | None = None,
    file_contents: dict[str, str] | None = None,
) -> Analysis | None:
    """
    Run AI root-cause analysis for an incident.

    Updates incident status: detected → analyzing → patch_ready/needs_review
    Stores the result as an Analysis record.
    Returns None if AI provider is not configured.
    """
    settings = get_settings()

    if not settings.nvidia_api_key or settings.nvidia_api_key.startswith("nvapi-xxx"):
        logger.warning(
            "analysis_skipped_no_api_key",
            incident_id=str(incident.id),
        )
        return None

    # Mark as analyzing
    incident.status = "analyzing"
    incident.updated_at = datetime.now(timezone.utc)

    # Audit
    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action="analysis_started",
        actor="system:ai",
        details={"model": settings.nvidia_model},
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    # Load repository for context
    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repo = repo_result.scalar_one_or_none()

    try:

        # Parse logs to extract key context (gives AI a focused 50-line excerpt)
        parsed_log = parse_build_log(build_logs) if build_logs else None
        focused_logs = parsed_log.key_log_excerpt if parsed_log else (build_logs or "")
        detected_framework = parsed_log.framework if parsed_log else None

        # Merge detected affected files into file_contents keys
        all_changed_files = list((file_contents or {}).keys())
        if parsed_log:
            for f in parsed_log.affected_files:
                if f not in all_changed_files:
                    all_changed_files.append(f)

        # Build enriched context using the context engine (fetches real file contents)
        from patchr.services.context_service import build_incident_context
        ctx = await build_incident_context(
            incident_id=str(incident.id),
            repo=repo,
            commit_sha=incident.commit_sha,
            affected_files=all_changed_files,
            build_logs=focused_logs,
            error_message=incident.title,
            commit_message=incident.commit_message,
            commit_author=None,
            github_token=settings.github_token or None,
        )

        # Merge any caller-supplied file_contents (e.g. from webhook handler)
        if file_contents:
            ctx.relevant_file_contents.update(file_contents)

        # Override framework detection if log parser found one
        if detected_framework and not ctx.framework:
            ctx.framework = detected_framework

        ai = get_ai_provider()
        result = await ai.analyze_incident(ctx)

        # Store analysis
        analysis = Analysis(
            id=uuid.uuid4(),
            incident_id=incident.id,
            model_provider="nvidia_nim",
            model_name=settings.nvidia_model,
            failure_type=result.failure_type,
            root_cause=result.root_cause,
            affected_files=result.affected_files,
            evidence=result.evidence,
            confidence=result.confidence,
            risk_level=result.risk_level,
            verification_plan=result.verification_plan,
            prompt_tokens=None,
            completion_tokens=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(analysis)

        # Update incident — transition to root_cause_identified or needs_review
        incident.failure_type = result.failure_type or incident.failure_type
        incident.summary = result.root_cause[:500] if result.root_cause else None
        incident.status = (
            "root_cause_identified" if result.confidence >= 0.6 else "needs_review"
        )
        incident.updated_at = datetime.now(timezone.utc)

        # Audit
        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="analysis_completed",
            actor="system:ai",
            details={
                "confidence": result.confidence,
                "failure_type": result.failure_type,
                "affected_files": result.affected_files,
                "risk_level": result.risk_level,
            },
            entity_type="analysis",
            entity_id=str(analysis.id),
            created_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        await db.refresh(analysis)

        logger.info(
            "analysis_completed",
            incident_id=str(incident.id),
            confidence=result.confidence,
            failure_type=result.failure_type,
        )

        # Always auto-trigger patch generation after analysis
        # The user should only need to click Approve/Reject — not Generate
        from patchr.services.patch_service import generate_patch
        await generate_patch(db, incident=incident, analysis=analysis)

        return analysis

    except Exception as exc:
        # Mark as analysis_failed on error so it's visible in the dashboard
        incident.status = IncidentStatus.ANALYSIS_FAILED
        incident.updated_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="analysis_completed",
            actor="system:ai",
            details={"error": str(exc)},
            entity_type="incident",
            entity_id=str(incident.id),
            created_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        logger.error(
            "analysis_failed",
            incident_id=str(incident.id),
            error=str(exc),
        )
        return None


# ─── Repository Sync ──────────────────────────────────────────────────────────


async def sync_repository_from_github(
    db: AsyncSession,
    repo: Repository,
    *,
    github_id: int,
    name: str,
    default_branch: str,
    private: bool,
) -> Repository:
    """
    Update a Repository record with fresh data from GitHub API.
    Called when a repository is first connected or on webhook events.
    """
    repo.github_id = github_id
    repo.name = name
    repo.default_branch = default_branch
    repo.private = private
    repo.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(repo)
    return repo


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _infer_severity(environment: str, error_description: str) -> str:
    """Infer incident severity from environment and error content."""
    if environment == "production":
        if any(kw in error_description.lower() for kw in ["crash", "panic", "oom", "out of memory"]):
            return "critical"
        return "high"
    elif environment in ("preview", "staging"):
        return "medium"
    return "low"


def _infer_failure_type(error_description: str, build_logs: str | None) -> str:
    """Classify the failure type from error text."""
    combined = (error_description + " " + (build_logs or "")).lower()

    patterns = {
        "import_error": ["cannot find module", "module not found", "import error", "failed to resolve"],
        "type_error": ["typeerror", "type error", "ts(", "ts error", "type '", "is not assignable"],
        "syntax_error": ["syntaxerror", "syntax error", "unexpected token", "unexpected identifier"],
        "build_error": ["build failed", "compilation failed", "webpack error", "vite error", "next error"],
        "env_variable": ["environment variable", "env var", "process.env", "missing required", "not defined"],
        "dependency_conflict": ["peer dep", "dependency conflict", "version conflict", "resolution failed", "enoent"],
        "framework_error": ["next.js", "nextjs", "react error", "framework"],
        "runtime_error": ["runtime error", "uncaught error", "unhandled rejection"],
    }

    for failure_type, keywords in patterns.items():
        if any(kw in combined for kw in keywords):
            return failure_type

    return "unknown"


def _generate_incident_title(
    error_description: str,
    failure_type: str,
    commit_sha: str,
) -> str:
    """Generate a concise incident title."""
    sha_short = commit_sha[:8] if commit_sha else "unknown"

    type_labels = {
        "build_error": "Build failure",
        "import_error": "Module import error",
        "type_error": "TypeScript error",
        "syntax_error": "Syntax error",
        "env_variable": "Missing environment variable",
        "dependency_conflict": "Dependency conflict",
        "framework_error": "Framework error",
        "runtime_error": "Runtime error",
    }
    label = type_labels.get(failure_type, "Deployment failure")

    # Extract first meaningful line from error
    first_line = error_description.strip().split("\n")[0][:120]
    if len(first_line) > 20:
        return f"{label} in {sha_short}: {first_line}"
    return f"{label} in deployment {sha_short}"


# ─── Journey-to-Incident Creation ────────────────────────────────────────────


async def get_or_create_incident_from_journey(
    db: AsyncSession,
    *,
    journey: "Journey",
    run: "JourneyRun",
    failing_step: str | None,
    failing_status: int | None,
) -> Incident | None:
    """
    Create or update an Incident from a journey failure.

    Deduplicates: if a non-resolved incident already exists for this journey,
    updates the occurrence count and last_seen_at instead of creating a new one.

    Returns the incident (new or existing).
    """
    if not journey.repository_id:
        return None

    # Build fingerprint based on journey + failing step
    title = (
        f"Journey '{journey.name}' failing at step '{failing_step}' "
        f"(HTTP {failing_status or 'unknown'})"
    )

    # Deduplication: find existing active incident for this journey
    existing_result = await db.execute(
        select(Incident).where(
            Incident.repository_id == journey.repository_id,
            Incident.source == IncidentSource.SYNTHETIC_JOURNEY,
            Incident.status.notin_(["resolved", "dismissed"]),
            Incident.title.like(f"%Journey '{journey.name}'%"),
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update occurrence count and last_seen
        existing.occurrence_count = (existing.occurrence_count or 1) + 1
        existing.last_seen_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=existing.id,
            action=AuditAction.INCIDENT_UPDATED,
            actor="system:journey_runner",
            details={
                "journey_id": str(journey.id),
                "run_id": str(run.id),
                "occurrence": existing.occurrence_count,
            },
            entity_type="incident",
            entity_id=str(existing.id),
            created_at=datetime.now(timezone.utc),
        ))
        await db.flush()
        return existing

    # Create new incident
    severity = IncidentSeverity.HIGH if journey.severity == "high" else IncidentSeverity.MEDIUM
    now = datetime.now(timezone.utc)

    incident = Incident(
        id=uuid.uuid4(),
        repository_id=journey.repository_id,
        title=title,
        status=IncidentStatus.DETECTED,
        severity=severity,
        source=IncidentSource.SYNTHETIC_JOURNEY,
        failure_type=FailureType.RUNTIME_ERROR,
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_CREATED,
        actor="system:journey_runner",
        details={
            "journey_id": str(journey.id),
            "journey_name": journey.name,
            "run_id": str(run.id),
            "failing_step": failing_step,
            "failing_status": failing_status,
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=now,
    ))

    await db.flush()
    logger.info(
        "journey_incident_created",
        incident_id=str(incident.id),
        journey=journey.name,
        failing_step=failing_step,
    )
    return incident
