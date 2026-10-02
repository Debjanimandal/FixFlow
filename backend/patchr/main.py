"""
FixFlow API — FastAPI Application

Entry point. Configures middleware, CORS, routers, and startup/shutdown.
"""

import structlog
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from patchr.config import get_settings
from patchr.routers import analysis, auth, incidents, patches, repositories, webhooks
from patchr.routers import journeys as journeys_router

settings = get_settings()

# Configure structured logging early
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.is_development else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}.get(settings.log_level.upper(), 20)
    ),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: auto-create tables, start APScheduler. Shutdown: stop scheduler."""
    logger.info("patchr_api_started", environment=settings.environment, version="0.1.0")

    # ── DB table init ───────────────────────────────────────────────────────
    try:
        from patchr.db.session import init_db, engine
        await init_db()
        # Add Vercel columns if missing — PostgreSQL only (SQLite creates them via create_all)
        db_url = settings.database_url
        if "postgresql" in db_url or "postgres" in db_url:
            async with engine.begin() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vercel_access_token VARCHAR(1024)"
                    )
                )
                await conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vercel_team_id VARCHAR(512)"
                    )
                )
        logger.info("database_tables_verified")
    except Exception as e:
        logger.warning("database_table_init_failed", error=str(e))

    # ── APScheduler: PR lifecycle monitor + journey heartbeat ─────────────────
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from patchr.services.pr_monitor_service import check_open_prs
        from patchr.services.journey_service import run_all_enabled_journeys

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            check_open_prs,
            trigger="interval",
            minutes=5,
            id="pr_lifecycle_monitor",
            replace_existing=True,
        )
        # Journey heartbeat: run enabled journeys every 5 minutes
        scheduler.add_job(
            _run_journey_heartbeat,
            trigger="interval",
            minutes=5,
            id="journey_heartbeat",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("scheduler_started", pr_interval_minutes=5, journey_interval_minutes=5)
    except ImportError:
        logger.warning("apscheduler_not_installed", hint="pip install apscheduler")
    except Exception as e:
        logger.warning("pr_monitor_scheduler_failed", error=str(e))

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("pr_monitor_scheduler_stopped")
    logger.info("patchr_api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="FixFlow API",
        description="Autonomous Self-Healing Codebase Platform",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    # Allow the Next.js frontend in development
    allowed_origins = [settings.frontend_url]
    if settings.is_development:
        allowed_origins += [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(repositories.router, prefix="/api/v1")
    app.include_router(incidents.router, prefix="/api/v1")
    app.include_router(analysis.router, prefix="/api/v1")
    app.include_router(patches.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(journeys_router.router, prefix="/api/v1")

    # ── Health ────────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health():
        """Check connectivity to all external services."""
        import httpx
        services: dict = {}
        overall = "healthy"

        # Database
        try:
            from patchr.db.session import AsyncSessionLocal
            from sqlalchemy import text
            t0 = time.monotonic()
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            services["database"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000)}
        except Exception as e:
            services["database"] = {"status": "error", "detail": str(e)[:100]}
            overall = "degraded"

        # GitHub
        if settings.github_token and not settings.github_token.startswith("ghp_your"):
            try:
                t0 = time.monotonic()
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"Bearer {settings.github_token}",
                                 "Accept": "application/vnd.github+json"}
                    )
                if r.status_code == 200:
                    services["github"] = {"status": "ok", "user": r.json().get("login"), "latency_ms": round((time.monotonic() - t0) * 1000)}
                else:
                    services["github"] = {"status": "error", "http": r.status_code}
                    overall = "degraded"
            except Exception as e:
                services["github"] = {"status": "error", "detail": str(e)[:100]}
                overall = "degraded"
        else:
            services["github"] = {"status": "not_configured"}

        # NVIDIA NIM
        if settings.nvidia_api_key and not settings.nvidia_api_key.startswith("nvapi-xxx"):
            try:
                t0 = time.monotonic()
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(
                        f"{settings.nvidia_base_url}/models",
                        headers={"Authorization": f"Bearer {settings.nvidia_api_key}"}
                    )
                if r.status_code == 200:
                    model_count = len(r.json().get("data", []))
                    services["nvidia_nim"] = {"status": "ok", "models": model_count, "latency_ms": round((time.monotonic() - t0) * 1000)}
                else:
                    services["nvidia_nim"] = {"status": "error", "http": r.status_code}
                    overall = "degraded"
            except Exception as e:
                services["nvidia_nim"] = {"status": "error", "detail": str(e)[:100]}
                overall = "degraded"
        else:
            services["nvidia_nim"] = {"status": "not_configured"}

        # Vercel
        if settings.vercel_access_token and not settings.vercel_access_token.startswith("your_vercel"):
            try:
                t0 = time.monotonic()
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(
                        "https://api.vercel.com/v9/projects",
                        headers={"Authorization": f"Bearer {settings.vercel_access_token}"}
                    )
                if r.status_code == 200:
                    projects = [p["name"] for p in r.json().get("projects", [])]
                    services["vercel"] = {"status": "ok", "projects": projects, "latency_ms": round((time.monotonic() - t0) * 1000)}
                else:
                    services["vercel"] = {"status": "error", "http": r.status_code}
            except Exception as e:
                services["vercel"] = {"status": "error", "detail": str(e)[:100]}
        else:
            services["vercel"] = {"status": "not_configured"}

        return {
            "status": overall,
            "version": "0.1.0",
            "environment": settings.environment,
            "services": services,
        }

    @app.get("/", tags=["meta"])
    async def root():
        return {"product": "PatchR", "version": "0.2.0", "docs": "/docs"}

    @app.get("/ready", tags=["meta"])
    async def ready():
        """Readiness check."""
        try:
            from patchr.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return {"ready": True}
        except Exception as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={"ready": False, "error": str(e)[:100]},
            )

    return app


async def _run_journey_heartbeat() -> None:
    """APScheduler job: run all enabled journeys on heartbeat interval."""
    try:
        from patchr.db.session import AsyncSessionLocal
        from patchr.services.journey_service import run_all_enabled_journeys
        logger.debug("journey_heartbeat_started")
        async with AsyncSessionLocal() as db:
            runs = await run_all_enabled_journeys(db, trigger="heartbeat")
            logger.info("journey_heartbeat_complete", runs=len(runs))
    except Exception as e:
        logger.error("journey_heartbeat_failed", error=str(e))


app = create_app()
