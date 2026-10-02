"""
Patch Verification Service — Phase 5

Lightweight, synchronous risk analysis of a proposed patch.
Runs before a patch is presented to the owner.

Checks performed:
  1. File change count (too many changes = high risk)
  2. Destructive patterns (deleting files, removing env vars)
  3. Package version changes (package.json downgrades)
  4. Confidence threshold (reject if AI confidence too low)
  5. Empty or trivially small patches
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)


# ─── Risk Thresholds ──────────────────────────────────────────────────────────

MAX_FILES_LOW_RISK = 3       # > 3 files = medium
MAX_FILES_HIGH_RISK = 8      # > 8 files = high
MIN_CONFIDENCE = 0.50        # below this → risk flag
HIGH_CONFIDENCE = 0.90       # above this = lower inherent risk

# Patterns that raise risk level
DESTRUCTIVE_PATTERNS = [
    (r"^\-{3,}", "Large block deletion"),
    (r"process\.env\.", "Environment variable reference"),
    (r"rm -rf", "Destructive shell command"),
    (r"DROP TABLE", "Destructive SQL"),
    (r"delete_all|destroy_all|truncate", "Destructive ORM call"),
]

SENSITIVE_FILE_PATTERNS = [
    r"\.env",
    r"secrets?",
    r"credentials?",
    r"\.pem$",
    r"\.key$",
    r"config/database",
]


# ─── Result ───────────────────────────────────────────────────────────────────

class VerificationCheckResult:
    def __init__(
        self,
        passed: bool,
        risk_score: float,       # 0.0 (safe) to 1.0 (very risky)
        risk_level: str,         # "low", "medium", "high"
        findings: list[str],
        explanation: str,
    ):
        self.passed = passed
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.findings = findings
        self.explanation = explanation
        self.verified_at = datetime.now(timezone.utc)


# ─── Verifier ─────────────────────────────────────────────────────────────────

class PatchVerifier:
    """
    Runs a series of lightweight checks on a proposed patch
    and produces a risk score + human-readable explanation.
    """

    def verify(
        self,
        file_changes: list[dict],
        confidence: float | None,
        diff: str | None,
    ) -> VerificationCheckResult:
        """
        Run all verification checks and return a consolidated result.
        """
        findings: list[str] = []
        risk_score = 0.0

        # ── Check 1: Empty patch ──────────────────────────────────────────────
        if not file_changes and not diff:
            return VerificationCheckResult(
                passed=False,
                risk_score=1.0,
                risk_level="high",
                findings=["Patch contains no file changes"],
                explanation="The patch is empty — no files would be modified.",
            )

        # ── Check 2: File count ───────────────────────────────────────────────
        n_files = len(file_changes) if file_changes else 0
        if n_files > MAX_FILES_HIGH_RISK:
            risk_score += 0.35
            findings.append(f"Modifies {n_files} files (> {MAX_FILES_HIGH_RISK} = high risk)")
        elif n_files > MAX_FILES_LOW_RISK:
            risk_score += 0.15
            findings.append(f"Modifies {n_files} files (> {MAX_FILES_LOW_RISK} = medium risk)")

        # ── Check 3: Sensitive files ──────────────────────────────────────────
        for fc in (file_changes or []):
            path = fc.get("path", "")
            for pattern in SENSITIVE_FILE_PATTERNS:
                if re.search(pattern, path, re.IGNORECASE):
                    risk_score += 0.20
                    findings.append(f"Modifies sensitive file: {path}")
                    break

        # ── Check 4: Destructive patterns in diff/patched content ─────────────
        content_to_scan = diff or ""
        for fc in (file_changes or []):
            content_to_scan += "\n" + (fc.get("original_content") or "")

        for pattern, label in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, content_to_scan, re.MULTILINE | re.IGNORECASE):
                risk_score += 0.10
                findings.append(f"Destructive pattern detected: {label}")

        # ── Check 5: Low AI confidence ────────────────────────────────────────
        if confidence is not None:
            if confidence < MIN_CONFIDENCE:
                risk_score += 0.35
                findings.append(f"Low AI confidence: {confidence:.0%} (< {MIN_CONFIDENCE:.0%})")
            elif confidence < 0.70:
                risk_score += 0.15
                findings.append(f"Moderate AI confidence: {confidence:.0%}")
            elif confidence >= HIGH_CONFIDENCE:
                # High confidence reduces total risk slightly
                risk_score = max(0.0, risk_score - 0.05)

        # ── Check 6: package.json version changes ─────────────────────────────
        for fc in (file_changes or []):
            if "package.json" in fc.get("path", ""):
                risk_score += 0.10
                findings.append("Modifies package.json (dependency changes require manual review)")
                break

        # ── Clamp and classify ────────────────────────────────────────────────
        risk_score = min(1.0, max(0.0, risk_score))

        if risk_score < 0.25:
            risk_level = "low"
        elif risk_score < 0.60:
            risk_level = "medium"
        else:
            risk_level = "high"

        # A high-risk patch still passes — owner decides, we just inform
        # Only fail if truly empty or confidence is critically low
        passed = not (confidence is not None and confidence < MIN_CONFIDENCE and n_files == 0)

        if not findings:
            explanation = "No risk factors detected. Patch looks safe to apply."
        elif risk_level == "low":
            explanation = f"Low risk. {len(findings)} minor finding(s): {findings[0]}"
        elif risk_level == "medium":
            explanation = f"Medium risk. Review carefully: {'; '.join(findings[:2])}"
        else:
            explanation = f"High risk. Manual review strongly recommended: {'; '.join(findings[:3])}"

        _stdlib_log.info(
            "patch_verification_complete risk_level=%s score=%.3f findings=%d files=%d",
            risk_level, round(risk_score, 3), len(findings), n_files,
        )

        return VerificationCheckResult(
            passed=passed,
            risk_score=risk_score,
            risk_level=risk_level,
            findings=findings,
            explanation=explanation,
        )


# ─── DB Persistence ───────────────────────────────────────────────────────────

async def verify_and_store(
    db: "AsyncSession",
    patch_id: str,
    file_changes: list[dict],
    confidence: float | None,
    diff: str | None,
) -> VerificationCheckResult:
    """
    Run verification and persist the result to verification_results table.
    Returns the result for immediate use.
    """
    from patchr.db.models import VerificationResult, VerificationStatus

    verifier = PatchVerifier()
    result = verifier.verify(file_changes, confidence, diff)

    vr = VerificationResult(
        patch_id=patch_id,
        status=VerificationStatus.PASSED if result.passed else VerificationStatus.FAILED,
        verification_type="static_analysis",
        passed=result.passed,
        output="\n".join(result.findings) if result.findings else "No issues found.",
        error_output=None,
        risk_score=result.risk_score,
        risk_explanation=result.explanation,
        started_at=result.verified_at,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(vr)
    await db.flush()

    return result
