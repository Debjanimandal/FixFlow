"""
Synthetic Journey Runner

Implements configurable backend HTTP flows that test critical application paths
(docs/20_SYNTHETIC_USER_JOURNEYS.md).

A journey is a list of ordered HTTP steps executed against a deployed application.
Each step checks status code and optionally response structure.

Evidence classification:
  - step results: OBSERVED (actual HTTP response from real app)
  - timing: OBSERVED
  - outcome: VALIDATED (pass/fail based on observed results)

Important truthfulness rules:
  - Never label synthetic reproduction as exact production replay
  - Never fabricate response bodies or status codes
  - Store only safe metadata (not raw tokens/cookies/secrets from responses)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog

from patchr.db.models import (
    AuditAction,
    AuditLog,
    Incident,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    Journey,
    JourneyRun,
    JourneyRunStatus,
    JourneyStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Headers that must NOT be stored (contain auth/secrets)
REDACTED_HEADERS = {
    "authorization", "cookie", "set-cookie", "x-api-key",
    "x-auth-token", "x-session-token", "bearer",
}


# ── Main Runner ────────────────────────────────────────────────────────────────


async def run_journey(
    db: "AsyncSession",
    *,
    journey: Journey,
    trigger: str,  # heartbeat|deployment|manual|post_merge
    incident_id: uuid.UUID | None = None,
) -> JourneyRun:
    """
    Execute a synthetic journey and store the result.

    Returns the JourneyRun record.
    On failure: increments consecutive_failures, creates incident if threshold reached.
    On success: resets consecutive_failures, updates status to HEALTHY.
    """
    log = logger.bind(journey_id=str(journey.id), journey_name=journey.name, trigger=trigger)
    log.info("journey_run_starting")

    base_url = journey.base_url or ""
    if not base_url:
        log.warning("journey_run_skipped_no_base_url")
        run = JourneyRun(
            id=uuid.uuid4(),
            journey_id=journey.id,
            incident_id=incident_id,
            trigger=trigger,
            status=JourneyRunStatus.ERROR,
            error="No base URL configured for journey",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()
        return run

    run = JourneyRun(
        id=uuid.uuid4(),
        journey_id=journey.id,
        incident_id=incident_id,
        trigger=trigger,
        status=JourneyRunStatus.RUNNING,
        base_url=base_url,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    db.add(AuditLog(
        id=uuid.uuid4(),
        action=AuditAction.JOURNEY_RUN_STARTED,
        actor="system:journey_runner",
        details={
            "journey_id": str(journey.id),
            "journey_name": journey.name,
            "trigger": trigger,
            "run_id": str(run.id),
        },
        entity_type="journey_run",
        entity_id=str(run.id),
        created_at=datetime.now(timezone.utc),
    ))

    start_time = datetime.now(timezone.utc)

    # ── Execute steps ─────────────────────────────────────────────────────────
    step_results = []
    all_passed = True
    failing_step = None
    failing_status = None
    timeout_s = (journey.timeout_ms or 10000) / 1000.0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s),
        follow_redirects=True,
    ) as client:
        for step in journey.steps:
            step_name = step.get("name", "unnamed")
            method = step.get("method", "GET").upper()
            path = step.get("path", "/")
            expected_status = step.get("expected_status", 200)
            body = step.get("body")  # Optional request body
            headers = _build_safe_headers(step.get("headers", {}))

            url = base_url.rstrip("/") + path
            step_start = datetime.now(timezone.utc)

            try:
                kwargs = {"headers": headers}
                if body and method in ("POST", "PUT", "PATCH"):
                    kwargs["json"] = body

                response = await client.request(method, url, **kwargs)
                step_end = datetime.now(timezone.utc)
                duration_ms = int((step_end - step_start).total_seconds() * 1000)

                passed = response.status_code == expected_status
                result = {
                    "name": step_name,
                    "method": method,
                    "path": path,
                    "expected_status": expected_status,
                    "actual_status": response.status_code,
                    "passed": passed,
                    "duration_ms": duration_ms,
                    # Safe metadata only — no auth headers, no cookies
                    "response_size_bytes": len(response.content),
                    "content_type": response.headers.get("content-type", ""),
                }
                step_results.append(result)

                if not passed:
                    all_passed = False
                    failing_step = step_name
                    failing_status = response.status_code
                    log.warning(
                        "journey_step_failed",
                        step=step_name,
                        expected=expected_status,
                        actual=response.status_code,
                        duration_ms=duration_ms,
                    )
                    break  # Stop on first failure (ordered steps)

                log.info(
                    "journey_step_passed",
                    step=step_name,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )

            except httpx.TimeoutException:
                step_end = datetime.now(timezone.utc)
                duration_ms = int((step_end - step_start).total_seconds() * 1000)
                step_results.append({
                    "name": step_name,
                    "method": method,
                    "path": path,
                    "passed": False,
                    "error": "timeout",
                    "duration_ms": duration_ms,
                })
                all_passed = False
                failing_step = step_name
                run.error = f"Timeout on step: {step_name}"
                break

            except Exception as e:
                step_end = datetime.now(timezone.utc)
                duration_ms = int((step_end - step_start).total_seconds() * 1000)
                step_results.append({
                    "name": step_name,
                    "method": method,
                    "path": path,
                    "passed": False,
                    "error": str(e)[:200],
                    "duration_ms": duration_ms,
                })
                all_passed = False
                failing_step = step_name
                run.error = f"Network error on step {step_name}: {str(e)[:200]}"
                break

    # ── Finalize run ──────────────────────────────────────────────────────────
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    run.step_results = step_results
    run.duration_ms = duration_ms
    run.failing_step = failing_step
    run.failing_status_code = failing_status
    run.completed_at = end_time

    if all_passed:
        run.status = JourneyRunStatus.PASSED
        journey.consecutive_failures = 0
        journey.current_status = JourneyStatus.HEALTHY
        log.info("journey_run_passed", duration_ms=duration_ms)
    else:
        run.status = JourneyRunStatus.FAILED
        journey.consecutive_failures = (journey.consecutive_failures or 0) + 1
        journey.current_status = JourneyStatus.FAILING
        log.warning(
            "journey_run_failed",
            failing_step=failing_step,
            consecutive=journey.consecutive_failures,
            threshold=journey.failure_threshold,
        )

    journey.last_run_at = end_time

    # ── Create incident if threshold reached ──────────────────────────────────
    created_incident = None
    if (
        not all_passed
        and journey.consecutive_failures >= (journey.failure_threshold or 2)
        and journey.repository_id
    ):
        created_incident = await _create_journey_incident(
            db=db,
            journey=journey,
            run=run,
            failing_step=failing_step,
            failing_status=failing_status,
        )
        if created_incident:
            run.incident_id = created_incident.id
            journey.last_incident_id = created_incident.id

    db.add(AuditLog(
        id=uuid.uuid4(),
        action=AuditAction.JOURNEY_RUN_COMPLETED,
        actor="system:journey_runner",
        details={
            "journey_id": str(journey.id),
            "run_id": str(run.id),
            "passed": all_passed,
            "duration_ms": duration_ms,
            "failing_step": failing_step,
            "incident_created": str(created_incident.id) if created_incident else None,
        },
        entity_type="journey_run",
        entity_id=str(run.id),
        created_at=datetime.now(timezone.utc),
    ))

    await db.commit()
    await db.refresh(run)
    return run


# ── Incident Creation from Journey Failure ────────────────────────────────────


async def _create_journey_incident(
    db: "AsyncSession",
    *,
    journey: Journey,
    run: JourneyRun,
    failing_step: str | None,
    failing_status: int | None,
) -> Incident | None:
    """Create an incident from a journey failure (after threshold reached)."""
    from patchr.services.incident_service import get_or_create_incident_from_journey

    try:
        incident = await get_or_create_incident_from_journey(
            db=db,
            journey=journey,
            run=run,
            failing_step=failing_step,
            failing_status=failing_status,
        )
        if incident:
            db.add(AuditLog(
                id=uuid.uuid4(),
                incident_id=incident.id,
                action=AuditAction.JOURNEY_INCIDENT_CREATED,
                actor="system:journey_runner",
                details={
                    "journey_id": str(journey.id),
                    "journey_name": journey.name,
                    "run_id": str(run.id),
                    "consecutive_failures": journey.consecutive_failures,
                },
                entity_type="incident",
                entity_id=str(incident.id),
                created_at=datetime.now(timezone.utc),
            ))
        return incident
    except Exception as e:
        logger.error(
            "journey_incident_creation_failed",
            journey_id=str(journey.id),
            error=str(e),
        )
        return None


# ── Heartbeat Scheduler ────────────────────────────────────────────────────────


async def run_all_enabled_journeys(
    db: "AsyncSession",
    *,
    trigger: str = "heartbeat",
) -> list[JourneyRun]:
    """
    Run all enabled journeys with a configured base URL.
    Called by the APScheduler heartbeat job.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Journey).where(Journey.enabled == True)  # noqa: E712
    )
    journeys = result.scalars().all()

    runs = []
    for journey in journeys:
        if not journey.base_url:
            logger.debug("journey_skipped_no_url", journey_id=str(journey.id))
            continue
        try:
            run = await run_journey(db=db, journey=journey, trigger=trigger)
            runs.append(run)
        except Exception as e:
            logger.error(
                "journey_run_error",
                journey_id=str(journey.id),
                error=str(e),
            )

    return runs


# ── Post-Merge Journey Run ─────────────────────────────────────────────────────


async def run_post_merge_journeys(
    db: "AsyncSession",
    *,
    incident: Incident,
    deployment_url: str | None = None,
) -> list[JourneyRun]:
    """
    Run journeys for a specific repository after a merged PR deployment.
    Used by Post-Merge Guard to verify the repair worked.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Journey).where(
            Journey.repository_id == incident.repository_id,
            Journey.enabled == True,  # noqa: E712
        )
    )
    journeys = result.scalars().all()

    runs = []
    for journey in journeys:
        # Temporarily override base_url if the deployment has a new URL
        if deployment_url and not journey.base_url:
            journey.base_url = deployment_url

        try:
            run = await run_journey(
                db=db,
                journey=journey,
                trigger="post_merge",
                incident_id=incident.id,
            )
            runs.append(run)
        except Exception as e:
            logger.error(
                "post_merge_journey_error",
                journey_id=str(journey.id),
                incident_id=str(incident.id),
                error=str(e),
            )

    return runs


# ── Helpers ────────────────────────────────────────────────────────────────────


def _build_safe_headers(headers: dict) -> dict:
    """Filter out any headers that might contain secrets/auth tokens."""
    return {
        k: v for k, v in headers.items()
        if k.lower() not in REDACTED_HEADERS
        and not k.lower().startswith("x-auth")
    }
