"""
Provider abstraction layer for deployment/log integrations.

PatchR's log architecture:
  - GitHub Provider  → CI/build logs (GitHub Actions workflow/job logs)
  - Vercel Provider  → Runtime logs (serverless function invocation logs)

Add new providers (Render, Railway, Netlify, etc.) by implementing DeploymentProvider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ─── Shared Data Structures ───────────────────────────────────────────────────


@dataclass
class DeploymentInfo:
    """Normalized deployment metadata, provider-agnostic."""
    id: str
    url: str | None
    state: str           # READY, ERROR, BUILDING, QUEUED, CANCELED, FAILED
    name: str            # project / app name
    target: str | None   # production, preview, staging
    commit_sha: str | None
    commit_message: str | None
    commit_author: str | None
    branch: str | None
    error_message: str | None
    created_at: int      # unix ms
    repo_full_name: str | None
    provider: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeLog:
    """A single runtime log entry from a deployed function/service."""
    timestamp: int           # unix ms
    level: str               # info, warn, error
    message: str
    source: str = "runtime"  # runtime, build, system
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    host: str | None = None
    request_id: str | None = None
    provider: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildLog:
    """A single build/CI log line."""
    timestamp: int
    level: str           # info, warn, error
    message: str
    source: str = "build"
    step: str | None = None   # e.g. "Install dependencies", "npm run build"
    provider: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)


# ─── Abstract Provider ────────────────────────────────────────────────────────


class DeploymentProvider(ABC):
    """
    Abstract base class for all deployment/hosting providers.

    Each provider implements the subset of methods relevant to its platform:
    - Vercel    → get_runtime_logs (serverless function logs)
    - GitHub    → get_build_logs (Actions CI logs)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier, e.g. 'vercel', 'github', 'render'."""
        ...

    @abstractmethod
    async def get_deployment(self, deployment_id: str) -> DeploymentInfo | None:
        """Fetch normalized deployment metadata by ID."""
        ...

    @abstractmethod
    async def get_deployment_status(self, deployment_id: str) -> str:
        """Return current deployment state string (e.g. 'READY', 'ERROR')."""
        ...

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
        Fetch runtime logs for a deployment.

        Default implementation returns an empty list.
        Override in providers that support runtime log access (e.g. Vercel).
        """
        return []

    async def get_build_logs(
        self,
        run_id: str | int,
        repo_full_name: str,
        *,
        max_lines: int = 500,
    ) -> list[BuildLog]:
        """
        Fetch CI/build logs for a workflow run.

        Default implementation returns an empty list.
        Override in providers that support build log access (e.g. GitHub).
        """
        return []
