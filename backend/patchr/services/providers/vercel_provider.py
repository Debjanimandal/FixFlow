"""
Vercel Provider — implements DeploymentProvider for Vercel runtime logs.

Responsibility: Runtime logs from Vercel serverless function deployments.
Build/CI logs are handled by GitHubProvider (not Vercel).

Authentication:
  Uses the user's Vercel OAuth token (from Vercel Integration OAuth flow).
  The Integration OAuth token has full API access — unlike App OAuth (cl_)
  which only has identity/OIDC scope.

Key endpoints:
  GET /v9/projects/{projectId}                                     — project metadata
  GET /v6/deployments?projectId={id}&state=READY&target=production — list deployments
  GET /v1/projects/{id}/deployments/{dep_id}/runtime-logs          — runtime logs
"""

from __future__ import annotations

from typing import Any

import structlog

from patchr.integrations.vercel import VercelClient, VercelError, get_vercel_client
from patchr.services.providers.base import (
    BuildLog,
    DeploymentInfo,
    DeploymentProvider,
    RuntimeLog,
)

logger = structlog.get_logger(__name__)


class VercelProvider(DeploymentProvider):
    """
    Vercel deployment provider.

    Provides runtime log access for Vercel-deployed projects.
    Instantiate with the user's per-user Vercel access token and optional team_id.

    Usage:
        provider = VercelProvider(token="vca_xxx", team_id="team_abc")
        async with provider:
            logs = await provider.get_runtime_logs("prj_xxx")
    """

    def __init__(self, token: str, team_id: str | None = None) -> None:
        self._token = token
        self._team_id = team_id
        self._client: VercelClient | None = None

    @property
    def provider_name(self) -> str:
        return "vercel"

    async def __aenter__(self) -> "VercelProvider":
        self._client = get_vercel_client(self._token, team_id=self._team_id)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.__aexit__(*args)
            self._client = None

    def _get_client(self) -> VercelClient:
        if self._client is None:
            raise RuntimeError("VercelProvider must be used as an async context manager")
        return self._client

    # ─── DeploymentProvider interface ─────────────────────────────────────────

    async def get_deployment(self, deployment_id: str) -> DeploymentInfo | None:
        """Fetch Vercel deployment metadata by ID."""
        client = self._get_client()
        try:
            raw = await client.get_deployment(deployment_id)
            return DeploymentInfo(
                id=raw.id,
                url=raw.url,
                state=raw.state,
                name=raw.name,
                target=raw.target,
                commit_sha=raw.commit_sha,
                commit_message=raw.commit_message,
                commit_author=raw.commit_author,
                branch=raw.branch,
                error_message=raw.error_message,
                created_at=raw.created_at,
                repo_full_name=raw.repo_full_name,
                provider="vercel",
            )
        except VercelError as e:
            logger.warning("vercel_provider_get_deployment_failed", id=deployment_id, error=e.message)
            return None

    async def get_deployment_status(self, deployment_id: str) -> str:
        """Return the current state of a Vercel deployment."""
        info = await self.get_deployment(deployment_id)
        return info.state if info else "UNKNOWN"

    async def get_runtime_logs(
        self,
        project_id: str,
        deployment_id: str | None = None,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int = 50,
    ) -> list[RuntimeLog]:
        """
        Fetch runtime logs for the most recent production deployment of a Vercel project.

        Uses the official Vercel API endpoint:
          GET /v1/projects/{projectId}/deployments/{deploymentId}/runtime-logs

        Runtime logs include serverless function invocations, console.log output,
        and request/response metadata. Vercel retains them for ~1 hour.

        Args:
            project_id:    Vercel project ID (prj_xxx)
            deployment_id: Specific deployment ID (optional; auto-resolves to latest prod)
            since:         Start timestamp (unix ms)
            until:         End timestamp (unix ms)
            limit:         Maximum number of log entries to return
        """
        client = self._get_client()
        raw_logs = await client.get_runtime_logs(
            project_id,
            since=since,
            until=until,
            limit=limit,
        )

        return [
            RuntimeLog(
                timestamp=entry.get("timestamp") or 0,
                level=entry.get("level") or "info",
                message=entry.get("message") or "",
                source="runtime",
                method=entry.get("method"),
                path=entry.get("path"),
                status_code=entry.get("statusCode") or entry.get("status_code"),
                host=entry.get("host"),
                request_id=entry.get("requestId") or entry.get("request_id"),
                provider="vercel",
                raw=entry,
            )
            for entry in raw_logs
        ]

    async def list_projects(self) -> list[dict]:
        """
        List all Vercel projects accessible by the token,
        including projects in teams the user belongs to.
        """
        client = self._get_client()
        return await client.list_all_projects(limit=100)
