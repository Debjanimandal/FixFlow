"""
Webhooks Router — Phase 2

Receives events from GitHub and Vercel.
Public endpoints secured via HMAC signature verification.

GitHub events processed:
  - deployment_status: Vercel deployment result (most important)
  - push: commit metadata for correlation

Vercel events processed:
  - deployment.error: failed deployment with build logs
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.config import Settings, get_settings
from patchr.db.models import Repository
from patchr.db.session import get_db
from patchr.schemas.api import WebhookAckResponse
from patchr.services import incident_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ─── Signature Verification ───────────────────────────────────────────────────


def _verify_github_signature(
    payload_body: bytes,
    signature_header: str | None,
    webhook_secret: str,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256. Header: X-Hub-Signature-256: sha256=<hex>"""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header[7:]
    mac = hmac.new(webhook_secret.encode(), payload_body, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected)


def _verify_vercel_signature(
    payload_body: bytes,
    signature_header: str | None,
    webhook_secret: str,
) -> bool:
    """Verify Vercel webhook HMAC-SHA1. Header: x-vercel-signature: <hex>"""
    if not signature_header:
        return False
    mac = hmac.new(webhook_secret.encode(), payload_body, hashlib.sha1)
    return hmac.compare_digest(mac.hexdigest(), signature_header)


# ─── GitHub Webhook ───────────────────────────────────────────────────────────


@router.post("/github", response_model=WebhookAckResponse)
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookAckResponse:
    """
    Receive GitHub webhook events.

    Acknowledges immediately (200 OK) then processes in background.
    GitHub requires a fast response to avoid retries.

    Supported events:
    - deployment_status → incident detection for failed deployments
    - push → commit metadata correlation
    """
    body = await request.body()

    # ── Signature verification ────────────────────────────────────────────────
    if settings.github_webhook_secret:
        if not _verify_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
            logger.warning(
                "github_webhook_invalid_signature",
                delivery=x_github_delivery,
                gh_event=x_github_event,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    repo_full_name = payload.get("repository", {}).get("full_name", "unknown")
    logger.info(
        "github_webhook_received",
        gh_event=x_github_event,
        delivery=x_github_delivery,
        repo=repo_full_name,
    )

    # ── Route to event handlers ───────────────────────────────────────────────
    if x_github_event == "deployment_status":
        background_tasks.add_task(
            _process_deployment_status,
            payload=payload,
            settings=settings,
        )
        return WebhookAckResponse(message="deployment_status queued for processing")

    if x_github_event == "push":
        background_tasks.add_task(
            _process_push_event,
            payload=payload,
            settings=settings,
        )
        return WebhookAckResponse(message="push event queued for processing")

    if x_github_event == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        merged = pr.get("merged", False)
        if action == "closed" and merged:
            background_tasks.add_task(
                _process_pr_merged,
                payload=payload,
                settings=settings,
            )
            return WebhookAckResponse(message="pull_request merged queued for post-merge guard")
        return WebhookAckResponse(message=f"pull_request action '{action}' acknowledged (not processed)")

    # Unhandled events — ack and ignore
    return WebhookAckResponse(message=f"event '{x_github_event}' acknowledged (not processed)")


# ─── GitHub Event Processors ──────────────────────────────────────────────────


async def _process_deployment_status(payload: dict, settings: Settings) -> None:
    """
    Process a GitHub deployment_status event.

    - "failure"/"error": create incident + trigger AI analysis
    - "success": if repo has an incident in RECOVERY_MONITORING, auto-resolve it
    """
    from patchr.db.session import AsyncSessionLocal

    dep_status = payload.get("deployment_status", {})
    deployment = payload.get("deployment", {})
    repository = payload.get("repository", {})

    state = dep_status.get("state", "")
    repo_full_name = repository.get("full_name", "")
    commit_sha = deployment.get("sha", "")
    environment = deployment.get("environment", "production")
    error_description = dep_status.get("description", f"Deployment {state}")
    vercel_deployment_id = dep_status.get("target_url", "").split("/")[-1] or None

    logger.info(
        "deployment_status_received",
        repo=repo_full_name,
        sha=commit_sha[:8] if commit_sha else "?",
        environment=environment,
        state=state,
    )

    # ── Successful deploy: check if we need to auto-resolve a recovering incident ──
    if state == "success":
        try:
            from patchr.services.pr_monitor_service import resolve_recovered_incident
            from patchr.db.models import Incident, IncidentStatus
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(Incident)
                    .join(Incident.repository)
                    .where(
                        Incident.status == IncidentStatus.RECOVERY_MONITORING,
                    )
                )
                recovering = result.scalars().all()
                for inc in recovering:
                    # Resolve any incident that was monitoring this repo's recovery
                    from patchr.db.models import Repository as RepoModel
                    repo_result = await db.execute(
                        select(RepoModel).where(RepoModel.id == inc.repository_id)
                    )
                    repo = repo_result.scalar_one_or_none()
                    if repo and repo.full_name == repo_full_name:
                        await resolve_recovered_incident(str(inc.id))
                        logger.info("auto_resolved_incident", incident_id=str(inc.id), repo=repo_full_name)
        except Exception as e:
            logger.warning("recovery_check_failed", error=str(e))
        return

    # ── Failed deploy: create incident + run AI analysis ─────────────────────
    if state not in ("failure", "error"):
        logger.debug("deployment_status_ignored", state=state)
        return

    # Fetch commit context from GitHub
    commit_message = None
    build_logs = None
    commit_diff = None
    file_contents = {}

    if settings.github_token and not settings.github_token.startswith("ghp_your"):
        try:
            from patchr.integrations.github import get_github_client
            async with get_github_client(settings.github_token) as gh:
                commit_info = await gh.get_commit(repo_full_name, commit_sha)
                commit_message = commit_info.message

                if commit_info.all_changed_files:
                    files = await gh.get_multiple_files(
                        repo_full_name,
                        commit_info.all_changed_files,
                        ref=commit_sha,
                        max_files=8,
                    )
                    file_contents = {path: fc.content for path, fc in files.items()}

        except Exception as e:
            logger.warning("github_context_fetch_failed", error=str(e), repo=repo_full_name)

    # Phase B: Fetch Vercel build logs if token is configured and we have a deployment ID
    if vercel_deployment_id and settings.vercel_access_token and not settings.vercel_access_token.startswith("your_vercel"):
        try:
            from patchr.integrations.vercel import get_vercel_client
            async with get_vercel_client(
                settings.vercel_access_token,
                team_id=settings.vercel_team_id or None,
            ) as vercel:
                build_logs = await vercel.get_build_logs_as_text(vercel_deployment_id, max_lines=300)
                logger.info("vercel_build_logs_fetched", deployment_id=vercel_deployment_id, chars=len(build_logs))
        except Exception as e:
            logger.warning("vercel_build_logs_failed", error=str(e), deployment_id=vercel_deployment_id)

    # Create incident + run analysis
    async with AsyncSessionLocal() as db:
        incident = await incident_service.create_incident_from_github_deployment(
            db,
            repository_full_name=repo_full_name,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deployment_vercel_id=vercel_deployment_id,
            error_description=error_description,
            build_logs=build_logs,
            environment=environment,
        )

        if incident:
            await incident_service.trigger_analysis(
                db,
                incident=incident,
                commit_diff=commit_diff,
                build_logs=build_logs,
                file_contents=file_contents,
            )


async def _process_push_event(payload: dict, settings: Settings) -> None:
    """
    Process a GitHub push event.

    Stores commit metadata and updates the repository record.
    Does not create incidents — those come from deployment_status events.

    Payload shape:
    {
      "ref": "refs/heads/main",
      "head_commit": { "id": "sha", "message": "...", "modified": [...], ... },
      "repository": { "full_name": "owner/repo", "id": 12345, "default_branch": "main" }
    }
    """
    from patchr.db.session import AsyncSessionLocal

    ref = payload.get("ref", "")
    head_commit = payload.get("head_commit", {})
    repository = payload.get("repository", {})

    repo_full_name = repository.get("full_name", "")
    github_id = repository.get("id", 0)
    default_branch = repository.get("default_branch", "main")
    pushed_branch = ref.replace("refs/heads/", "")

    logger.info(
        "push_event_received",
        repo=repo_full_name,
        branch=pushed_branch,
        sha=(head_commit.get("id", "")[:8] if head_commit.get("id") else "?"),
    )

    # Update repository metadata if it's registered
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Repository).where(Repository.full_name == repo_full_name)
        )
        repo = result.scalar_one_or_none()
        if repo:
            repo.github_id = repo.github_id or github_id
            repo.default_branch = default_branch
            repo.updated_at = datetime.now(timezone.utc)
            await db.commit()
            logger.debug("repository_updated_from_push", repo=repo_full_name)


# ─── Vercel Webhook ───────────────────────────────────────────────────────────


@router.post("/vercel", response_model=WebhookAckResponse)
async def receive_vercel_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_vercel_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookAckResponse:
    """
    Receive Vercel deployment webhook events.

    Vercel events:
    - deployment.error: failed deployment with build logs → create incident
    - deployment.ready: successful deployment (record baseline only)

    Vercel webhooks send build logs directly in the payload — richer than
    GitHub deployment_status events. We use both: Vercel for logs, GitHub
    for commit diff and file content.
    """
    body = await request.body()

    if settings.vercel_webhook_secret:
        if not _verify_vercel_signature(body, x_vercel_signature, settings.vercel_webhook_secret):
            logger.warning("vercel_webhook_invalid_signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event_type = payload.get("type", "unknown")
    dep_payload = payload.get("payload", {})
    deployment = dep_payload.get("deployment", {})
    deployment_id = deployment.get("id", "unknown")
    project_name = dep_payload.get("project", {}).get("name", "unknown")

    logger.info(
        "vercel_webhook_received",
        event_type=event_type,
        deployment_id=deployment_id,
        project=project_name,
    )

    if event_type == "deployment.error":
        background_tasks.add_task(
            _process_vercel_deployment_error,
            payload=payload,
            settings=settings,
        )
        return WebhookAckResponse(message="deployment.error queued for processing")

    if event_type == "deployment.ready":
        background_tasks.add_task(
            _process_vercel_deployment_ready,
            payload=payload,
            settings=settings,
        )
        return WebhookAckResponse(message="deployment.ready queued for processing")

    return WebhookAckResponse(message=f"Vercel event '{event_type}' acknowledged")


async def _process_vercel_deployment_error(payload: dict, settings: Settings) -> None:
    """
    Process a Vercel deployment.error event.

    Vercel payload (simplified):
    {
      "type": "deployment.error",
      "payload": {
        "deployment": {
          "id": "dpl_xxx",
          "url": "my-app.vercel.app",
          "meta": { "githubCommitSha": "abc123", "githubCommitMessage": "..." }
        },
        "project": { "id": "prj_xxx", "name": "my-app" },
        "links": { "deployment": "https://vercel.com/..." },
        "build": { "output": "...build logs..." }  # may be present
      }
    }
    """
    from patchr.db.session import AsyncSessionLocal

    dep_payload = payload.get("payload", {})
    deployment = dep_payload.get("deployment", {})
    project = dep_payload.get("project", {})
    build = dep_payload.get("build", {})

    vercel_deployment_id = deployment.get("id", "")
    vercel_project_id = project.get("id", "")
    meta = deployment.get("meta", {})

    commit_sha = meta.get("githubCommitSha") or meta.get("commitSha", "")
    commit_message = meta.get("githubCommitMessage") or meta.get("commitMessage")
    repo_full_name = meta.get("githubRepo") or meta.get("githubCommitRepo", "")
    build_logs = build.get("output", "") or dep_payload.get("logs", "")
    error_message = deployment.get("errorMessage") or "Vercel deployment failed"

    logger.info(
        "vercel_deployment_error",
        deployment_id=vercel_deployment_id,
        project=project.get("name"),
        sha=commit_sha[:8] if commit_sha else "?",
    )

    if not repo_full_name or not commit_sha:
        logger.warning(
            "vercel_event_missing_github_context",
            deployment_id=vercel_deployment_id,
        )
        return

    # Fetch additional context from GitHub
    file_contents = {}
    if settings.github_token and not settings.github_token.startswith("ghp_your"):
        try:
            from patchr.integrations.github import get_github_client
            async with get_github_client(settings.github_token) as gh:
                commit_info = await gh.get_commit(repo_full_name, commit_sha)
                if not commit_message:
                    commit_message = commit_info.message

                if commit_info.all_changed_files:
                    files = await gh.get_multiple_files(
                        repo_full_name,
                        commit_info.all_changed_files,
                        ref=commit_sha,
                        max_files=8,
                    )
                    file_contents = {path: fc.content for path, fc in files.items()}

        except Exception as e:
            logger.warning("github_context_fetch_failed", error=str(e))

    # Combine Vercel error + build logs as the primary failure signal
    full_error = f"{error_message}\n\n{build_logs[:4000]}" if build_logs else error_message

    async with AsyncSessionLocal() as db:
        incident = await incident_service.create_incident_from_github_deployment(
            db,
            repository_full_name=repo_full_name,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deployment_vercel_id=vercel_deployment_id,
            error_description=full_error,
            build_logs=build_logs or None,
            environment=deployment.get("target", "production"),
        )

        if incident:
            await incident_service.trigger_analysis(
                db,
                incident=incident,
                build_logs=build_logs or None,
                file_contents=file_contents,
            )


async def _process_vercel_deployment_ready(payload: dict, settings: Settings) -> None:
    """
    Process a Vercel deployment.ready event.

    A successful Vercel deployment after a PR merge means the fix worked.
    If the repo has an incident in RECOVERY_MONITORING, auto-resolve it.
    """
    from patchr.db.session import AsyncSessionLocal

    dep_payload = payload.get("payload", {})
    deployment = dep_payload.get("deployment", {})
    meta = deployment.get("meta", {})

    repo_full_name = meta.get("githubRepo") or meta.get("githubCommitRepo", "")
    deployment_id = deployment.get("id", "unknown")

    logger.info(
        "vercel_deployment_ready",
        deployment_id=deployment_id,
        repo=repo_full_name,
    )

    if not repo_full_name:
        logger.debug("vercel_ready_no_repo_context", deployment_id=deployment_id)
        return

    try:
        from patchr.services.pr_monitor_service import resolve_recovered_incident
        from patchr.db.models import Incident, IncidentStatus, Repository as RepoModel
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            # Find repos matching this full_name
            repo_result = await db.execute(
                select(RepoModel).where(RepoModel.full_name == repo_full_name)
            )
            repo = repo_result.scalar_one_or_none()
            if not repo:
                return

            # Find incidents in RECOVERY_MONITORING for this repo
            inc_result = await db.execute(
                select(Incident).where(
                    Incident.repository_id == repo.id,
                    Incident.status == IncidentStatus.RECOVERY_MONITORING,
                )
            )
            recovering = inc_result.scalars().all()
            for inc in recovering:
                await resolve_recovered_incident(str(inc.id))
                logger.info(
                    "vercel_ready_auto_resolved",
                    incident_id=str(inc.id),
                    repo=repo_full_name,
                    deployment_id=deployment_id,
                )
    except Exception as e:
        logger.warning("vercel_ready_resolution_failed", error=str(e), repo=repo_full_name)


async def _process_pr_merged(payload: dict, settings: Settings) -> None:
    """
    Process a GitHub pull_request closed+merged event.
    Hands off to Post-Merge Guard if the PR belongs to a PatchR incident.
    """
    from patchr.db.session import AsyncSessionLocal
    from patchr.services.post_merge_guard import handle_pr_merged

    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_url = pr.get("html_url")
    merged_at_str = pr.get("merged_at")
    commit_sha = pr.get("merge_commit_sha")

    if not pr_number:
        logger.warning("pr_merged_missing_number")
        return

    merged_at = None
    if merged_at_str:
        try:
            from datetime import datetime, timezone
            merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
        except Exception:
            pass

    logger.info(
        "pr_merged_processing",
        pr_number=pr_number,
        pr_url=pr_url,
    )

    try:
        async with AsyncSessionLocal() as db:
            incident = await handle_pr_merged(
                db,
                pr_number=pr_number,
                pr_url=pr_url,
                merged_at=merged_at,
                commit_sha=commit_sha,
            )
            if incident:
                logger.info(
                    "post_merge_guard_triggered",
                    incident_id=str(incident.id),
                    pr_number=pr_number,
                )
    except Exception as e:
        logger.error("pr_merged_processing_failed", pr_number=pr_number, error=str(e))


@router.post("/runtime-error", summary="Ingest client-side or backend runtime errors")
async def ingest_runtime_error(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Public telemetry webhook endpoint for applications to report live runtime exceptions.
    Matches repository by repo_id or repo_full_name.
    Creates a runtime_error incident and triggers NVIDIA AI analysis.
    """
    from patchr.db.models import Incident, AuditLog

    repo_id_str = payload.get("repo_id") or payload.get("repository_id")
    repo_full_name = payload.get("repo_full_name") or payload.get("repository")

    repo = None
    if repo_id_str:
        try:
            repo_uuid = uuid.UUID(repo_id_str)
            res = await db.execute(select(Repository).where(Repository.id == repo_uuid))
            repo = res.scalar_one_or_none()
        except Exception:
            pass

    if not repo and repo_full_name:
        res = await db.execute(
            select(Repository).where(Repository.full_name.ilike(repo_full_name.strip()))
        )
        repo = res.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found for provided identifier")

    path = payload.get("path") or payload.get("url") or "/unknown"
    error_msg = payload.get("message") or payload.get("error") or "Unhandled runtime exception"
    stack = payload.get("stack") or ""
    status_code = payload.get("status_code", 500)
    title = f"Runtime Error: {payload.get('method', 'GET')} {path} -> {status_code}"

    full_context = f"{error_msg}\n{stack}".strip()
    now = datetime.now(timezone.utc)

    incident = Incident(
        id=uuid.uuid4(),
        repository_id=repo.id,
        title=title,
        status="detected",
        severity="high" if status_code >= 500 else "medium",
        source="runtime_error",
        failure_type="runtime_error",
        commit_message=full_context[:500],
        created_at=now,
        updated_at=now,
    )
    db.add(incident)

    audit = AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action="incident_created",
        actor="telemetry:client",
        details={
            "repo": repo.full_name,
            "path": path,
            "message": error_msg[:200],
            "status_code": status_code,
            "user_agent": payload.get("user_agent", ""),
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=now,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(incident)

    # Queue AI analysis if NVIDIA NIM configured
    if settings.nvidia_api_key and not settings.nvidia_api_key.startswith("nvapi-xxx"):
        from patchr.routers.repositories import _trigger_analysis_for_incident
        background_tasks.add_task(
            _trigger_analysis_for_incident,
            incident_id=str(incident.id),
            full_name=repo.full_name,
            settings=settings,
        )

    return {
        "status": "received",
        "incident_id": str(incident.id),
        "title": title,
        "message": "Runtime error recorded. PatchR AI incident analysis queued.",
    }
