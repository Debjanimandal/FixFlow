"""
Repositories Router â€” Phase 3

CRUD for connected GitHub repositories.
Now with:
  - Auto-sync GitHub metadata on connect (name, default branch, github_id)
  - Vercel project linking
  - Webhook registration status
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.auth import get_current_owner
from patchr.config import Settings, get_settings
from patchr.db.models import Repository, User
from patchr.db.session import get_db_or_503 as get_db
from patchr.schemas.api import RepositoryCreate, RepositoryResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _parse_uuid(val: str | None) -> uuid.UUID | None:
    """Safely convert a string user_id from JWT to uuid.UUID for SQLite compatibility."""
    if not val:
        return None
    try:
        return uuid.UUID(val)
    except (ValueError, AttributeError):
        return None


async def _get_user_by_id(db: AsyncSession, user_id: str | None) -> User | None:
    """Safely resolve User from string user_id (UUID or github_{numeric})."""
    if not user_id:
        return None
    if user_id.startswith("github_"):
        try:
            gh_id = int(user_id[len("github_"):])
        except ValueError:
            return None
        result = await db.execute(select(User).where(User.github_id == gh_id))
        return result.scalar_one_or_none()
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


@router.get("/github-repos")
async def list_github_repos(
    q: str = "",
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> list[dict]:
    """
    Fetch repos accessible to the logged-in GitHub user.
    Uses their OAuth access token from the JWT (so you only see YOUR repos).
    Falls back to GITHUB_TOKEN if no user token is in the JWT.
    """
    import httpx

    # Prefer the user's own OAuth token â€” only then filter by their login
    user_token = current_user.get("github_access_token", "")
    token_to_use = user_token or settings.github_token
    github_login = current_user.get("github_login", "")

    headers = {
        "Authorization": f"Bearer {token_to_use}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    all_repos: list[dict] = []
    page = 1
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"GitHub API error: {resp.text}")
            batch = resp.json()
            if not batch:
                break
            all_repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    results = [
        {
            "id": r["id"],
            "name": r["name"],
            "full_name": r["full_name"],
            "private": r["private"],
            "description": r.get("description") or "",
            "default_branch": r.get("default_branch", "main"),
            "updated_at": r.get("updated_at", ""),
            "html_url": r.get("html_url", ""),
            "language": r.get("language") or "",
        }
        for r in all_repos
        # If we used the user's own token, show all their repos.
        # If falling back to static GITHUB_TOKEN, filter to only show the logged-in user's repos.
        if (user_token) or (not github_login) or r["full_name"].lower().startswith(github_login.lower() + "/")
    ]

    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in r["full_name"].lower()]

    return results


@router.get("/vercel-projects")
async def list_vercel_projects(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> list[dict]:
    """
    Fetch Vercel projects using the logged-in user's personal Vercel token
    (saved in Settings). Falls back to VERCEL_ACCESS_TOKEN in .env.
    """
    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User

    # 1. Try user's own stored token first
    vercel_token = None
    user_id = current_user.get("user_id")
    if user_id:
        db_user = await _get_user_by_id(db, user_id)
        if db_user and db_user.vercel_access_token:
            vercel_token = db_user.vercel_access_token

    # 2. Fall back to global .env VERCEL_ACCESS_TOKEN if user has none
    if not vercel_token:
        vercel_token = settings.vercel_access_token
    if not vercel_token:
        raise HTTPException(
            status_code=503,
            detail="No Vercel token found. Go to Settings > Vercel Account and paste your Vercel API token.",
        )

    try:
        async with get_vercel_client(vercel_token) as vercel:
            projects = await vercel.list_all_projects(limit=100)
    except VercelError as e:
        raise HTTPException(status_code=502, detail=f"Vercel API error: {e.message}")

    return [
        {
            "id": p.id,
            "name": p.name,
            "framework": p.framework,
            "linked_repo": p.linked_repo,
        }
        for p in projects
    ]


@router.post("/vercel-sync")
async def sync_vercel_projects(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Auto-match Vercel projects to connected GitHub repos.
    Uses the user's stored Vercel token (from Settings) or falls back to .env.
    """
    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User

    # Resolve the right Vercel token
    vercel_token = None
    user_id = current_user.get("user_id")
    if user_id:
        db_user = await _get_user_by_id(db, user_id)
        if db_user and db_user.vercel_access_token:
            vercel_token = db_user.vercel_access_token
    # Fall back to global .env VERCEL_ACCESS_TOKEN if no user token
    if not vercel_token:
        vercel_token = settings.vercel_access_token

    try:
        async with get_vercel_client(vercel_token) as vercel:
            vercel_projects = await vercel.list_all_projects(limit=100)
    except VercelError as e:
        raise HTTPException(status_code=502, detail=f"Vercel API error: {e.message}")

    # Load all connected GitHub repos from DB
    repo_result = await db.execute(select(Repository))
    connected_repos = {r.full_name.lower(): r for r in repo_result.scalars().all()}

    linked = 0
    already_linked = 0
    unmatched: list[str] = []

    for project in vercel_projects:
        if not project.linked_repo:
            unmatched.append(project.name)
            continue

        repo_key = project.linked_repo.lower()
        repo = connected_repos.get(repo_key)

        if repo is None:
            unmatched.append(project.name)
            continue

        if repo.vercel_project_id == project.id:
            already_linked += 1
            continue

        repo.vercel_project_id = project.id
        repo.vercel_project_name = project.name
        repo.updated_at = datetime.now(timezone.utc)
        linked += 1
        logger.info("vercel_auto_linked", repo=repo.full_name, vercel_project=project.name)

    if linked > 0:
        await db.commit()

    return {
        "linked": linked,
        "already_linked": already_linked,
        "unmatched_vercel_projects": unmatched,
        "message": (
            f"Auto-linked {linked} repo(s) to Vercel."
            if linked > 0
            else "No auto-matches found. Use 'link anyway' in Repositories to link manually."
        ),
    }


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[RepositoryResponse]:
    """List all connected repositories."""
    result = await db.execute(select(Repository).order_by(Repository.created_at.desc()))
    repos = result.scalars().all()
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> RepositoryResponse:
    """Get a single connected repository by ID."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return RepositoryResponse.model_validate(repo)


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    body: RepositoryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> RepositoryResponse:
    """
    Connect a GitHub repository to PatchR.

    - Validates the full_name format
    - Creates the repository record
    - Auto-syncs GitHub metadata in the background (github_id, default_branch)
    - Vercel project_id can be linked for enhanced log fetching
    """
    if "/" not in body.full_name or body.full_name.count("/") != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="full_name must be in 'owner/repo' format",
        )

    # Check for duplicate
    result = await db.execute(
        select(Repository).where(Repository.full_name == body.full_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository '{body.full_name}' is already connected",
        )

    repo = Repository(
        id=uuid.uuid4(),
        name=body.full_name.split("/")[-1],
        full_name=body.full_name,
        # Use a unique negative placeholder so the UNIQUE(github_id) constraint
        # doesn't collide when importing multiple repos before the background
        # GitHub sync fills in the real ID.
        github_id=-(abs(hash(body.full_name)) % (10**15)),
        vercel_project_id=body.vercel_project_id,
        vercel_project_name=body.vercel_project_name,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Sync GitHub metadata in background (non-blocking)
    if settings.github_token and not settings.github_token.startswith("ghp_your"):
        background_tasks.add_task(
            _sync_github_metadata,
            repo_id=str(repo.id),
            full_name=body.full_name,
            settings=settings,
        )

    # Auto-detect Vercel project linked to this GitHub repo (non-blocking)
    # Uses GitHub Deployments API first (works for any user), falls back to Vercel API
    if not body.vercel_project_id:
        background_tasks.add_task(
            _auto_detect_vercel,
            repo_id=str(repo.id),
            full_name=body.full_name,
            settings=settings,
        )

    # Scan for existing deployment failures and create incidents (non-blocking)
    background_tasks.add_task(
        _scan_deployments_on_import,
        repo_id=str(repo.id),
        full_name=body.full_name,
        settings=settings,
    )

    logger.info("repository_connected", full_name=body.full_name, repo_id=str(repo.id))
    return RepositoryResponse.model_validate(repo)


@router.patch("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(
    repo_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> RepositoryResponse:
    """Update repository settings (Vercel project_id, active status)."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if "vercel_project_id" in body:
        repo.vercel_project_id = body["vercel_project_id"]
    if "vercel_project_name" in body:
        repo.vercel_project_name = body["vercel_project_name"]
    if "is_active" in body:
        repo.is_active = body["is_active"]

    repo.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(repo)
    return RepositoryResponse.model_validate(repo)


@router.post("/{repo_id}/sync", response_model=RepositoryResponse)
async def sync_repository(
    repo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> RepositoryResponse:
    """Force-sync repository metadata from GitHub."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if not settings.github_token or settings.github_token.startswith("ghp_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_TOKEN not configured",
        )

    background_tasks.add_task(
        _sync_github_metadata,
        repo_id=str(repo.id),
        full_name=repo.full_name,
        settings=settings,
    )

    return RepositoryResponse.model_validate(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> None:
    """Disconnect a repository. Cascades to deployments and incidents."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    await db.delete(repo)
    await db.commit()


# â”€â”€â”€ Deployment Status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/{repo_id}/deployment-status")
async def get_deployment_status(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Fetch live deployment status for a repository.

    Two modes:
    1. If vercel_project_id is set AND a Vercel token is available â†’ use Vercel API
       (gives full deployment details, build logs, etc.)
    2. Otherwise â†’ use GitHub Deployments API (works for ANY repo deployed via Vercel,
       without needing a Vercel token â€” just uses the user's GitHub OAuth token)
    """
    from patchr.db.models import User

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # â”€â”€ Mode 1: Full Vercel API (if project ID + token available) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if repo.vercel_project_id:
        vercel_token: str | None = None
        user_id = current_user.get("user_id")
        if user_id:
            try:
                db_user = await _get_user_by_id(db, user_id)
                if db_user and db_user.vercel_access_token:
                    vercel_token = db_user.vercel_access_token
            except Exception:
                pass
        if not vercel_token:
            vercel_token = settings.vercel_access_token

        if vercel_token:
            try:
                from patchr.integrations.vercel import get_vercel_client, VercelError
                async with get_vercel_client(vercel_token, team_id=settings.vercel_team_id or None) as vercel:
                    deployments = await vercel.list_recent_deployments(
                        project_id=repo.vercel_project_id,
                        limit=5,
                    )
                latest_state = deployments[0].state if deployments else None
                return {
                    "linked": True,
                    "source": "vercel_api",
                    "latest_state": latest_state,
                    "vercel_project_name": repo.vercel_project_name,
                    "deployments": [
                        {
                            "id": d.id,
                            "state": d.state,
                            "url": d.url,
                            "branch": d.branch,
                            "commit_sha": d.commit_sha,
                            "commit_message": d.commit_message,
                            "created_at": d.created_at,
                            "error_message": d.error_message,
                        }
                        for d in deployments
                    ],
                }
            except Exception as e:
                logger.debug("vercel_api_fallback_to_github", error=str(e))
                # Fall through to GitHub mode

    # â”€â”€ Mode 2: GitHub Deployments API (works for any user's repo) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    github_token = settings.github_token
    # Prefer user's own token from JWT if available
    user_github_token = current_user.get("github_access_token")
    if user_github_token:
        github_token = user_github_token

    if not github_token or github_token.startswith("ghp_your"):
        return {
            "linked": bool(repo.vercel_project_name),
            "source": "none",
            "latest_state": None,
            "vercel_project_name": repo.vercel_project_name,
            "deployments": [],
        }

    try:
        from patchr.integrations.github import get_github_client, GitHubError
        async with get_github_client(github_token) as gh:
            gh_deployments = await gh.get_recent_deployment_statuses(repo.full_name, limit=5)
    except Exception as e:
        logger.debug("github_deployment_fetch_failed", error=str(e))
        return {
            "linked": bool(repo.vercel_project_name),
            "source": "error",
            "latest_state": None,
            "vercel_project_name": repo.vercel_project_name,
            "deployments": [],
        }

    # Map GitHub deployment states to Vercel-like states for frontend consistency
    state_map = {
        "success": "READY",
        "failure": "ERROR",
        "error": "ERROR",
        "pending": "BUILDING",
        "queued": "QUEUED",
        "in_progress": "BUILDING",
        "inactive": "CANCELED",
    }

    deployments_out = []
    for d in gh_deployments:
        gh_state = d.get("state", "pending")
        mapped_state = state_map.get(gh_state, "UNKNOWN")
        created_at_str = d.get("created_at", "")
        # Convert ISO timestamp to unix ms
        created_at_ms = 0
        if created_at_str:
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(created_at_str.replace("Z", "+00:00"))
                created_at_ms = int(parsed.timestamp() * 1000)
            except Exception:
                pass

        deployments_out.append({
            "id": str(d.get("id", "")),
            "state": mapped_state,
            "url": d.get("environment_url"),
            "branch": None,  # GitHub deployments API doesn't always include branch
            "commit_sha": d.get("commit_sha"),
            "commit_message": d.get("description"),
            "created_at": created_at_ms,
            "error_message": None if gh_state == "success" else d.get("description"),
        })

    latest_state = deployments_out[0]["state"] if deployments_out else None

    return {
        "linked": True,
        "source": "github_api",
        "latest_state": latest_state,
        "vercel_project_name": repo.vercel_project_name,
        "deployments": deployments_out,
    }


@router.post("/{repo_id}/scan-deployments")
async def scan_deployments(
    repo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Scan this repository for failed deployments and create incidents.

    Uses the GitHub Deployments API to find recent deployment failures.
    For each new failure, creates an incident and optionally triggers AI analysis.
    This works WITHOUT webhooks â€” ideal for detecting pre-existing failures
    or when the webhook endpoint isn't reachable.
    """
    from patchr.services.deployment_poller import scan_repo_deployments, scan_repo_and_analyze

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # Do a quick synchronous scan for incidents
    created = await scan_repo_deployments(db, repo, settings)

    # If incidents were created and AI is configured, trigger analysis in background
    if created and settings.nvidia_api_key and not settings.nvidia_api_key.startswith("nvapi-xxx"):
        for inc_info in created:
            background_tasks.add_task(
                _trigger_analysis_for_incident,
                incident_id=inc_info["incident_id"],
                full_name=repo.full_name,
                settings=settings,
            )

    return {
        "scanned": True,
        "repo": repo.full_name,
        "incidents_created": len(created),
        "incidents": created,
        "message": (
            f"Found {len(created)} new deployment failure(s). AI analysis queued."
            if created
            else "No new deployment failures found."
        ),
    }


@router.post("/scan-all")
async def scan_all_deployments(
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Scan ALL connected repositories for failed deployments.
    Creates incidents for any new failures found across all repos.
    """
    from patchr.services.deployment_poller import scan_all_repos

    result = await scan_all_repos(settings)
    return result


@router.post("/{repo_id}/scan-runtime")
async def scan_runtime_errors(
    repo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    since_minutes: int = 30,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Scan this repository's Vercel runtime logs for 500+ errors.

    Uses the user's Vercel Integration OAuth token (connected via Settings â†’ Connect Vercel).
    The token is stored per-user after OAuth authorization and includes the team_id
    automatically â€” no manual token entry required.
    """
    from patchr.services.deployment_poller import scan_runtime_errors as _scan_runtime
    from patchr.db.models import User

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # Resolve the user's Vercel token and team_id (from OAuth integration)
    user_vercel_token: str | None = None
    user_vercel_team_id: str | None = None
    user_id = current_user.get("user_id")
    if user_id:
        try:
            db_user = await _get_user_by_id(db, user_id)
            if db_user:
                if db_user.vercel_access_token:
                    user_vercel_token = db_user.vercel_access_token
                if db_user.vercel_team_id:
                    user_vercel_team_id = db_user.vercel_team_id
        except Exception:
            pass

    vercel_token = user_vercel_token
    if not vercel_token:
        return {
            "scanned": False,
            "message": (
                "No Vercel account connected. "
                "Go to Settings â†’ Vercel Account and click 'Connect Vercel' to authorize."
            ),
            "incidents_created": 0,
            "incidents": [],
        }

    if not repo.vercel_project_id:
        # Try to auto-resolve the Vercel project ID using the Vercel API.
        # Use the same token we already resolved (user OAuth > global .env) â€”
        # the user's token is more likely to have access to their own projects.
        resolve_token = vercel_token
        resolved = False
        if resolve_token:
            try:
                from patchr.integrations.vercel import get_vercel_client, VercelError
                # Use team_id from user's OAuth token exchange (stored per-user)
                effective_team_id = user_vercel_team_id or settings.vercel_team_id or None
                async with get_vercel_client(resolve_token, team_id=effective_team_id) as vercel:
                    # Strategy 1: Try looking up project by various name guesses
                    possible_names = set()
                    if repo.vercel_project_name:
                        # The stored name might be a deployment hostname like
                        # "demo-clfclpyvo-debjanimandal556-gmailcoms-projects"
                        # or an actual project name like "demo". Try both.
                        possible_names.add(repo.vercel_project_name)
                        parts = repo.vercel_project_name.split("-")
                        possible_names.add(parts[0])  # first word
                        # Also try first two parts (common for Vercel project names)
                        if len(parts) >= 2:
                            possible_names.add(f"{parts[0]}-{parts[1]}")
                    # Also try the repo name itself (most common match)
                    possible_names.add(repo.name.lower())
                    possible_names.add(repo.full_name.split("/")[-1].lower())

                    for name in possible_names:
                        try:
                            project = await vercel.get_project(name)
                            repo.vercel_project_id = project.id
                            repo.vercel_project_name = project.name
                            await db.commit()
                            await db.refresh(repo)
                            resolved = True
                            break
                        except VercelError:
                            continue

                    # Strategy 2: List all projects and match by linked GitHub repo
                    if not resolved:
                        projects = await vercel.list_all_projects(limit=100)
                        for p in projects:
                            repo_match = p.linked_repo and p.linked_repo.lower() == repo.full_name.lower()
                            if repo_match:
                                repo.vercel_project_id = p.id
                                repo.vercel_project_name = p.name
                                await db.commit()
                                await db.refresh(repo)
                                resolved = True
                                break
            except Exception:
                pass

        if not repo.vercel_project_id:
            return {
                "scanned": False,
                "message": (
                    "Could not resolve Vercel project. "
                    "Your connected Vercel token doesn't have access to this project. "
                    "Go to Settings â†’ update your Vercel token with one that has access to "
                    f"the project linked to '{repo.full_name}'."
                ),
                "incidents_created": 0,
                "incidents": [],
            }

    created, scan_error = await _scan_runtime(
        db,
        repo,
        settings,
        since_minutes=since_minutes,
        user_vercel_token=vercel_token,
        user_vercel_team_id=user_vercel_team_id,
    )

    if scan_error:
        return {
            "scanned": False,
            "repo": repo.full_name,
            "since_minutes": since_minutes,
            "incidents_created": 0,
            "incidents": [],
            "message": (
                f"Vercel API returned: {scan_error}. "
                "Ensure your Vercel OAuth integration has the 'Logs' permission in Vercel Developer Console, "
                "or add a Personal Access Token with log access in Settings."
            ),
        }

    # If incidents were created and AI is configured, trigger analysis in background
    if created and settings.nvidia_api_key and not settings.nvidia_api_key.startswith("nvapi-xxx"):
        for inc_info in created:
            background_tasks.add_task(
                _trigger_analysis_for_incident,
                incident_id=inc_info["incident_id"],
                full_name=repo.full_name,
                settings=settings,
            )

    # If no new incidents were created, check if there are existing open ones
    # so the user gets a useful message rather than thinking no errors exist.
    if not created:
        from patchr.db.models import Incident as _Inc
        existing_result = await db.execute(
            select(_Inc).where(
                _Inc.repository_id == repo.id,
                _Inc.source == "vercel_deployment",
                _Inc.failure_type == "runtime_error",
                _Inc.status.notin_(["resolved", "dismissed"]),
            )
        )
        existing_open = existing_result.scalars().all()
        if existing_open:
            return {
                "scanned": True,
                "repo": repo.full_name,
                "since_minutes": since_minutes,
                "incidents_created": 0,
                "incidents": [],
                "message": (
                    f"Runtime errors still active â€” {len(existing_open)} open incident(s) already being tracked. "
                    f"Check the Incidents page to review AI analysis and approve patches."
                ),
            }

    return {
        "scanned": True,
        "repo": repo.full_name,
        "since_minutes": since_minutes,
        "incidents_created": len(created),
        "incidents": created,
        "message": (
            f"Found {len(created)} runtime error pattern(s). Incidents created. AI analysis queued."
            if created
            else f"No new runtime errors in the last {since_minutes} minutes."
        ),
    }


@router.get("/{repo_id}/debug-runtime-logs", summary="[DEBUG] Raw Vercel runtime log API response")
async def debug_runtime_logs(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Diagnostic endpoint â€” returns the raw response from the Vercel runtime logs API.
    Use this to debug why 'Scan Runtime' returns no errors when Vercel shows errors.
    Hit: GET /api/v1/repositories/{repo_id}/debug-runtime-logs
    """
    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    user_id = current_user.get("user_id")
    user_vercel_token = None
    user_vercel_team_id = None
    if user_id:
        db_user = await _get_user_by_id(db, user_id)
        if db_user:
            user_vercel_token = db_user.vercel_access_token
            user_vercel_team_id = db_user.vercel_team_id

    if not user_vercel_token:
        return {"error": "No Vercel token. Connect Vercel in Settings first."}

    effective_team_id = user_vercel_team_id or settings.vercel_team_id or None
    project_id = repo.vercel_project_id

    if not project_id:
        return {"error": "No vercel_project_id on this repo", "repo": repo.full_name}

    try:
        async with get_vercel_client(user_vercel_token, team_id=effective_team_id) as vercel:
            client = vercel._get_client()

            # Step 1: get project to find production deployment ID
            proj_resp = await client.get(f"/v9/projects/{project_id}")
            proj_data = proj_resp.json() if proj_resp.status_code == 200 else {"error": proj_resp.text, "http_status": proj_resp.status_code}

            targets = proj_data.get("targets", {}) if isinstance(proj_data, dict) else {}
            production = targets.get("production", {})
            dep_id = production.get("id")

            # Step 2: try runtime logs for that deployment
            logs_raw = None
            logs_status = None
            if dep_id:
                logs_resp = await client.get(
                    f"/v1/projects/{project_id}/deployments/{dep_id}/runtime-logs",
                    params={"limit": 10},
                )
                logs_status = logs_resp.status_code
                try:
                    logs_raw = logs_resp.json()
                except Exception:
                    logs_raw = logs_resp.text[:2000]

            # Step 3: list recent deployments for reference
            deps_resp = await client.get(
                "/v6/deployments",
                params={"projectId": project_id, "limit": 3, "target": "production"},
            )
            deps_data = deps_resp.json() if deps_resp.status_code == 200 else {"error": deps_resp.text, "http_status": deps_resp.status_code}

        return {
            "repo": repo.full_name,
            "vercel_project_id": project_id,
            "team_id_used": effective_team_id,
            "production_deployment_id": dep_id,
            "project_api_status": proj_resp.status_code,
            "runtime_logs_api_status": logs_status,
            "runtime_logs_response": logs_raw,
            "recent_deployments_response": deps_data,
        }

    except VercelError as e:
        return {"error": e.message, "http_status": e.status, "team_id_used": effective_team_id}
    except Exception as e:
        return {"error": str(e)}


@router.get("/{repo_id}/deployment-logs/{deployment_id}")
async def get_deployment_logs(
    repo_id: uuid.UUID,
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Fetch build logs for a specific Vercel deployment.

    Returns the raw build log text for display in the frontend log viewer.
    """
    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if not repo.vercel_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository is not linked to a Vercel project",
        )

    # Resolve Vercel token
    vercel_token: str | None = None
    user_id = current_user.get("user_id")
    if user_id:
        try:
            db_user = await _get_user_by_id(db, user_id)
            if db_user and db_user.vercel_access_token:
                vercel_token = db_user.vercel_access_token
        except Exception:
            pass
    if not vercel_token:
        vercel_token = settings.vercel_access_token
    if not vercel_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No Vercel token configured.",
        )

    try:
        async with get_vercel_client(vercel_token, team_id=settings.vercel_team_id or None) as vercel:
            logs = await vercel.get_build_logs(deployment_id, max_lines=500)
    except VercelError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vercel API error: {e.message}",
        )

    return {
        "deployment_id": deployment_id,
        "log_count": len(logs),
        "logs": [
            {
                "text": log.text,
                "type": log.log_type,
                "is_error": log.is_error,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


# â”€â”€â”€ Background Tasks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


async def _trigger_analysis_for_incident(
    incident_id: str, full_name: str, settings: Settings
) -> None:
    """Background task: trigger AI analysis for a scanned incident."""
    from patchr.db.session import AsyncSessionLocal
    from patchr.services import incident_service
    from patchr.services.deployment_poller import _fetch_build_context

    try:
        async with AsyncSessionLocal() as db:
            from patchr.db.models import Incident
            _inc_id = uuid.UUID(str(incident_id)) if not isinstance(incident_id, uuid.UUID) else incident_id
            result = await db.execute(select(Incident).where(Incident.id == _inc_id))
            incident = result.scalar_one_or_none()
            if not incident:
                return

            build_logs = await _fetch_build_context(full_name, incident.commit_sha, settings)
            await incident_service.trigger_analysis(
                db, incident=incident, build_logs=build_logs
            )
    except Exception as e:
        logger.warning("analysis_trigger_failed", incident_id=incident_id, error=str(e))


async def _scan_deployments_on_import(repo_id: str, full_name: str, settings: Settings) -> None:
    """Background task: scan for failed deployments AND runtime errors after repo import."""
    from patchr.services.deployment_poller import scan_repo_and_analyze, scan_runtime_errors
    from patchr.db.session import AsyncSessionLocal
    try:
        await scan_repo_and_analyze(repo_id, full_name, settings)

        # Also scan runtime errors if Vercel project is linked
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Repository).where(Repository.id == repo_id))
            repo = result.scalar_one_or_none()
            if repo and repo.vercel_project_id:
                await scan_runtime_errors(db, repo, settings, since_minutes=60)
    except Exception as e:
        logger.warning("import_scan_failed", repo=full_name, error=str(e))


async def _sync_github_metadata(repo_id: str, full_name: str, settings: Settings) -> None:
    """
    Background task: fetch GitHub repo metadata and update the DB record.
    Runs after a repository is connected.
    """
    from patchr.db.session import AsyncSessionLocal
    from patchr.integrations.github import get_github_client, GitHubError

    try:
        async with get_github_client(settings.github_token) as gh:
            repo_info = await gh.get_repo(full_name)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Repository).where(Repository.id == repo_id))
            repo = result.scalar_one_or_none()
            if repo:
                repo.github_id = repo_info.github_id
                repo.name = repo_info.name
                repo.default_branch = repo_info.default_branch
                repo.private = repo_info.private
                repo.updated_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(
                    "repository_github_synced",
                    full_name=full_name,
                    default_branch=repo_info.default_branch,
                )
    except GitHubError as e:
        logger.warning(
            "repository_github_sync_failed",
            full_name=full_name,
            status=e.status,
            error=e.message,
        )
    except Exception as e:
        logger.error("repository_github_sync_error", full_name=full_name, error=str(e))


async def _auto_detect_vercel(repo_id: str, full_name: str, settings: Settings) -> None:
    """
    Background task: auto-detect Vercel deployment for this GitHub repo.

    Strategy (in order):
    1. GitHub Deployments API â€” check if vercel[bot] has deployed this repo.
       Works for ANY user's repo without needing a Vercel token.
    2. Vercel API (if token available) â€” list projects and match by linked_repo.
       Only works for repos in the token-holder's Vercel account.

    If detected via GitHub, stores the deployment URL as vercel_project_name
    (for display) even without a vercel_project_id.
    """
    from patchr.db.session import AsyncSessionLocal

    # â”€â”€ Strategy 1: GitHub Deployments API (works for any user) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if settings.github_token and not settings.github_token.startswith("ghp_your"):
        try:
            from patchr.integrations.github import get_github_client, GitHubError
            async with get_github_client(settings.github_token) as gh:
                vercel_info = await gh.detect_vercel_from_deployments(full_name)

            if vercel_info and vercel_info.get("detected"):
                env_url = vercel_info.get("environment_url", "")
                # Extract a project name from the URL (e.g. "my-app" from "my-app.vercel.app")
                project_display_name = ""
                if env_url and ".vercel.app" in env_url:
                    hostname = env_url.replace("https://", "").replace("http://", "").split("/")[0]
                    project_display_name = hostname.replace(".vercel.app", "").split("-git-")[0]
                elif env_url:
                    project_display_name = env_url.replace("https://", "").split("/")[0]

                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Repository).where(Repository.id == repo_id))
                    repo = result.scalar_one_or_none()
                    if repo and not repo.vercel_project_id:
                        repo.vercel_project_name = project_display_name or "Vercel (detected)"
                        repo.updated_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.info(
                            "vercel_detected_via_github",
                            repo=full_name,
                            env_url=env_url,
                            state=vercel_info.get("state"),
                        )
                        return  # Done â€” GitHub detection succeeded
        except Exception as e:
            logger.debug("github_vercel_detect_failed", repo=full_name, error=str(e))

    # â”€â”€ Strategy 2: Vercel API (only if token configured) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if settings.vercel_access_token and not settings.vercel_access_token.startswith("your_vercel"):
        try:
            from patchr.integrations.vercel import get_vercel_client, VercelError
            async with get_vercel_client(settings.vercel_access_token, team_id=settings.vercel_team_id or None) as vercel:
                projects = await vercel.list_all_projects(limit=100)

            matched_project = None
            for project in projects:
                if project.linked_repo and project.linked_repo.lower() == full_name.lower():
                    matched_project = project
                    break

            if not matched_project:
                logger.debug("vercel_auto_detect_no_match", repo=full_name)
                return

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Repository).where(Repository.id == repo_id))
                repo = result.scalar_one_or_none()
                if repo and not repo.vercel_project_id:
                    repo.vercel_project_id = matched_project.id
                    repo.vercel_project_name = matched_project.name
                    repo.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info(
                        "vercel_auto_detected",
                        repo=full_name,
                        vercel_project=matched_project.name,
                        vercel_project_id=matched_project.id,
                    )

        except Exception as e:
            logger.warning("vercel_auto_detect_error", repo=full_name, error=str(e))


# â”€â”€â”€ Phase C: Webhook Auto-Registration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post("/{repo_id}/register-webhook", response_model=RepositoryResponse)
async def register_webhook(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> RepositoryResponse:
    """
    Automatically register a GitHub webhook for this repository.

    Calls the GitHub Hooks API to register the PatchR webhook URL with
    'push' and 'deployment_status' events. Stores the webhook ID so it
    can be deleted later.

    Requires:
    - GITHUB_TOKEN with 'admin:repo_hook' scope
    - GITHUB_WEBHOOK_SECRET set in .env
    - FRONTEND_URL set so we know where to point the webhook
    """
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if not settings.github_token or settings.github_token.startswith("ghp_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_TOKEN not configured",
        )

    if not settings.github_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_WEBHOOK_SECRET not set in .env",
        )

    # Build the webhook URL â€” uses the configured API_BASE_URL for the public endpoint
    webhook_url = f"{settings.api_base_url.rstrip('/')}/api/v1/webhooks/github"

    from patchr.integrations.github import get_github_client, GitHubError
    try:
        async with get_github_client(settings.github_token) as gh:
            # Delete existing webhook if one is registered
            if repo.github_webhook_id:
                await gh.delete_webhook(repo.full_name, repo.github_webhook_id)
                logger.info("github_webhook_deleted", repo=repo.full_name, old_id=repo.github_webhook_id)

            hook_data = await gh.create_webhook(
                full_name=repo.full_name,
                url=webhook_url,
                secret=settings.github_webhook_secret,
                events=["push", "deployment_status"],
            )

        repo.github_webhook_id = hook_data["id"]
        repo.webhook_active = True
        repo.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(repo)

        logger.info(
            "github_webhook_registered",
            repo=repo.full_name,
            webhook_id=hook_data["id"],
            url=webhook_url,
        )
        return RepositoryResponse.model_validate(repo)

    except GitHubError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub API error: {e.message} (HTTP {e.status}). "
                   f"Make sure your token has 'admin:repo_hook' scope.",
        )


@router.delete("/{repo_id}/register-webhook", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_webhook(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
) -> None:
    """Remove the PatchR webhook from the GitHub repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if not repo.github_webhook_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No webhook registered for this repository",
        )

    from patchr.integrations.github import get_github_client, GitHubError
    try:
        async with get_github_client(settings.github_token) as gh:
            await gh.delete_webhook(repo.full_name, repo.github_webhook_id)

        repo.github_webhook_id = None
        repo.webhook_active = False
        repo.updated_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("github_webhook_unregistered", repo=repo.full_name)

    except GitHubError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub API error: {e.message}",
        )


# â”€â”€â”€ Phase D: Vercel Project Linking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post("/{repo_id}/link-vercel", response_model=RepositoryResponse)
async def link_vercel_project(
    repo_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(get_current_owner),
) -> RepositoryResponse:
    """
    Link a Vercel project to this repository WITH backend verification.

    1. Resolves the user's Vercel token (DB token > .env fallback)
    2. Calls Vercel API to confirm the project_id exists in their account
    3. Only saves if verification passes
    4. Optionally registers a Vercel deployment webhook
    """
    from patchr.integrations.vercel import get_vercel_client, VercelError
    from patchr.db.models import User

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    vercel_project_id = body.get("vercel_project_id", "").strip()
    should_register_webhook = body.get("register_webhook", True)

    if not vercel_project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="vercel_project_id is required",
        )

    # â”€â”€ Resolve Vercel token (user's DB token > .env) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    vercel_token: str | None = None
    user_id = current_user.get("user_id")
    if user_id:
        try:
            db_user = await _get_user_by_id(db, user_id)
            if db_user and db_user.vercel_access_token:
                vercel_token = db_user.vercel_access_token
        except Exception:
            pass
    if not vercel_token:
        vercel_token = settings.vercel_access_token
    if not vercel_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No Vercel token configured. Add your token in Settings â†’ Vercel Account.",
        )

    # â”€â”€ Verify project exists in user's Vercel account â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        async with get_vercel_client(vercel_token) as vercel:
            project = await vercel.get_project(vercel_project_id)
    except VercelError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vercel project '{vercel_project_id}' not found in your account: {e.message}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not verify Vercel project: {str(e)[:100]}",
        )

    vercel_project_name = project.name

    # â”€â”€ Save to DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    repo.vercel_project_id = vercel_project_id
    repo.vercel_project_name = vercel_project_name
    repo.updated_at = datetime.now(timezone.utc)

    # Optionally register Vercel webhook
    vercel_webhook_status = "skipped"
    if should_register_webhook and settings.vercel_webhook_secret:
        try:
            webhook_url = f"{settings.api_base_url.rstrip('/')}/api/v1/webhooks/vercel"
            async with get_vercel_client(vercel_token) as vercel:
                await vercel.register_webhook(
                    url=webhook_url,
                    events=["deployment.error", "deployment.ready"],
                    project_ids=[vercel_project_id],
                )
            vercel_webhook_status = "registered"
            logger.info("vercel_webhook_registered", project_id=vercel_project_id, url=webhook_url)
        except Exception as e:
            vercel_webhook_status = f"failed: {str(e)[:80]}"
            logger.warning("vercel_webhook_register_failed", error=str(e))

    await db.commit()
    await db.refresh(repo)

    logger.info(
        "vercel_project_linked",
        repo=repo.full_name,
        vercel_project=vercel_project_name,
        webhook_status=vercel_webhook_status,
    )
    return RepositoryResponse.model_validate(repo)


