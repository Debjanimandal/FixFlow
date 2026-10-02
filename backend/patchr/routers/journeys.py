"""
Journeys Router

CRUD and execution endpoints for Synthetic User Journeys.
Implements docs/20_SYNTHETIC_USER_JOURNEYS.md API surface.

All routes require owner authentication.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from patchr.auth import get_current_owner
from patchr.db.models import (
    AuditAction,
    AuditLog,
    Journey,
    JourneyRun,
    JourneyRunStatus,
    JourneyStatus,
    Repository,
)
from patchr.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/journeys", tags=["journeys"])


# ── Journey CRUD ───────────────────────────────────────────────────────────────


@router.get("")
async def list_journeys(
    repository_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[dict]:
    """List all journeys with their current status."""
    query = select(Journey)
    if repository_id:
        query = query.where(Journey.repository_id == repository_id)
    query = query.order_by(Journey.created_at.desc())

    result = await db.execute(query)
    journeys = result.scalars().all()

    return [_journey_to_dict(j) for j in journeys]


@router.post("")
async def create_journey(
    body: dict,
    db: AsyncSession = Depends(get_db),
    owner: str = Depends(get_current_owner),
) -> dict:
    """
    Create a new synthetic journey.

    Body fields:
      - name (required)
      - steps (required): list of {name, method, path, expected_status}
      - repository_id (optional)
      - base_url (optional — will use repository deployment_url if not set)
      - enabled (default: true)
      - severity (default: high)
      - timeout_ms (default: 10000)
      - failure_threshold (default: 2)
      - heartbeat_cron (optional)
    """
    name = body.get("name")
    steps = body.get("steps")
    if not name or not steps:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name and steps are required",
        )

    # Validate steps
    for i, step in enumerate(steps):
        if "path" not in step:
            raise HTTPException(
                status_code=422,
                detail=f"Step {i} missing required field: path",
            )

    # Validate repository if provided
    repo_id = None
    if body.get("repository_id"):
        try:
            repo_id = uuid.UUID(str(body["repository_id"]))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid repository_id")

        repo_result = await db.execute(select(Repository).where(Repository.id == repo_id))
        if not repo_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Repository not found")

    journey = Journey(
        id=uuid.uuid4(),
        repository_id=repo_id,
        name=name,
        description=body.get("description"),
        enabled=body.get("enabled", True),
        severity=body.get("severity", "high"),
        steps=steps,
        base_url=body.get("base_url"),
        timeout_ms=body.get("timeout_ms", 10000),
        failure_threshold=body.get("failure_threshold", 2),
        heartbeat_cron=body.get("heartbeat_cron"),
        current_status=JourneyStatus.UNKNOWN,
        consecutive_failures=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(journey)

    db.add(AuditLog(
        id=uuid.uuid4(),
        action=AuditAction.JOURNEY_CREATED,
        actor="system:owner",
        details={"name": name, "steps": len(steps)},
        entity_type="journey",
        entity_id=str(journey.id),
        created_at=datetime.now(timezone.utc),
    ))

    await db.commit()
    await db.refresh(journey)
    logger.info("journey_created", journey_id=str(journey.id), name=name)
    return _journey_to_dict(journey)


@router.get("/{journey_id}")
async def get_journey(
    journey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """Get a single journey with its current status."""
    result = await db.execute(select(Journey).where(Journey.id == journey_id))
    journey = result.scalar_one_or_none()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    return _journey_to_dict(journey)


@router.put("/{journey_id}")
async def update_journey(
    journey_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """Update a journey's configuration."""
    result = await db.execute(select(Journey).where(Journey.id == journey_id))
    journey = result.scalar_one_or_none()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    updatable = ["name", "description", "enabled", "severity", "steps",
                 "base_url", "timeout_ms", "failure_threshold", "heartbeat_cron"]
    for field in updatable:
        if field in body:
            setattr(journey, field, body[field])

    journey.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(journey)
    return _journey_to_dict(journey)


@router.delete("/{journey_id}")
async def delete_journey(
    journey_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """Delete a journey."""
    result = await db.execute(select(Journey).where(Journey.id == journey_id))
    journey = result.scalar_one_or_none()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    await db.delete(journey)
    await db.commit()
    return {"deleted": True, "journey_id": str(journey_id)}


# ── Journey Execution ──────────────────────────────────────────────────────────


@router.post("/{journey_id}/run")
async def run_journey_now(
    journey_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """
    Manually trigger a journey run (Run Now button).
    Runs asynchronously; poll /runs for results.
    """
    result = await db.execute(select(Journey).where(Journey.id == journey_id))
    journey = result.scalar_one_or_none()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    if not journey.enabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Journey is disabled",
        )

    if not journey.base_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Journey has no base_url configured",
        )

    background_tasks.add_task(
        _run_journey_background,
        journey_id=str(journey_id),
        trigger="manual",
    )

    return {
        "journey_id": str(journey_id),
        "status": "run_started",
        "message": "Journey run started. Check /runs for results.",
    }


@router.get("/{journey_id}/runs")
async def list_journey_runs(
    journey_id: uuid.UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> list[dict]:
    """List all runs for a journey, most recent first."""
    # Verify journey exists
    result = await db.execute(select(Journey).where(Journey.id == journey_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Journey not found")

    runs_result = await db.execute(
        select(JourneyRun)
        .where(JourneyRun.journey_id == journey_id)
        .order_by(JourneyRun.started_at.desc())
        .limit(limit)
    )
    runs = runs_result.scalars().all()

    return [_run_to_dict(r) for r in runs]


@router.get("/{journey_id}/runs/{run_id}")
async def get_journey_run(
    journey_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _owner: str = Depends(get_current_owner),
) -> dict:
    """Get a single journey run with step details."""
    result = await db.execute(
        select(JourneyRun).where(
            JourneyRun.id == run_id,
            JourneyRun.journey_id == journey_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Journey run not found")

    return _run_to_dict(run, include_steps=True)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _journey_to_dict(j: Journey) -> dict:
    return {
        "id": str(j.id),
        "repository_id": str(j.repository_id) if j.repository_id else None,
        "name": j.name,
        "description": j.description,
        "enabled": j.enabled,
        "severity": j.severity,
        "steps": j.steps,
        "base_url": j.base_url,
        "timeout_ms": j.timeout_ms,
        "failure_threshold": j.failure_threshold,
        "heartbeat_cron": j.heartbeat_cron,
        "current_status": j.current_status.value if j.current_status else "unknown",
        "consecutive_failures": j.consecutive_failures,
        "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
        "last_incident_id": str(j.last_incident_id) if j.last_incident_id else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


def _run_to_dict(r: JourneyRun, include_steps: bool = False) -> dict:
    d = {
        "id": str(r.id),
        "journey_id": str(r.journey_id),
        "incident_id": str(r.incident_id) if r.incident_id else None,
        "trigger": r.trigger,
        "status": r.status.value if r.status else "unknown",
        "failing_step": r.failing_step,
        "failing_status_code": r.failing_status_code,
        "duration_ms": r.duration_ms,
        "base_url": r.base_url,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }
    if include_steps:
        d["step_results"] = r.step_results or []
    return d


async def _run_journey_background(journey_id: str, trigger: str) -> None:
    """Background task: execute a journey."""
    from patchr.db.session import AsyncSessionLocal
    from patchr.services.journey_service import run_journey

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Journey).where(Journey.id == journey_id))
        journey = result.scalar_one_or_none()
        if not journey:
            return
        try:
            await run_journey(db=db, journey=journey, trigger=trigger)
        except Exception as e:
            logger.error(
                "journey_background_failed",
                journey_id=journey_id,
                error=str(e),
            )
