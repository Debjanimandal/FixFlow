# PatchR - Project Task Log

> Living document. Check off items as they are completed.
> Last updated: 2026-08-21

---

## COMPLETED

### Codebase Restructure
- [x] Moved apps/api/ to backend/ (flat at root)
- [x] Moved apps/web/ to frontend/ (flat at root)
- [x] Created root Makefile orchestration
- [x] Rewrote README.md files (root + backend + frontend)

### Phase 1-7 - Full Backend + Dashboard
- [x] FastAPI backend: auth, repositories, incidents, analysis, patches, verification, webhooks
- [x] PostgreSQL schema (7 tables) live in Supabase
- [x] NVIDIA NIM AI integration (analysis + patch generation)
- [x] GitHub + Vercel webhook ingestion with HMAC verification
- [x] PR creation workflow (branch -> commits -> PR)
- [x] Next.js dashboard: incidents list, detail, analysis, patch diff, audit log
- [x] Repositories + Settings pages
- [x] Demo mode via NEXT_PUBLIC_DEMO_MODE env var

### Public Landing Page (2026-08-20)
- [x] Full marketing landing page at / (framer-motion, responsive)
- [x] Hero, Integration strip, Problem, Value (99% stat card), How It Works
- [x] Feature sections (Monitoring, Verification, Oversight)
- [x] Use Cases, Security, FAQ, Final CTA, Footer

### Dashboard UI Overhaul (2026-08-21)
- [x] Light Premium SaaS design system -- token-based CSS, off-white surfaces
- [x] Premium metric cards, Recharts data visualizations (Line + Donut charts)
- [x] Recovery Activity panel, Live Activity stream, Active Incidents table
- [x] 16-state incident pipeline bar visualization on detail page
- [x] All 16 status chips with semantic colors

### Critical Bug Fixes (2026-08-21)
- [x] is_active field added to Repository model -- was crashing POST /repositories
- [x] update_incident was missing await db.commit() -- status changes silently lost
- [x] AuditAction enum missing PATCH_GENERATION_FAILED -- patch failures crashed silently
- [x] _create_github_pr orphaned DB session -- PR audit logs were not saving
- [x] Patch service was sending file_contents={} -- AI had no code context

### High-Impact Features (2026-08-21)
- [x] Context Engine (context_service.py) -- fetches real file contents from GitHub before AI analysis
- [x] 16-state incident pipeline -- expanded from 7 states, SQL migration applied
- [x] 15s dashboard polling + 10s detail page polling -- live status updates
- [x] POST /incidents/simulate-failure -- 3 realistic error scenarios, picks any active repo
- [x] POST /incidents/{id}/dismiss -- writes audit log + sets resolved_at
- [x] POST /incidents/{id}/resolve -- calculates time_to_resolve_seconds + audit log
- [x] POST /incidents/{id}/reanalyze -- re-triggers AI pipeline from failed/stalled states
- [x] GET /incidents/{id}/analyses -- lists all AI analyses for an incident
- [x] GET /incidents/{id}/patches -- lists all patches for an incident
- [x] GET /incidents/{id}/audit -- full immutable audit trail per incident
- [x] pr_monitor_service.py created -- polls GitHub PR state, drives RECOVERY_MONITORING -> RESOLVED

### Environment / Keys
- [x] DATABASE_URL -- Supabase connected
- [x] NVIDIA_API_KEY -- real key set in .env
- [x] GITHUB_TOKEN -- real PAT set in .env
- [x] OWNER_PASSWORD -- set
- [x] JWT_SECRET -- set
- [x] GITHUB_WEBHOOK_SECRET -- set

---

## HIGH PRIORITY -- Pipeline Completion

### Phase A -- Wire PR Lifecycle Monitor
# pr_monitor_service.py exists but is NOT running yet. Pipeline stuck at PR_CREATED forever.
- [ ] Add pr_state (open/merged/closed) column to patches table
- [ ] Add pr_merged_at (DateTime) column to patches table
- [ ] Create Alembic migration for the above two columns
- [ ] Wire APScheduler in main.py startup -> runs check_open_prs() every 5 min
- [ ] In _process_deployment_status webhook handler -- on successful deploy, call resolve_recovered_incident() if repo has incident in RECOVERY_MONITORING

### Phase B -- Build Logs from Vercel API
# Without real build logs, the AI works blind and produces lower-quality patches.
- [ ] In routers/webhooks.py -> _process_deployment_status():
- [ ] If VERCEL_ACCESS_TOKEN is set, call VercelClient.get_build_logs_as_text(deployment_id)
- [ ] Pass result as build_logs= into incident_service.create_incident_from_github_deployment()
- Note: VercelClient already exists in integrations/vercel.py -- just needs wiring

---

## MEDIUM PRIORITY

### Phase C -- Webhook Auto-Registration
# Currently users must manually go to GitHub Settings -> Webhooks.
- [ ] Add POST /repositories/{id}/register-webhook to routers/repositories.py
- [ ] Calls GitHub API -> POST /repos/{owner}/{repo}/hooks
- [ ] Registers PatchR webhook URL with deployment_status + push events
- [ ] Stores webhook ID in repositories table (new github_webhook_id column)
- [ ] Add Alembic migration for github_webhook_id column

### Phase D -- Vercel Project Linking
- [ ] Add POST /repositories/{id}/link-vercel endpoint
- [ ] Accepts vercel_project_id + vercel_project_name
- [ ] Calls Vercel API to register webhook for deployment.error + deployment.ready
- [ ] Add VERCEL_WEBHOOK_SECRET to .env + Vercel dashboard

### Phase E -- Enhanced Health Endpoint
- [ ] GET /api/v1/health currently returns {"status": "ok"} only
- [ ] Expand to check: DB ping, GitHub API reachable, NVIDIA API key valid, Vercel reachable
- [ ] Return per-service status + latency ms

### Frontend: Real Integration Status on Settings Page
- [ ] Settings page currently hardcodes integration status -- wire to real /health API

### Backend: Pagination
- [ ] Wire limit/offset params from incidents API to frontend paginator

### Notifications (Slack)
- [ ] SLACK_WEBHOOK_URL config + notification_service.py
- [ ] Notify on: incident detected, patch approved, incident resolved

---

## LOWER PRIORITY

### Phase F -- Normalized Event Model
- [ ] Create schemas/events.py -> NormalizedEvent dataclass
- [ ] Refactor GitHub + Vercel handlers to normalize payloads first, then process
- [ ] Enables adding GitHub Actions / PagerDuty as future event sources trivially

### Security Hardening
- [ ] Rate limiting on auth endpoint (slowapi)
- [ ] Warn at startup if JWT_SECRET is still default
- [ ] Enforce webhook secrets in production mode

### Frontend: Error Handling
- [ ] React error boundaries on all dashboard pages
- [ ] Handle JWT expiry gracefully (redirect to login)

### Frontend: Incident Filtering
- [ ] Filter by severity, repository, date range, keyword search

### Tests
- [ ] Unit: webhook HMAC signature verification (valid + tampered)
- [ ] Unit: incident state machine transitions
- [ ] Unit: AI output JSON parsing + validation
- [ ] Integration: POST /incidents/simulate-failure E2E
- [ ] Integration: dismiss + resolve audit trail correctness
- [ ] GitHub Actions CI pipeline

### Production Deployment
- [ ] Backend: Railway / Render / Fly.io
- [ ] Frontend: Vercel
- [ ] Set all production env vars, ENVIRONMENT=production
- [ ] Switch from Cloudflare tunnel to production domain for webhooks

---

## Configuration Reference

| Variable | File | Status |
|---|---|---|
| DATABASE_URL | backend/.env | Set |
| NVIDIA_API_KEY | backend/.env | Set |
| GITHUB_TOKEN | backend/.env | Set |
| OWNER_PASSWORD | backend/.env | Set |
| JWT_SECRET | backend/.env | Set |
| GITHUB_WEBHOOK_SECRET | backend/.env | Set |
| VERCEL_ACCESS_TOKEN | backend/.env | Needed for build logs |
| VERCEL_WEBHOOK_SECRET | backend/.env | Needed for Vercel direct webhooks |

---

## Change Log

| Date | What Changed |
|---|---|
| 2026-08-08 | Project created. Phases 1-4 scaffolded |
| 2026-08-11 | Demo mode added. NVIDIA NIM integrated. Log parser built |
| 2026-08-13 | Supabase connected. All 7 DB tables created. NullPool fix applied |
| 2026-08-13 | GitHub PR creation implemented. Verification layer built |
| 2026-08-19 | Demo mode re-enabled. Mock data added to all dashboard pages |
| 2026-08-20 | Public landing page built (framer-motion, fully responsive) |
| 2026-08-21 | Full codebase audit. Critical bugs fixed. Context engine added. 16-state pipeline |
| 2026-08-21 | Dashboard Light Premium UI overhaul. All design passes complete |
| 2026-08-21 | Phase 1 backend endpoints: dismiss, resolve, reanalyze, simulate-failure, PR monitor service |