"""
PR Monitor Service — Phase 17

Polls GitHub for PR state after PatchR creates a draft PR.
Drives: PR_CREATED → RECOVERY_MONITORING → RESOLVED

Runs as a background APScheduler job every 5 minutes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.db.models import AuditLog, Incident, IncidentStatus, Patch, PatchStatus, Repository

logger = structlog.get_logger(__name__)


async def check_open_prs() -> None:
    """
    APScheduler job: check all patches in PR_CREATED state.
    For each, poll GitHub for the PR's current state.
    - If merged → transition incident to RECOVERY_MONITORING
    - If closed (without merge) → transition incident to AWAITING_REVIEW
    """
    from patchr.config import get_settings
    from patchr.db.session import AsyncSessionLocal

    settings = get_settings()

    if not settings.github_token or settings.github_token.startswith("ghp_your"):
        return

    async with AsyncSessionLocal() as db:
        # Find all patches in PR_CREATED state with a PR number
        result = await db.execute(
            select(Patch).where(
                Patch.status == PatchStatus.PR_CREATED,
                Patch.github_pr_number.isnot(None),
            )
        )
        patches = result.scalars().all()

        if not patches:
            return

        logger.info("pr_monitor_checking", count=len(patches))

        for patch in patches:
            try:
                await _check_single_pr(db, patch, settings)
            except Exception as e:
                logger.warning(
                    "pr_monitor_check_failed",
                    patch_id=str(patch.id),
                    error=str(e),
                )


async def _check_single_pr(db: AsyncSession, patch: Patch, settings) -> None:
    """Check and update the state of a single PR."""
    from patchr.integrations.github import get_github_client

    # Load incident and repo
    inc_result = await db.execute(
        select(Incident).where(Incident.id == patch.incident_id)
    )
    incident = inc_result.scalar_one_or_none()
    if not incident:
        return

    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        return

    async with get_github_client(settings.github_token) as gh:
        pr_data = await gh.get_pr(repo.full_name, patch.github_pr_number)

    pr_state = pr_data.get("state", "")
    merged = pr_data.get("merged", False)
    merged_at = pr_data.get("merged_at")

    now = datetime.now(timezone.utc)

    if merged:
        # PR merged — start recovery monitoring
        logger.info(
            "pr_merged",
            patch_id=str(patch.id),
            pr_number=patch.github_pr_number,
            repo=repo.full_name,
        )

        # Update patch
        patch.status = PatchStatus.APPLIED
        if merged_at:
            try:
                patch.pr_merged_at = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            except Exception:
                patch.pr_merged_at = now
        patch.pr_state = "merged"

        # Transition incident to recovery monitoring
        incident.status = IncidentStatus.RECOVERY_MONITORING
        incident.updated_at = now

        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="pr_merged",
            actor="system:pr_monitor",
            entity_type="patch",
            entity_id=str(patch.id),
            details={
                "pr_number": patch.github_pr_number,
                "merged_at": merged_at,
            },
            created_at=now,
        ))
        await db.commit()

    elif pr_state == "closed" and not merged:
        # PR closed without merge — send back for review
        logger.info(
            "pr_closed_unmerged",
            patch_id=str(patch.id),
            pr_number=patch.github_pr_number,
        )
        patch.pr_state = "closed"
        incident.status = IncidentStatus.AWAITING_REVIEW
        incident.updated_at = now

        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="pr_closed_unmerged",
            actor="system:pr_monitor",
            entity_type="patch",
            entity_id=str(patch.id),
            details={"pr_number": patch.github_pr_number},
            created_at=now,
        ))
        await db.commit()
    else:
        # Still open — log but no state change
        logger.debug(
            "pr_still_open",
            patch_id=str(patch.id),
            pr_number=patch.github_pr_number,
        )


async def resolve_recovered_incident(incident_id: str) -> None:
    """
    Called when a successful deployment event is received for a repo
    that has an incident in RECOVERY_MONITORING.
    Transitions: RECOVERY_MONITORING → RESOLVED
    """
    from patchr.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.status == IncidentStatus.RECOVERY_MONITORING,
            )
        )
        incident = result.scalar_one_or_none()
        if not incident:
            return

        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.updated_at = now
        if incident.created_at:
            created = (
                incident.created_at.replace(tzinfo=timezone.utc)
                if incident.created_at.tzinfo is None
                else incident.created_at
            )
            incident.time_to_resolve_seconds = int((now - created).total_seconds())

        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="incident_resolved",
            actor="system:pr_monitor",
            entity_type="incident",
            entity_id=str(incident.id),
            details={
                "reason": "Successful deployment after PR merge",
                "time_to_resolve_seconds": incident.time_to_resolve_seconds,
            },
            created_at=now,
        ))
        await db.commit()

        logger.info(
            "incident_auto_resolved",
            incident_id=str(incident_id),
            time_to_resolve_seconds=incident.time_to_resolve_seconds,
        )
