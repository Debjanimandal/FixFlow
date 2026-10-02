"""
Patches Router

Endpoints for reviewing, approving, and rejecting AI-proposed patches.
Approval gate: owner must explicitly approve before any PR/action is taken.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from patchr.auth import actor_name, get_current_owner
from patchr.config import Settings, get_settings
from patchr.db.models import AuditAction, AuditLog, Patch, PatchStatus
from patchr.db.session import get_db
from patchr.schemas.api import (
    PatchApproveRequest,
    PatchRejectRequest,
    PatchResponse,
    VerificationResultResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/patches", tags=["patches"])


@router.post("/generate/{incident_id}")
async def generate_patch_for_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
):
    """
    Manually trigger patch generation for an incident that has completed analysis.

    - Requires an Analysis record with confidence >= 0.4
    - AI proposes a minimal code fix for the identified root cause
    - Patch stored as "proposed" — awaiting owner approval
    """
    from patchr.db.models import Analysis, Incident
    from patchr.services.patch_service import generate_patch

    # Load incident
    inc_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    # Get latest analysis
    anal_result = await db.execute(
        select(Analysis)
        .where(Analysis.incident_id == incident_id)
        .order_by(Analysis.created_at.desc())
    )
    analysis = anal_result.scalars().first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No analysis found for this incident. Run analysis first.",
        )

    patch = await generate_patch(db, incident=incident, analysis=analysis)
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Patch generation failed or was skipped (check confidence score and API key).",
        )

    return {"patch_id": str(patch.id), "status": patch.status, "confidence": patch.confidence}

@router.get("/{patch_id}", response_model=PatchResponse)
async def get_patch(
    patch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> PatchResponse:
    """Get a patch by ID with full detail."""
    result = await db.execute(select(Patch).where(Patch.id == patch_id))
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")
    return PatchResponse.model_validate(patch)


@router.get("/{patch_id}/verification", response_model=list[VerificationResultResponse])
async def list_verification_results(
    patch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[VerificationResultResponse]:
    """List all verification results for a patch."""
    from patchr.db.models import VerificationResult
    result = await db.execute(
        select(VerificationResult)
        .where(VerificationResult.patch_id == patch_id)
        .order_by(VerificationResult.created_at.asc())
    )
    results = result.scalars().all()
    return [VerificationResultResponse.model_validate(r) for r in results]


@router.post("/{patch_id}/approve", response_model=PatchResponse)
async def approve_patch(
    patch_id: uuid.UUID,
    body: PatchApproveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
    settings: Settings = Depends(get_settings),
) -> PatchResponse:
    """
    Owner explicitly approves a patch.
    Human approval gate — required before any PR or deployment action.

    If create_pr=True: creates a branch, commits file changes, opens a draft PR on GitHub.
    The patch status advances: PROPOSED/VERIFIED → PR_CREATED or APPLIED.
    """
    result = await db.execute(select(Patch).where(Patch.id == patch_id))
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    if patch.status not in (PatchStatus.VERIFIED, PatchStatus.PROPOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patch in status '{patch.status}' cannot be approved",
        )

    patch.status = PatchStatus.PR_CREATED if body.create_pr else PatchStatus.APPLIED
    patch.approved_at = datetime.now(timezone.utc)

    # Record audit log — every owner decision is immutable
    audit = AuditLog(
        incident_id=patch.incident_id,
        action=AuditAction.PATCH_APPROVED,
        actor=actor_name(owner),
        entity_type="patch",
        entity_id=str(patch.id),
        details={"create_pr": body.create_pr},
    )
    db.add(audit)

    await db.flush()
    await db.commit()
    await db.refresh(patch)

    logger.info("patch_approved", patch_id=str(patch_id), create_pr=body.create_pr)

    # Phase 7 — create GitHub PR in background
    if body.create_pr:
        background_tasks.add_task(
            _create_github_pr,
            patch_id=str(patch.id),
            settings=settings,
        )

    return PatchResponse.model_validate(patch)


async def _create_github_pr(patch_id: str, settings: Settings) -> None:
    """
    Background task: create a branch and open a draft PR on GitHub
    for an approved patch.
    """
    from patchr.db.models import Incident, Patch, Repository
    from patchr.db.session import AsyncSessionLocal
    from patchr.integrations.github import get_github_client, GitHubError

    try:
        async with AsyncSessionLocal() as db:
            # Load patch with incident and repository
            patch_result = await db.execute(select(Patch).where(Patch.id == patch_id))
            patch = patch_result.scalar_one_or_none()
            if not patch:
                logger.error("pr_create_patch_not_found", patch_id=patch_id)
                return

            inc_result = await db.execute(select(Incident).where(Incident.id == patch.incident_id))
            incident = inc_result.scalar_one_or_none()
            if not incident:
                logger.error("pr_create_incident_not_found", patch_id=patch_id)
                return

            repo_result = await db.execute(select(Repository).where(Repository.id == incident.repository_id))
            repo = repo_result.scalar_one_or_none()
            if not repo:
                logger.error("pr_create_repo_not_found", patch_id=patch_id)
                return

            if not settings.github_token or settings.github_token.startswith("ghp_your"):
                logger.warning("pr_create_skipped_no_token", patch_id=patch_id)
                return

            file_changes = patch.file_changes or []
            if not file_changes:
                logger.warning("pr_create_no_file_changes", patch_id=patch_id)
                return

            async with get_github_client(settings.github_token) as gh:
                branch_name, pr_number, pr_url = await gh.create_patch_pr(
                    full_name=repo.full_name,
                    default_branch=repo.default_branch or "main",
                    patch_id=str(patch.id),
                    incident_title=incident.title,
                    file_changes=file_changes,
                    patch_description=patch.description or "",
                )

            # Store PR details back on the patch
            patch.github_pr_number = pr_number
            patch.github_pr_url = pr_url

            # Audit log the PR creation — same session, no orphan
            from patchr.db.models import AuditAction, AuditLog
            audit = AuditLog(
                incident_id=patch.incident_id,
                action=AuditAction.PR_CREATED,
                actor="system:github",
                entity_type="patch",
                entity_id=str(patch.id),
                details={"pr_number": pr_number, "pr_url": pr_url, "branch": branch_name},
            )
            db.add(audit)
            await db.commit()

            logger.info("pr_created_successfully", pr_number=pr_number, url=pr_url)

    except GitHubError as e:
        logger.error("pr_create_github_error", patch_id=patch_id, status=e.status, error=e.message)
    except Exception as e:
        logger.error("pr_create_unexpected_error", patch_id=patch_id, error=str(e))


@router.post("/{patch_id}/reject", response_model=PatchResponse)
async def reject_patch(
    patch_id: uuid.UUID,
    body: PatchRejectRequest,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> PatchResponse:
    """Owner rejects a patch. Records reason in audit trail."""
    result = await db.execute(select(Patch).where(Patch.id == patch_id))
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    if patch.status == PatchStatus.APPLIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already-applied patch",
        )

    patch.status = PatchStatus.REJECTED
    patch.rejected_at = datetime.now(timezone.utc)
    patch.rejection_reason = body.reason

    audit = AuditLog(
        incident_id=patch.incident_id,
        action=AuditAction.PATCH_REJECTED,
        actor=actor_name(owner),
        entity_type="patch",
        entity_id=str(patch.id),
        details={"reason": body.reason},
    )
    db.add(audit)

    await db.flush()
    await db.refresh(patch)

    logger.info("patch_rejected", patch_id=str(patch_id), reason=body.reason)

    return PatchResponse.model_validate(patch)
