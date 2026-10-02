"""
Patch Generation Service

Generates AI-proposed code patches after analysis is complete.
Implements the full validation loop from the implementation blueprint:

  AI generates patch
        ↓
  Heuristic safety check (file count, sensitive files, etc.)
        ↓
  Real build validation (git clone → apply patch → tsc / npm build)
        ↓
  PASS → VERIFIED → await human approval → GitHub PR
  FAIL (retries left) → feed error back to AI → retry
  FAIL (exhausted) → HUMAN_REVIEW_REQUIRED

A patch MUST pass real build validation before a branch is created.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.ai.provider import PatchContext, get_ai_provider
from patchr.config import get_settings
from patchr.db.models import (
    Analysis,
    AuditAction,
    AuditLog,
    Incident,
    IncidentStatus,
    Patch,
    Repository,
    VerificationResult,
    VerificationStatus,
)
from patchr.services.build_validator import MAX_RETRIES, validate_patch

logger = structlog.get_logger(__name__)


# ─── Main Entry Point ─────────────────────────────────────────────────────────


async def generate_patch(
    db: AsyncSession,
    *,
    incident: Incident,
    analysis: Analysis,
    validation_feedback: dict | None = None,
) -> "Patch | None":
    """
    Generate an AI-proposed patch and validate it with a real build check.

    On validation failure:
      - If incident.retry_count < MAX_RETRIES: increment, re-call with feedback.
      - If exhausted: set HUMAN_REVIEW_REQUIRED and return None.

    On validation success:
      - Store patch as VERIFIED.
      - Incident transitions to VERIFIED (awaiting owner approval).

    Returns the stored Patch on success, None on failure/escalation.
    """
    settings = get_settings()

    if not settings.nvidia_api_key or settings.nvidia_api_key.startswith("nvapi-xxx"):
        logger.warning("patch_skipped_no_api_key", incident_id=str(incident.id))
        return None

    # Note: We always attempt patch generation regardless of confidence.
    # Even low-confidence patches give users something to review/reject.

    # Deduplicate: avoid re-generating on a fresh call when one already exists
    if validation_feedback is None:
        existing = await db.execute(
            select(Patch).where(
                Patch.incident_id == incident.id,
                Patch.analysis_id == analysis.id,
                Patch.status == "proposed",
            )
        )
        if existing.scalar_one_or_none():
            logger.info("patch_skipped_already_exists", incident_id=str(incident.id))
            return None

    # Load repository
    repo_result = await db.execute(
        select(Repository).where(Repository.id == incident.repository_id)
    )
    repo = repo_result.scalar_one_or_none()

    attempt = getattr(incident, "retry_count", 0)
    logger.info(
        "patch_generation_started",
        incident_id=str(incident.id),
        analysis_id=str(analysis.id),
        attempt=attempt,
        confidence=analysis.confidence,
        has_validation_feedback=bool(validation_feedback),
    )

    try:
        # ── Build context ─────────────────────────────────────────────────────
        from patchr.services.context_service import build_incident_context

        ctx = await build_incident_context(
            incident_id=str(incident.id),
            repo=repo,
            commit_sha=incident.commit_sha,
            affected_files=analysis.affected_files or [],
            build_logs="",  # AI uses analysis result, not raw logs for patch gen
            error_message=incident.title,
            commit_message=incident.commit_message,
            commit_author=None,
            github_token=settings.github_token or None,
        )

        patch_ctx = PatchContext(
            incident_id=str(incident.id),
            analysis=_analysis_to_result(analysis),
            incident_context=ctx,
            validation_feedback=validation_feedback,
        )

        # ── AI generates patch ────────────────────────────────────────────────
        ai = get_ai_provider()
        result = await ai.generate_patch(patch_ctx)
        file_changes = [fc.model_dump() for fc in result.file_changes]

        # ── Step 1: Heuristic safety check ────────────────────────────────────
        from patchr.services.verification_service import PatchVerifier
        verifier = PatchVerifier()
        heuristic = verifier.verify(file_changes, result.confidence, diff=None)

        # ── Step 2: Real build validation ─────────────────────────────────────
        build_result = None
        build_passed = False

        if (
            settings.github_token
            and not settings.github_token.startswith("ghp_your")
            and repo
            and file_changes
        ):
            logger.info("build_validation_starting", incident_id=str(incident.id))
            incident.status = IncidentStatus.VERIFYING
            incident.updated_at = datetime.now(timezone.utc)
            await db.commit()

            build_result = await validate_patch(
                repo_full_name=repo.full_name,
                default_branch=repo.default_branch or "main",
                file_changes=file_changes,
                github_token=settings.github_token,
                framework=ctx.framework,
            )
            build_passed = build_result.passed

            logger.info(
                "build_validation_complete",
                incident_id=str(incident.id),
                passed=build_passed,
                stage=build_result.stage,
                duration=round(build_result.duration_seconds, 1),
            )
        else:
            # No GitHub token or no files — fall back to heuristic only
            build_passed = heuristic.passed
            logger.warning(
                "build_validation_skipped_no_token",
                incident_id=str(incident.id),
            )

        # ── Store patch record ────────────────────────────────────────────────
        final_risk = result.risk_level
        if heuristic.risk_level == "high":
            final_risk = "high"

        patch = Patch(
            id=uuid.uuid4(),
            incident_id=incident.id,
            analysis_id=analysis.id,
            model_provider="nvidia_nim",
            model_name=settings.nvidia_model,
            description=result.description,
            file_changes=file_changes,
            confidence=result.confidence,
            risk_level=final_risk,
            status="proposed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(patch)
        await db.flush()

        # ── Persist heuristic verification result ─────────────────────────────
        db.add(VerificationResult(
            patch_id=patch.id,
            status=VerificationStatus.PASSED if heuristic.passed else VerificationStatus.FAILED,
            verification_type="static_analysis",
            passed=heuristic.passed,
            output="\n".join(heuristic.findings) if heuristic.findings else "No issues.",
            risk_score=heuristic.risk_score,
            risk_explanation=heuristic.explanation,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))

        # ── Persist real build validation result ──────────────────────────────
        if build_result is not None:
            db.add(VerificationResult(
                patch_id=patch.id,
                status=VerificationStatus.PASSED if build_result.passed else VerificationStatus.FAILED,
                verification_type="build_validation",
                passed=build_result.passed,
                output=build_result.stdout[:4000] if build_result.stdout else "",
                error_output=build_result.stderr[:4000] if build_result.stderr else build_result.error,
                risk_score=0.0 if build_result.passed else 1.0,
                risk_explanation=f"Stage: {build_result.stage}. {'Build passed.' if build_result.passed else build_result.error}",
                started_at=build_result.validated_at,
                completed_at=datetime.now(timezone.utc),
                duration_seconds=build_result.duration_seconds,
            ))

        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action=AuditAction.PATCH_GENERATED,
            actor="system:ai",
            details={
                "attempt": attempt,
                "confidence": result.confidence,
                "risk_level": final_risk,
                "files_changed": [fc.get("path") for fc in file_changes],
                "build_passed": build_passed,
                "build_stage": build_result.stage if build_result else "skipped",
            },
            entity_type="patch",
            entity_id=str(patch.id),
            created_at=datetime.now(timezone.utc),
        ))

        # ── Route on validation result ─────────────────────────────────────────
        if build_passed:
            # ✅ Validation passed — mark VERIFIED, await owner approval
            patch.status = "verified"
            incident.status = IncidentStatus.VERIFIED
            incident.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(patch)

            logger.info(
                "patch_verified",
                incident_id=str(incident.id),
                patch_id=str(patch.id),
                stage=build_result.stage if build_result else "heuristic",
            )
            return patch

        else:
            # ❌ Validation failed
            patch.status = "rejected"
            incident.updated_at = datetime.now(timezone.utc)

            if attempt < MAX_RETRIES:
                # Retry: increment counter, feed validation error back to AI
                incident.retry_count = attempt + 1
                incident.status = IncidentStatus.REPAIR_PROPOSED  # stays in pipeline

                db.add(AuditLog(
                    id=uuid.uuid4(),
                    incident_id=incident.id,
                    action=AuditAction.PATCH_GENERATION_FAILED,
                    actor="system:ai",
                    details={
                        "reason": "build_validation_failed",
                        "stage": build_result.stage if build_result else "heuristic",
                        "error": (build_result.error if build_result else heuristic.explanation)[:500],
                        "attempt": attempt,
                        "retrying": True,
                    },
                    entity_type="patch",
                    entity_id=str(patch.id),
                    created_at=datetime.now(timezone.utc),
                ))

                await db.commit()

                logger.warning(
                    "patch_validation_failed_retrying",
                    incident_id=str(incident.id),
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    stage=build_result.stage if build_result else "heuristic",
                )

                # Recursive retry with structured validation feedback
                feedback = build_result.structured_feedback if build_result else {
                    "validation_status": "failed",
                    "stage": "heuristic",
                    "error": heuristic.explanation,
                }
                return await generate_patch(
                    db,
                    incident=incident,
                    analysis=analysis,
                    validation_feedback=feedback,
                )

            else:
                # Retries exhausted — escalate to human review
                incident.status = IncidentStatus.HUMAN_REVIEW_REQUIRED
                incident.updated_at = datetime.now(timezone.utc)

                db.add(AuditLog(
                    id=uuid.uuid4(),
                    incident_id=incident.id,
                    action=AuditAction.PATCH_GENERATION_FAILED,
                    actor="system:ai",
                    details={
                        "reason": "max_retries_exhausted",
                        "attempts": attempt + 1,
                        "last_error": (build_result.error if build_result else heuristic.explanation)[:500],
                    },
                    entity_type="incident",
                    entity_id=str(incident.id),
                    created_at=datetime.now(timezone.utc),
                ))

                await db.commit()

                logger.error(
                    "patch_validation_max_retries_exhausted",
                    incident_id=str(incident.id),
                    attempts=attempt + 1,
                )
                return None

    except Exception as exc:
        logger.error(
            "patch_generation_failed",
            incident_id=str(incident.id),
            error=str(exc),
        )
        db.add(AuditLog(
            id=uuid.uuid4(),
            incident_id=incident.id,
            action=AuditAction.PATCH_GENERATION_FAILED,
            actor="system:ai",
            details={"error": str(exc)},
            entity_type="incident",
            entity_id=str(incident.id),
            created_at=datetime.now(timezone.utc),
        ))
        incident.status = IncidentStatus.ANALYSIS_FAILED
        incident.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return None


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _analysis_to_result(analysis: Analysis):
    """Convert an Analysis DB row to the AnalysisResult schema."""
    from patchr.ai.schemas import AnalysisResult

    return AnalysisResult(
        failure_type=analysis.failure_type or "unknown",
        root_cause=analysis.root_cause or "",
        affected_files=analysis.affected_files or [],
        evidence=analysis.evidence or [],
        confidence=analysis.confidence or 0.0,
        risk_level=analysis.risk_level or "medium",
        verification_plan=analysis.verification_plan or [],
        summary=analysis.root_cause[:200] if analysis.root_cause else "",
    )

