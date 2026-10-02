"""
Post-Merge Guard

Watches the deployed environment after a PatchR repair PR is merged.
Implements docs/21_POST_MERGE_GUARD.md.

Flow:
  1. GitHub emits PR merged event
  2. PatchR identifies the PR as associated with an incident/candidate
  3. Incident moves to deploying_watching
  4. Wait for related deployment to become ready
  5. Run relevant journey/health check
  6. Watch configured runtime signals during watch window
  7. Mark RESOLVED if healthy, REOPENED if known failure returns

Truthfulness:
  - A short watch window proves only configured checks remained healthy
  - Do not claim long-term correctness
  - Idempotent: multiple merge events must not duplicate transitions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

from patchr.db.models import (
    AuditAction,
    AuditLog,
    CandidateStatus,
    Incident,
    IncidentStatus,
    JourneyRunStatus,
    PatchCandidate,
    Patch,
    PatchStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Default watch window: 5 minutes post-deploy
DEFAULT_WATCH_WINDOW_MINUTES = 5


async def handle_pr_merged(
    db: "AsyncSession",
    *,
    pr_number: int,
    pr_url: str | None,
    merged_at: datetime | None = None,
    commit_sha: str | None = None,
) -> Incident | None:
    """
    Called when a PR merged event is received via webhook.

    Finds the incident/candidate associated with this PR number,
    transitions incident to deploying_watching.

    Returns the Incident if found and transitioned, None otherwise.
    """
    from sqlalchemy import select

    # Find candidate with this PR number (Arena flow)
    cand_result = await db.execute(
        select(PatchCandidate).where(
            PatchCandidate.github_pr_number == pr_number
        )
    )
    candidate = cand_result.scalar_one_or_none()

    # Also check legacy Patch model
    patch = None
    if not candidate:
        patch_result = await db.execute(
            select(Patch).where(Patch.github_pr_number == pr_number)
        )
        patch = patch_result.scalar_one_or_none()

    if not candidate and not patch:
        logger.info("pr_merged_not_patchr_pr", pr_number=pr_number)
        return None

    # Get incident
    incident_id = candidate.incident_id if candidate else patch.incident_id
    inc_result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = inc_result.scalar_one_or_none()

    if not incident:
        logger.warning("pr_merged_incident_not_found", pr_number=pr_number)
        return None

    # Idempotency: do not re-transition if already past pr_created
    if incident.status in (
        IncidentStatus.DEPLOYING_WATCHING,
        IncidentStatus.RECOVERY_MONITORING,
        IncidentStatus.RESOLVED,
    ):
        logger.info(
            "pr_merged_already_watching",
            incident_id=str(incident.id),
            status=incident.status,
        )
        return incident

    log = logger.bind(incident_id=str(incident.id), pr_number=pr_number)
    log.info("pr_merged_incident_found")

    # Update candidate/patch PR state
    now = merged_at or datetime.now(timezone.utc)
    if candidate:
        candidate.pr_state = "merged"
        candidate.pr_merged_at = now
    if patch:
        patch.pr_state = "merged"
        patch.pr_merged_at = now

    # Transition incident
    incident.status = IncidentStatus.DEPLOYING_WATCHING
    incident.merged_pr_number = pr_number
    incident.watch_until = datetime.now(timezone.utc) + timedelta(
        minutes=DEFAULT_WATCH_WINDOW_MINUTES
    )
    incident.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.PR_MERGED,
        actor="system:github_webhook",
        details={
            "pr_number": pr_number,
            "pr_url": pr_url,
            "merged_at": now.isoformat(),
            "commit_sha": commit_sha,
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    ))

    await db.commit()
    log.info("incident_moved_to_deploying_watching")

    return incident


async def check_deployment_and_resolve(
    db: "AsyncSession",
    *,
    incident: Incident,
    deployment_url: str | None = None,
) -> IncidentStatus:
    """
    Run journeys/health checks after a PatchR PR deployment becomes ready.
    Called by the deployment poller or PR monitor when deployment is READY.

    Returns the new incident status.
    """
    from patchr.services.journey_service import run_post_merge_journeys

    log = logger.bind(incident_id=str(incident.id))
    log.info("post_merge_guard_checking")

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.DEPLOYMENT_WATCH_STARTED,
        actor="system:post_merge_guard",
        details={
            "deployment_url": deployment_url,
            "watch_until": incident.watch_until.isoformat() if incident.watch_until else None,
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    ))

    # Transition to RECOVERY_MONITORING
    incident.status = IncidentStatus.RECOVERY_MONITORING
    incident.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Run all repository journeys as post-merge check
    try:
        journey_runs = await run_post_merge_journeys(
            db=db,
            incident=incident,
            deployment_url=deployment_url,
        )

        passed_count = sum(1 for r in journey_runs if r.status == JourneyRunStatus.PASSED)
        failed_count = sum(1 for r in journey_runs if r.status == JourneyRunStatus.FAILED)

        log.info(
            "post_merge_journeys_complete",
            total=len(journey_runs),
            passed=passed_count,
            failed=failed_count,
        )

        if journey_runs and failed_count > 0:
            # Known failure returned — reopen
            return await _reopen_incident(
                db,
                incident,
                reason=f"{failed_count}/{len(journey_runs)} post-merge journeys failed",
                journey_runs=journey_runs,
            )
        elif journey_runs and passed_count == len(journey_runs):
            # All journeys passed — resolve
            return await _resolve_incident(
                db, incident, passed_journey_count=passed_count
            )
        else:
            # No journeys configured or mix — resolve with caveat
            if not journey_runs:
                # No journeys to run; resolve based on deployment health
                return await _resolve_incident(db, incident, passed_journey_count=0)
            return incident.status

    except Exception as e:
        log.error("post_merge_guard_error", error=str(e))
        # Don't auto-resolve on error; stay in RECOVERY_MONITORING
        await db.commit()
        return incident.status


async def _resolve_incident(
    db: "AsyncSession",
    incident: Incident,
    *,
    passed_journey_count: int,
) -> IncidentStatus:
    """Mark incident as RESOLVED after successful post-merge watch."""
    now = datetime.now(timezone.utc)
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now
    if incident.created_at:
        incident.time_to_resolve_seconds = int(
            (now - incident.created_at).total_seconds()
        )
    incident.updated_at = now

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_RESOLVED,
        actor="system:post_merge_guard",
        details={
            "passed_journey_count": passed_journey_count,
            "truthfulness_note": (
                "No regressions detected by configured checks during watch window. "
                "Does not guarantee long-term correctness."
            ),
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=now,
    ))

    await db.commit()
    logger.info("incident_resolved", incident_id=str(incident.id))

    # Enqueue memory creation (do not block the request)
    await _enqueue_memory_creation(db, incident)

    return IncidentStatus.RESOLVED


async def _reopen_incident(
    db: "AsyncSession",
    incident: Incident,
    *,
    reason: str,
    journey_runs: list,
) -> IncidentStatus:
    """Reopen incident if known failure returns after merge."""
    incident.status = IncidentStatus.REOPENED
    incident.updated_at = datetime.now(timezone.utc)

    # Collect failing step info
    failing_info = [
        {"run_id": str(r.id), "step": r.failing_step, "status_code": r.failing_status_code}
        for r in journey_runs
        if r.failing_step
    ]

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_REOPENED,
        actor="system:post_merge_guard",
        details={
            "reason": reason,
            "failing_journeys": failing_info,
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    ))

    await db.commit()
    logger.warning("incident_reopened", incident_id=str(incident.id), reason=reason)
    return IncidentStatus.REOPENED


async def _enqueue_memory_creation(
    db: "AsyncSession",
    incident: Incident,
) -> None:
    """
    Store normalized incident memory for future similar incident retrieval.
    Called after resolution — does not block the main flow.
    """
    try:
        from patchr.services.memory_service import store_incident_memory
        await store_incident_memory(db, incident=incident)
    except Exception as e:
        logger.warning(
            "memory_creation_failed",
            incident_id=str(incident.id),
            error=str(e),
        )
