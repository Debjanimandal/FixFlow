"""
GitHub API Integration Client — Phase 2

Uses a Personal Access Token (PAT) for now.
Architecture is designed to be upgraded to GitHub App auth later
by simply swapping out how the token is obtained.

All methods are async and use httpx under the hood.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ─── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class RepoInfo:
    github_id: int
    full_name: str
    name: str
    default_branch: str
    private: bool
    description: str | None


@dataclass
class CommitInfo:
    sha: str
    message: str
    author_name: str
    author_email: str
    url: str
    added_files: list[str]
    removed_files: list[str]
    modified_files: list[str]

    @property
    def all_changed_files(self) -> list[str]:
        return self.added_files + self.modified_files + self.removed_files


@dataclass
class FileDiff:
    """A single file's changes from a commit comparison."""
    filename: str
    status: str          # added, removed, modified, renamed
    additions: int
    deletions: int
    patch: str | None    # unified diff text, None if binary or too large


@dataclass
class CommitComparison:
    """Result of comparing two commits (base...head)."""
    base_commit: str
    head_commit: str
    files: list[FileDiff]
    total_additions: int
    total_deletions: int

    @property
    def changed_file_paths(self) -> list[str]:
        return [f.filename for f in self.files]


@dataclass
class FileContent:
    path: str
    content: str         # decoded text content
    sha: str             # blob SHA
    size: int


class GitHubError(Exception):
    """Raised when GitHub API returns an error response."""
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"GitHub API {status}: {message}")


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub API rate limit is exceeded."""
    pass


# ─── Client ───────────────────────────────────────────────────────────────────


class GitHubClient:
    """
    Async GitHub REST API v3 client.

    Authenticated with a Personal Access Token.
    Required token scopes: repo (read), deployments (read)

    Usage:
        async with GitHubClient.from_token(token) as client:
            repo = await client.get_repo("acme/my-app")
    """

    BASE_URL = "https://api.github.com"
    TIMEOUT = 30.0  # seconds

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "FixFlow/0.1.0",
        }
        self._client: httpx.AsyncClient | None = None

    # ─── Context Manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> GitHubClient:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._headers,
            timeout=self.TIMEOUT,
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GitHubClient must be used as an async context manager")
        return self._client

    async def _get(self, path: str, **params) -> Any:
        client = self._get_client()
        response = await client.get(path, params=params)
        self._raise_for_status(response)
        return response.json()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            raise GitHubRateLimitError(429, "Rate limit exceeded")
        if response.status_code >= 400:
            try:
                msg = response.json().get("message", response.text)
            except Exception:
                msg = response.text
            raise GitHubError(response.status_code, msg)

    # ─── Repository ───────────────────────────────────────────────────────────

    async def get_repo(self, full_name: str) -> RepoInfo:
        """Fetch repository metadata."""
        data = await self._get(f"/repos/{full_name}")
        return RepoInfo(
            github_id=data["id"],
            full_name=data["full_name"],
            name=data["name"],
            default_branch=data["default_branch"],
            private=data["private"],
            description=data.get("description"),
        )

    # ─── Commits ──────────────────────────────────────────────────────────────

    async def get_commit(self, full_name: str, sha: str) -> CommitInfo:
        """Fetch a single commit with its changed files."""
        data = await self._get(f"/repos/{full_name}/commits/{sha}")
        commit = data["commit"]
        files = data.get("files", [])

        added = [f["filename"] for f in files if f["status"] == "added"]
        removed = [f["filename"] for f in files if f["status"] == "removed"]
        modified = [f["filename"] for f in files if f["status"] in ("modified", "renamed", "changed")]

        return CommitInfo(
            sha=data["sha"],
            message=commit["message"],
            author_name=commit["author"]["name"],
            author_email=commit["author"]["email"],
            url=data["html_url"],
            added_files=added,
            removed_files=removed,
            modified_files=modified,
        )

    async def compare_commits(
        self, full_name: str, base: str, head: str
    ) -> CommitComparison:
        """
        Compare two commits and get file diffs.
        base..head — files that changed going from base to head.
        """
        data = await self._get(f"/repos/{full_name}/compare/{base}...{head}")
        files = []
        total_add = total_del = 0
        for f in data.get("files", []):
            diff = FileDiff(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch"),
            )
            files.append(diff)
            total_add += diff.additions
            total_del += diff.deletions

        return CommitComparison(
            base_commit=data["base_commit"]["sha"],
            head_commit=data["merge_base_commit"]["sha"],
            files=files,
            total_additions=total_add,
            total_deletions=total_del,
        )

    # ─── File Content ─────────────────────────────────────────────────────────

    async def get_file_content(
        self, full_name: str, path: str, ref: str
    ) -> FileContent | None:
        """
        Fetch the decoded content of a file at a given ref.
        Returns None if the file doesn't exist (404) or is a directory/binary.
        """
        try:
            data = await self._get(
                f"/repos/{full_name}/contents/{path}", ref=ref
            )
        except GitHubError as e:
            if e.status == 404:
                return None
            raise

        if data.get("type") != "file":
            return None

        # GitHub returns base64-encoded content
        try:
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None

        return FileContent(
            path=path,
            content=raw,
            sha=data["sha"],
            size=data["size"],
        )

    async def get_multiple_files(
        self, full_name: str, paths: list[str], ref: str, max_files: int = 10
    ) -> dict[str, FileContent]:
        """
        Fetch multiple files concurrently. Skips files that don't exist.
        Respects max_files limit to avoid excessive API calls.
        """
        import asyncio
        results: dict[str, FileContent] = {}
        paths_to_fetch = paths[:max_files]

        async def fetch_one(path: str):
            try:
                fc = await self.get_file_content(full_name, path, ref)
                if fc:
                    results[path] = fc
            except GitHubError:
                pass  # Skip files that error

        await asyncio.gather(*[fetch_one(p) for p in paths_to_fetch])
        return results

    # ─── GitHub Actions Logs ───────────────────────────────────────────────────

    async def get_failed_workflow_logs(
        self,
        full_name: str,
        commit_sha: str | None = None,
    ) -> str | None:
        """
        Fetch the error output from GitHub Actions for a failed workflow run.

        Finds the most recent failed run for the given commit SHA, downloads
        the job log, and returns the error-relevant lines (up to 4000 chars).
        This is used to give the AI the ACTUAL build error message.
        """
        # 1. Find the failed run for this commit
        params: dict = {"status": "failure", "per_page": 5}
        if commit_sha:
            params["head_sha"] = commit_sha

        try:
            runs_data = await self._get(f"/repos/{full_name}/actions/runs", **params)
        except GitHubError:
            return None

        runs = runs_data.get("workflow_runs", [])
        if not runs:
            return None

        run_id = runs[0]["id"]
        run_name = runs[0].get("name", "CI")

        # 2. Get jobs for the run → find the failed job
        try:
            jobs_data = await self._get(f"/repos/{full_name}/actions/runs/{run_id}/jobs")
        except GitHubError:
            return None

        jobs = jobs_data.get("jobs", [])
        failed_job = next((j for j in jobs if j.get("conclusion") == "failure"), None)
        if not failed_job:
            return None

        job_id = failed_job["id"]
        job_name = failed_job.get("name", "build")
        failed_steps = [
            s["name"] for s in failed_job.get("steps", [])
            if s.get("conclusion") == "failure"
        ]

        # 3. Download the raw log for the failed job
        client = self._get_client()
        try:
            resp = await client.get(
                f"/repos/{full_name}/actions/jobs/{job_id}/logs",
                follow_redirects=True,
            )
            if resp.status_code == 200:
                raw_log = resp.text
                # Filter for error-relevant lines only
                error_kw = {
                    "error", "failed", "cannot find", "not found", "undefined",
                    "module not found", "cannot resolve", "typeerror",
                    "syntaxerror", "referenceerror", "importerror",
                    "build failed", "exit code", "npm error", "yarn error",
                }
                error_lines = [
                    line.strip()
                    for line in raw_log.splitlines()
                    if any(kw in line.lower() for kw in error_kw)
                    and line.strip()
                ]
                # Keep the last 60 lines (root error is usually at the bottom)
                condensed = error_lines[-60:] if len(error_lines) > 60 else error_lines
                if condensed:
                    header = (
                        f"Workflow: {run_name} | Job: {job_name}\n"
                        f"Failed step(s): {', '.join(failed_steps) if failed_steps else 'unknown'}\n"
                        f"Error log:\n"
                    )
                    return header + "\n".join(condensed)
        except Exception:
            pass

        # Fallback: just return the failed step names
        if failed_steps:
            return (
                f"GitHub Actions job '{job_name}' in '{run_name}' failed at steps: "
                + ", ".join(failed_steps)
            )
        return None


    async def register_webhook(
        self,
        full_name: str,
        webhook_url: str,
        secret: str,
        events: list[str] | None = None,
    ) -> int:
        """
        Register a webhook on a repo.
        Returns the webhook ID (for deregistration).
        """
        client = self._get_client()
        payload = {
            "name": "web",
            "active": True,
            "events": events or ["push", "deployment_status"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }
        response = await client.post(f"/repos/{full_name}/hooks", json=payload)
        self._raise_for_status(response)
        return response.json()["id"]

    async def delete_webhook(self, full_name: str, hook_id: int) -> None:
        """Delete a webhook registration."""
        client = self._get_client()
        response = await client.delete(f"/repos/{full_name}/hooks/{hook_id}")
        if response.status_code not in (204, 404):
            self._raise_for_status(response)

    # ─── Pull Requests & Branch Management ───────────────────────────────────

    async def get_branch_sha(self, full_name: str, branch: str) -> str:
        """Get the HEAD commit SHA of a branch."""
        data = await self._get(f"/repos/{full_name}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    async def create_branch(
        self, full_name: str, new_branch: str, from_sha: str
    ) -> None:
        """Create a new branch at the given commit SHA."""
        client = self._get_client()
        response = await client.post(
            f"/repos/{full_name}/git/refs",
            json={"ref": f"refs/heads/{new_branch}", "sha": from_sha},
        )
        # 422 = branch already exists, treat as ok
        if response.status_code not in (201, 422):
            self._raise_for_status(response)

    async def update_file(
        self,
        full_name: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> None:
        """
        Create or update a file on a branch via GitHub Contents API.
        sha is required when updating an existing file.
        Content must be base64-encoded.
        """
        import base64 as b64
        client = self._get_client()
        payload: dict[str, Any] = {
            "message": message,
            "content": b64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        response = await client.put(
            f"/repos/{full_name}/contents/{path}",
            json=payload,
        )
        self._raise_for_status(response)

    async def create_pull_request(
        self,
        full_name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = True,
    ) -> dict[str, Any]:
        """Create a PR. Returns the full PR object from GitHub."""
        client = self._get_client()
        response = await client.post(
            f"/repos/{full_name}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
                "draft": draft,
            },
        )
        self._raise_for_status(response)
        return response.json()

    async def create_patch_pr(
        self,
        full_name: str,
        default_branch: str,
        patch_id: str,
        incident_title: str,
        file_changes: list[dict],
        patch_description: str,
    ) -> tuple[str, int, str]:
        """
        Full workflow: create branch → apply file changes → open draft PR.

        Returns: (branch_name, pr_number, pr_html_url)

        file_changes: list of dicts with keys:
          path, patched_content, original_content, change_type, explanation
        """
        branch_name = f"patchr/fix-{patch_id[:8]}"

        # 1. Get base branch SHA
        base_sha = await self.get_branch_sha(full_name, default_branch)

        # 2. Create the patch branch
        await self.create_branch(full_name, branch_name, base_sha)
        logger.info("github_branch_created", branch=branch_name, repo=full_name)

        # 3. Apply each file change
        for change in file_changes:
            path = change.get("path", "")
            new_content = change.get("patched_content") or ""
            change_type = change.get("change_type", "modify")
            explanation = change.get("explanation", "")

            if not path or not new_content:
                continue

            # Get current file SHA (needed to update existing files)
            existing = None
            if change_type != "create":
                existing = await self.get_file_content(full_name, path, default_branch)

            commit_msg = f"fix({path}): {explanation or 'PatchR automated fix'}"
            await self.update_file(
                full_name=full_name,
                path=path,
                content=new_content,
                message=commit_msg,
                branch=branch_name,
                sha=existing.sha if existing else None,
            )
            logger.info("github_file_updated", path=path, branch=branch_name)

        # 4. Open the draft PR
        pr_body = (
            f"## 🔧 PatchR Automated Fix\n\n"
            f"**Incident:** {incident_title}\n\n"
            f"**Description:** {patch_description}\n\n"
            f"---\n"
            f"*This PR was generated automatically by [PatchR](https://github.com/your-org/patchr). "
            f"Review carefully before merging.*\n\n"
            f"**Patch ID:** `{patch_id}`"
        )
        pr_data = await self.create_pull_request(
            full_name=full_name,
            title=f"fix: {incident_title[:72]}",
            body=pr_body,
            head_branch=branch_name,
            base_branch=default_branch,
            draft=True,
        )

        logger.info(
            "github_pr_created",
            repo=full_name,
            pr_number=pr_data["number"],
            url=pr_data["html_url"],
        )
        return branch_name, pr_data["number"], pr_data["html_url"]

    async def push_changes_to_branch(
        self,
        full_name: str,
        branch: str,
        file_changes: list[dict],
        incident_title: str,
    ) -> tuple[str, list[str]]:
        """
        Commit the patch file changes DIRECTLY to an existing branch (no PR).

        Each file is written via the Contents API, which produces one commit per
        file on the target branch. Returns (commit_url_of_branch, committed_paths).

        file_changes: list of dicts with keys:
          path, patched_content, original_content, change_type, explanation
        """
        committed_paths: list[str] = []

        for change in file_changes:
            path = change.get("path", "")
            new_content = change.get("patched_content") or ""
            change_type = change.get("change_type", "modify")
            explanation = change.get("explanation", "")

            if not path or not new_content:
                continue

            # Need the current blob SHA to update an existing file.
            existing = None
            if change_type != "create":
                existing = await self.get_file_content(full_name, path, branch)

            commit_msg = f"fix({path}): {explanation or 'FixFlow automated fix'} [{incident_title[:60]}]"
            await self.update_file(
                full_name=full_name,
                path=path,
                content=new_content,
                message=commit_msg,
                branch=branch,
                sha=existing.sha if existing else None,
            )
            committed_paths.append(path)
            logger.info("github_file_pushed", path=path, branch=branch, repo=full_name)

        branch_url = f"https://github.com/{full_name}/tree/{branch}"
        logger.info(
            "github_direct_push_complete",
            repo=full_name,
            branch=branch,
            files=len(committed_paths),
        )
        return branch_url, committed_paths

    async def create_webhook(
        self,
        full_name: str,
        url: str,
        secret: str,
        events: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Register a webhook on a GitHub repository.

        Returns the created webhook object (includes 'id' field).
        Raises GitHubError if the repo doesn't exist or token lacks permission.
        """
        client = self._get_client()
        response = await client.post(
            f"/repos/{full_name}/hooks",
            json={
                "name": "web",
                "active": True,
                "events": events or ["push", "deployment_status"],
                "config": {
                    "url": url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0",
                },
            },
        )
        self._raise_for_status(response)
        return response.json()

    async def delete_webhook(self, full_name: str, hook_id: int) -> None:
        """Delete a registered webhook by ID."""
        client = self._get_client()
        response = await client.delete(f"/repos/{full_name}/hooks/{hook_id}")
        if response.status_code not in (204, 404):
            self._raise_for_status(response)

    async def get_pr(self, full_name: str, pr_number: int) -> dict[str, Any]:
        """
        Get a pull request's current state.

        Returns dict with 'state' (open/closed), 'merged' (bool), 'merged_at' (str|None).
        """
        return await self._get(f"/repos/{full_name}/pulls/{pr_number}")
    # ─── Deployments API ──────────────────────────────────────────────────────

    async def get_deployments(
        self, full_name: str, environment: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Fetch recent deployments for a repo from GitHub's Deployments API.

        GitHub tracks ALL deployments including those from Vercel, Netlify, etc.
        Each deployment has an associated environment URL and status.

        Returns raw deployment dicts with: id, sha, ref, environment, 
        description, creator, created_at, payload.
        """
        params: dict[str, Any] = {"per_page": limit}
        if environment:
            params["environment"] = environment
        client = self._get_client()
        response = await client.get(f"/repos/{full_name}/deployments", params=params)
        self._raise_for_status(response)
        return response.json()

    async def get_deployment_statuses(
        self, full_name: str, deployment_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Fetch statuses for a specific deployment.

        Statuses include: success, failure, error, inactive, pending, queued.
        The environment_url field contains the deployed URL (e.g. Vercel preview URL).
        """
        client = self._get_client()
        response = await client.get(
            f"/repos/{full_name}/deployments/{deployment_id}/statuses",
            params={"per_page": limit},
        )
        self._raise_for_status(response)
        return response.json()

    async def detect_vercel_from_deployments(self, full_name: str) -> dict[str, Any] | None:
        """
        Detect if a repo has Vercel deployments by checking GitHub's Deployments API.

        Looks for deployments where the environment_url contains '.vercel.app'
        or the deployment creator is 'vercel[bot]'.

        Returns a dict with deployment info if found:
        {
            "detected": True,
            "environment_url": "https://my-app.vercel.app",
            "state": "success" | "failure" | "error",
            "commit_sha": "abc123...",
            "environment": "Production",
            "created_at": "2026-08-23T...",
        }
        or None if no Vercel deployment is found.
        """
        try:
            deployments = await self.get_deployments(full_name, limit=20)
        except GitHubError:
            return None

        for dep in deployments:
            # Check if this is a Vercel deployment
            creator_login = (dep.get("creator") or {}).get("login", "")
            description = dep.get("description") or ""
            payload_str = str(dep.get("payload") or "")

            is_vercel = (
                creator_login == "vercel[bot]"
                or "vercel" in description.lower()
                or "vercel" in payload_str.lower()
            )

            if not is_vercel:
                continue

            # Get the latest status to find the environment URL
            dep_id = dep.get("id")
            if not dep_id:
                continue

            try:
                statuses = await self.get_deployment_statuses(full_name, dep_id, limit=1)
            except GitHubError:
                continue

            if not statuses:
                continue

            latest_status = statuses[0]
            env_url = latest_status.get("environment_url") or ""
            state = latest_status.get("state", "unknown")

            return {
                "detected": True,
                "environment_url": env_url,
                "state": state,  # success, failure, error, inactive, pending
                "commit_sha": dep.get("sha"),
                "environment": dep.get("environment", "production"),
                "created_at": dep.get("created_at"),
                "deployment_id": dep_id,
            }

        return None

    async def get_recent_deployment_statuses(
        self, full_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get combined deployment + status info for recent deployments.

        Returns a list of dicts, each containing:
        {
            "id": deployment_id,
            "state": "success" | "failure" | "error" | "pending",
            "environment_url": "https://...",
            "commit_sha": "abc...",
            "environment": "Production",
            "created_at": "...",
            "description": "...",
            "is_vercel": bool,
        }
        """
        try:
            deployments = await self.get_deployments(full_name, limit=limit)
        except GitHubError:
            return []

        results = []
        for dep in deployments:
            creator_login = (dep.get("creator") or {}).get("login", "")
            description = dep.get("description") or ""

            is_vercel = (
                creator_login == "vercel[bot]"
                or "vercel" in description.lower()
            )

            dep_id = dep.get("id")
            if not dep_id:
                continue

            # Get latest status
            state = "pending"
            env_url = ""
            try:
                statuses = await self.get_deployment_statuses(full_name, dep_id, limit=1)
                if statuses:
                    state = statuses[0].get("state", "pending")
                    env_url = statuses[0].get("environment_url") or ""
            except GitHubError:
                pass

            results.append({
                "id": dep_id,
                "state": state,
                "environment_url": env_url,
                "commit_sha": dep.get("sha"),
                "environment": dep.get("environment", "production"),
                "created_at": dep.get("created_at"),
                "description": description,
                "is_vercel": is_vercel,
            })

        return results



# ─── Factory ──────────────────────────────────────────────────────────────────


def get_github_client(token: str) -> GitHubClient:
    """
    Create a GitHub client from a PAT token.
    Use as: async with get_github_client(token) as gh: ...
    """
    if not token:
        raise ValueError("GITHUB_TOKEN is not configured. Add it to apps/api/.env")
    return GitHubClient(token)
