"""
GitHub Provider — implements DeploymentProvider for GitHub Actions CI/build logs.

Responsibility: Build logs from GitHub Actions workflow runs.
Runtime logs are handled by VercelProvider (not GitHub).

Authentication:
  Uses the user's GitHub OAuth token (stored per-user from GitHub OAuth login).
"""

from __future__ import annotations

from typing import Any

import structlog

from patchr.integrations.github import GitHubClient, GitHubError, get_github_client
from patchr.services.providers.base import (
    BuildLog,
    DeploymentInfo,
    DeploymentProvider,
    RuntimeLog,
)

logger = structlog.get_logger(__name__)


class GitHubProvider(DeploymentProvider):
    """
    GitHub deployment provider.

    Provides build/CI log access from GitHub Actions workflow runs.
    Instantiate with the user's per-user GitHub access token.

    Usage:
        provider = GitHubProvider(token="gha_xxx")
        async with provider:
            logs = await provider.get_build_logs(run_id, "owner/repo")
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._client: GitHubClient | None = None

    @property
    def provider_name(self) -> str:
        return "github"

    async def __aenter__(self) -> "GitHubProvider":
        self._client = get_github_client(self._token)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.__aexit__(*args)
            self._client = None

    def _get_client(self) -> GitHubClient:
        if self._client is None:
            raise RuntimeError("GitHubProvider must be used as an async context manager")
        return self._client

    # ─── DeploymentProvider interface ─────────────────────────────────────────

    async def get_deployment(self, deployment_id: str) -> DeploymentInfo | None:
        """
        Fetch GitHub deployment metadata.
        deployment_id format: '{repo_full_name}:{deployment_id}'
        """
        client = self._get_client()
        try:
            parts = deployment_id.split(":", 1)
            if len(parts) != 2:
                return None
            repo, dep_id = parts
            deps = await client.get_recent_deployment_statuses(repo, limit=50)
            for d in deps:
                if str(d.get("id")) == dep_id:
                    return DeploymentInfo(
                        id=str(d.get("id", "")),
                        url=d.get("url"),
                        state=d.get("state", "unknown"),
                        name=repo.split("/")[-1],
                        target=d.get("environment", "production"),
                        commit_sha=d.get("commit_sha"),
                        commit_message=d.get("commit_message"),
                        commit_author=d.get("commit_author"),
                        branch=d.get("branch"),
                        error_message=d.get("description") if d.get("state") in ("failure", "error") else None,
                        created_at=0,
                        repo_full_name=repo,
                        provider="github",
                    )
        except GitHubError as e:
            logger.warning("github_provider_get_deployment_failed", id=deployment_id, error=e.message)
        return None

    async def get_deployment_status(self, deployment_id: str) -> str:
        """Return the current state of a GitHub deployment."""
        info = await self.get_deployment(deployment_id)
        return info.state if info else "unknown"

    async def get_build_logs(
        self,
        run_id: str | int,
        repo_full_name: str,
        *,
        max_lines: int = 500,
    ) -> list[BuildLog]:
        """
        Fetch CI build logs for a GitHub Actions workflow run.

        Args:
            run_id:          GitHub Actions workflow run ID
            repo_full_name:  Repository full name (owner/repo)
            max_lines:       Maximum log lines to return
        """
        client = self._get_client()
        try:
            raw_logs = await client.get_workflow_run_logs(
                repo_full_name=repo_full_name,
                run_id=int(run_id),
                max_lines=max_lines,
            )
            return [
                BuildLog(
                    timestamp=log.created_at,
                    level="error" if "error" in log.text.lower() else "info",
                    message=log.text,
                    source="build",
                    step=getattr(log, "step_name", None),
                    provider="github",
                    raw={"text": log.text, "created_at": log.created_at},
                )
                for log in raw_logs
            ]
        except (GitHubError, AttributeError) as e:
            logger.warning(
                "github_provider_build_logs_failed",
                run_id=run_id,
                repo=repo_full_name,
                error=str(e),
            )
            return []
