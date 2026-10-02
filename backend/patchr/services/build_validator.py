"""
Build Validator Service

Validates a proposed patch by:
  1. Cloning the repository to a temp directory (git clone --depth=1)
  2. Applying the file changes from the patch
  3. Running the fastest available build check:
     - tsc --noEmit --skipLibCheck  (TypeScript projects, ~10-30s)
     - npm run build                (fallback)
  4. Returning a structured BuildValidationResult

This is the core safety gate from Section 20 of the implementation blueprint.
A patch MUST pass validation before a GitHub branch is created.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_RETRIES: int = 2        # Max autonomous patch retries before HUMAN_REVIEW_REQUIRED
MAX_OUTPUT_LINES: int = 100
CLONE_TIMEOUT: int = 60
INSTALL_TIMEOUT: int = 90
BUILD_TIMEOUT: int = 120

IS_WINDOWS = platform.system() == "Windows"


# ─── Result ───────────────────────────────────────────────────────────────────


@dataclass
class BuildValidationResult:
    """
    Result of the build validation step.

    passed   — True only if the build/typecheck exited 0.
    stage    — clone | apply | install | typecheck | build | timeout | skipped | error
    error    — Short human-readable failure reason.
    structured_feedback — dict injected into the AI retry prompt.
    """

    passed: bool
    stage: str
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    duration_seconds: float = 0.0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def structured_feedback(self) -> dict[str, Any]:
        """Formatted feedback for the AI retry prompt."""
        return {
            "validation_status": "passed" if self.passed else "failed",
            "stage": self.stage,
            "error": self.error or self._key_error(),
            "stderr_excerpt": self.stderr[-2000:] if self.stderr else "",
        }

    def _key_error(self) -> str:
        if not self.stderr:
            return ""
        lines = self.stderr.strip().split("\n")
        error_lines = [
            ln for ln in lines
            if any(kw in ln for kw in [
                "error TS", "Error:", "ERROR", "failed",
                "Cannot find", "Module not found", "SyntaxError",
                "TypeError", "ENOENT",
            ])
        ]
        return "\n".join(error_lines[:15]) if error_lines else "\n".join(lines[-30:])


# ─── Subprocess helpers ───────────────────────────────────────────────────────


def _tail(text: str, max_lines: int = MAX_OUTPUT_LINES) -> str:
    if not text:
        return ""
    return "\n".join(text.split("\n")[-max_lines:])


def _run_sync(cmd: list[str], cwd: str, timeout: int) -> tuple[int, str, str]:
    """
    Synchronous subprocess runner.
    Returns (returncode, stdout, stderr).
    Special codes: -1=timeout, -2=not found, -3=other error.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=IS_WINDOWS,  # Windows needs shell for PATH resolution of npm/npx
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timed out after {timeout}s"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"
    except Exception as exc:
        return -3, "", str(exc)


async def _run(cmd: list[str], cwd: str, timeout: int) -> tuple[int, str, str]:
    """Async wrapper — runs in thread pool so the event loop stays responsive."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync, cmd, cwd, timeout)


# ─── Patch application ────────────────────────────────────────────────────────


def _apply_file_changes(tmp_dir: str, file_changes: list[dict]) -> list[str]:
    """
    Write patched file contents into the cloned repository.

    Strategy:
    - modify/create with original_content: search-and-replace in existing file.
    - modify/create without original_content: write patched_content as full file.
    - delete: remove file if it exists.

    Returns list of error strings (empty = success).
    """
    errors: list[str] = []

    for fc in file_changes:
        rel_path: str = fc.get("path", "")
        change_type: str = fc.get("change_type", "modify")
        patched: str = fc.get("patched_content") or ""
        original: str = fc.get("original_content") or ""

        if not rel_path:
            errors.append("File change missing 'path'")
            continue

        abs_path = os.path.join(tmp_dir, rel_path.lstrip("/\\"))

        try:
            if change_type == "delete":
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                continue

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            if original and os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                    existing = fh.read()
                new_content = (
                    existing.replace(original, patched, 1)
                    if original in existing
                    else patched  # original not found → use full patched content
                )
            else:
                new_content = patched

            with open(abs_path, "w", encoding="utf-8") as fh:
                fh.write(new_content)

        except Exception as exc:
            errors.append(f"{rel_path}: {exc}")

    return errors


# ─── Main Validator ───────────────────────────────────────────────────────────


async def validate_patch(
    *,
    repo_full_name: str,
    default_branch: str,
    file_changes: list[dict],
    github_token: str,
    framework: str | None = None,
) -> BuildValidationResult:
    """
    Full validation pipeline: clone → apply → (install) → typecheck/build.

    Always cleans up the temp directory, even on error.
    """
    log = logger.bind(repo=repo_full_name, n_files=len(file_changes), framework=framework)
    tmp_dir = tempfile.mkdtemp(prefix="patchr_val_")
    t_start = datetime.now(timezone.utc)

    def elapsed() -> float:
        return (datetime.now(timezone.utc) - t_start).total_seconds()

    try:
        # ── Step 1: Clone ─────────────────────────────────────────────────────
        clone_url = (
            f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"
        )
        log.info("build_val_clone_start", branch=default_branch)

        rc, _, stderr = await _run(
            ["git", "clone", "--depth=1", f"--branch={default_branch}", clone_url, tmp_dir],
            cwd=os.path.dirname(tmp_dir),
            timeout=CLONE_TIMEOUT,
        )

        if rc != 0:
            log.warning("build_val_clone_failed", rc=rc)
            return BuildValidationResult(
                passed=False, stage="clone",
                stderr=_tail(stderr),
                error=f"git clone failed (rc={rc}): {stderr[:200]}",
                duration_seconds=elapsed(),
            )

        log.info("build_val_clone_ok")

        # ── Step 2: Apply patch ───────────────────────────────────────────────
        apply_errors = _apply_file_changes(tmp_dir, file_changes)
        if apply_errors:
            log.warning("build_val_apply_failed", errors=apply_errors)
            return BuildValidationResult(
                passed=False, stage="apply",
                error="; ".join(apply_errors[:5]),
                duration_seconds=elapsed(),
            )
        log.info("build_val_patch_applied", n_files=len(file_changes))

        # ── Step 3: Detect project type ───────────────────────────────────────
        has_pkg = os.path.exists(os.path.join(tmp_dir, "package.json"))
        has_ts  = os.path.exists(os.path.join(tmp_dir, "tsconfig.json"))
        has_nm  = os.path.exists(os.path.join(tmp_dir, "node_modules"))

        if not has_pkg:
            log.info("build_val_no_pkg_json_skip")
            return BuildValidationResult(
                passed=True, stage="skipped",
                stdout="No package.json — patch applied cleanly (non-JS project).",
                duration_seconds=elapsed(),
            )

        # ── Step 4: npm ci (only if node_modules absent) ──────────────────────
        if not has_nm:
            log.info("build_val_npm_ci_start")
            rc, out, err = await _run(
                ["npm", "ci", "--prefer-offline", "--no-audit", "--quiet"],
                cwd=tmp_dir, timeout=INSTALL_TIMEOUT,
            )
            if rc not in (0, -2):  # -2 = npm not on PATH → skip gracefully
                log.warning("build_val_npm_ci_failed", rc=rc)
                return BuildValidationResult(
                    passed=False, stage="install",
                    stdout=_tail(out), stderr=_tail(err),
                    error=f"npm ci failed (rc={rc})",
                    duration_seconds=elapsed(),
                )
            log.info("build_val_npm_ci_ok", rc=rc)

        # ── Step 5a: TypeScript typecheck (fast path) ─────────────────────────
        if has_ts:
            log.info("build_val_tsc_start")
            tsc_candidates = [
                ["npx", "--no", "tsc", "--noEmit", "--skipLibCheck"],
                [
                    os.path.join(tmp_dir, "node_modules", ".bin", "tsc"),
                    "--noEmit", "--skipLibCheck",
                ],
            ]
            tsc_rc, tsc_out, tsc_err = -2, "", "tsc not available"
            for cmd in tsc_candidates:
                tsc_rc, tsc_out, tsc_err = await _run(cmd, cwd=tmp_dir, timeout=BUILD_TIMEOUT)
                if tsc_rc != -2:
                    break

            if tsc_rc == -1:
                return BuildValidationResult(
                    passed=False, stage="timeout",
                    error=f"TypeScript check timed out after {BUILD_TIMEOUT}s",
                    duration_seconds=elapsed(),
                )

            if tsc_rc != -2:
                log.info("build_val_tsc_done", rc=tsc_rc)
                return BuildValidationResult(
                    passed=(tsc_rc == 0),
                    stage="typecheck",
                    stdout=_tail(tsc_out),
                    stderr=_tail(tsc_err),
                    error="" if tsc_rc == 0 else f"TypeScript errors found (rc={tsc_rc})",
                    duration_seconds=elapsed(),
                )

            log.info("build_val_tsc_unavailable_fallback")

        # ── Step 5b: npm run build (fallback) ─────────────────────────────────
        log.info("build_val_npm_build_start")
        rc, out, err = await _run(
            ["npm", "run", "build"], cwd=tmp_dir, timeout=BUILD_TIMEOUT
        )

        if rc == -1:
            return BuildValidationResult(
                passed=False, stage="timeout",
                error=f"Build timed out after {BUILD_TIMEOUT}s",
                duration_seconds=elapsed(),
            )

        log.info("build_val_npm_build_done", rc=rc)
        return BuildValidationResult(
            passed=(rc == 0),
            stage="build",
            stdout=_tail(out),
            stderr=_tail(err),
            error="" if rc == 0 else f"npm run build failed (rc={rc})",
            duration_seconds=elapsed(),
        )

    except Exception as exc:
        logger.error("build_val_unexpected_error", error=str(exc))
        return BuildValidationResult(
            passed=False, stage="error", error=str(exc),
            duration_seconds=elapsed(),
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        log.info("build_val_cleanup_done", duration_seconds=elapsed())
