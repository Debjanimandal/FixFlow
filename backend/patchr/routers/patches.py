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
from patchr.integrations.github import GitHubError
from patchr.schemas.api import (
    PatchApproveRequest,
    PatchRejectRequest,
    PatchResponse,
    VerificationResultResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("/{patch_id}/pr-debug")
async def pr_debug(
    patch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: dict = Depends(get_current_owner),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Diagnostic: report which GitHub token would be used to create the PR for
    this patch and whether that token can actually push to the target repo.

    Returns the GitHub user behind each token and that token's repo permissions
    so we can see exactly why PR creation does or doesn't work.
    """
    import httpx
    from patchr.db.models import Incident, Repository

    patch_result = await db.execute(select(Patch).where(Patch.id == patch_id))
    patch = patch_result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="Patch not found")

    inc_result = await db.execute(select(Incident).where(Incident.id == patch.incident_id))
    incident = inc_result.scalar_one_or_none()
    repo = None
    if incident:
        repo_result = await db.execute(select(Repository).where(Repository.id == incident.repository_id))
        repo = repo_result.scalar_one_or_none()

    user_token = owner.get("github_access_token") if isinstance(owner, dict) else None
    server_token = settings.github_token
    server_usable = bool(server_token) and not server_token.startswith("ghp_your")

    async def inspect(token: str | None) -> dict:
        if not token:
            return {"present": False}
        info: dict = {"present": True}
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                u = await c.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                )
                info["github_user"] = u.json().get("login") if u.status_code == 200 else None
                info["user_http"] = u.status_code
                # OAuth token scopes are exposed in this header
                info["scopes"] = u.headers.get("x-oauth-scopes")
                if repo:
                    r = await c.get(
                        f"https://api.github.com/repos/{repo.full_name}",
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                    )
                    if r.status_code == 200:
                        perms = r.json().get("permissions", {})
                        info["repo_http"] = 200
                        info["can_push"] = bool(perms.get("push") or perms.get("admin"))
                        info["permissions"] = perms
                    else:
                        info["repo_http"] = r.status_code
                        info["can_push"] = False
        except Exception as e:
            info["error"] = str(e)[:200]
        return info

    which = "user_oauth" if user_token else ("server_env" if server_usable else "none")

    return {
        "patch_id": str(patch_id),
        "repo": repo.full_name if repo else None,
        "default_branch": repo.default_branch if repo else None,
        "token_that_will_be_used": which,
        "user_oauth_token": await inspect(user_token),
        "server_env_token": await inspect(server_token if server_usable else None),
        "file_changes_count": len(patch.file_changes or []),
    }


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

    patch.approved_at = datetime.now(timezone.utc)

    # Record the owner's approval decision — immutable audit entry.
    audit = AuditLog(
        incident_id=patch.incident_id,
        action=AuditAction.PATCH_APPROVED,
        actor=actor_name(owner),
        entity_type="patch",
        entity_id=str(patch.id),
        details={"create_pr": body.create_pr},
    )
    db.add(audit)

    # ── Approve without PR ────────────────────────────────────────────────────
    if not body.create_pr:
        patch.status = PatchStatus.APPLIED
        await db.commit()
        await db.refresh(patch)
        logger.info("patch_approved", patch_id=str(patch_id), create_pr=False)
        return PatchResponse.model_validate(patch)

    # ── Approve + push directly to GitHub (synchronous, so failures surface) ──
    # No pull request is created. The patched files are committed straight to
    # the repository's default branch via the GitHub Contents API.
    await db.commit()  # persist the approval audit before the external call
    logger.info("patch_approved", patch_id=str(patch_id), create_pr=True)

    # Prefer the logged-in user's own GitHub OAuth token (it has write access to
    # their repos via the 'repo' scope granted at login). Fall back to the
    # server-wide GITHUB_TOKEN only if the user token is unavailable.
    user_github_token = owner.get("github_access_token") if isinstance(owner, dict) else None

    try:
        branch, branch_url, committed_paths = await _push_patch_to_github(
            db, patch=patch, settings=settings, user_github_token=user_github_token
        )
    except GitHubError as e:
        logger.error("push_github_error", patch_id=str(patch_id), status=e.status, error=e.message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"GitHub rejected the push (HTTP {e.status}): {e.message}. "
                "Check that your GitHub account (or GITHUB_TOKEN) has write access to this repo."
            ),
        )
    except _PRPreconditionError as e:
        logger.warning("push_precondition_failed", patch_id=str(patch_id), reason=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("push_unexpected_error", patch_id=str(patch_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to push the changes to GitHub: {str(e)[:200]}",
        )

    # Success — the code is now live on the branch. Mark the patch APPLIED and
    # store the branch URL so the UI can link to the pushed code on GitHub.
    patch.github_pr_url = branch_url
    patch.status = PatchStatus.APPLIED

    db.add(AuditLog(
        incident_id=patch.incident_id,
        action=AuditAction.PR_CREATED,  # reused action; details note it was a direct push
        actor="system:github",
        entity_type="patch",
        entity_id=str(patch.id),
        details={
            "mode": "direct_push",
            "branch": branch,
            "branch_url": branch_url,
            "files": committed_paths,
        },
    ))
    await db.commit()
    await db.refresh(patch)

    logger.info("patch_pushed_to_github", patch_id=str(patch_id), branch=branch, files=len(committed_paths))
    return PatchResponse.model_validate(patch)


class _PRPreconditionError(Exception):
    """Raised when a push cannot proceed due to missing config/data (not a GitHub API error)."""


async def _push_patch_to_github(
    db: AsyncSession,
    patch: Patch,
    settings: Settings,
    user_github_token: str | None = None,
) -> tuple[str, str, list[str]]:
    """
    Commit the patch's file changes DIRECTLY to the repository's default branch
    (no pull request). Returns (branch, branch_url, committed_paths).

    Receives the already-loaded `patch` ORM object (its id/foreign keys are real
    uuid.UUID values) so we never re-query a UUID column with a plain string.

    Token selection: prefer the logged-in user's GitHub OAuth token (write access
    to their own repos), fall back to the server-wide GITHUB_TOKEN.

    Raises:
      _PRPreconditionError — missing token, incident/repo, or file changes.
      GitHubError          — the GitHub API rejected a request.
    """
    from patchr.db.models import Incident, Repository
    from patchr.integrations.github import get_github_client

    inc_result = await db.execute(select(Incident).where(Incident.id == patch.incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise _PRPreconditionError("Incident for this patch not found")

    repo_result = await db.execute(select(Repository).where(Repository.id == incident.repository_id))
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise _PRPreconditionError("Repository for this incident not found")

    # Resolve the token to push with: the user's OAuth token takes priority
    # because it carries write permission to repos the user owns. The static
    # server GITHUB_TOKEN is only a fallback (and may be read-only).
    server_token = settings.github_token
    server_token_usable = bool(server_token) and not server_token.startswith("ghp_your")
    token_to_use = user_github_token or (server_token if server_token_usable else None)

    if not token_to_use:
        raise _PRPreconditionError(
            "No GitHub token available to push. Sign in with GitHub (so your OAuth token "
            "is used) or set a GITHUB_TOKEN with 'repo' write scope in backend/.env."
        )

    file_changes = patch.file_changes or []
    if not file_changes:
        raise _PRPreconditionError("This patch has no file changes to commit")

    branch = repo.default_branch or "main"

    async with get_github_client(token_to_use) as gh:
        branch_url, committed_paths = await gh.push_changes_to_branch(
            full_name=repo.full_name,
            branch=branch,
            file_changes=file_changes,
            incident_title=incident.title,
        )

    if not committed_paths:
        raise _PRPreconditionError("No files were committed (all file changes were empty)")

    return branch, branch_url, committed_paths


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
