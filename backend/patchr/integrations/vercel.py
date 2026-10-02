"""
Vercel API Integration Client — Phase 3

Authenticated with a Vercel Access Token (created in Vercel dashboard).
Fetches deployment details and build logs for AI analysis context.

Key endpoints used:
  GET /v13/deployments/{id}           — deployment metadata
  GET /v2/deployments/{id}/events     — build log stream (NDJSON)
  GET /v9/projects/{id}               — project info
  POST /v1/webhooks                   — register deployment event webhook
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


# ─── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class DeploymentInfo:
    id: str
    url: str | None
    state: str               # READY, ERROR, CANCELED, BUILDING, QUEUED
    name: str                # project name
    target: str | None       # production, preview
    commit_sha: str | None
    commit_message: str | None
    commit_author: str | None
    branch: str | None
    error_message: str | None
    created_at: int          # unix ms
    repo_full_name: str | None   # owner/repo from GitHub meta


@dataclass
class BuildLog:
    """A single log line from a Vercel build."""
    text: str
    created_at: int
    log_type: str = "stdout"   # stdout, stderr, command, event

    @property
    def is_error(self) -> bool:
        return self.log_type == "stderr" or "error" in self.text.lower()


@dataclass
class ProjectInfo:
    id: str
    name: str
    framework: str | None
    root_directory: str | None
    linked_repo: str | None    # full_name of connected GitHub repo


class VercelError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Vercel API {status}: {message}")


# ─── Client ───────────────────────────────────────────────────────────────────


def _extract_linked_repo(link: dict) -> str | None:
    """
    Extract the full GitHub repo name (owner/repo) from a Vercel project's link object.

    Vercel uses different field structures depending on how the project was connected:
      - Manual GitHub connection:   link.org  + link.repo
      - GitHub App connection:      link.repoOwner + link.repoSlug
      - Older API variants:         link.owner + link.slug

    Returns 'owner/repo' string or None if no repo is linked.
    """
    if not link:
        return None

    # Variant 1: manual link (most common in older projects)
    org = link.get("org") or link.get("owner")
    repo = link.get("repo") or link.get("slug")
    if org and repo:
        return f"{org}/{repo}"

    # Variant 2: GitHub App connection
    owner = link.get("repoOwner")
    slug = link.get("repoSlug")
    if owner and slug:
        return f"{owner}/{slug}"

    # Variant 3: some accounts expose a full "repoId" string — skip (numeric only)
    return None


class VercelClient:

    """
    Async Vercel REST API client.

    Usage:
        async with VercelClient(token) as vercel:
            info = await vercel.get_deployment("dpl_xxx")
            logs = await vercel.get_build_logs("dpl_xxx")
    """

    BASE_URL = "https://api.vercel.com"
    TIMEOUT = 30.0

    def __init__(self, access_token: str, team_id: str | None = None):
        self._token = access_token
        self._team_id = team_id
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> VercelClient:
        params = {}
        if self._team_id:
            params["teamId"] = self._team_id
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "FixFlow/0.1.0",
            },
            timeout=self.TIMEOUT,
            params=params,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("VercelClient must be used as async context manager")
        return self._client

    async def _get(self, path: str, **extra_params) -> Any:
        client = self._get_client()
        response = await client.get(path, params=extra_params or None)
        self._raise_for_status(response)
        return response.json()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                data = response.json()
                msg = data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise VercelError(response.status_code, msg)

    # ─── Deployments ──────────────────────────────────────────────────────────

    async def get_deployment(self, deployment_id: str) -> DeploymentInfo:
        """Fetch deployment metadata by ID."""
        data = await self._get(f"/v13/deployments/{deployment_id}")

        meta = data.get("gitSource") or data.get("meta") or {}
        repo = meta.get("repoOwner") and f"{meta['repoOwner']}/{meta.get('repoSlug', '')}"

        return DeploymentInfo(
            id=data["id"],
            url=data.get("url"),
            state=data.get("readyState", "UNKNOWN"),
            name=data.get("name", ""),
            target=data.get("target"),
            commit_sha=meta.get("commitSha") or meta.get("sha"),
            commit_message=meta.get("commitMessage"),
            commit_author=meta.get("commitAuthorName"),
            branch=meta.get("ref") or meta.get("branch"),
            error_message=data.get("errorMessage"),
            created_at=data.get("createdAt", 0),
            repo_full_name=repo if repo and "/" in repo else None,
        )

    async def get_build_logs(
        self, deployment_id: str, max_lines: int = 500
    ) -> list[BuildLog]:
        """
        Fetch build log events for a deployment.
        Returns list of BuildLog objects, oldest-first.
        Handles Vercel's NDJSON streaming format.
        """
        client = self._get_client()
        response = await client.get(
            f"/v2/deployments/{deployment_id}/events",
            params={"limit": max_lines, "direction": "forward"},
        )
        self._raise_for_status(response)

        logs: list[BuildLog] = []
        for line in response.text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                event = json.loads(line)
                payload = event.get("payload", {})
                text = payload.get("text", "")
                if text:
                    logs.append(BuildLog(
                        text=text,
                        created_at=event.get("created", 0),
                        log_type=payload.get("type", "stdout"),
                    ))
            except Exception:
                continue

        return logs

    async def get_build_logs_as_text(
        self, deployment_id: str, max_lines: int = 500
    ) -> str:
        """Get build logs concatenated as plain text — ready for AI prompt."""
        logs = await self.get_build_logs(deployment_id, max_lines=max_lines)
        return "\n".join(log.text for log in logs)

    async def list_recent_deployments(
        self, project_id: str, limit: int = 10, state: str | None = None
    ) -> list[DeploymentInfo]:
        """List recent deployments for a project."""
        params: dict[str, Any] = {"projectId": project_id, "limit": limit}
        if state:
            params["state"] = state
        data = await self._get("/v6/deployments", **params)
        deployments = data.get("deployments", [])
        result = []
        for d in deployments:
            meta = d.get("meta", {})
            result.append(DeploymentInfo(
                id=d["uid"],
                url=d.get("url"),
                state=d.get("readyState", "UNKNOWN"),
                name=d.get("name", ""),
                target=d.get("target"),
                commit_sha=meta.get("commitSha") or meta.get("sha"),
                commit_message=meta.get("commitMessage"),
                commit_author=meta.get("commitAuthorName"),
                branch=meta.get("ref"),
                error_message=d.get("errorMessage"),
                created_at=d.get("createdAt", 0),
                repo_full_name=None,
            ))
        return result

    # ─── Projects ─────────────────────────────────────────────────────────────

    async def get_project(self, project_id_or_name: str) -> ProjectInfo:
        """Fetch project metadata."""
        data = await self._get(f"/v9/projects/{project_id_or_name}")
        repo = _extract_linked_repo(data.get("link", {}))

        return ProjectInfo(
            id=data["id"],
            name=data["name"],
            framework=data.get("framework"),
            root_directory=data.get("rootDirectory"),
            linked_repo=repo,
        )

    async def list_projects(self, limit: int = 50, team_id: str | None = None) -> list[ProjectInfo]:
        """List all Vercel projects. Optionally override team_id for this call."""
        params: dict[str, Any] = {"limit": limit}
        if team_id:
            params["teamId"] = team_id
        data = await self._get("/v9/projects", **params)
        results = []
        for p in data.get("projects", []):
            repo = _extract_linked_repo(p.get("link", {}))
            results.append(ProjectInfo(
                id=p["id"],
                name=p["name"],
                framework=p.get("framework"),
                root_directory=p.get("rootDirectory"),
                linked_repo=repo,
            ))
        return results

    async def list_teams(self) -> list[dict]:
        """Return all Vercel teams the authenticated user belongs to."""
        try:
            data = await self._get("/v2/teams", limit=100)
            return data.get("teams", [])
        except Exception:
            return []

    async def list_all_projects(self, limit: int = 100) -> list[ProjectInfo]:
        """
        List projects across the user's personal account AND all their teams.
        This is needed when the target project lives inside a Vercel team.
        Deduplicates by project id — a project can appear in both personal
        and team scopes if it was transferred or shared.
        """
        seen: set[str] = set()
        all_projects: list[ProjectInfo] = []

        def _add_unique(projects: list[ProjectInfo]) -> None:
            for p in projects:
                if p.id not in seen:
                    seen.add(p.id)
                    all_projects.append(p)

        # Personal account projects (no teamId)
        try:
            _add_unique(await self.list_projects(limit=limit, team_id=None))
        except Exception:
            pass
        # Team projects
        try:
            teams = await self.list_teams()
            for team in teams:
                team_id = team.get("id")
                if team_id:
                    try:
                        _add_unique(await self.list_projects(limit=limit, team_id=team_id))
                    except Exception:
                        continue
        except Exception:
            pass
        return all_projects

    # ─── Webhooks ─────────────────────────────────────────────────────────────

    async def register_webhook(
        self,
        url: str,
        events: list[str] | None = None,
        project_ids: list[str] | None = None,
    ) -> str:
        """
        Register a webhook to receive deployment events.
        Returns the webhook ID.

        Default events: deployment.created, deployment.error, deployment.ready
        """
        client = self._get_client()
        payload: dict[str, Any] = {
            "url": url,
            "events": events or [
                "deployment.created",
                "deployment.error",
                "deployment.ready",
                "deployment.canceled",
            ],
        }
        if project_ids:
            payload["projectIds"] = project_ids

        response = await client.post("/v1/webhooks", json=payload)
        self._raise_for_status(response)
        return response.json()["id"]

    async def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook."""
        client = self._get_client()
        response = await client.delete(f"/v1/webhooks/{webhook_id}")
        if response.status_code not in (200, 204, 404):
            self._raise_for_status(response)

    # ─── Runtime Logs ─────────────────────────────────────────────────────────

    async def get_runtime_logs(
        self,
        project_id: str,
        *,
        since: int | None = None,
        until: int | None = None,
        status_code: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Fetch runtime logs for a Vercel project using the official Vercel API.

        Calls:
          GET /v1/projects/{projectId}/deployments/{deploymentId}/runtime-logs
          ?teamId={teamId}&limit={limit}&since={since}&until={until}

        Targets the most recent production deployment for the project.
        Vercel retains runtime logs for approximately 1 hour.

        Returns list of normalized log entries:
          { timestamp, method, path, statusCode, message, host, level, source }
        """
        # Step 1: Get the project's most recent production deployment
        try:
            project_data = await self._get(f"/v9/projects/{project_id}")
        except VercelError as e:
            logger.warning("vercel_runtime_logs_project_fetch_failed", project_id=project_id, error=e.message)
            return []

        targets = project_data.get("targets", {})
        production = targets.get("production", {})
        deployment_id = production.get("id")

        # Fallback: list recent deployments and take the latest READY one
        if not deployment_id:
            try:
                deps_data = await self._get(
                    f"/v6/deployments",
                    projectId=project_id,
                    state="READY",
                    target="production",
                    limit=1,
                )
                deps = deps_data.get("deployments", [])
                if deps:
                    deployment_id = deps[0].get("uid") or deps[0].get("id")
            except VercelError:
                pass

        if not deployment_id:
            logger.info("vercel_runtime_logs_no_deployment", project_id=project_id)
            return []

        # Step 2: Fetch runtime logs from the official API
        params: dict[str, Any] = {"limit": limit}
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until

        try:
            raw = await self._get(
                f"/v1/projects/{project_id}/deployments/{deployment_id}/runtime-logs",
                **params,
            )
        except VercelError as e:
            logger.warning(
                "vercel_runtime_logs_api_failed",
                project_id=project_id,
                deployment_id=deployment_id,
                status=e.status,
                error=e.message,
            )
            raise

        # Step 3: Normalize the response
        log_entries = raw if isinstance(raw, list) else raw.get("logs", raw.get("rows", []))
        results: list[dict] = []

        for entry in log_entries:
            proxy = entry.get("proxy") or {}
            ts = entry.get("timestamp") or entry.get("createdAt") or 0
            sc = (
                entry.get("statusCode")
                or proxy.get("statusCode")
                or entry.get("status")
                or 0
            )
            try:
                sc = int(sc)
            except (TypeError, ValueError):
                sc = 0

            if status_code and sc != status_code:
                continue

            normalized = {
                "timestamp": ts,
                "method": entry.get("method") or proxy.get("method") or "?",
                "path": entry.get("path") or proxy.get("path") or "?",
                "statusCode": sc,
                "message": (
                    entry.get("message")
                    or entry.get("msg")
                    or entry.get("body")
                    or ""
                ),
                "host": entry.get("host") or proxy.get("host") or "",
                "requestId": entry.get("requestId") or entry.get("request_id") or "",
                "level": entry.get("level") or ("error" if sc >= 500 else "info"),
                "source": "vercel_api",
            }
            results.append(normalized)
            if len(results) >= limit:
                break

        return results


    async def get_error_logs(
        self,
        project_id: str,
        since_minutes_ago: int = 30,
        limit: int = 20,
    ) -> list[dict]:
        """
        Convenience: fetch only error logs (status >= 500) from the last N minutes.

        Returns simplified log entries:
        {
            "timestamp": int (unix ms),
            "method": "GET",
            "path": "/api/something",
            "status_code": 500,
            "message": "Error: ...",
            "host": "my-app.vercel.app",
        }
        """
        import time
        now = int(time.time() * 1000)   # current time in ms
        since = int((time.time() - since_minutes_ago * 60) * 1000)

        raw_logs = await self.get_runtime_logs(
            project_id, since=since, until=now, limit=limit
        )

        errors = []
        for log in raw_logs:
            status = log.get("statusCode") or log.get("status_code") or log.get("proxy", {}).get("statusCode", 0)
            if isinstance(status, str):
                try:
                    status = int(status)
                except ValueError:
                    continue

            if status >= 500:
                errors.append({
                    "timestamp": log.get("timestamp") or log.get("createdAt") or 0,
                    "method": log.get("method") or log.get("proxy", {}).get("method", "?"),
                    "path": log.get("path") or log.get("proxy", {}).get("path", "?"),
                    "status_code": status,
                    "message": log.get("message") or log.get("msg") or "",
                    "host": log.get("host") or log.get("proxy", {}).get("host", ""),
                    "request_id": log.get("requestId") or log.get("request_id") or "",
                })

        return errors


# ─── Factory ──────────────────────────────────────────────────────────────────


def get_vercel_client(access_token: str, team_id: str | None = None) -> VercelClient:
    """Create a Vercel client. Use as: async with get_vercel_client(token) as v: ..."""
    if not access_token:
        raise ValueError("VERCEL_ACCESS_TOKEN is not configured. Add it to apps/api/.env")
    return VercelClient(access_token, team_id=team_id)
