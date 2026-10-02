"""
Incidents Router

CRUD + analysis trigger for incidents.
All routes require owner authentication.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from patchr.auth import actor_name, get_current_owner
from patchr.config import Settings, get_settings
from patchr.db.models import AuditAction, AuditLog, Incident, IncidentStatus, Repository
from patchr.db.session import get_db
from patchr.schemas.api import (
    AuditLogResponse,
    AnalysisResponse,
    IncidentDetail,
    IncidentListItem,
    IncidentUpdate,
    PatchResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentListItem])
async def list_incidents(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[IncidentListItem]:
    """
    List all incidents, optionally filtered by status.
    Returns lightweight list items — no nested relations.
    """
    query = select(Incident, Repository.full_name).join(
        Repository, Incident.repository_id == Repository.id, isouter=True
    ).order_by(Incident.created_at.desc()).limit(limit).offset(offset)

    if status_filter:
        try:
            status_enum = IncidentStatus(status_filter)
            query = query.where(Incident.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    result = await db.execute(query)
    rows = result.all()

    # Deduplication: if same repo+commit_sha appears more than once, keep only the
    # incident with the most advanced status (verified > patch_ready > analyzed > detected).
    STATUS_RANK = {
        "verified": 0, "patch_ready": 1, "root_cause_identified": 2,
        "analyzing": 3, "needs_review": 4, "analysis_failed": 5, "detected": 6,
        "resolved": 7, "dismissed": 8,
    }
    seen: dict[tuple, tuple] = {}  # (repo_id, commit_sha) → (rank, incident, repo_full_name)
    for incident, repo_full_name in rows:
        key = (str(incident.repository_id), str(incident.commit_sha or incident.id))
        rank = STATUS_RANK.get(str(incident.status).lower(), 99)
        if key not in seen or rank < seen[key][0]:
            seen[key] = (rank, incident, repo_full_name)

    items = []
    for _rank, incident, repo_full_name in seen.values():
        item = IncidentListItem.model_validate(incident)
        item.repository_full_name = repo_full_name
        items.append(item)

    # Re-sort by created_at desc (dict order is insertion order after dedup)
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> IncidentDetail:
    """Get full incident detail."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentDetail.model_validate(incident)


@router.patch("/{incident_id}", response_model=IncidentDetail)
async def update_incident(
    incident_id: uuid.UUID,
    body: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> IncidentDetail:
    """Update incident status or severity (e.g. dismiss, escalate)."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if body.status is not None:
        try:
            incident.status = IncidentStatus(body.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {body.status}",
            )

    await db.flush()
    await db.commit()
    await db.refresh(incident)
    return IncidentDetail.model_validate(incident)


@router.get("/{incident_id}/analyses", response_model=list[AnalysisResponse])
async def list_analyses(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[AnalysisResponse]:
    """List all AI analyses for an incident."""
    from patchr.db.models import Analysis
    result = await db.execute(
        select(Analysis).where(Analysis.incident_id == incident_id).order_by(Analysis.created_at.desc())
    )
    analyses = result.scalars().all()

    # Resolve the incident's repository so each affected file can be shown
    # against its actual source root (e.g. the real "owner/repo" the file lives in).
    incident_result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = incident_result.scalar_one_or_none()
    repository_full_name: str | None = None
    if incident is not None:
        repo_result = await db.execute(
            select(Repository.full_name).where(Repository.id == incident.repository_id)
        )
        repository_full_name = repo_result.scalar_one_or_none()

    responses: list[AnalysisResponse] = []
    for a in analyses:
        response = AnalysisResponse.model_validate(a)
        response.repository_full_name = repository_full_name
        responses.append(response)
    return responses


@router.get("/{incident_id}/affected-sources")
async def get_affected_sources(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> list[dict]:
    """
    Return the FULL source code of each affected file for the latest analysis,
    with the exact line number(s) where the error occurs marked for highlighting.

    The error lines are detected by matching the AI evidence snippets against
    the real file content fetched from GitHub (at the incident's commit SHA,
    falling back to the repository default branch).
    """
    from patchr.db.models import Analysis
    from patchr.integrations.github import get_github_client, GitHubError

    # Load incident + repository
    inc_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repo = repo_result.scalar_one_or_none()

    # Latest analysis (holds affected_files + evidence)
    analysis_result = await db.execute(
        select(Analysis)
        .where(Analysis.incident_id == incident_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    affected_files: list[str] = list(analysis.affected_files or []) if analysis else []
    evidence: list[str] = list(analysis.evidence or []) if analysis else []

    if not repo or not affected_files:
        return []

    if not settings.github_token or settings.github_token.startswith("ghp_your"):
        # No token — return the file names without content so the UI can still
        # render a message instead of failing.
        return [
            {
                "path": path,
                "content": None,
                "error_lines": [],
                "available": False,
            }
            for path in affected_files
        ]

    ref = incident.commit_sha or repo.default_branch or "main"
    sources: list[dict] = []

    async with get_github_client(settings.github_token) as gh:
        for path in affected_files[:10]:
            content: str | None = None
            try:
                fc = await gh.get_file_content(repo.full_name, path, ref=ref)
                if fc is None and incident.commit_sha:
                    # Fall back to the default branch if the commit ref failed
                    fc = await gh.get_file_content(
                        repo.full_name, path, ref=repo.default_branch or "main"
                    )
                content = fc.content if fc else None
            except GitHubError:
                content = None
            except Exception:
                content = None

            error_lines = _detect_error_lines(content, evidence) if content else []

            sources.append({
                "path": path,
                "content": content,
                "error_lines": error_lines,
                "available": content is not None,
            })

    return sources


@router.get("/{incident_id}/file-content")
async def get_file_content_for_incident(
    incident_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Return the FULL source code of a single file (by repo-relative `path`) for
    this incident, fetched from GitHub at the incident's commit SHA (falling
    back to the repository default branch).

    Used by the patch full-screen view so it can show the complete file around
    the patched region rather than only the changed snippet.
    """
    from patchr.integrations.github import get_github_client, GitHubError

    inc_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = inc_result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if not settings.github_token or settings.github_token.startswith("ghp_your"):
        return {"path": path, "content": None, "available": False}

    ref = incident.commit_sha or repo.default_branch or "main"
    content: str | None = None
    try:
        async with get_github_client(settings.github_token) as gh:
            fc = await gh.get_file_content(repo.full_name, path, ref=ref)
            if fc is None and incident.commit_sha:
                fc = await gh.get_file_content(
                    repo.full_name, path, ref=repo.default_branch or "main"
                )
            content = fc.content if fc else None
    except GitHubError:
        content = None
    except Exception:
        content = None

    return {"path": path, "content": content, "available": content is not None}


def _detect_error_lines(content: str, evidence: list[str]) -> list[int]:
    """
    Determine which 1-based line numbers of `content` are implicated by the
    AI evidence. A line is flagged if a meaningful evidence snippet appears
    within it (case-insensitive substring match). Returns a sorted unique list.
    """
    if not content or not evidence:
        return []

    lines = content.splitlines()
    flagged: set[int] = set()

    # Build normalized snippets from evidence. Evidence often contains log noise;
    # we match on substantial fragments (>= 6 chars) so trivial tokens don't
    # over-highlight the whole file.
    snippets: list[str] = []
    for ev in evidence:
        if not isinstance(ev, str):
            continue
        text = ev.strip()
        if len(text) >= 6:
            snippets.append(text.lower())
        # Also pull out quoted fragments like '...' or "..." which usually
        # contain the exact offending code (import paths, symbol names).
        import re as _re
        for frag in _re.findall(r"['\"`]([^'\"`]{4,})['\"`]", ev):
            snippets.append(frag.strip().lower())

    if not snippets:
        return []

    for idx, line in enumerate(lines, start=1):
        line_lc = line.lower()
        if not line_lc.strip():
            continue
        for snip in snippets:
            # Match either direction: the snippet is in the line, or (for short
            # lines) the line is contained in a longer evidence snippet.
            if (snip in line_lc) or (len(line_lc.strip()) >= 6 and line_lc.strip() in snip):
                flagged.add(idx)
                break

    return sorted(flagged)


@router.get("/{incident_id}/patches", response_model=list[PatchResponse])
async def list_patches(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[PatchResponse]:
    """List all proposed patches for an incident."""
    from patchr.db.models import Patch
    result = await db.execute(
        select(Patch).where(Patch.incident_id == incident_id).order_by(Patch.created_at.desc())
    )
    patches = result.scalars().all()
    return [PatchResponse.model_validate(p) for p in patches]


@router.get("/{incident_id}/audit", response_model=list[AuditLogResponse])
async def list_audit_logs(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[AuditLogResponse]:
    """Full audit trail for an incident — every AI action and owner decision."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.incident_id == incident_id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()
    return [AuditLogResponse.model_validate(log) for log in logs]


# ─── Action Endpoints ─────────────────────────────────────────────────────────


@router.post("/{incident_id}/dismiss", response_model=IncidentDetail)
async def dismiss_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> IncidentDetail:
    """
    Owner dismisses an incident as not actionable.
    Records audit entry and marks resolved_at timestamp.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.DISMISSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incident is already {incident.status}",
        )

    now = datetime.now(timezone.utc)
    incident.status = IncidentStatus.DISMISSED
    incident.resolved_at = now
    incident.updated_at = now
    if incident.created_at:
        delta = now - incident.created_at.replace(tzinfo=timezone.utc) if incident.created_at.tzinfo is None else now - incident.created_at
        incident.time_to_resolve_seconds = int(delta.total_seconds())

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_DISMISSED,
        actor=actor_name(owner),
        entity_type="incident",
        entity_id=str(incident.id),
        details={"previous_status": str(incident.status)},
        created_at=now,
    ))

    await db.commit()
    await db.refresh(incident)
    logger.info("incident_dismissed", incident_id=str(incident_id), actor=actor_name(owner))
    return IncidentDetail.model_validate(incident)


@router.post("/{incident_id}/resolve", response_model=IncidentDetail)
async def resolve_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> IncidentDetail:
    """
    Owner manually marks an incident as resolved.
    Calculates time_to_resolve_seconds and writes audit entry.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident is already resolved",
        )

    now = datetime.now(timezone.utc)
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now
    incident.updated_at = now
    if incident.created_at:
        created = incident.created_at.replace(tzinfo=timezone.utc) if incident.created_at.tzinfo is None else incident.created_at
        incident.time_to_resolve_seconds = int((now - created).total_seconds())

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_RESOLVED,
        actor=actor_name(owner),
        entity_type="incident",
        entity_id=str(incident.id),
        details={"time_to_resolve_seconds": incident.time_to_resolve_seconds},
        created_at=now,
    ))

    await db.commit()
    await db.refresh(incident)
    logger.info("incident_resolved", incident_id=str(incident_id), actor=actor_name(owner))
    return IncidentDetail.model_validate(incident)


@router.post("/{incident_id}/reanalyze")
async def reanalyze_incident(
    incident_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
    settings: Settings = Depends(get_settings),
):
    """
    Re-trigger AI analysis for an incident that failed or needs review.
    Allowed from statuses: detected, analysis_failed, needs_review, root_cause_identified.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    allowed = {
        IncidentStatus.DETECTED,
        IncidentStatus.ANALYSIS_FAILED,
        IncidentStatus.NEEDS_REVIEW,
        IncidentStatus.ROOT_CAUSE_IDENTIFIED,
        IncidentStatus.HUMAN_REVIEW_REQUIRED,
        IncidentStatus.AWAITING_REVIEW,
    }
    if incident.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot re-analyze incident in status '{incident.status}'. Allowed: {[s.value for s in allowed]}",
        )

    # Reset retry counter so the full 2-attempt budget is available again
    incident.retry_count = 0
    incident.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(
        _run_reanalysis,
        incident_id=str(incident_id),
        settings=settings,
    )

    return {"message": "Re-analysis queued (retry_count reset)", "incident_id": str(incident_id)}


async def _run_reanalysis(incident_id: str, settings: Settings) -> None:
    """Background task: re-trigger analysis for an incident."""
    from patchr.db.session import AsyncSessionLocal
    from patchr.services import incident_service
    from patchr.services.deployment_poller import _fetch_build_context
    from patchr.db.models import Repository
    import uuid as _uuid

    try:
        inc_uuid = _uuid.UUID(incident_id)
    except (ValueError, AttributeError) as e:
        logger.error("reanalysis_invalid_id", incident_id=incident_id, error=str(e))
        return

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Incident).where(Incident.id == inc_uuid))
            incident = result.scalar_one_or_none()
            if not incident:
                logger.warning("reanalysis_incident_not_found", incident_id=incident_id)
                return

            # Fetch the repository so we have full_name
            repo_result = await db.execute(
                select(Repository).where(Repository.id == incident.repository_id)
            )
            repo = repo_result.scalar_one_or_none()
            full_name = repo.full_name if repo else None

            # Fetch build logs from GitHub (commit diff + workflow error log)
            build_logs = None
            if full_name and incident.commit_sha:
                try:
                    build_logs = await _fetch_build_context(
                        full_name, incident.commit_sha, settings
                    )
                except Exception as e:
                    logger.warning("reanalysis_build_context_failed", incident_id=incident_id, error=str(e))

            await incident_service.trigger_analysis(
                db, incident=incident, build_logs=build_logs
            )
    except Exception as e:
        logger.error("reanalysis_background_task_failed", incident_id=incident_id, error=str(e), exc_info=True)


@router.post("/simulate-failure")
async def simulate_failure(
    background_tasks: BackgroundTasks,
    scenario: str | None = None,   # ?scenario=import_case | type_error | build_error
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
    settings: Settings = Depends(get_settings),
):
    """
    Simulate a deployment failure on a registered repository.
    Picks the first active repository and creates a test incident,
    then kicks off the full AI analysis → patch → validation pipeline.

    Pass ?scenario=import_case for the canonical deterministic demo scenario
    (case-sensitive module import error — always produces a one-line fix).

    Used for development, demos, and end-to-end testing.
    """
    # Pick the first active repository
    result = await db.execute(
        select(Repository)
        .where(Repository.is_active == True)
        .order_by(Repository.created_at.desc())
        .limit(1)
    )
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active repositories connected. Add a repository first via POST /repositories.",
        )

    # ── Scenario catalogue ────────────────────────────────────────────────────
    SCENARIOS = {
        # ━━ Canonical demo scenario: case-sensitive import ━━━━━━━━━━━━━━━━━━━━━━━━━
        # Developer commits: import Button from './Button'
        # Actual file:       button.tsx (lowercase b)
        # PatchR should produce a one-line fix in < 3 minutes.
        "import_case": {
            "failure_type": "import_error",
            "error": "Module not found: Error: Can't resolve './Button' in '/vercel/path0/src/components'",
            "build_logs": (
                "[18:32:14.422] Running build in Washington, D.C., USA (East) – iad1\n"
                "[18:32:14.850] Cloning github.com/{repo} (Branch: main, Commit: abc1234)\n"
                "[18:32:16.012] Running \"npm install\" ...\n"
                "[18:32:24.033] info  - Creating an optimized production build ...\n"
                "[18:32:26.178] Failed to compile.\n"
                "[18:32:26.179] ./src/components/Dashboard.tsx\n"
                "[18:32:26.179] Module not found: Error: Can't resolve './Button'\n"
                "[18:32:26.179]   in '/vercel/path0/src/components'\n"
                "[18:32:26.180] Import trace for requested module:\n"
                "[18:32:26.180]   ./src/components/Dashboard.tsx\n"
                "[18:32:26.181] > Build failed because of webpack errors\n"
                "[18:32:26.182] Error: Command \"npm run build\" exited with 1\n"
            ).replace("{repo}", repo.full_name),
            "commit_message": "feat: add dashboard with Button component import",
        },
        # ━━ TypeScript type error ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        "type_error": {
            "failure_type": "type_error",
            "error": "Type 'string' is not assignable to type 'number'",
            "build_logs": (
                "info  - Compiling ...\n"
                "./src/lib/utils.ts:42:5 - error TS2322: Type 'string' is not assignable to type 'number'.\n"
                "42     return config.timeout\n"
                "       ~~~~~~\n"
                "Found 1 error in ./src/lib/utils.ts:42\n"
            ),
            "commit_message": "refactor: update config timeout field type",
        },
        # ━━ Build syntax error ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        "build_error": {
            "failure_type": "build_error",
            "error": "SyntaxError: Unexpected token — Next.js compilation error",
            "build_logs": (
                "info  - Compiling /dashboard...\n"
                "error - Build failed because of webpack errors\n"
                "ERROR in ./src/app/page.tsx\n"
                "SyntaxError: Unexpected token 'export'\n"
                "  at new Script (node:vm:100:7)\n"
                "Build failed with exit code 1\n"
            ),
            "commit_message": "feat: add new page with export syntax",
        },
    }

    import random
    if scenario and scenario in SCENARIOS:
        chosen = SCENARIOS[scenario]
    else:
        # Default to the canonical import_case for reliable demos
        chosen = SCENARIOS["import_case"]

    # Create a fake commit SHA for the simulated event
    fake_sha = uuid.uuid4().hex[:40]

    from patchr.services import incident_service

    incident = await incident_service.create_incident_from_github_deployment(
        db,
        repository_full_name=repo.full_name,
        commit_sha=fake_sha,
        commit_message=chosen.get("commit_message", f"chore: simulated {chosen['failure_type']}"),
        deployment_vercel_id=None,
        error_description=chosen["error"],
        build_logs=chosen["build_logs"],
        environment="production",
    )

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A similar incident for this repository is already open.",
        )

    # Kick off the full pipeline in background
    background_tasks.add_task(
        _run_simulated_analysis,
        incident_id=str(incident.id),
        build_logs=chosen["build_logs"],
        settings=settings,
    )

    return {
        "incident_id": str(incident.id),
        "repository": repo.full_name,
        "failure_type": chosen["failure_type"],
        "scenario": scenario or "import_case",
        "status": "detected",
        "message": "Simulated failure created. AI analysis + real build validation pipeline running in background.",
    }


async def _run_simulated_analysis(incident_id: str, build_logs: str, settings: Settings) -> None:
    """Background task: run full analysis pipeline for a simulated incident."""
    from patchr.db.session import AsyncSessionLocal
    from patchr.services import incident_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalar_one_or_none()
        if incident:
            await incident_service.trigger_analysis(
                db,
                incident=incident,
                build_logs=build_logs,
            )


# ─── Patch Arena / Candidate Endpoints ────────────────────────────────────────


@router.get("/{incident_id}/candidates")
async def get_candidates(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[dict]:
    """
    Get all Patch Arena candidates for an incident.
    Returns Arena table with validation results for each candidate.
    """
    from patchr.db.models import PatchCandidate
    from patchr.services.repair_proof_service import get_all_candidates_proof

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return await get_all_candidates_proof(db, incident=incident)


@router.get("/{incident_id}/verification")
async def get_verification_proof(
    incident_id: uuid.UUID,
    candidate_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Get the Repair Proof for an incident's selected candidate.
    Exposes observed/inferred/synthetic/validated evidence labels.
    """
    from patchr.services.repair_proof_service import get_repair_proof

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    proof = await get_repair_proof(db, incident=incident, candidate_id=candidate_id)
    if not proof:
        raise HTTPException(status_code=404, detail="No verified candidate found")

    return proof


@router.post("/{incident_id}/arena")
async def trigger_arena(
    incident_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> dict:
    """
    Trigger the Patch Arena for an incident.
    Generates 2-3 candidates concurrently and validates each.
    Returns immediately; arena runs in background.
    """
    from patchr.db.models import Analysis

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Check that analysis exists
    analysis_result = await db.execute(
        select(Analysis).where(Analysis.incident_id == incident_id)
        .order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Incident must have a completed analysis before running Arena",
        )

    background_tasks.add_task(
        _run_arena_background,
        incident_id=str(incident_id),
        analysis_id=str(analysis.id),
    )

    return {
        "incident_id": str(incident_id),
        "status": "arena_started",
        "message": "Patch Arena running in background. Check /candidates for results.",
    }


@router.post("/{incident_id}/manual-review")
async def request_manual_review(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> dict:
    """
    Manually escalate an incident to human_review_required.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = IncidentStatus.HUMAN_REVIEW_REQUIRED
    incident.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action=AuditAction.INCIDENT_UPDATED,
        actor=actor_name(owner),
        details={"escalated_to": "manual_review_required", "by": "human"},
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    return {"incident_id": str(incident_id), "status": "manual_review_required"}


@router.get("/{incident_id}/timeline")
async def get_incident_timeline(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[dict]:
    """
    Get the incident timeline (audit logs ordered by created_at).
    Used for the left panel of the Visual Verification Workspace.
    """
    from patchr.db.models import AuditLog as AuditLogModel

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    logs_result = await db.execute(
        select(AuditLogModel)
        .where(AuditLogModel.incident_id == incident_id)
        .order_by(AuditLogModel.created_at)
    )
    logs = list(logs_result.scalars().all())

    return [
        {
            "id": str(log.id),
            "action": log.action.value if log.action else None,
            "actor": log.actor,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/{incident_id}/evidence")
async def get_incident_evidence(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Get all collected evidence for an incident.
    Returns deployment, analysis, and verification context.
    """
    from patchr.db.models import Analysis, Deployment

    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Get latest analysis
    analysis_result = await db.execute(
        select(Analysis).where(Analysis.incident_id == incident_id)
        .order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    # Get deployment
    deployment = None
    if incident.deployment_id:
        dep_result = await db.execute(
            select(Deployment).where(Deployment.id == incident.deployment_id)
        )
        deployment = dep_result.scalar_one_or_none()

    return {
        "incident_id": str(incident_id),
        "title": incident.title,
        "status": incident.status.value,
        "severity": incident.severity.value if incident.severity else None,
        "failure_type": incident.failure_type.value if incident.failure_type else None,
        "occurrence_count": incident.occurrence_count,
        "first_seen_at": incident.first_seen_at.isoformat() if incident.first_seen_at else None,
        "last_seen_at": incident.last_seen_at.isoformat() if incident.last_seen_at else None,
        "commit_sha": incident.commit_sha,
        "commit_message": incident.commit_message,
        "deployment": {
            "vercel_id": deployment.vercel_deployment_id if deployment else None,
            "state": deployment.state if deployment else None,
            "url": deployment.vercel_url if deployment else None,
            "build_logs_available": bool(deployment and deployment.build_logs),
        } if deployment else None,
        "analysis": {
            "failure_type": analysis.failure_type,
            "root_cause": analysis.root_cause,
            "affected_files": analysis.affected_files,
            "evidence": analysis.evidence,
            "confidence": analysis.confidence,
            "risk_level": analysis.risk_level,
            "verification_plan": analysis.verification_plan,
            "summary": analysis.summary,
        } if analysis else None,
    }


async def _run_arena_background(incident_id: str, analysis_id: str) -> None:
    """Background task: run Patch Arena for an incident."""
    from patchr.db.session import AsyncSessionLocal
    from patchr.db.models import Analysis
    from patchr.services.patch_arena import run_patch_arena

    async with AsyncSessionLocal() as db:
        inc_result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = inc_result.scalar_one_or_none()
        if not incident:
            return

        analysis_result = await db.execute(
            select(Analysis).where(Analysis.id == analysis_id)
        )
        analysis = analysis_result.scalar_one_or_none()
        if not analysis:
            return

        try:
            await run_patch_arena(db, incident=incident, analysis=analysis)
        except Exception as e:
            logger.error(
                "arena_background_task_failed",
                incident_id=incident_id,
                error=str(e),
            )
