# PatchR Backend

**FastAPI backend for the PatchR autonomous self-healing platform.**

This service is fully independent. It runs on its own, connects to Supabase, and exposes a REST API that the frontend consumes via HTTP.

---

## Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn (async)
- **Database**: PostgreSQL via Supabase (async SQLAlchemy + asyncpg)
- **AI**: NVIDIA NIM — OpenAI-compatible API
- **Auth**: JWT (single owner, password-configurable)
- **Integrations**: GitHub REST API v3, Vercel REST API

---

## Setup

### 1. Install dependencies
```bash
pip install -e ".[dev]"
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to Get |
|---|---|
| `DATABASE_URL` | Supabase Dashboard → Settings → Database → Connection String |
| `OWNER_PASSWORD` | Choose a strong password |
| `JWT_SECRET` | Run: `openssl rand -hex 32` |
| `NVIDIA_API_KEY` | https://build.nvidia.com → API Keys |
| `GITHUB_TOKEN` | https://github.com/settings/tokens (scopes: `repo`, `workflow`) |
| `GITHUB_WEBHOOK_SECRET` | Any strong random string |
| `VERCEL_ACCESS_TOKEN` | https://vercel.com/account/tokens |

### 3. Start the server
```bash
uvicorn patchr.main:app --reload --port 8000
```

---

## API Reference

| Endpoint | Description |
|---|---|
| `GET /health` | Health check — no auth required |
| `GET /docs` | Interactive Swagger UI (dev only) |
| `POST /api/v1/auth/login` | Owner login → returns JWT |
| `GET /api/v1/repositories` | List connected repos |
| `POST /api/v1/repositories` | Connect a new repo |
| `GET /api/v1/incidents` | List incidents (filterable, paginated) |
| `GET /api/v1/incidents/{id}` | Incident detail |
| `GET /api/v1/incidents/{id}/analyses` | AI analyses for an incident |
| `GET /api/v1/incidents/{id}/patches` | Proposed patches |
| `POST /api/v1/patches/{id}/approve` | Approve + create GitHub PR |
| `POST /api/v1/patches/{id}/reject` | Reject a patch |
| `POST /api/v1/webhooks/github` | GitHub webhook receiver |
| `POST /api/v1/webhooks/vercel` | Vercel webhook receiver |

---

## Project Structure

```
backend/
├── patchr/
│   ├── ai/               NVIDIA NIM provider, prompt templates, schemas
│   ├── db/
│   │   ├── models.py     SQLAlchemy ORM models (7 tables)
│   │   ├── session.py    Async engine + session factory (NullPool for Supabase)
│   │   └── migrations/   Alembic migration versions
│   ├── integrations/
│   │   ├── github.py     GitHub REST client (branches, PRs, files)
│   │   └── vercel.py     Vercel REST client (build logs, deployments)
│   ├── routers/
│   │   ├── auth.py       Login endpoint
│   │   ├── repositories.py
│   │   ├── incidents.py
│   │   ├── analysis.py
│   │   ├── patches.py    Approve/reject + GitHub PR creation
│   │   └── webhooks.py   GitHub + Vercel event ingestion (HMAC verified)
│   ├── schemas/          Pydantic request/response models
│   ├── services/
│   │   ├── incident_service.py    Incident detection from webhook events
│   │   ├── analysis_service.py   AI-powered root cause analysis
│   │   ├── patch_service.py      AI patch generation
│   │   ├── verification_service.py  Risk scoring (Phase 5)
│   │   └── log_parser.py         Build log classification
│   ├── workers/          Background job workers
│   ├── auth.py           JWT creation + verification
│   ├── config.py         Pydantic settings (loads from .env)
│   └── main.py           FastAPI app factory + lifespan
├── .env                  (gitignored) real secrets
├── .env.example          template
├── alembic.ini
└── pyproject.toml
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `repositories` | Connected GitHub repos |
| `deployments` | Deployment events from webhooks |
| `incidents` | Detected failures |
| `analyses` | AI root-cause analyses |
| `patches` | AI-proposed code patches |
| `verification_results` | Risk scores per patch |
| `audit_logs` | Immutable action trail |

---

## Running in Production

```bash
uvicorn patchr.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Set `ENVIRONMENT=production` in `.env` to:
- Disable `/docs` and `/redoc`
- Switch to JSON structured logging
- Enable stricter CORS
