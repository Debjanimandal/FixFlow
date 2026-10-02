# PatchR — Project Status & Architecture

> **Last Updated:** August 23, 2026  
> **Stack:** Next.js 16 · FastAPI · PostgreSQL (Supabase) · NVIDIA NIM · GitHub OAuth · Vercel API

---

## What is PatchR?

PatchR is an **autonomous deployment repair agent**. It watches your GitHub repositories and Vercel deployments, detects failures, diagnoses root causes using AI, generates a patch, and asks for your approval before pushing the fix.

---

## Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER JOURNEY                                  │
└─────────────────────────────────────────────────────────────────────┘

 1. LOGIN                    2. CONNECT REPO             3. CONNECT VERCEL
 ─────────────────           ─────────────────────       ─────────────────────
 User visits /login          User clicks                 User goes to Settings
        │                    "Import Repository"         pastes Vercel API token
        ▼                           │                           │
 GitHub OAuth redirect              ▼                           ▼
        │                    Fetches user's              Token stored in DB
        ▼                    GitHub repos via            against user account
 PatchR issues JWT           OAuth token                        │
 (stored in localStorage)           │                           ▼
        │                           ▼                    vercel-sync runs →
        ▼                    Repo saved in DB            auto-matches repos
 Dashboard unlocked          Webhook registered           to Vercel projects
                             on GitHub repo

 4. MONITORING               5. INCIDENT DETECTED        6. AI DIAGNOSIS
 ─────────────────────       ─────────────────────       ─────────────────────
 GitHub sends webhook        Incident created in DB      NVIDIA NIM LLM
 on push / deployment        with status=DETECTED        reads:
        │                           │                     · Build logs
        ▼                           ▼                     · Commit diff
 PatchR receives             AI pipeline triggered        · Error description
 webhook event               (async background)                  │
        │                                                         ▼
        ▼                                                Root cause identified
 Deployment status                                       Patch proposed
 parsed and logged

 7. PATCH REVIEW             8. USER APPROVES            9. RESOLVED
 ─────────────────────       ─────────────────────       ─────────────────────
 Diff shown in UI            User clicks Approve         PR created on GitHub
 "Awaiting Review"                  │                    Deployment re-runs
        │                           ▼                    Status → RESOLVED
        ▼                    PR created via               (or MONITORING)
 User can Approve            GitHub API
 or Reject
```

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js 16, Turbopack)     localhost:3000                │
│                                                                      │
│  /login          GitHub OAuth entry point                            │
│  /auth/callback  Receives JWT from backend                           │
│  /dashboard      Protected dashboard shell                           │
│    /repositories Connect repos, link Vercel, see status             │
│    /incidents    List all detected failures                          │
│    /incidents/[id]  Incident detail + patch diff viewer             │
│    /patches      All AI-generated patches                            │
│    /monitoring   Live deployment feed (placeholder)                  │
│    /settings     Connect Vercel token, webhook URLs, env vars        │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ REST API (Bearer JWT)
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│  BACKEND  (FastAPI + Uvicorn)          localhost:8000                │
│                                                                      │
│  /api/v1/auth/                                                       │
│    GET  /github              → Redirect to GitHub OAuth              │
│    GET  /github/callback     → Exchange code → issue JWT             │
│    GET  /me                  → Current user info                     │
│    GET  /vercel-token        → Check if user has Vercel token        │
│    PUT  /vercel-token        → Save user's personal Vercel token     │
│                                                                      │
│  /api/v1/repositories/                                               │
│    GET  /github-repos        → User's GitHub repos (OAuth filtered)  │
│    GET  /vercel-projects     → User's Vercel projects (per-user tok) │
│    POST /vercel-sync         → Auto-match repos ↔ Vercel projects   │
│    GET  /                    → List connected repos                  │
│    POST /                    → Connect a new repo                    │
│    PATCH /{id}               → Update repo settings                  │
│    POST /{id}/link-vercel    → Link Vercel (with API verification)   │
│    POST /{id}/register-webhook → Register GitHub webhook             │
│    DELETE /{id}              → Disconnect repo                       │
│                                                                      │
│  /api/v1/incidents/                                                  │
│    GET  /                    → List incidents (with filters)         │
│    GET  /{id}                → Incident detail                       │
│    POST /simulate-failure    → Simulate failure for testing          │
│                                                                      │
│  /api/v1/patches/                                                    │
│    GET  /{id}                → Patch detail + diff                   │
│    POST /{id}/approve        → Approve patch (creates PR)            │
│    POST /{id}/reject         → Reject patch                          │
│                                                                      │
│  /api/v1/webhooks/                                                   │
│    POST /github              → Receive GitHub push/deploy events     │
│    POST /vercel              → Receive Vercel deployment events      │
│                                                                      │
│  /api/v1/analysis/                                                   │
│    POST /incidents/{id}/analyze → Trigger AI root-cause analysis     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────────┐
          │                 │                     │
          ▼                 ▼                     ▼
  ┌───────────────┐  ┌────────────┐     ┌──────────────────┐
  │  PostgreSQL   │  │ GitHub API │     │  NVIDIA NIM API  │
  │  (Supabase)   │  │            │     │  llama-3.1-70b   │
  │               │  │ • OAuth    │     │                  │
  │  Users        │  │ • Repos    │     │  Root cause      │
  │  Repositories │  │ • Webhooks │     │  analysis        │
  │  Incidents    │  │ • PRs      │     │  Patch gen       │
  │  Analyses     │  └────────────┘     └──────────────────┘
  │  Patches      │
  │  Deployments  │         ▼
  └───────────────┘  ┌────────────┐
                     │ Vercel API │
                     │            │
                     │ • Projects │
                     │ • Deploy   │
                     │   logs     │
                     │ • Webhooks │
                     └────────────┘
```

---

## Database Models

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `User` | `github_id`, `github_login`, `vercel_access_token` | Authenticated user with per-user Vercel token |
| `Repository` | `full_name`, `vercel_project_id`, `webhook_active` | Connected GitHub repo |
| `Incident` | `status`, `severity`, `source`, `failure_type` | Detected deployment failure |
| `Analysis` | `root_cause`, `confidence_score`, `suggested_fix` | AI diagnosis result |
| `Patch` | `patch_diff`, `status`, `pr_url` | AI-generated code fix |
| `Deployment` | `status`, `build_logs`, `commit_sha` | Vercel deployment event |

---

## Incident Status Lifecycle

```
DETECTED
    │
    ▼
ANALYZING ──(fail)──► ANALYSIS_FAILED
    │
    ▼
ROOT_CAUSE_IDENTIFIED
    │
    ▼
REPAIR_PROPOSED
    │
    ▼
VERIFYING ──(fail)──► VERIFICATION_FAILED
    │
    ▼
AWAITING_REVIEW ──(reject)──► REJECTED
    │
    ▼ (approve)
PR_CREATED
    │
    ▼
RECOVERY_MONITORING
    │
    ▼
RESOLVED
```

---

## What's Done ✅

### Authentication
- [x] GitHub OAuth login (full redirect flow)
- [x] JWT issued per-user with GitHub profile embedded
- [x] Graceful DB fallback — login works even if Supabase is unreachable
- [x] Protected dashboard routes

### Repository Management
- [x] List user's GitHub repos (filtered to logged-in user's account only)
- [x] Connect a repo (saves to DB)
- [x] Disconnect a repo
- [x] GitHub webhook auto-registration (`admin:repo_hook` scope)
- [x] Branch info auto-sync from GitHub API

### Vercel Integration
- [x] Per-user Vercel API token (saved in DB, not shared .env)
- [x] Auto-sync: match Vercel projects to repos via `linked_repo` metadata
- [x] Manual link with **backend verification** (Vercel API confirms project exists)
- [x] Unlink Vercel project from repo
- [x] Settings page with token input, project preview, status

### Incidents & AI
- [x] Incident model with full status lifecycle
- [x] NVIDIA NIM (Llama 3.1 70B) integration for root-cause analysis
- [x] Simulate failure endpoint for testing
- [x] Patch generation (diff format)
- [x] Patch approve → creates GitHub PR
- [x] Patch reject with reason

### Infrastructure
- [x] Async PostgreSQL (SQLAlchemy + asyncpg + Supabase)
- [x] `get_db_or_503` — clean HTTP 503 instead of connection crashes
- [x] 5-second DB connection timeout (fails fast instead of hanging)
- [x] APScheduler PR lifecycle monitor (every 5 min)
- [x] Structured logging (structlog)
- [x] CORS configured for localhost:3000

### Frontend
- [x] Login page with GitHub OAuth button
- [x] Dashboard layout with sidebar navigation
- [x] Repositories page with Vercel status, error banner + retry
- [x] Settings page (Vercel token, webhook URLs, env checklist)
- [x] Incidents list with status/severity badges
- [x] Incident detail page (placeholder for diff viewer)
- [x] Patches page

---

## What's Left to Build 🔲

### Phase 2 — Live Incident Detection
- [ ] Webhook handler: parse Vercel `deployment.error` events
- [ ] Pull build logs from Vercel API on failure
- [ ] Auto-trigger AI analysis pipeline on deployment failure
- [ ] Live monitoring dashboard (real-time feed)

### Phase 3 — User Consent Flow (Diff Viewer)
- [ ] Side-by-side diff viewer in incident detail page
- [ ] Approve / Reject buttons with confirmation modal
- [ ] Email or in-app notification when patch is ready for review

### Phase 4 — Autonomous PR Creation
- [ ] GitHub PR created automatically on approval
- [ ] PR description generated from AI analysis
- [ ] Monitor PR merge → trigger re-deployment check

### Phase 5 — Production Hardening
- [ ] Move Vercel token encryption at rest
- [ ] Vercel OAuth app (vs manual token paste)
- [ ] Multi-repo webhook fan-out
- [ ] Rate limiting and audit logs

---

## Environment Variables Required

| Variable | Used For | Status |
|----------|----------|--------|
| `DATABASE_URL` | PostgreSQL connection | ✅ Set |
| `GITHUB_CLIENT_ID` | OAuth App | ✅ Set |
| `GITHUB_CLIENT_SECRET` | OAuth App | ✅ Set |
| `GITHUB_TOKEN` | Webhook registration | ✅ Set |
| `GITHUB_WEBHOOK_SECRET` | Webhook HMAC | ✅ Set |
| `NVIDIA_API_KEY` | AI diagnosis | ✅ Set |
| `JWT_SECRET` | Token signing | ✅ Set |
| `VERCEL_ACCESS_TOKEN` | Fallback (global) | ✅ Set |
| `VERCEL_WEBHOOK_SECRET` | Vercel webhook HMAC | ⚠️ Not set |
| `API_BASE_URL` | Public backend URL (ngrok) | ⚠️ localhost only |

---

## Running Locally

```bash
# Terminal 1 — Backend
cd backend
py -m uvicorn patchr.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npm run dev -- --port 3000
```

Visit: `http://localhost:3000`

> **Note:** Supabase requires internet access. If DNS fails, login still works via stateless JWT but repo/incident data won't persist.
