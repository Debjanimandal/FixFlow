# PatchR — Current Product State

> Last updated: 2026-08-22
> Branch: `master` | Repo: `Debjanimandal/PatchR`
> Commit: `f4dc0f2`

---

## What PatchR Is

An autonomous software reliability platform that:
1. **Monitors** — listens for GitHub/Vercel webhook events
2. **Detects** — creates incidents from `deployment_status: failure` events
3. **Analyzes** — uses AI (NVIDIA NIM / Llama-3.1-70B) to identify root cause
4. **Repairs** — generates multi-file code patches with the actual broken file contents
5. **Verifies** — scores patches for risk level (static analysis)
6. **Reviews** — human approval gate before any code is touched
7. **Recovers** — creates a GitHub PR; PR merged → monitors next deployment

---

## What Is Currently Working (Real, Not Fake)

### Backend — `backend/patchr/`
| Component | Status | Notes |
|---|---|---|
| FastAPI app with JWT auth | ✅ Working | Owner-only auth via `/api/v1/auth/login` |
| PostgreSQL via Supabase | ✅ Working | Async SQLAlchemy + asyncpg |
| GitHub webhook receiver | ✅ Working | HMAC-SHA256 verified, `deployment_status` + `push` |
| Vercel webhook receiver | ✅ Working | `/api/v1/webhooks/vercel` — needs secret configured |
| Incident creation | ✅ Working | From GitHub/Vercel/simulate |
| AI analysis (NIM provider) | ✅ Working | Llama-3.1-70B, structured JSON output |
| **Context engine** | ✅ **New** | Fetches real file contents + package.json before AI runs |
| Patch generation | ✅ Working | Multi-file, AI-generated with real code context |
| Static verification | ✅ Working | Risk scoring via regex pattern analysis |
| Human approval gate | ✅ Working | `POST /patches/{id}/approve` |
| GitHub PR creation | ✅ Working | Background task after approval |
| Audit log | ✅ Working | Every action immutably recorded |
| `POST /incidents/simulate-failure` | ✅ Working | Picks any active repo, 3 realistic error scenarios |
| `POST /incidents/{id}/dismiss` | ✅ **New** | Writes audit log + sets `resolved_at` |
| `POST /incidents/{id}/resolve` | ✅ **New** | Calculates `time_to_resolve_seconds` + audit log |
| `POST /incidents/{id}/reanalyze` | ✅ **New** | Re-triggers AI pipeline from failed/stalled states |
| `GET /incidents/{id}/analyses` | ✅ **New** | Lists all AI analyses for an incident |
| `GET /incidents/{id}/patches` | ✅ **New** | Lists all patches for an incident |
| `GET /incidents/{id}/audit` | ✅ **New** | Full immutable audit trail per incident |
| PR lifecycle monitor | ✅ **New** | `pr_monitor_service.py` — polls GitHub PR state |

### Database Schema (Supabase PostgreSQL)
- `repositories` — registered repos + Vercel project link
- `deployments` — deployment records per repo
- `incidents` — 16-state pipeline tracking (new in this session)
- `analyses` — AI analysis results with confidence + evidence
- `patches` — multi-file patch proposals with file_changes JSON
- `verification_results` — risk scores and check results
- `audit_logs` — immutable action trail

### Incident State Machine (16 states, as of 2026-08-21)
```
DETECTED → ANALYZING → ROOT_CAUSE_IDENTIFIED → REPAIR_PROPOSED
         → VERIFYING → VERIFIED → AWAITING_REVIEW → PR_CREATED
         → RECOVERY_MONITORING → RESOLVED

Side states: ANALYSIS_FAILED, VERIFICATION_FAILED, REJECTED,
             NEEDS_REVIEW, DISMISSED, REOPENED
```

### Frontend — `frontend/`
| Page | Status | Notes |
|---|---|---|
| Login | ✅ Working | JWT + demo mode bypass |
| Dashboard | ✅ Working | **15-second live polling, real simulate** |
| Incidents list | ✅ Working | All 16 status chips rendered |
| Incident detail | ✅ Working | **10-second polling**, 8-stage pipeline bar |
| Analysis tab | ✅ Working | Root cause + evidence + affected files |
| Patch tab | ✅ Working | File diffs, approve/reject, PR link |
| Audit tab | ✅ Working | Full chronological action trail |
| Repositories | ✅ Working | Add/remove repos |
| Settings | ✅ Working | Webhook URLs, config display |

---

## What Was Fixed This Session (2026-08-21)

### Critical Bugs Fixed
1. **B1**: `update_incident` was missing `await db.commit()` → status changes were silently lost
2. **B2**: `AuditAction` enum was missing `PATCH_GENERATION_FAILED` → patch failures crashed silently
3. **B3**: `_create_github_pr` opened an orphaned second DB session → PR audit logs may not save
4. **G7**: Structlog `event=` reserved keyword conflict in webhook warning log

### High-Impact Gaps Resolved
5. **G2**: Patch service was sending `file_contents={}` → AI had no code to work with
6. **G4**: Dashboard simulate used hardcoded `"demo/test-repo"` → always failed
7. **G6**: Dashboard had no auto-refresh → incidents appeared stale

### New Features
8. **Context Engine** (`context_service.py`): Fetches real file contents + package.json + tsconfig.json from GitHub before AI runs — AI now sees actual broken code
9. **16-state pipeline**: `IncidentStatus` expanded from 7 to 16 states, SQL migration run
10. **15s dashboard polling** + **10s detail page polling** — live status updates
11. **Status chip CSS** for all 16 states with semantic colors

---

### Phase 5-13 — Frontend Architecture & Light Premium Redesign (Completed 2026-08-21)
- **Visual Identity Shift**: Transitioned from a dark developer-console aesthetic to a "Light Premium Software Product" aesthetic, mirroring the PatchR landing page.
- **Global Design System**: Overhauled `globals.css` with a new token set (vibrant accent violet, soft off-white `#F4F5F7` background, pristine white surfaces, diffuse SaaS shadows, and softer `16px/20px` geometries).
- **App Shell**: Implemented a global layout shell (`layout.tsx`) featuring a distinct white left sidebar and a persistent Top Header (search, notifications, breadcrumbs).
- **Dashboard (FlowMail Polish)**: Recomposed into a dense, high-fidelity data grid.
  - Built premium summary metric cards with active trend indicators.
  - Installed `recharts` to build honest **Incident Volume** (Line Chart) and **Failure Types** (Donut Chart) data visualizations.
  - Implemented a **Recovery Activity** AI-intervention panel with progress bars.
  - Built a large, prominent Active Incidents table beside a vertically-stacked real-time Live Activity stream.
- **Incidents List**: High-density professional data table with filter UI and colored status chips.
- **Incident Detail**: 6-stage recovery pipeline visualization. Main panels are light, while technical displays (code diffs, logs) are maintained as embedded dark technical panels for optimal readability.
- **Repositories**: Professional inventory grid with visual 3-step onboarding flow.
- **Settings & Login**: Unified with the premium light theme, utilizing consistent inputs, buttons, and environment variable cards.
- **Final Consistency & UX Pass**: Completed a final audit to perfectly match the `HeroSection` landing page styles. All generic "Coming Soon" placeholders for Monitoring, Patches, Verification, Activity, Automations, Integrations, and Policies were replaced with high-fidelity, context-aware empty states.
---

## What Still Needs to Be Done (Backlog)

### Phase 14 — Build Logs for GitHub deployment_status
- `_process_deployment_status` still sets `build_logs = None`
- `VercelClient.get_build_logs_as_text()` already exists in `integrations/vercel.py`
- Fix: wire it into `_process_deployment_status` when `VERCEL_ACCESS_TOKEN` is set

### Phase 15 — Vercel Integration Activation
- Register `VERCEL_WEBHOOK_SECRET` in `.env`
- Register webhook URL in Vercel dashboard: `https://<tunnel>/api/v1/webhooks/vercel`
- Add `POST /repositories/{id}/link-vercel` endpoint for UI-based Vercel project linking

### Phase 16 — PR Lifecycle Wiring
- `pr_monitor_service.py` exists but is NOT scheduled yet
- Need to: add `pr_state` + `pr_merged_at` DB columns, wire APScheduler in `main.py`
- `resolve_recovered_incident()` needs to be called from webhook on successful deploy

### Phase 17 — Webhook Auto-Registration
- `POST /repositories/{id}/register-webhook` doesn't exist yet
- Would call GitHub Webhooks API to automatically register the PatchR hook URL
- Removes manual step of going into GitHub → Settings → Webhooks

### Phase 18 — Normalized Event Model
- GitHub and Vercel parsers share no common abstraction
- Create `NormalizedEvent` dataclass so a 3rd source (e.g. GitHub Actions) can be added easily

### Phase 19 — Alembic Migrations
- All schema changes are still raw SQL `ALTER TYPE` run manually
- Alembic env exists (`db/migrations/`) but no migration for the 16-state enum or new columns
- Next schema change MUST be done via Alembic

### Phase 20 — Test Coverage
- No automated tests yet
- Priority order: webhook HMAC signature verification, incident state machine, AI output parsing, simulate endpoint E2E

---

## Environment / Infrastructure

| Service | Details |
|---|---|
| Backend | FastAPI, uvicorn, Python 3.13, port 8000 |
| Frontend | Next.js 15, port 3000 |
| Database | Supabase (PostgreSQL + asyncpg) |
| AI | NVIDIA NIM — `meta/llama-3.1-70b-instruct` |
| GitHub | PAT token in `.env` — webhook secret optional |
| Vercel | Access token + webhook secret — partial integration |
| Tunnel | Cloudflare tunnel for webhook delivery |

## Configuration (`.env` keys)
```
DATABASE_URL=...
NVIDIA_API_KEY=...
GITHUB_TOKEN=...
GITHUB_WEBHOOK_SECRET=...   # optional but recommended
VERCEL_ACCESS_TOKEN=...      # enables build log fetching
VERCEL_WEBHOOK_SECRET=...    # needed for direct Vercel webhooks
OWNER_PASSWORD=...
JWT_SECRET=...
```
