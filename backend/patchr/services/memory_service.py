"""
Incident Memory Service

Stores normalized fingerprints of resolved incidents for retrieval during
future similar incident analysis (docs/22_INCIDENT_MEMORY.md).

Important rules:
  - Memory is supplementary context ONLY — never treated as proof
  - Current validation always remains mandatory
  - Do not store raw diffs, secrets, or raw model outputs
  - Never expose memory injection as "proof" to the reviewer
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from patchr.db.models import (
    CandidateStatus,
    Incident,
    IncidentMemory,
    IncidentStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def store_incident_memory(
    db: "AsyncSession",
    *,
    incident: Incident,
) -> IncidentMemory | None:
    """
    Create a normalized IncidentMemory record after an incident resolves.
    Called by post_merge_guard after successful resolution.
    """
    from sqlalchemy import select
    from patchr.db.models import PatchCandidate, Analysis

    # Only store memory for resolved incidents
    if incident.status not in (IncidentStatus.RESOLVED,):
        return None

    # Get the selected candidate
    cand_result = await db.execute(
        select(PatchCandidate).where(
            PatchCandidate.incident_id == incident.id,
            PatchCandidate.is_selected == True,  # noqa: E712
        )
    )
    selected_candidate = cand_result.scalar_one_or_none()

    # Get the analysis
    analysis_result = await db.execute(
        select(Analysis).where(
            Analysis.incident_id == incident.id
        ).order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    if not analysis:
        logger.warning("memory_no_analysis", incident_id=str(incident.id))
        return None

    # Build normalized fingerprint
    fingerprint = _normalize_fingerprint(
        error_pattern=incident.title,
        failure_type=analysis.failure_type or "unknown",
        affected_files=analysis.affected_files or [],
    )

    # Count candidates
    all_cands_result = await db.execute(
        select(PatchCandidate).where(PatchCandidate.incident_id == incident.id)
    )
    all_candidates = all_cands_result.scalars().all()
    eligible_count = sum(1 for c in all_candidates if c.is_eligible)

    # Build safe diff summary (not the raw diff — just the key change description)
    diff_summary = None
    if selected_candidate and selected_candidate.description:
        diff_summary = selected_candidate.description[:500]

    memory = IncidentMemory(
        id=uuid.uuid4(),
        incident_id=incident.id,
        repository_id=incident.repository_id,
        fingerprint=fingerprint,
        failure_type=analysis.failure_type,
        error_class=_extract_error_class(incident.title),
        error_pattern=_normalize_error_message(incident.title),
        affected_route=_extract_route(analysis.affected_files or []),
        root_cause_summary=_safe_truncate(analysis.root_cause, 500),
        successful_strategy=(
            selected_candidate.strategy.value if selected_candidate else None
        ),
        successful_diff_summary=diff_summary,
        final_outcome="resolved",
        time_to_resolve_seconds=incident.time_to_resolve_seconds,
        candidate_count=len(all_candidates),
        passed_candidate_count=eligible_count,
        created_at=datetime.now(timezone.utc),
    )
    db.add(memory)
    await db.commit()

    logger.info(
        "incident_memory_stored",
        incident_id=str(incident.id),
        fingerprint=fingerprint[:40],
    )
    return memory


async def retrieve_similar_memories(
    db: "AsyncSession",
    *,
    fingerprint: str,
    failure_type: str | None = None,
    limit: int = 3,
) -> list[IncidentMemory]:
    """
    Retrieve historical memories similar to the current incident.
    Used during analysis to provide historical context (not proof).
    """
    from sqlalchemy import select, or_

    conditions = [IncidentMemory.fingerprint == fingerprint]
    if failure_type:
        conditions.append(IncidentMemory.failure_type == failure_type)

    result = await db.execute(
        select(IncidentMemory)
        .where(or_(*conditions))
        .order_by(IncidentMemory.created_at.desc())
        .limit(limit)
    )
    memories = result.scalars().all()
    logger.debug(
        "memories_retrieved",
        fingerprint=fingerprint[:40],
        count=len(memories),
    )
    return list(memories)


def format_memory_context(memories: list[IncidentMemory]) -> str:
    """
    Format historical memories as context for AI prompts.
    Clearly labeled as historical evidence, not proof.
    """
    if not memories:
        return ""

    parts = ["=== HISTORICAL CONTEXT (Not Proof) ==="]
    parts.append(
        "The following are similar past incidents that were resolved. "
        "These are examples only. Current validation remains mandatory."
    )
    for i, m in enumerate(memories, 1):
        parts.append(f"\n--- Historical Incident {i} ---")
        if m.failure_type:
            parts.append(f"Type: {m.failure_type}")
        if m.root_cause_summary:
            parts.append(f"Root Cause: {m.root_cause_summary}")
        if m.successful_strategy:
            parts.append(f"Successful Strategy: {m.successful_strategy}")
        if m.successful_diff_summary:
            parts.append(f"What worked: {m.successful_diff_summary}")
        if m.time_to_resolve_seconds:
            parts.append(f"Resolved in: {m.time_to_resolve_seconds // 60} minutes")
    parts.append("\n=== END HISTORICAL CONTEXT ===")
    return "\n".join(parts)


# ── Fingerprinting ─────────────────────────────────────────────────────────────


def compute_incident_fingerprint(
    error_message: str | None,
    failure_type: str,
    affected_files: list[str],
) -> str:
    """
    Compute a normalized fingerprint for deduplication.
    Normalizes error messages to remove instance-specific data.
    """
    normalized_msg = _normalize_error_message(error_message or "")
    normalized_files = ",".join(sorted(affected_files[:5]))
    raw = f"{failure_type}:{normalized_msg[:200]}:{normalized_files}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _normalize_fingerprint(
    error_pattern: str,
    failure_type: str,
    affected_files: list[str],
) -> str:
    return compute_incident_fingerprint(error_pattern, failure_type, affected_files)


def _normalize_error_message(msg: str) -> str:
    """Remove instance-specific data from error messages."""
    if not msg:
        return ""
    # Remove UUIDs
    msg = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', msg)
    # Remove hex strings (commit shas, etc.)
    msg = re.sub(r'\b[0-9a-f]{8,}\b', '<hex>', msg)
    # Remove file line numbers
    msg = re.sub(r':\d+:\d+', ':<line>:<col>', msg)
    msg = re.sub(r'line \d+', 'line <N>', msg)
    # Remove timestamps
    msg = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<timestamp>', msg)
    # Remove file paths with version numbers
    msg = re.sub(r'/node_modules/[^/\s]+/[^\s]+', '<dep>', msg)
    return msg.strip()[:300]


def _extract_error_class(title: str) -> str | None:
    """Extract error class name from error title."""
    # Common patterns: TypeError: ..., SyntaxError: ..., etc.
    match = re.match(r'^(\w+Error|\w+Exception):', title)
    if match:
        return match.group(1)
    return None


def _extract_route(affected_files: list[str]) -> str | None:
    """Extract API route hint from affected files."""
    for f in affected_files:
        # Next.js API routes
        if "/api/" in f or "/pages/api/" in f:
            return f
        # Express-style routes
        if "route" in f.lower() or "controller" in f.lower():
            return f
    return affected_files[0] if affected_files else None


def _safe_truncate(text: str | None, max_len: int) -> str | None:
    if not text:
        return None
    return text[:max_len] + ("..." if len(text) > max_len else "")
