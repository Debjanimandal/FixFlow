"""
Analysis Router

Manual triggers for AI analysis — useful during development and testing
when you don't want to wait for a real webhook event.

POST /incidents/{id}/analyze — trigger analysis on any incident
POST /incidents/{id}/simulate — simulate a deployment failure (dev only)
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.auth import get_current_owner
from patchr.config import Settings, get_settings
from patchr.db.models import Incident, Repository
from patchr.db.session import get_db
from patchr.services import incident_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["analysis"])


class AnalyzeTriggerRequest(BaseModel):
    build_logs: str | None = None
    commit_diff: str | None = None
    file_contents: dict[str, str] | None = None


class SimulateFailureRequest(BaseModel):
    """For dev testing — simulate a deployment failure without a real webhook."""
    repository_full_name: str
    commit_sha: str = "dev0000"
    commit_message: str = "test: simulated failure"
    error_description: str = "Module not found: Cannot find module './missing-import'"
    build_logs: str = ""
    environment: str = "production"


@router.post("/{incident_id}/analyze")
async def trigger_analysis(
    incident_id: str,
    body: AnalyzeTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
):
    """
    Manually trigger AI analysis for an incident.

    Useful for:
    - Re-running analysis with different context
    - Testing the AI pipeline without a real webhook
    - Running analysis on manually created incidents

    Runs in background — returns immediately.
    """
    try:
        parsed_id = uuid.UUID(incident_id) if isinstance(incident_id, str) else incident_id
    except (ValueError, TypeError):
        parsed_id = incident_id

    result = await db.execute(
        select(Incident).where((Incident.id == parsed_id) | (Incident.id == incident_id))
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    if incident.status in ("resolved", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot analyze an incident with status '{incident.status}'",
        )

    logger.info("manual_analysis_triggered", incident_id=str(incident.id), by="owner")

    # Run in background — don't block the HTTP response
    background_tasks.add_task(
        _run_analysis_background,
        incident_id=str(incident.id),
        build_logs=body.build_logs,
        commit_diff=body.commit_diff,
        file_contents=body.file_contents,
        settings=settings,
    )

    return {
        "status": "queued",
        "message": "Analysis started in background. Check incident status for updates.",
        "incident_id": str(incident.id),
    }


async def _run_analysis_background(
    incident_id: str,
    build_logs: str | None,
    commit_diff: str | None,
    file_contents: dict[str, str] | None,
    settings: Settings,
) -> None:
    """Background task: load incident from a fresh DB session and run analysis."""
    from patchr.db.session import AsyncSessionLocal

    try:
        parsed_id = uuid.UUID(incident_id) if isinstance(incident_id, str) else incident_id
    except (ValueError, TypeError):
        parsed_id = incident_id

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Incident).where((Incident.id == parsed_id) | (Incident.id == incident_id))
        )
        incident = result.scalar_one_or_none()
        if not incident:
            logger.error("analysis_background_incident_not_found", incident_id=incident_id)
            return

        # If no build logs provided, try to get them from the stored deployment
        if not build_logs and incident.deployment_id:
            from patchr.db.models import Deployment
            dep_result = await db.execute(
                select(Deployment).where(Deployment.id == incident.deployment_id)
            )
            dep = dep_result.scalar_one_or_none()
            if dep:
                build_logs = dep.build_logs

        await incident_service.trigger_analysis(
            db,
            incident=incident,
            build_logs=build_logs,
            commit_diff=commit_diff,
            file_contents=file_contents,
        )


@router.post("/simulate-failure")
async def simulate_failure(
    body: SimulateFailureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _owner: str = Depends(get_current_owner),
):
    """
    [DEV ONLY] Simulate a deployment failure to test the full pipeline.

    Creates an incident from the provided parameters and triggers AI analysis.
    Use this to test without setting up real GitHub webhooks.
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation endpoint is only available in development mode",
        )

    logger.info(
        "failure_simulation_started",
        repo=body.repository_full_name,
        sha=body.commit_sha,
    )

    incident = await incident_service.create_incident_from_github_deployment(
        db,
        repository_full_name=body.repository_full_name,
        commit_sha=body.commit_sha,
        commit_message=body.commit_message,
        deployment_vercel_id=None,
        error_description=body.error_description,
        build_logs=body.build_logs or None,
        environment=body.environment,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{body.repository_full_name}' is not connected. Add it first via POST /api/v1/repositories.",
        )

    # Trigger analysis in background
    background_tasks.add_task(
        _run_analysis_background,
        incident_id=str(incident.id),
        build_logs=body.build_logs or None,
        commit_diff=None,
        file_contents=None,
        settings=settings,
    )

    return {
        "status": "created",
        "incident_id": str(incident.id),
        "message": "Incident created and analysis started. Check the dashboard.",
    }
