"""
Repair Proof Service

Generates and retrieves the Repair Proof artifact for an incident.
Implements docs/18_REPAIR_PROOF_VERIFICATION.md.

The proof classifies every piece of evidence as:
  - observed: directly received from external signal
  - correlated: deterministically linked by IDs/metadata
  - inferred: AI/system conclusion from evidence
  - synthetic: generated test input or localized reproduction
  - validated: result of an executed check

Critical rule: A patch is VERIFIED only when stored validation evidence exists.
Do not claim "zero regressions" — report "no regressions detected by configured checks."
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from patchr.db.models import (
    CandidateStatus,
    EvidenceLabel,
    Incident,
    IncidentStatus,
    PatchCandidate,
    VerificationRun,
    VerificationStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ── Proof Schema ───────────────────────────────────────────────────────────────


class RepairProof:
    """
    Evidence-backed proof of repair for a single candidate.
    All fields are classified by truthfulness label.
    """

    def __init__(
        self,
        incident: Incident,
        candidate: PatchCandidate,
        verification_runs: list[VerificationRun],
        analysis: dict | None = None,
    ):
        self.incident = incident
        self.candidate = candidate
        self.verification_runs = verification_runs
        self.analysis = analysis or {}

    def to_dict(self) -> dict:
        """Serialize proof to API response format."""
        candidate = self.candidate
        incident = self.incident

        # ── Observed Evidence ─────────────────────────────────────────────────
        observed = []
        if incident.title:
            observed.append({
                "label": EvidenceLabel.OBSERVED.value,
                "item": f"Failure signal: {incident.title[:200]}",
                "source": incident.source.value if incident.source else "unknown",
            })
        if incident.commit_sha:
            observed.append({
                "label": EvidenceLabel.CORRELATED.value,
                "item": f"Correlated commit: {incident.commit_sha[:12]}",
                "source": "github",
            })
        if incident.commit_message:
            observed.append({
                "label": EvidenceLabel.CORRELATED.value,
                "item": f"Commit message: {incident.commit_message[:100]}",
                "source": "github",
            })

        # ── Analysis Evidence ──────────────────────────────────────────────────
        inferred = []
        if self.analysis.get("root_cause"):
            inferred.append({
                "label": EvidenceLabel.INFERRED.value,
                "item": f"Root cause hypothesis: {self.analysis['root_cause'][:300]}",
                "confidence": self.analysis.get("confidence"),
            })
        for ev in (self.analysis.get("evidence") or []):
            inferred.append({
                "label": EvidenceLabel.OBSERVED.value,
                "item": str(ev)[:200],
            })

        # ── Validation Results ─────────────────────────────────────────────────
        validated = []
        for run in self.verification_runs:
            validated.append({
                "label": run.evidence_label.value if run.evidence_label else EvidenceLabel.VALIDATED.value,
                "stage": run.stage,
                "status": run.status.value if run.status else "unknown",
                "passed": run.passed,
                "reproduction_level": run.reproduction_level or "unverified",
                "exit_code": run.exit_code,
                "duration_seconds": run.duration_seconds,
                "stdout_excerpt": _safe_excerpt(run.stdout, 500),
                "stderr_excerpt": _safe_excerpt(run.stderr, 500) if not run.passed else None,
                "risk_score": run.risk_score,
                "risk_explanation": run.risk_explanation,
            })

        # ── Overall validity ───────────────────────────────────────────────────
        is_verified = candidate.is_eligible is True
        build_passed = candidate.build_passed
        reproduction_passed = candidate.reproduction_passed

        # ── Truthfulness summary ───────────────────────────────────────────────
        truthfulness_note = (
            "This proof reflects configured validation results. "
            "Reproduction is localized synthetic — not exact production replay. "
            "Build/test pass does not guarantee future-state correctness. "
            "No regressions detected by configured checks."
        )
        if not is_verified:
            truthfulness_note = (
                "This candidate did not pass all required validation gates. "
                "It is NOT eligible for PR creation."
            )

        return {
            "incident_id": str(incident.id),
            "candidate_id": str(candidate.id),
            "candidate_index": candidate.candidate_index,
            "strategy": candidate.strategy.value if candidate.strategy else None,
            "is_verified": is_verified,
            "is_selected": candidate.is_selected,
            "status": candidate.status.value if candidate.status else None,

            # Evidence sections
            "observed_evidence": observed,
            "inferred_evidence": inferred,
            "validated_evidence": validated,

            # Summary
            "validation_summary": {
                "reproduction_passed": reproduction_passed,
                "build_passed": build_passed,
                "tests_passed": candidate.tests_passed,
                "no_new_failures": candidate.no_new_failures,
                "is_eligible": is_verified,
            },

            # Risk
            "risk": {
                "level": candidate.risk_level,
                "score": candidate.risk_score,
                "discard_reason": candidate.discard_reason,
            },

            # Uncertainty
            "uncertainty": (
                "Root cause is a hypothesis based on AI analysis of available evidence. "
                "Confidence: "
                + (f"{candidate.confidence:.0%}" if candidate.confidence is not None else "unknown")
                + ". Current validation results are the primary evidence."
            ),

            # Human approval boundary
            "human_approval": {
                "required": True,
                "approved_at": candidate.approved_at.isoformat() if candidate.approved_at else None,
                "rejected_at": candidate.rejected_at.isoformat() if candidate.rejected_at else None,
                "rejection_reason": candidate.rejection_reason,
                "note": "PatchR does not automatically merge production changes.",
            },

            "truthfulness_note": truthfulness_note,
        }


# ── Proof Retrieval ────────────────────────────────────────────────────────────


async def get_repair_proof(
    db: "AsyncSession",
    *,
    incident: Incident,
    candidate_id: uuid.UUID | None = None,
) -> dict | None:
    """
    Get the Repair Proof for an incident's selected (or specified) candidate.
    Returns None if no eligible candidate exists.
    """
    from sqlalchemy import select
    from patchr.db.models import Analysis

    # Get candidate
    if candidate_id:
        cand_result = await db.execute(
            select(PatchCandidate).where(
                PatchCandidate.id == candidate_id,
                PatchCandidate.incident_id == incident.id,
            )
        )
        candidate = cand_result.scalar_one_or_none()
    else:
        # Get selected candidate or first eligible
        cand_result = await db.execute(
            select(PatchCandidate).where(
                PatchCandidate.incident_id == incident.id,
                PatchCandidate.is_selected == True,  # noqa: E712
            ).limit(1)
        )
        candidate = cand_result.scalar_one_or_none()

        if not candidate:
            # Fall back to first eligible
            cand_result = await db.execute(
                select(PatchCandidate).where(
                    PatchCandidate.incident_id == incident.id,
                    PatchCandidate.is_eligible == True,  # noqa: E712
                ).order_by(PatchCandidate.candidate_index).limit(1)
            )
            candidate = cand_result.scalar_one_or_none()

    if not candidate:
        return None

    # Get verification runs for this candidate
    runs_result = await db.execute(
        select(VerificationRun).where(
            VerificationRun.candidate_id == candidate.id
        ).order_by(VerificationRun.created_at)
    )
    runs = list(runs_result.scalars().all())

    # Get analysis
    analysis_result = await db.execute(
        select(Analysis).where(
            Analysis.incident_id == incident.id
        ).order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    analysis_dict = {}
    if analysis:
        analysis_dict = {
            "failure_type": analysis.failure_type,
            "root_cause": analysis.root_cause,
            "affected_files": analysis.affected_files,
            "evidence": analysis.evidence,
            "confidence": analysis.confidence,
            "risk_level": analysis.risk_level,
            "summary": analysis.summary,
        }

    proof = RepairProof(
        incident=incident,
        candidate=candidate,
        verification_runs=runs,
        analysis=analysis_dict,
    )
    return proof.to_dict()


async def get_all_candidates_proof(
    db: "AsyncSession",
    *,
    incident: Incident,
) -> list[dict]:
    """
    Get proof for ALL candidates (for Patch Arena table view).
    Returns list sorted by candidate_index.
    """
    from sqlalchemy import select

    cand_result = await db.execute(
        select(PatchCandidate).where(
            PatchCandidate.incident_id == incident.id
        ).order_by(PatchCandidate.candidate_index)
    )
    candidates = list(cand_result.scalars().all())

    proofs = []
    for candidate in candidates:
        # Get verification runs for this candidate
        runs_result = await db.execute(
            select(VerificationRun).where(
                VerificationRun.candidate_id == candidate.id
            ).order_by(VerificationRun.created_at)
        )
        runs = list(runs_result.scalars().all())

        proof_entry = {
            "candidate_id": str(candidate.id),
            "candidate_index": candidate.candidate_index,
            "strategy": candidate.strategy.value if candidate.strategy else None,
            "status": candidate.status.value if candidate.status else None,
            "is_eligible": candidate.is_eligible,
            "is_selected": candidate.is_selected,
            "confidence": candidate.confidence,
            "risk_level": candidate.risk_level,
            "risk_score": candidate.risk_score,
            "reproduction_passed": candidate.reproduction_passed,
            "build_passed": candidate.build_passed,
            "tests_passed": candidate.tests_passed,
            "no_new_failures": candidate.no_new_failures,
            "discard_reason": candidate.discard_reason,
            "changed_files_count": candidate.changed_files_count,
            "changed_lines_count": candidate.changed_lines_count,
            "description": candidate.description,
            "verification_stages": [
                {
                    "stage": r.stage,
                    "status": r.status.value if r.status else None,
                    "passed": r.passed,
                    "evidence_label": r.evidence_label.value if r.evidence_label else None,
                    "duration_seconds": r.duration_seconds,
                    "exit_code": r.exit_code,
                    "stdout_excerpt": _safe_excerpt(r.stdout, 300),
                    "stderr_excerpt": _safe_excerpt(r.stderr, 300) if not r.passed else None,
                }
                for r in runs
            ],
        }
        proofs.append(proof_entry)

    return proofs


def generate_pr_repair_report(
    incident: Incident,
    candidate: PatchCandidate,
    analysis: dict,
    verification_runs: list[VerificationRun],
    patchr_incident_url: str,
) -> str:
    """
    Generate the PatchR Repair Report markdown for inclusion in the PR body.
    Per docs/34_PR_REPAIR_REPORT.md.
    """
    lines = ["# PatchR Repair Report", ""]
    lines.append(f"> This PR was generated autonomously by PatchR.")
    lines.append(f"> View full incident details: {patchr_incident_url}")
    lines.append("")

    # Incident section
    lines.append("## Incident")
    lines.append(f"- **Incident ID:** `{incident.id}`")
    lines.append(f"- **Type:** {incident.failure_type.value if incident.failure_type else 'unknown'}")
    lines.append(f"- **Severity:** {incident.severity.value if incident.severity else 'medium'}")
    lines.append(f"- **First seen:** {incident.first_seen_at.strftime('%Y-%m-%d %H:%M UTC') if incident.first_seen_at else 'unknown'}")
    lines.append(f"- **Occurrences:** {incident.occurrence_count}")
    lines.append("")

    # Root Cause Hypothesis
    root_cause = analysis.get("root_cause", "Not available")
    lines.append("## Root Cause Hypothesis")
    lines.append(f"> {root_cause[:500]}")
    lines.append("")

    # Evidence (observed/correlated only)
    lines.append("## Evidence")
    if incident.commit_sha:
        lines.append(f"- `[CORRELATED]` Commit: `{incident.commit_sha[:12]}`")
    for ev in (analysis.get("evidence") or [])[:5]:
        lines.append(f"- `[OBSERVED]` {str(ev)[:200]}")
    lines.append("")

    # Repair Candidate
    lines.append("## Repair Candidate")
    lines.append(f"- **Strategy:** {candidate.strategy.value if candidate.strategy else 'unknown'}")
    lines.append(f"- **Confidence:** {(candidate.confidence or 0):.0%}")
    lines.append(f"- **Files changed:** {candidate.changed_files_count or 0}")
    lines.append(f"- **Lines changed:** {candidate.changed_lines_count or 0}")
    lines.append("")
    if candidate.description:
        lines.append(f"**What this patch does:** {candidate.description[:400]}")
        lines.append("")

    # Validation
    lines.append("## Validation")
    for run in verification_runs:
        icon = "✅" if run.passed else "❌"
        label = run.evidence_label.value if run.evidence_label else "validated"
        lines.append(f"- {icon} **{run.stage}** `[{label.upper()}]`")
        if run.duration_seconds:
            lines.append(f"  - Duration: {run.duration_seconds:.1f}s")
        if not run.passed and run.stderr:
            lines.append(f"  - Error: `{_safe_excerpt(run.stderr, 150)}`")
    lines.append("")
    lines.append("> No regressions detected by configured checks. Does not guarantee future correctness.")
    lines.append("")

    # Risk
    lines.append("## Risk")
    lines.append(f"- **Level:** {candidate.risk_level or 'medium'}")
    lines.append(f"- **Score:** {(candidate.risk_score or 0):.2f}")
    lines.append("")

    # Uncertainty
    lines.append("## Uncertainty")
    lines.append(
        "The root cause is a hypothesis generated from available evidence. "
        "Reproduction is localized synthetic — not exact production state replay. "
        "Validation results prove the configured checks passed, not mathematical correctness."
    )
    lines.append("")

    # Human Approval
    lines.append("## Human Approval Required")
    lines.append(
        "**PatchR does not automatically merge production changes.** "
        "Review the diff, validate the evidence, and merge manually."
    )

    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _safe_excerpt(text: str | None, max_len: int) -> str | None:
    if not text:
        return None
    text = text.strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")
