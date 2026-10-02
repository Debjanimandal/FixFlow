# PatchR — Complete Workflow

> The full lifecycle from first login to autonomous deployment repair.

---

## Overview: The 5 Phases

```
┌──────────┐    ┌────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  PHASE 1 │───►│  PHASE 2   │───►│   PHASE 3    │───►│   PHASE 4   │───►│  PHASE 5   │
│  SETUP   │    │ MONITORING │    │  AI DIAGNOSIS│    │USER CONSENT │    │ RESOLUTION │
└──────────┘    └────────────┘    └──────────────┘    └─────────────┘    └────────────┘
 Login             Webhook           Root cause          Diff review        PR created
 Connect repo      received          + patch gen         Approve/Reject     Deployed ✅
 Link Vercel       Incident          AI explains         User decides       Closed ✓
                   created           the fix
```

---

## Phase 1 — Setup

### 1A. GitHub Login

```
User                    PatchR Frontend         PatchR Backend         GitHub
 │                            │                       │                    │
 │  Visit /login              │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │                       │                    │
 │  Click "Sign in with       │                       │                    │
 │  GitHub"                   │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │  GET /api/v1/auth/    │                    │
 │                            │  github               │                    │
 │                            │──────────────────────►│                    │
 │                            │                       │  Redirect to       │
 │                            │                       │  GitHub OAuth      │
 │                            │                       │──────────────────► │
 │                            │                       │                    │
 │  ◄────────────────── GitHub login page shown ──────────────────────── │
 │                            │                       │                    │
 │  Authorize PatchR          │                       │                    │
 │──────────────────────────────────────────────────────────────────────► │
 │                            │                       │                    │
 │                            │                       │  ◄──code=xxx────── │
 │                            │                       │                    │
 │                            │                       │  Exchange code     │
 │                            │                       │  → access_token    │
 │                            │                       │──────────────────► │
 │                            │                       │  ◄──access_token── │
 │                            │                       │                    │
 │                            │                       │  Fetch user profile│
 │                            │                       │──────────────────► │
 │                            │                       │  ◄──{login,name}── │
 │                            │                       │                    │
 │                            │                       │  Save user to DB   │
 │                            │                       │  Issue JWT         │
 │                            │                       │                    │
 │                            │  ◄── redirect to      │                    │
 │                            │  /auth/callback       │                    │
 │                            │  ?token=eyJ...        │                    │
 │                            │                       │                    │
 │                            │  Store JWT in         │                    │
 │                            │  localStorage         │                    │
 │                            │                       │                    │
 │  ◄──────────── Redirect to /dashboard ────────────│                    │
```

---

### 1B. Connect a GitHub Repository

```
User                    Repositories Page          Backend              GitHub API
 │                            │                       │                    │
 │  Click "Import             │                       │                    │
 │  Repository"               │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │  GET /github-repos    │                    │
 │                            │──────────────────────►│                    │
 │                            │                       │  Fetch repos using │
 │                            │                       │  user's OAuth token│
 │                            │                       │──────────────────► │
 │                            │                       │  ◄── repo list ─── │
 │                            │                       │                    │
 │                            │  Only shows repos     │                    │
 │                            │  under YOUR account   │                    │
 │  ◄── searchable repo list ─│                       │                    │
 │                            │                       │                    │
 │  Select repo &             │                       │                    │
 │  click "Import"            │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │  POST /repositories   │                    │
 │                            │  { full_name }        │                    │
 │                            │──────────────────────►│                    │
 │                            │                       │  Save to DB        │
 │                            │                       │  Auto-register     │
 │                            │                       │  GitHub webhook    │
 │                            │                       │──────────────────► │
 │                            │                       │  ◄── webhook_id ── │
 │                            │                       │                    │
 │  ◄── Repo appears in list ─│                       │                    │
 │       ✅ Webhook Active    │                       │                    │
```

---

### 1C. Connect Vercel Account

```
User                    Settings Page              Backend             Vercel API
 │                            │                       │                    │
 │  Go to Settings →          │                       │                    │
 │  Vercel Account            │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │  GET /auth/           │                    │
 │                            │  vercel-token         │                    │
 │                            │──────────────────────►│                    │
 │                            │  { has_token: false } │                    │
 │                            │                       │                    │
 │  Get token from            │                       │                    │
 │  vercel.com/account/tokens │                       │                    │
 │  Paste token → Save        │                       │                    │
 │──────────────────────────► │                       │                    │
 │                            │  PUT /auth/           │                    │
 │                            │  vercel-token         │                    │
 │                            │  { token: "vcp_..." } │                    │
 │                            │──────────────────────►│                    │
 │                            │                       │  Store token in DB │
 │                            │                       │  against User row  │
 │                            │                       │                    │
 │                            │                       │  GET /v9/projects  │
 │                            │                       │──────────────────► │
 │                            │                       │  ◄── project list ─│
 │                            │                       │                    │
 │  ◄── Your Vercel projects  │                       │                    │
 │       appear in preview    │                       │                    │
 │                            │                       │                    │
 │  Go to Repositories        │                       │                    │
 │  Page reloads              │                       │                    │
 │                            │  vercel-sync runs     │                    │
 │                            │──────────────────────►│                    │
 │                            │                       │  Compare           │
 │                            │                       │  project.link.repo │
 │                            │                       │  with repo names   │
 │                            │                       │  Auto-links matches│
 │  ◄── Matched repos show    │                       │                    │
 │       ✅ webchat           │                       │                    │
```

---

## Phase 2 — Live Monitoring

### How Deployment Failures Are Detected

```
GitHub / Vercel               PatchR Webhook               Database
     │                             │                           │
     │  Push to connected repo     │                           │
     │────────────────────────────►│                           │
     │                             │  Parse push event         │
     │                             │  Extract commit_sha,      │
     │                             │  commit_message, diff     │
     │                             │                           │
     │  Deployment starts on       │                           │
     │  Vercel (auto-triggered)    │                           │
     │                             │                           │
     │  deployment.error event     │                           │
     │────────────────────────────►│                           │
     │                             │  Match to repo in DB      │
     │                             │──────────────────────────►│
     │                             │                           │ Create Incident
     │                             │                           │ status=DETECTED
     │                             │                           │ severity=HIGH
     │                             │                           │
     │                             │  Fetch build logs         │
     │                             │  from Vercel API          │
     │                             │──────────────────────────►│ (stored in DB)
     │                             │                           │
     │                             │  Trigger AI analysis      │
     │                             │  pipeline (background)    │
```

---

## Phase 3 — AI Diagnosis Pipeline

```
Incident (status=DETECTED)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  ANALYSIS PIPELINE  (runs as async background task)     │
│                                                         │
│  Input:                                                 │
│  ├─ build_logs      (from Vercel API)                  │
│  ├─ commit_diff     (from GitHub API)                  │
│  ├─ error_message   (from webhook payload)             │
│  └─ repo_context    (language, framework, branch)      │
│                                                         │
│  Step 1: Format prompt                                  │
│  ┌────────────────────────────────────┐                 │
│  │ "You are a senior engineer.        │                 │
│  │  Deployment failed with:           │                 │
│  │  [build_logs]                      │                 │
│  │  Recent commit diff:               │                 │
│  │  [commit_diff]                     │                 │
│  │  Identify root cause and           │                 │
│  │  generate a patch."               │                 │
│  └────────────────────────────────────┘                 │
│                                                         │
│  Step 2: Call NVIDIA NIM (Llama 3.1 70B)               │
│  ├─ Model: meta/llama-3.1-70b-instruct                 │
│  └─ Temperature: 0.1 (deterministic)                   │
│                                                         │
│  Step 3: Parse AI response                             │
│  ├─ root_cause      → Analysis.root_cause              │
│  ├─ confidence      → Analysis.confidence_score        │
│  ├─ suggested_fix   → Analysis.suggested_fix           │
│  └─ patch_diff      → Patch.patch_diff                 │
│                                                         │
│  Step 4: Risk scoring & verification                   │
│  └─ Confidence < threshold? → status=NEEDS_REVIEW      │
│                                                         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
              Incident: status=AWAITING_REVIEW
              Patch: status=REPAIR_PROPOSED
              → User notified in dashboard
```

---

## Phase 4 — User Consent Flow

```
User                  Incident Detail Page          Backend           GitHub
 │                          │                          │                 │
 │  Open Incidents list     │                          │                 │
 │─────────────────────────►│                          │                 │
 │                          │  GET /incidents          │                 │
 │                          │─────────────────────────►│                 │
 │                          │  ◄── list with           │                 │
 │                          │     "Awaiting Review"    │                 │
 │                          │                          │                 │
 │  Click incident          │                          │                 │
 │─────────────────────────►│                          │                 │
 │                          │  GET /incidents/{id}     │                 │
 │                          │  GET /incidents/{id}     │                 │
 │                          │  /patches                │                 │
 │                          │─────────────────────────►│                 │
 │                          │                          │                 │
 │                          │  ◄── incident + patch    │                 │
 │                          │      with diff           │                 │
 │                          │                          │                 │
 │  ◄── Diff viewer shown   │                          │                 │
 │      ┌─────────┬───────┐ │                          │                 │
 │      │ BEFORE  │ AFTER │ │                          │                 │
 │      │ - line  │ +fix  │ │                          │                 │
 │      └─────────┴───────┘ │                          │                 │
 │      [Approve] [Reject]  │                          │                 │
 │                          │                          │                 │
 │  ─── APPROVE ──────────► │                          │                 │
 │                          │  POST /patches/{id}      │                 │
 │                          │  /approve                │                 │
 │                          │─────────────────────────►│                 │
 │                          │                          │  Create PR      │
 │                          │                          │─────────────────►
 │                          │                          │  ◄── PR URL ─── │
 │                          │                          │                 │
 │  ◄── PR link shown       │  Incident: PR_CREATED    │                 │
 │                          │                          │                 │
 │  ─── REJECT ───────────► │                          │                 │
 │  (with reason)           │  POST /patches/{id}      │                 │
 │                          │  /reject { reason }      │                 │
 │                          │─────────────────────────►│                 │
 │                          │                          │  Patch: REJECTED│
 │                          │                          │  Incident stays │
 │                          │                          │  open for manual│
 │  ◄── Marked rejected     │                          │  fix            │
```

---

## Phase 5 — Resolution Monitoring

```
GitHub PR (created by PatchR)
         │
         │  Developer merges PR
         ▼
Vercel auto-deploys merged code
         │
         │  deployment.ready event
         ▼
PatchR Webhook receives event
         │
         ▼
Match deployment to Incident
         │
         ├── ✅ Success → Incident: RESOLVED
         │              Close PR monitoring
         │              Log resolution time
         │
         └── ❌ Still failing → Incident: REOPENED
                              AI re-diagnoses
                              New patch generated
```

---

## Master End-to-End Data Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  1. TRIGGER          GitHub push / Vercel deployment.error webhook        │
│         │                                                                 │
│         ▼                                                                 │
│  2. DETECT           Create Incident (DETECTED)                           │
│         │            Fetch build logs + commit diff                       │
│         ▼                                                                 │
│  3. ANALYZE          NVIDIA NIM Llama 3.1                                │
│         │            Input: logs + diff + error                           │
│         │            Output: root_cause + patch_diff + confidence         │
│         ▼                                                                 │
│  4. VERIFY           Risk score check                                     │
│         │            Auto-approve if confidence > threshold               │
│         │            Otherwise → AWAITING_REVIEW                         │
│         ▼                                                                 │
│  5. CONSENT          User sees diff in dashboard                          │
│         │            Approve → create PR                                  │
│         │            Reject → close with reason                           │
│         ▼                                                                 │
│  6. FIX              GitHub PR created with patch                         │
│         │            Developer reviews & merges                           │
│         ▼                                                                 │
│  7. CONFIRM          Monitor next deployment                              │
│                      Healthy → RESOLVED ✅                               │
│                      Still failing → REOPENED 🔄                        │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Key Data Objects

### Incident
```json
{
  "id": "uuid",
  "title": "Build failed: Cannot find module '@/components/Button'",
  "status": "awaiting_review",
  "severity": "critical",
  "source": "vercel_deployment",
  "failure_type": "build_error",
  "commit_sha": "a3f9d12",
  "commit_message": "refactor: move Button component",
  "repository_full_name": "AnkitBhattacherjee/my-app",
  "build_logs": "Error: Cannot find module...",
  "created_at": "2026-08-23T01:00:00Z"
}
```

### Analysis
```json
{
  "id": "uuid",
  "incident_id": "uuid",
  "root_cause": "The Button component was moved but the import path was not updated in 3 files.",
  "confidence_score": 0.94,
  "suggested_fix": "Update import from '@/components/Button' to '@/components/ui/Button'",
  "model_used": "meta/llama-3.1-70b-instruct",
  "created_at": "2026-08-23T01:00:15Z"
}
```

### Patch
```json
{
  "id": "uuid",
  "incident_id": "uuid",
  "status": "awaiting_review",
  "patch_diff": "--- a/pages/home.tsx\n+++ b/pages/home.tsx\n@@ -1,4 +1,4 @@\n-import Button from '@/components/Button'\n+import Button from '@/components/ui/Button'",
  "files_changed": ["pages/home.tsx", "pages/about.tsx"],
  "pr_url": null,
  "created_at": "2026-08-23T01:00:16Z"
}
```

---

## Integration Points Summary

| Integration | What It Does | Token Used |
|---|---|---|
| **GitHub OAuth** | User login, profile fetch | GitHub OAuth App |
| **GitHub Repos API** | List user's repos (filtered) | User's OAuth access token |
| **GitHub Webhooks API** | Register push/deploy hooks on repos | `GITHUB_TOKEN` (PAT) |
| **GitHub Contents API** | Fetch files for diff context | `GITHUB_TOKEN` |
| **GitHub PRs API** | Create PR with patch | `GITHUB_TOKEN` |
| **Vercel Projects API** | List projects, auto-match repos | Per-user `vercel_access_token` (DB) |
| **Vercel Deployments API** | Fetch build logs on failure | Per-user `vercel_access_token` (DB) |
| **Vercel Webhooks API** | Register deployment event hooks | Per-user `vercel_access_token` (DB) |
| **NVIDIA NIM API** | LLM root-cause + patch generation | `NVIDIA_API_KEY` |

---

## Webhook Event Map

| Webhook Source | Event | PatchR Action |
|---|---|---|
| GitHub | `push` | Record commit, note changed files |
| GitHub | `deployment_status` | Track deploy start/finish |
| Vercel | `deployment.error` | **Create incident**, fetch logs, trigger AI |
| Vercel | `deployment.ready` | Mark incident RESOLVED if PR was merged |
| Vercel | `deployment.canceled` | Update deployment status |
