"""
Deployment Poller Service

Actively scans connected repositories for failed deployments via the
GitHub Deployments API. Creates incidents for any new failures found.

This is the bridge that makes PatchR work WITHOUT relying on webhooks:
- On repo import: scan for recent failures
- On demand: POST /repositories/{id}/scan-deployments
- Periodically: frontend polls or backend scheduler triggers

Flow:
  1. Fetch recent deployments from GitHub (includes Vercel deploys)
  2. For each deployment with state == "failure" or "error":
     a. Check if we already have an incident for this commit
     b. If not, create one and trigger AI analysis
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.config import Settings, get_settings
from patchr.db.models import Incident, Repository

logger = structlog.get_logger(__name__)


async def scan_repo_deployments(
    db: AsyncSession,
    repo: Repository,
    settings: Settings | None = None,
    max_deployments: int = 10,
) -> list[dict]:
    """
    Scan a repository's GitHub deployments for failures.
    Creates incidents for any new failures found.

    Returns a list of newly created incident summaries.
    """
    if settings is None:
        settings = get_settings()

    github_token = settings.github_token
    if not github_token or github_token.startswith("ghp_your"):
        logger.warning("scan_skipped_no_token", repo=repo.full_name)
        return []

    from patchr.integrations.github import get_github_client, GitHubError

    try:
        async with get_github_client(github_token) as gh:
            deployments = await gh.get_recent_deployment_statuses(
                repo.full_name, limit=max_deployments
            )
    except GitHubError as e:
        logger.warning("scan_github_error", repo=repo.full_name, error=e.message)
        return []
    except Exception as e:
        logger.error("scan_unexpected_error", repo=repo.full_name, error=str(e))
        return []

    if not deployments:
        logger.debug("scan_no_deployments", repo=repo.full_name)
        return []

    # Find failed deployments
    failed = [
        d for d in deployments
        if d.get("state") in ("failure", "error")
    ]

    if not failed:
        logger.debug("scan_no_failures", repo=repo.full_name, total=len(deployments))
        return []

    logger.info(
        "scan_found_failures",
        repo=repo.full_name,
        failure_count=len(failed),
        total_deployments=len(deployments),
    )

    # Create incidents for failures we haven't seen yet
    created_incidents = []
    for dep in failed:
        commit_sha = dep.get("commit_sha") or ""
        if not commit_sha:
            continue

        # Deduplicate: skip if ANY incident already exists for this repo+commit (any status)
        from sqlalchemy import func
        count_result = await db.execute(
            select(func.count()).select_from(Incident).where(
                Incident.repository_id == repo.id,
                Incident.commit_sha == commit_sha,
            )
        )
        if count_result.scalar() > 0:
            logger.debug("scan_skip_duplicate", repo=repo.full_name, sha=commit_sha[:8])
            continue

        # Create the incident
        env_url = dep.get("environment_url", "")
        description = dep.get("description", "")
        environment = dep.get("environment", "production")

        error_description = (
            f"Deployment failed: {description}"
            if description
            else f"Deployment to {environment} failed"
        )

        incident = await _create_incident_from_scan(
            db,
            repo=repo,
            commit_sha=commit_sha,
            error_description=error_description,
            environment=environment,
            environment_url=env_url,
            deployment_id_str=str(dep.get("id", "")),
        )

        if incident:
            created_incidents.append({
                "incident_id": str(incident.id),
                "title": incident.title,
                "commit_sha": commit_sha[:8],
                "status": "detected",
            })

    if created_incidents:
        logger.info(
            "scan_incidents_created",
            repo=repo.full_name,
            count=len(created_incidents),
        )

    return created_incidents


async def scan_repo_and_analyze(
    repo_id: str,
    full_name: str,
    settings: Settings,
) -> None:
    """
    Background task: scan a repo for failed deployments and trigger AI analysis.
    Called after repo import or on-demand scan.
    """
    from patchr.db.session import AsyncSessionLocal
    from patchr.services import incident_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        if not repo:
            return

        created = await scan_repo_deployments(db, repo, settings)

        # Trigger AI analysis for each new incident
        if created and settings.nvidia_api_key and not settings.nvidia_api_key.startswith("nvapi-xxx"):
            for inc_info in created:
                try:
                    inc_result = await db.execute(
                        select(Incident).where(Incident.id == inc_info["incident_id"])
                    )
                    incident = inc_result.scalar_one_or_none()
                    if incident:
                        # Fetch build logs and commit context for analysis
                        build_logs = await _fetch_build_context(
                            full_name, incident.commit_sha, settings
                        )
                        await incident_service.trigger_analysis(
                            db,
                            incident=incident,
                            build_logs=build_logs,
                        )
                except Exception as e:
                    logger.warning(
                        "scan_analysis_trigger_failed",
                        incident_id=inc_info["incident_id"],
                        error=str(e),
                    )


async def scan_all_repos(settings: Settings | None = None) -> dict:
    """
    Scan ALL connected repositories for failed deployments.
    Returns a summary of what was found.
    """
    if settings is None:
        settings = get_settings()

    from patchr.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Repository).where(Repository.is_active == True)
        )
        repos = result.scalars().all()

        total_incidents = []
        for repo in repos:
            created = await scan_repo_deployments(db, repo, settings)
            total_incidents.extend(created)

    return {
        "repos_scanned": len(repos),
        "incidents_created": len(total_incidents),
        "incidents": total_incidents,
    }


# ─── Internal Helpers ──────────────────────────────────────────────────────────


async def _create_incident_from_scan(
    db: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    error_description: str,
    environment: str,
    environment_url: str,
    deployment_id_str: str,
) -> Incident | None:
    """Create an incident from a scanned deployment failure."""
    from patchr.db.models import AuditLog

    # Determine severity
    severity = "high" if environment.lower() == "production" else "medium"

    # Generate title
    title = f"Build Error: {error_description[:80]}"
    if "failed" not in title.lower() and "error" not in title.lower():
        title = f"Deployment Failed ({environment})"

    incident = Incident(
        id=uuid.uuid4(),
        repository_id=repo.id,
        title=title,
        status="detected",
        severity=severity,
        source="vercel_deployment",
        failure_type="build_error",
        commit_sha=commit_sha,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(incident)

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        incident_id=incident.id,
        action="incident_created",
        actor="system:deployment_scanner",
        details={
            "repo": repo.full_name,
            "sha": commit_sha,
            "environment": environment,
            "environment_url": environment_url,
            "error": error_description[:500],
            "source": "github_deployments_api",
        },
        entity_type="incident",
        entity_id=str(incident.id),
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(incident)

    logger.info(
        "incident_created_from_scan",
        incident_id=str(incident.id),
        repo=repo.full_name,
        sha=commit_sha[:8],
    )

    return incident


async def _fetch_build_context(
    full_name: str,
    commit_sha: str | None,
    settings: Settings,
) -> str | None:
    """
    Fetch rich build context for AI analysis:
    - Commit message
    - Unified diff of changed files (exact line changes, not just filenames)
    - GitHub Actions workflow error log (the actual build error message)

    This context is fed to the AI so it can generate an accurate patch
    instead of guessing from vague signals.
    """
    if not commit_sha or not settings.github_token or settings.github_token.startswith("ghp_your"):
        return None

    build_context_parts: list[str] = []

    try:
        from patchr.integrations.github import get_github_client
        async with get_github_client(settings.github_token) as gh:

            # ── 1. Commit metadata ────────────────────────────────────────
            try:
                commit_info = await gh.get_commit(full_name, commit_sha)
                if commit_info.message:
                    build_context_parts.append(f"Commit message: {commit_info.message.strip()}")
            except Exception:
                pass

            # ── 2. Unified diffs of changed files ────────────────────────
            # Pull raw commit data so we get the `patch` field per file
            try:
                raw_data = await gh._get(f"/repos/{full_name}/commits/{commit_sha}")
                files = raw_data.get("files", [])
                diff_sections: list[str] = []
                for f in files[:8]:  # cap at 8 files to stay within token budget
                    fname = f.get("filename", "?")
                    status = f.get("status", "modified")
                    patch = f.get("patch")  # unified diff text from GitHub
                    if patch:
                        diff_sections.append(
                            f"### {fname} ({status})\n```diff\n{patch[:1500]}\n```"
                        )
                    else:
                        diff_sections.append(f"### {fname} ({status}) — binary or no diff available")

                if diff_sections:
                    build_context_parts.append(
                        "CHANGED FILES (UNIFIED DIFF):\n" + "\n\n".join(diff_sections)
                    )
            except Exception as e:
                logger.warning("build_context_diff_fetch_failed", error=str(e))

            # ── 3. GitHub Actions build error log ────────────────────────
            try:
                workflow_logs = await gh.get_failed_workflow_logs(full_name, commit_sha)
                if workflow_logs:
                    # Cap at 3500 chars — enough to capture the key error
                    build_context_parts.append(
                        f"GITHUB ACTIONS BUILD ERROR:\n{workflow_logs[:3500]}"
                    )
            except Exception as e:
                logger.warning("build_context_workflow_logs_failed", error=str(e))

    except Exception as e:
        logger.warning("build_context_fetch_failed", full_name=full_name, error=str(e))

    if not build_context_parts:
        return None

    return "\n\n---\n\n".join(build_context_parts)



# ─── Runtime Error Monitoring ──────────────────────────────────────────────────


async def scan_runtime_errors(
    db: AsyncSession,
    repo: Repository,
    settings: Settings | None = None,
    since_minutes: int = 30,
    user_vercel_token: str | None = None,
    user_vercel_team_id: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Scan a repository's Vercel runtime logs for 500 errors.

    Requires the repo to have a vercel_project_id AND a Vercel token.
    Token resolution: user_vercel_token (from OAuth) > settings.vercel_access_token
    user_vercel_team_id: from the OAuth token exchange response (stored per-user in DB).
    Creates incidents for new runtime errors (grouped by path to avoid spam).

    Returns (created_incidents, error_message_if_any).
    """
    if settings is None:
        settings = get_settings()

    if not repo.vercel_project_id:
        return ([], "Repository has no linked Vercel project")

    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User as _User

    # ── Token resolution strategy ─────────────────────────────────────────────
    # Build a list of (token, team_id) candidates to try in priority order:
    #   1. The current user's OAuth token + their team_id
    #   2. All other users' Vercel tokens from the DB
    #   3. Global VERCEL_ACCESS_TOKEN from settings (legacy)
    #
    # This is necessary because the Vercel project may belong to a different
    # Vercel account than the user currently logged into PatchR.  We try all
    # available tokens and use the first one that can actually read logs.

    candidates: list[tuple[str, str | None]] = []

    primary_token = user_vercel_token or settings.vercel_access_token
    if primary_token:
        effective_team_id = user_vercel_team_id or settings.vercel_team_id or None
        candidates.append((primary_token, effective_team_id))

    # Pull all other users' tokens from DB as fallback
    try:
        users_result = await db.execute(
            select(_User).where(_User.vercel_access_token.isnot(None))
        )
        for db_user in users_result.scalars().all():
            tok = db_user.vercel_access_token
            tid = getattr(db_user, "vercel_team_id", None)
            pair = (tok, tid)
            if pair not in candidates:
                candidates.append(pair)
    except Exception:
        pass  # If DB query fails, continue with what we have

    if not candidates:
        logger.warning("runtime_scan_no_tokens", repo=repo.full_name)
        return ([], "No Vercel tokens available")

    logger.info(
        "runtime_scan_starting",
        repo=repo.full_name,
        project_id=repo.vercel_project_id,
        candidate_count=len(candidates),
        since_minutes=since_minutes,
    )

    error_logs: list[dict] = []
    last_error: str | None = None

    for idx, (token, team_id) in enumerate(candidates):
        try:
            async with get_vercel_client(token, team_id=team_id) as vercel:
                logs = await vercel.get_error_logs(
                    repo.vercel_project_id,
                    since_minutes_ago=since_minutes,
                    limit=50,
                )
            logger.info(
                "runtime_scan_raw_logs",
                repo=repo.full_name,
                token_index=idx,
                token_prefix=token[:8],
                log_count=len(logs),
                sample=logs[:2] if logs else [],
            )
            error_logs = logs
            last_error = None
            break  # success — stop trying more tokens
        except VercelError as e:
            last_error = f"HTTP {e.status}: {e.message}"
            logger.warning(
                "runtime_scan_token_failed",
                repo=repo.full_name,
                token_index=idx,
                token_prefix=token[:8],
                status=e.status,
                error=e.message,
            )
            continue  # try next token
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "runtime_scan_token_exception",
                repo=repo.full_name,
                token_index=idx,
                token_prefix=token[:8],
                error=str(e),
            )
            continue

    if not error_logs and last_error:
        # All tokens tried and failed — log a summary
        logger.warning(
            "runtime_scan_all_tokens_failed",
            repo=repo.full_name,
            candidates_tried=len(candidates),
            last_error=last_error,
        )
        return ([], last_error)

    if not error_logs:
        return ([], None)

    logger.info("runtime_errors_found", repo=repo.full_name, count=len(error_logs))

    # Group errors by path to avoid creating one incident per request
    error_paths: dict[str, list[dict]] = {}
    for err in error_logs:
        path = err.get("path", "/unknown")
        error_paths.setdefault(path, []).append(err)

    created_incidents = []
    skipped_existing = 0
    for path, errors in error_paths.items():
        # Check if we already have a recent runtime error incident for this path
        from patchr.db.models import Incident
        existing = await db.execute(
            select(Incident).where(
                Incident.repository_id == repo.id,
                Incident.title.contains(path),
                Incident.source == "vercel_deployment",
                Incident.failure_type == "runtime_error",
                Incident.status.notin_(["resolved", "dismissed"]),
            )
        )
        if existing.scalar_one_or_none():
            skipped_existing += 1
            continue

        # Create incident for this error path
        error_count = len(errors)
        first_error = errors[0]
        status_code = first_error.get("status_code", 500)
        message = first_error.get("message", "")

        title = f"Runtime Error: {first_error.get('method', 'GET')} {path} → {status_code}"
        if error_count > 1:
            title += f" ({error_count} occurrences)"

        # Build a summary of the errors for AI analysis
        error_summary = f"Runtime errors detected on {repo.full_name}\n"
        error_summary += f"Path: {path}\n"
        error_summary += f"Status: {status_code}\n"
        error_summary += f"Occurrences: {error_count} in last {since_minutes} minutes\n"
        error_summary += f"Host: {first_error.get('host', '?')}\n"
        if message:
            error_summary += f"\nError message:\n{message[:500]}\n"

        # Get latest deployment commit for context
        latest_commit_sha = None
        try:
            from patchr.integrations.github import get_github_client
            if settings.github_token:
                async with get_github_client(settings.github_token) as gh:
                    deploys = await gh.get_deployments(repo.full_name, limit=1)
                    if deploys:
                        latest_commit_sha = deploys[0].get("sha")
        except Exception:
            pass

        incident = Incident(
            id=uuid.uuid4(),
            repository_id=repo.id,
            title=title,
            status="detected",
            severity="high" if error_count >= 3 else "medium",
            source="vercel_deployment",
            failure_type="runtime_error",
            commit_sha=latest_commit_sha,
            commit_message=error_summary[:500],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(incident)

        from patchr.db.models import AuditLog
        audit = AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action="incident_created",
            actor="system:runtime_monitor",
            details={
                "repo": repo.full_name,
                "path": path,
                "status_code": status_code,
                "error_count": error_count,
                "message": message[:200],
                "source": "vercel_runtime_logs",
            },
            entity_type="incident",
            entity_id=str(incident.id),
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        await db.commit()
        await db.refresh(incident)

        created_incidents.append({
            "incident_id": str(incident.id),
            "title": title,
            "path": path,
            "error_count": error_count,
            "status": "detected",
        })

        logger.info(
            "runtime_incident_created",
            incident_id=str(incident.id),
            repo=repo.full_name,
            path=path,
            error_count=error_count,
        )

    return (created_incidents, None)
