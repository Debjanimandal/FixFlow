"""
Context Service — Phase 4

Builds a rich IncidentContext before AI analysis runs.
Fetches:
  1. Changed file contents from GitHub
  2. package.json / pyproject.toml from repo root
  3. tsconfig.json (if TypeScript project)
  4. Framework detection from package.json

This is the difference between the AI working with real code vs. hallucinating fixes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from patchr.ai.provider import IncidentContext
from patchr.db.models import Repository

logger = structlog.get_logger(__name__)

# Root-level files to always attempt to fetch for context
ROOT_CONTEXT_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.ts",
    "vite.config.js",
]

FRAMEWORK_SIGNALS: dict[str, list[str]] = {
    "nextjs": ["next"],
    "vite": ["vite"],
    "react": ["react", "react-dom"],
    "express": ["express"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "nuxt": ["nuxt"],
    "svelte": ["svelte", "@sveltejs/kit"],
    "astro": ["astro"],
}


def _detect_framework(package_json: dict[str, Any] | None) -> str | None:
    """Detect framework from package.json dependencies."""
    if not package_json:
        return None

    all_deps: dict[str, str] = {}
    all_deps.update(package_json.get("dependencies", {}))
    all_deps.update(package_json.get("devDependencies", {}))

    dep_keys = [k.lower() for k in all_deps]

    for framework, signals in FRAMEWORK_SIGNALS.items():
        if any(sig in dep_keys for sig in signals):
            return framework

    return None


async def build_incident_context(
    *,
    incident_id: str,
    repo: Repository,
    commit_sha: str | None,
    affected_files: list[str],
    build_logs: str | None,
    error_message: str | None,
    commit_message: str | None,
    commit_author: str | None,
    github_token: str | None,
) -> IncidentContext:
    """
    Build a fully populated IncidentContext for AI analysis.

    If github_token is not configured, returns a minimal context using only
    the data already stored in the incident record. The AI will still function
    but will have less context to work with.
    """
    log = logger.bind(incident_id=incident_id, repo=repo.full_name)

    relevant_file_contents: dict[str, str] = {}
    package_json: dict[str, Any] | None = None
    framework: str | None = None
    changed_files: list[str] = list(affected_files)

    if github_token and not github_token.startswith("ghp_your"):
        try:
            from patchr.integrations.github import get_github_client, GitHubError

            async with get_github_client(github_token) as gh:
                ref = commit_sha or repo.default_branch or "main"

                # ── 1. Fetch changed file contents ─────────────────────────
                if affected_files:
                    files_to_fetch = affected_files[:8]  # cap at 8 for latency
                    fetched = await gh.get_multiple_files(
                        repo.full_name, files_to_fetch, ref=ref, max_files=8
                    )
                    relevant_file_contents = {
                        path: fc.content for path, fc in fetched.items()
                    }
                    log.info(
                        "context_files_fetched",
                        count=len(relevant_file_contents),
                        paths=list(relevant_file_contents.keys()),
                    )

                # ── 2. Fetch root context files ────────────────────────────
                root_tasks = [
                    gh.get_file_content(repo.full_name, f, ref=repo.default_branch or "main")
                    for f in ROOT_CONTEXT_FILES
                ]
                root_results = await asyncio.gather(*root_tasks, return_exceptions=True)

                for filename, result in zip(ROOT_CONTEXT_FILES, root_results):
                    if isinstance(result, Exception) or result is None:
                        continue

                    # Parse package.json specially
                    if filename == "package.json":
                        try:
                            package_json = json.loads(result.content)
                        except json.JSONDecodeError:
                            log.warning("package_json_parse_error")

                    # Store other root files if they aren't already in relevant_file_contents
                    elif filename not in relevant_file_contents:
                        relevant_file_contents[filename] = result.content

                # ── 3. Detect framework ────────────────────────────────────
                framework = _detect_framework(package_json)
                if framework:
                    log.info("framework_detected", framework=framework)

        except Exception as e:
            log.warning("context_build_github_error", error=str(e))
            # Continue with empty context — don't fail the incident

    else:
        log.info("context_build_skipped_no_token")

    log.info(
        "context_built",
        file_count=len(relevant_file_contents),
        has_package_json=package_json is not None,
        framework=framework,
    )

    return IncidentContext(
        incident_id=incident_id,
        repository_full_name=repo.full_name,
        default_branch=repo.default_branch or "main",
        build_logs=build_logs or "",
        error_message=error_message,
        commit_sha=commit_sha,
        commit_message=commit_message,
        commit_author=commit_author,
        changed_files=changed_files,
        relevant_file_contents=relevant_file_contents,
        package_json=package_json,
        framework=framework,
    )
