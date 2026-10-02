# PatchR - Implementation Roadmap

> This document tracks what has been built, what is actively being worked on,
> and what comes next. It is the single source of truth for engineering progress.
> Last updated: 2026-08-21

---

## Vision

PatchR is an **autonomous software reliability platform**. When a deployment fails,
PatchR detects it, fetches the broken code, uses AI to understand the root cause,
generates a verified patch, and opens a draft PR for the owner to approve -- all
within minutes, with zero manual debugging.

---

## Current Architecture

```
GitHub / Vercel Webhook
        |
        v
  FastAPI Backend (port 8000)
        |
        |-- routers/webhooks.py       -- ingress, HMAC verification
        |-- services/incident_service.py  -- state machine orchestrator
        |-- services/context_service.py  -- fetches real code from GitHub
        |-- services/patch_service.py    -- AI patch generation (NVIDIA NIM)
        |-- services/verification_service.py -- static risk analysis
        |-- integrations/github.py       -- GitHub REST API client
        |-- integrations/vercel.py       -- Vercel REST API client
        |
        v
  Supabase PostgreSQL (7 tables)
  repositories | deployments | incidents | analyses | patches
  verification_results | audit_logs

  Next.js Frontend (port 3000)
  / (landing) | /dashboard | /incidents | /repositories | /settings
```

---

## Pipeline State Machine (16 States)

```
DETECTED
    --> ANALYZING
        --> ROOT_CAUSE_IDENTIFIED
            --> REPAIR_PROPOSED
                --> VERIFYING
                    --> VERIFIED
                        --> AWAITING_REVIEW  <-- owner sees it here
                            --> PR_CREATED
                                --> RECOVERY_MONITORING
                                    --> RESOLVED

Side states (can occur at any point):
  ANALYSIS_FAILED | VERIFICATION_FAILED | REJECTED | NEEDS_REVIEW
  DISMISSED | REOPENED
```

---

## What Is Fully Working Today

| Component | Status | Notes |
|---|---|---|
| GitHub webhook ingress | DONE | HMAC-SHA256 verified |
| Vercel webhook ingress | DONE | needs secret configured |
| Incident creation pipeline | DONE | auto-deduplication |
| Context engine | DONE | fetches real broken code before AI |
| AI analysis (NVIDIA NIM) | DONE | Llama-3.1-70B |
| Patch generation | DONE | multi-file, real code context |
| Static verification | DONE | risk scoring |
| Human approval gate | DONE | POST /patches/{id}/approve |
| GitHub PR creation | DONE | branch + commits + draft PR |
| Audit log | DONE | every action immutably recorded |
| simulate-failure endpoint | DONE | 3 realistic error scenarios |
| dismiss / resolve endpoints | DONE | with audit + timestamps |
| reanalyze endpoint | DONE | re-triggers from failed states |
| pr_monitor_service.py | DONE (not wired) | file created, not scheduled yet |
| Dashboard (Next.js) | DONE | live polling, all 16 states |
| Landing page | DONE | marketing page at / |
| Real API keys | DONE | NVIDIA + GitHub + Vercel all verified |

---

## Phase A -- Wire PR Lifecycle (Next Up)

**Goal**: Close the biggest dead end. Right now incidents are permanently stuck
at PR_CREATED because nothing monitors whether the PR was merged.

**Files to change**:

1. `backend/patchr/db/models.py`
   - Add `pr_state: Mapped[str | None]` to Patch model
   - Add `pr_merged_at: Mapped[datetime | None]` to Patch model

2. `backend/patchr/db/migrations/versions/` -- new Alembic migration
   - ALTER TABLE patches ADD COLUMN pr_state VARCHAR(50)
   - ALTER TABLE patches ADD COLUMN pr_merged_at TIMESTAMPTZ

3. `backend/patchr/main.py`
   - Import APScheduler (already in pyproject.toml)
   - In lifespan() startup: schedule pr_monitor_service.check_open_prs every 5 min

4. `backend/patchr/routers/webhooks.py` -- _process_deployment_status()
   - After successful deploy: check if repo has incident in RECOVERY_MONITORING
   - If yes: call pr_monitor_service.resolve_recovered_incident(incident_id)

**Result**: Full pipeline closes -- PR merged -> RECOVERY_MONITORING -> next
successful deploy -> RESOLVED. Incidents no longer get stuck.

---

## Phase B -- Build Logs from Vercel API

**Goal**: Give the AI real build output instead of just the generic error message.
This directly improves patch quality.

**Files to change**:

1. `backend/patchr/routers/webhooks.py` -- _process_deployment_status()
   - If settings.vercel_access_token is set:
     - Instantiate VercelClient (already in integrations/vercel.py)
     - Call get_build_logs_as_text(deployment_vercel_id)
     - Pass result as build_logs= to incident_service

**VercelClient already has this method** -- it is literally one if-block to add.

**Result**: AI sees the actual stack trace / compilation error, not just
"Deployment failed". Much better root cause identification.

---

## Phase C -- Webhook Auto-Registration

**Goal**: Remove the manual step of going to GitHub Settings -> Webhooks.
User connects a repo on the dashboard -> webhook is registered automatically.

**Files to change**:

1. `backend/patchr/integrations/github.py`
   - Add create_webhook(full_name, url, secret, events) method

2. `backend/patchr/routers/repositories.py`
   - Add POST /repositories/{id}/register-webhook endpoint
   - Calls GitHubClient.create_webhook()
   - Stores returned webhook ID in repositories.github_webhook_id

3. `backend/patchr/db/models.py`
   - Add github_webhook_id: Mapped[str | None] to Repository

4. New Alembic migration for github_webhook_id column

**Result**: One-click repo onboarding. No manual webhook setup.

---

## Phase D -- Vercel Project Linking

**Goal**: Connect a Vercel project to a repository so Vercel webhooks deliver
build errors directly (more reliable than GitHub deployment_status events).

**Files to change**:

1. `backend/patchr/routers/repositories.py`
   - Add POST /repositories/{id}/link-vercel endpoint
   - Accepts vercel_project_id + vercel_project_name
   - Calls VercelClient.register_webhook() with deployment.error + deployment.ready

2. Frontend: add "Link Vercel Project" button on Repositories page

**Prerequisite**: VERCEL_WEBHOOK_SECRET must be set in .env and Vercel dashboard.
VERCEL_ACCESS_TOKEN is already configured (webchat project token).

---

## Phase E -- Enhanced Health Endpoint

**Goal**: GET /api/v1/health returns real connectivity status for all services.
Used by monitoring systems and the Settings page.

**Current**: {"status": "ok", "version": "0.1.0"}

**Target**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "database": {"status": "ok", "latency_ms": 12},
    "github": {"status": "ok", "user": "AyushmanGupta21"},
    "nvidia_nim": {"status": "ok", "models": 102},
    "vercel": {"status": "ok", "projects": ["webchat"]}
  }
}
```

**Files to change**: `backend/patchr/main.py` (enhance /health endpoint)

---

## Phase F -- Test Coverage

**Goal**: Prevent regressions. The codebase has no automated tests yet.

**Priority order**:
1. Webhook HMAC signature verification (valid + tampered payloads)
2. Incident state machine -- valid transitions pass, invalid ones raise
3. simulate-failure endpoint -- full E2E with mock AI
4. dismiss / resolve -- audit log written, timestamps set correctly
5. AI output JSON parsing -- malformed responses are handled gracefully

**Tool**: pytest + pytest-asyncio (already available in the Python env)

---

## Phase G -- Production Deployment

**Goal**: Move from localhost to production.

**Backend**: Railway or Fly.io
- Set all env vars in platform dashboard
- Set ENVIRONMENT=production (disables /docs, enables JSON logs)
- Replace Cloudflare tunnel with production domain

**Frontend**: Vercel
- Set NEXT_PUBLIC_API_URL to production backend URL
- Set NEXT_PUBLIC_DEMO_MODE=false

**Database**: Supabase (already production -- just update DATABASE_URL)

---

## API Reference (Key Endpoints)

### Auth
- POST /api/v1/auth/login -- get JWT token

### Incidents
- GET /api/v1/incidents -- list all (filter by status)
- GET /api/v1/incidents/{id} -- full detail
- POST /api/v1/incidents/simulate-failure -- trigger test pipeline
- POST /api/v1/incidents/{id}/reanalyze -- re-trigger AI
- POST /api/v1/incidents/{id}/dismiss -- owner dismisses
- POST /api/v1/incidents/{id}/resolve -- owner resolves
- GET /api/v1/incidents/{id}/analyses -- AI analysis results
- GET /api/v1/incidents/{id}/patches -- proposed patches
- GET /api/v1/incidents/{id}/audit -- full audit trail

### Patches
- POST /api/v1/patches/{id}/approve -- owner approves, triggers PR creation
- POST /api/v1/patches/{id}/reject -- owner rejects with reason

### Repositories
- GET /api/v1/repositories -- list connected repos
- POST /api/v1/repositories -- connect new repo
- DELETE /api/v1/repositories/{id} -- disconnect

### Webhooks
- POST /api/v1/webhooks/github -- GitHub webhook receiver
- POST /api/v1/webhooks/vercel -- Vercel webhook receiver

### Meta
- GET /health -- service status
- GET /docs -- Swagger UI (development only)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13), uvicorn, asyncio |
| ORM | SQLAlchemy 2.x async + asyncpg |
| Database | Supabase (PostgreSQL) |
| AI | NVIDIA NIM -- meta/llama-3.1-70b-instruct |
| GitHub | REST API v3 (PAT auth) |
| Vercel | REST API (project-scoped token) |
| Frontend | Next.js 15, TypeScript, Framer Motion |
| Scheduling | APScheduler (wired in Phase A) |
| Auth | JWT (owner-only, single-user) |
| Logging | structlog (structured JSON in production) |

---

## Environment Variables

| Variable | Purpose | Status |
|---|---|---|
| DATABASE_URL | Supabase connection string | Set |
| NVIDIA_API_KEY | NVIDIA NIM inference | Set |
| GITHUB_TOKEN | GitHub REST API | Set |
| VERCEL_ACCESS_TOKEN | Vercel REST API (webchat project) | Set |
| OWNER_PASSWORD | Dashboard login | Set |
| JWT_SECRET | Token signing | Set |
| GITHUB_WEBHOOK_SECRET | Webhook HMAC verification | Set |
| VERCEL_WEBHOOK_SECRET | Vercel webhook verification | Not set yet |