"""
Provider layer for PatchR deployment integrations.

PatchR's log architecture:
  - Vercel Provider  → Runtime logs (serverless function invocations)
  - GitHub Provider  → Build/CI logs (GitHub Actions workflows)

Usage:
    from patchr.services.providers import VercelProvider, GitHubProvider
"""

from patchr.services.providers.base import (
    BuildLog,
    DeploymentInfo,
    DeploymentProvider,
    RuntimeLog,
)
from patchr.services.providers.github_provider import GitHubProvider
from patchr.services.providers.vercel_provider import VercelProvider

__all__ = [
    "DeploymentProvider",
    "DeploymentInfo",
    "RuntimeLog",
    "BuildLog",
    "VercelProvider",
    "GitHubProvider",
]
