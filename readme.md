<p align="center">
  <img src="https://raw.githubusercontent.com/Debjanimandal/PatchR/master/frontend/public/window.svg" alt="PatchR Logo" width="80" height="80" style="border-radius: 12px; background: #0f172a; padding: 12px;" />
</p>

<h1 align="center">PatchR</h1>
<p align="center"><strong>Autonomous Self-Healing Codebase &amp; Deployment Reliability Platform</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white" alt="Python 3.13" />
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?logo=supabase&logoColor=white" alt="Supabase" />
  <img src="https://img.shields.io/badge/AI-NVIDIA%20NIM%20(Llama--3.1--70B)-76B900?logo=nvidia&logoColor=white" alt="NVIDIA NIM" />
  <img src="https://img.shields.io/badge/GitHub-REST%20v3-181717?logo=github&logoColor=white" alt="GitHub" />
  <img src="https://img.shields.io/badge/Vercel-Deployment%20API-000000?logo=vercel&logoColor=white" alt="Vercel" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT" />
</p>

<p align="center">
  <a href="http://localhost:3000"><strong>Frontend App</strong></a> &nbsp;&middot;&nbsp;
  <a href="https://github.com/Debjanimandal/PatchR"><strong>GitHub Repository</strong></a> &nbsp;&middot;&nbsp;
  <a href="http://localhost:8000/docs"><strong>Interactive API Docs (Swagger)</strong></a> &nbsp;&middot;&nbsp;
  <a href="#7-architecture--end-to-end-data-flow"><strong>Architecture Diagram</strong></a>
</p>

---

> **PatchR** is an autonomous engineering reliability layer that continuously monitors GitHub repositories and Vercel deployments. When builds fail or runtime 500 errors spike, PatchR ingests error logs, fetches the affected codebase context, diagnoses the exact root cause using NVIDIA NIM (Llama 3.1 70B), runs static risk verification, generates a clean unified diff patch, and opens a GitHub Pull Request upon developer approval.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Solution &amp; Value Proposition](#3-solution--value-proposition)
4. [Tech Stack](#4-tech-stack)
5. [Current Features](#5-current-features)
6. [Incident Lifecycle &amp; Safety Pipeline](#6-incident-lifecycle--safety-pipeline)
7. [Architecture &amp; End-to-End Data Flow](#7-architecture--end-to-end-data-flow)
8. [Setup Instructions](#8-setup-instructions)
9. [Environment Variables](#9-environment-variables)
10. [API &amp; Webhook Reference](#10-api--webhook-reference)
11. [Deployment Poller &amp; Runtime Monitoring](#11-deployment-poller--runtime-monitoring)
12. [Proof of Functionality](#12-proof-of-functionality)
13. [Security, Governance &amp; Auditability](#13-security-governance--auditability)
14. [Roadmap &amp; Future Scope](#14-roadmap--future-scope)

---

## 1. Project Overview

Modern deployment pipelines frequently fail due to broken imports, missing environment configurations, type mismatches, or regression errors. Diagnosing these failures usually forces engineers to context-switch, sift through thousands of lines of terminal logs, cross-reference recent Git commits, inspect code locally, write a patch, test it, and manually open a PR.

**PatchR eliminates the manual triage cycle.** It acts as an always-on DevOps copilot and self-healing agent that:
1. **Detects** build, deployment, and runtime failures in real time via GitHub/Vercel webhooks and active deployment polling.
2. **Gathers context** by extracting broken file contents, commit diffs, and environment metadata directly via the GitHub Contents API.
3. **Diagnoses & generates fixes** using **NVIDIA NIM (`meta/llama-3.1-70b-instruct`)** with structured JSON output and low-temperature deterministic reasoning.
4. **Verifies safety** using static analysis and confidence scoring to prevent risky code regressions.
5. **Awaits human approval** through an interactive side-by-side diff viewer before touching production.
6. **Creates GitHub PRs & tracks recovery** automatically, closing the loop when subsequent deployments succeed.

---

## 2. Problem Statement

Engineering teams spend hundreds of hours every quarter debugging failed deployments and triaging runtime crashes:

- **High Mean Time to Resolution (MTTR):** Build logs on modern cloud platforms (Vercel, AWS, Cloudflare) are noisy and buried in build artifacts. Finding the single missing token or syntax failure takes valuable engineering time.
- **Context Loss:** When an alert fires, engineers must manually map the failing log stack trace back to the exact commit SHA and the changed source files.
- **Repeated Failure Patterns:** A large percentage of deployment errors are recurring classes of bugs (e.g., mismatched import paths, unhandled promise rejections, type mismatches, missing dependency versions).
- **Risk of Blind Automation:** Developers rightfully distrust fully autonomous "black box" bots that push unreviewed code directly to production branches.

---

## 3. Solution & Value Proposition

PatchR introduces a **Human-in-the-Loop Autonomous Remediation Architecture**:

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ 1. INGESTION    │ ──► │ 2. AI DIAGNOSIS  │ ──► │ 3. VERIFICATION  │ ──► │ 4. HUMAN GATE   │ ──► PR Created &
│ Webhook/Poller  │     │ NVIDIA NIM 70B   │     │ Static Risk Score│     │ Interactive Diff│     Auto-Monitored
└─────────────────┘     └──────────────────┘     └──────────────────┘     └─────────────────┘
```

- **Zero-Friction Ingress:** Works via GitHub Webhooks, Vercel deployment events, or on-demand active polling (no webhooks required for local development).
- **Deep Code Understanding:** Rather than feeding blind error snippets to an LLM, PatchR's **Context Engine** retrieves the exact broken files and repository tree before prompting.
- **Deterministic Fixes:** Utilizes NVIDIA NIM's optimized inference with schema-enforced JSON generation for reliable, syntactically valid patches.
- **Safety First:** Strict human consent gate with confidence scoring and risk analysis. No branch or pull request is modified without developer sign-off.
- **Full Operational Memory:** Every incident, analysis, verification score, human decision, and PR creation is immutably recorded in an audit trail.

---

## 4. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | **Next.js 16** (App Router), React 19, TypeScript | Server and client component composition, high performance Turbopack builds |
| **Styling & UI** | **Tailwind CSS**, Framer Motion, Lucide Icons, Recharts | Premium SaaS aesthetic, responsive layouts, data visualization |
| **Backend API** | **FastAPI**, Python 3.13, Pydantic v2 | High-throughput asynchronous REST API, OpenAPI/Swagger generation |
| **Database & ORM** | **PostgreSQL** (Supabase), Async SQLAlchemy, Alembic | Relational integrity, asyncpg driver, automated schema migrations |
| **AI Reasoning Layer** | **NVIDIA NIM** (`meta/llama-3.1-70b-instruct`) | OpenAI-compatible high-speed inference, deep code reasoning, structured JSON |
| **Git Orchestration** | **GitHub REST v3 API** (via `httpx`) | OAuth login, repository search, webhook management, branch & PR creation |
| **Deployment Engine** | **Vercel REST API** | Project auto-matching, runtime error log inspection, deployment status tracking |
| **Background Scheduler**| **APScheduler** (AsyncIOScheduler) | Background PR lifecycle tracking and deployment health polling |
| **Telemetry & Logs** | **Structlog** | Production structured JSON and colored development console logging |

---

## 5. Current Features

### 🔐 Authentication & Access Control
- **GitHub OAuth 2.0 Integration:** Secure sign-in flow with code exchange and scoped token issuance.
- **Stateless JWT Tokens:** Embedded GitHub profile and identity verification for protected API routes.
- **Graceful DB Fallback:** Resilient authentication fallback ensuring dashboard accessibility even during database DNS hiccups.

### 📦 Repository & Infrastructure Management
- **Repository Importer:** Lists repositories owned by the authenticated GitHub user.
- **Automated Webhook Registration:** Registers GitHub deployment and push webhooks programmatically with HMAC-SHA256 secrets.
- **Per-User Vercel Integration:** Secure personal Vercel access token storage in PostgreSQL.
- **Smart Project Auto-Sync (`vercel-sync`):** Automatically links GitHub repositories to their corresponding Vercel projects.
- **Manual Verification Linking:** Backend API verification confirming Vercel project existence before binding.

### 🚨 Multi-Vector Incident Detection
- **Webhook Ingress:** Ingests `push`, `deployment_status`, and Vercel deployment error events.
- **Active Deployment Poller:** Scans GitHub Deployments API for `failure` and `error` states without requiring public webhook URLs.
- **Vercel Runtime Error Monitor:** Scans production serverless function runtime logs for 500-level HTTP errors, automatically grouping duplicates by route.
- **Failure Simulator:** Built-in test harness (`/simulate-failure`) with realistic build, syntax, and runtime failure scenarios.

### 🧠 AI Diagnosis & Patch Synthesis
- **Context Engine:** Fetches real source code and modified files from GitHub before AI invocation.
- **NVIDIA NIM Integration:** Low-temperature (0.1) inference using Llama 3.1 70B for factual root-cause diagnosis.
- **Structured JSON Output:** Formats diagnosis into `root_cause`, `confidence_score`, `suggested_fix`, and `patch_diff`.
- **Multi-File Diff Engine:** Produces valid unified diffs across multiple files with line-level context.

### 🛡️ Safety, Verification & Human Gate
- **Static Verification Engine:** Computes risk scores based on file touch count, destructive changes, and confidence thresholds.
- **Interactive Diff Viewer:** Visual before-and-after comparison with color-coded additions and deletions.
- **One-Click Approval / Rejection:** Developer can approve the patch to open a PR or reject it with structured feedback.

### 🚀 Autonomous GitHub PR Lifecycle
- **Automated Branch Creation:** Generates isolated fix branches (e.g., `patchr/fix-incident-a3f9d12`).
- **Git Commit Engine:** Applies patched files via GitHub Contents API without cloning repos locally.
- **Draft PR Generator:** Creates draft Pull Requests with AI-generated markdown descriptions explaining the root cause and applied fix.
- **Lifecycle Poller:** Automatically detects when the PR is merged or closed, transitioning the incident to `RECOVERY_MONITORING` and `RESOLVED`.

---

## 6. Incident Lifecycle & Safety Pipeline

PatchR implements an **explicit 16-state finite state machine** to ensure complete transparency and safety:

```
                      ┌───────────────┐
                      │   DETECTED    │
                      └───────┬───────┘
                              │
                              ▼
                      ┌───────────────┐        ┌─────────────────┐
                      │   ANALYZING   │ ─────► │ ANALYSIS_FAILED │
                      └───────┬───────┘        └─────────────────┘
                              │
                              ▼
               ┌───────────────────────────────┐
               │     ROOT_CAUSE_IDENTIFIED     │
               └──────────────┬────────────────┘
                              │
                              ▼
               ┌───────────────────────────────┐
               │        REPAIR_PROPOSED        │
               └──────────────┬────────────────┘
                              │
                              ▼
                      ┌───────────────┐        ┌─────────────────────┐
                      │   VERIFYING   │ ─────► │ VERIFICATION_FAILED │
                      └───────┬───────┘        └─────────────────────┘
                              │
                              ▼
                      ┌───────────────┐
                      │   VERIFIED    │
                      └───────┬───────┘
                              │
                              ▼
                      ┌───────────────┐        ┌─────────────────┐
                      │AWAITING_REVIEW│ ─────► │    REJECTED     │
                      └───────┬───────┘        └─────────────────┘
                              │ (Developer Approves)
                              ▼
                      ┌───────────────┐
                      │  PR_CREATED   │
                      └───────┬───────┘
                              │ (PR Merged / Deployed)
                              ▼
               ┌───────────────────────────────┐
               │      RECOVERY_MONITORING      │
               └──────────────┬────────────────┘
                              │
                              ▼
                      ┌───────────────┐
                      │   RESOLVED    │
                      └───────────────┘
```

> **Safety Guarantee:** No code is ever merged or pushed directly to default branches. PatchR strictly creates isolated branches, submits draft Pull Requests, and requires human approval at the `AWAITING_REVIEW` gate.

---

## 7. Architecture & End-to-End Data Flow

### System Component Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PatchR Next.js 16 Frontend (App Router)              │
│                                                                        │
│  /login          GitHub OAuth & Token Handler                          │
│  /dashboard      Live Operational Metrics & Incidents Table            │
│  /repositories   Connected Repos, Vercel Project Linker & Webhooks     │
│  /incidents      Incident Filter, State Timeline & Multi-File Diff View│
│  /patches        AI-Generated Fixes, PR Status & Approval Triggers     │
│  /settings       Vercel API Token Manager & Webhook Configurations     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / Bearer JWT
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      PatchR FastAPI Backend Services                   │
│                                                                        │
│  ┌─────────────────────────┐    ┌───────────────────────────────────┐  │
│  │   Routers & Ingress     │    │        Core Services Engine       │  │
│  │  • /api/v1/auth         │    │  • incident_service (State FSM)   │  │
│  │  • /api/v1/repositories │    │  • context_service (GitHub Files) │  │
│  │  • /api/v1/incidents    │    │  • patch_service (Diff Synthesis) │  │
│  │  • /api/v1/patches      │    │  • verification_service (Safety)  │  │
│  │  • /api/v1/webhooks     │    │  • deployment_poller (Active Scan)│  │
│  │  • /api/v1/analysis     │    │  • pr_monitor_service (Lifecycle) │  │
│  └────────────┬────────────┘    └─────────────────┬─────────────────┘  │
└───────────────┼───────────────────────────────────┼────────────────────┘
                │                                   │
      ┌─────────┴─────────┐               ┌─────────┴─────────┐
      ▼                   ▼               ▼                   ▼
┌───────────────┐   ┌────────────┐  ┌────────────┐   ┌──────────────────┐
│  PostgreSQL   │   │ GitHub API │  │ Vercel API │   │ NVIDIA NIM API   │
│  (Supabase)   │   │            │  │            │   │ llama-3.1-70b    │
│               │   │ • OAuth    │  │ • Projects │   │                  │
│ • Users       │   │ • Contents │  │ • Build Log│   │ • Root Cause     │
│ • Repos       │   │ • Webhooks │  │ • Runtime  │   │ • Patch Gen      │
│ • Incidents   │   │ • Branches │  │   Logs     │   │ • JSON Schema    │
│ • Patches     │   │ • PRs      │  │ • Deploy   │   └──────────────────┘
│ • Audit Logs  │   └────────────┘  │   Events   │
└───────────────┘                   └────────────┘
```

### End-to-End Incident Resolution Sequence

```
Deployment Fails (Vercel) 
      │
      ▼
PatchR Ingestion (Webhook / Poller) ──► Incident Created [DETECTED]
      │
      ▼
Context Engine ────────────────────────► Fetches Broken Files via GitHub API
      │
      ▼
NVIDIA NIM (Llama 3.1 70B) ────────────► Analyzes Logs + Code Context [ANALYZING]
      │
      ▼
Static Risk Scoring Engine ────────────► Computes Safety Score & Diffs [VERIFIED]
      │
      ▼
Dashboard Diff Viewer ─────────────────► Developer Reviews Diff [AWAITING_REVIEW]
      │
      ├─► [REJECT] ──► Incident Marked Rejected with Notes
      │
      └─► [APPROVE]
              │
              ▼
GitHub Orchestrator ───────────────────► Creates Branch + Commits Patch + Opens Draft PR [PR_CREATED]
              │
              ▼
Recovery Monitor (APScheduler) ────────► Monitors Vercel Build on Merged PR ──► [RESOLVED] ✅
```

---

## 8. Setup Instructions

### Prerequisites
- **Python 3.11+** (Python 3.13 recommended)
- **Node.js 18+** & `npm`
- **PostgreSQL Database** (e.g. Free tier [Supabase](https://supabase.com))
- **NVIDIA NIM API Key** (from [build.nvidia.com](https://build.nvidia.com))
- **GitHub Personal Access Token** (`repo`, `admin:repo_hook`, `workflow`) & **GitHub OAuth App**
- *(Optional)* **Vercel Access Token** (for deployment build and runtime log access)

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/Debjanimandal/PatchR.git
cd PatchR
```

### Step 2: Install All Dependencies
Using the root Makefile:
```bash
make install
```
*Or manually:*
```bash
# Backend dependencies
cd backend && pip install -e . && cd ..

# Frontend dependencies
cd frontend && npm install && cd ..
```

---

### Step 3: Configure Environment Variables

#### 1. Backend Configuration (`backend/.env`)
```bash
cd backend
cp .env.example .env   # or create backend/.env
```
Fill in the parameters:
```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:5432/postgres
JWT_SECRET=your-32-character-random-jwt-secret
OWNER_PASSWORD=adminpassword123

# NVIDIA NIM AI
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=meta/llama-3.1-70b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# GitHub Integration
GITHUB_TOKEN=ghp_your_github_personal_access_token
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# Vercel Integration
VERCEL_ACCESS_TOKEN=vcp_your_vercel_access_token
VERCEL_WEBHOOK_SECRET=your_vercel_webhook_secret_here

# URLs
FRONTEND_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
```

#### 2. Frontend Configuration (`frontend/.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_MODE=false
```

---

### Step 4: Run Database Migrations
```bash
make db
# Or: cd backend && alembic upgrade head
```

---

### Step 5: Start Development Servers
Run both backend and frontend concurrently:
```bash
make dev
```

Or start each service in separate terminals:

```bash
# Terminal 1 — Backend (FastAPI)
make api
# Running at http://localhost:8000 (Swagger docs at /docs)

# Terminal 2 — Frontend (Next.js)
make web
# Running at http://localhost:3000
```

---

## 9. Environment Variables

### Backend Variables (`backend/.env`)

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://...` | Supabase / PostgreSQL async connection string |
| `JWT_SECRET` | ✅ | Random 32+ hex string | Signs and verifies user authentication tokens |
| `OWNER_PASSWORD` | ✅ | `admin123` | Master password fallback for dashboard access |
| `NVIDIA_API_KEY` | ✅ | `nvapi-...` | Access key for NVIDIA NIM Llama 3.1 70B inference |
| `NVIDIA_MODEL` | ✅ | `meta/llama-3.1-70b-instruct` | LLM model used for root-cause diagnosis and patch synthesis |
| `GITHUB_TOKEN` | ✅ | `ghp_...` | GitHub PAT for branch creation, file reads, and PR generation |
| `GITHUB_CLIENT_ID` | ✅ | `Ov23li...` | GitHub OAuth App Client ID for developer login |
| `GITHUB_CLIENT_SECRET` | ✅ | `sec_...` | GitHub OAuth App Client Secret |
| `GITHUB_WEBHOOK_SECRET` | ✅ | Random string | HMAC-SHA256 signature verification for GitHub hooks |
| `VERCEL_ACCESS_TOKEN` | ⚠️ | `vcp_...` | Global fallback token for Vercel project inspection & logs |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | Allowed CORS origin for frontend client requests |

### Frontend Variables (`frontend/.env.local`)

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Target FastAPI backend URL for API client requests |
| `NEXT_PUBLIC_DEMO_MODE` | `false` | When `true`, enables mock telemetry and simulated data |

---

## 10. API & Webhook Reference

### Core API Endpoints

| Category | Method | Endpoint | Description |
|---|---|---|---|
| **Auth** | `GET` | `/api/v1/auth/github` | Initiates GitHub OAuth login redirect |
| **Auth** | `GET` | `/api/v1/auth/github/callback` | Exchanges OAuth code, issues user JWT |
| **Auth** | `GET` | `/api/v1/auth/me` | Fetches current user profile and integration state |
| **Auth** | `GET/PUT`| `/api/v1/auth/vercel-token` | Inspects or saves user's personal Vercel API token |
| **Repos** | `GET` | `/api/v1/repositories/github-repos` | Lists user's accessible GitHub repositories |
| **Repos** | `GET` | `/api/v1/repositories/vercel-projects`| Lists connected Vercel projects |
| **Repos** | `POST` | `/api/v1/repositories/vercel-sync` | Auto-matches GitHub repos to Vercel projects |
| **Repos** | `POST` | `/api/v1/repositories/` | Connects a repository to PatchR |
| **Repos** | `POST` | `/api/v1/repositories/{id}/scan-deployments` | Triggers active scan for failed deployments |
| **Incidents** | `GET` | `/api/v1/incidents/` | Lists incidents with status/severity filters |
| **Incidents** | `GET` | `/api/v1/incidents/{id}` | Fetches full incident details, timeline, and logs |
| **Incidents** | `POST` | `/api/v1/incidents/simulate-failure` | Simulates realistic deployment failure scenarios |
| **Incidents** | `POST` | `/api/v1/incidents/{id}/reanalyze` | Manually re-triggers AI analysis pipeline |
| **Patches** | `GET` | `/api/v1/patches/{id}` | Fetches AI patch diff and affected file list |
| **Patches** | `POST` | `/api/v1/patches/{id}/approve` | **Approves patch and opens GitHub Draft PR** |
| **Patches** | `POST` | `/api/v1/patches/{id}/reject` | Rejects proposed patch with reason |
| **Webhooks** | `POST` | `/api/v1/webhooks/github` | Ingests GitHub `push` and `deployment_status` |
| **Webhooks** | `POST` | `/api/v1/webhooks/vercel` | Ingests Vercel `deployment.error` events |

### Webhook Event Processing Map

| Provider | Event Header | Payload Trigger | PatchR Autonomous Action |
|---|---|---|---|
| **GitHub** | `X-GitHub-Event: deployment_status` | `state: failure` / `error` | Creates Incident (`DETECTED`), fetches logs & triggers AI analysis |
| **GitHub** | `X-GitHub-Event: deployment_status` | `state: success` | Checks if repo had incident in `RECOVERY_MONITORING` → resolves incident |
| **GitHub** | `X-GitHub-Event: push` | Commit pushed to branch | Records commit metadata, tracks file diff context |
| **Vercel** | `deployment.error` | Deployment build fails | Creates Incident, fetches Vercel build logs, runs diagnosis |
| **Vercel** | `deployment.ready` | Deployment successfully finishes | Confirms PR fix resolved deployment → transitions to `RESOLVED` |

---

## 11. Deployment Poller & Runtime Monitoring

For developers running in local development or behind firewalls without public ngrok webhook tunnels, PatchR provides an **Active Polling & Runtime Monitoring Engine** (`patchr.services.deployment_poller`):

### 1. GitHub Deployments Active Poller
- Scans connected repositories via `GET /repos/{owner}/{repo}/deployments` and `/statuses`.
- Filters for `state == "failure"` or `"error"`.
- Deduplicates automatically against existing open incidents in PostgreSQL.
- Pulls commit metadata and triggers the NVIDIA NIM AI diagnosis pipeline automatically.

### 2. Vercel Serverless Runtime Log Scanner
- Connects to the Vercel Logs API using the user's personal Vercel access token.
- Analyzes recent execution logs (last 30 minutes) for HTTP `500` / `502` / `504` status codes.
- Groups identical error paths together to prevent incident spam.
- Extracts stack traces, error messages, and host context to trigger autonomous AI root-cause analysis.

---

## 12. Proof of Functionality

The following end-to-end capabilities have been built, integrated, and verified across the PatchR platform:

| # | Workflow / Flow | Verification Method | Status |
|---|---|---|---|
| 1 | **GitHub OAuth Login** | Real OAuth flow redirects to GitHub, exchanges authorization code, issues JWT, and loads user profile | ✅ Verified |
| 2 | **Repository Import** | Fetches user's repositories via GitHub API, stores in PostgreSQL with branch tracking | ✅ Verified |
| 3 | **Automated Webhook Registration** | Automatically calls GitHub Webhook API to bind deployment events with HMAC secret | ✅ Verified |
| 4 | **Per-User Vercel Token & Sync** | Securely stores user token in DB and queries Vercel API to auto-match projects | ✅ Verified |
| 5 | **Active Failure Detection** | Detects broken deployments via Deployments API and creates structured incidents | ✅ Verified |
| 6 | **Context Retrieval Engine** | Fetches exact broken file contents and dependencies from GitHub before prompting LLM | ✅ Verified |
| 7 | **NVIDIA NIM AI Diagnosis** | Analyzes error logs + code with Llama 3.1 70B, outputting structured root-cause explanations | ✅ Verified |
| 8 | **Unified Diff Patch Generation** | AI synthesizes syntactically valid multi-file diff patches | ✅ Verified |
| 9 | **Static Safety Verification** | Computes safety risk score and checks for destructive changes | ✅ Verified |
| 10 | **Interactive Diff Review** | Frontend renders visual diff with side-by-side modifications | ✅ Verified |
| 11 | **Automated PR Creation** | Approving patch creates a Git branch, applies commits via GitHub API, and opens a draft PR | ✅ Verified |
| 12 | **PR Lifecycle Recovery Poller** | APScheduler monitors PR merge state and auto-resolves incident upon successful deployment | ✅ Verified |
| 13 | **Immutable Audit Trail** | Every state transition, user approval, and AI action is logged with timestamps and actor metadata | ✅ Verified |

---

## 13. Security, Governance & Auditability

PatchR is engineered with strict enterprise security and safety primitives:

- **Human-in-the-Loop Gate:** PatchR never commits directly to main branches or pushes unreviewed code to production. All automated patches are staged in draft Pull Requests and require explicit developer consent.
- **Cryptographic Webhook Verification:** Inbound GitHub and Vercel webhooks are validated using HMAC-SHA256 signatures before processing.
- **Isolated Token Storage:** Vercel access tokens are stored on a per-user basis in PostgreSQL, eliminating shared credential security risks.
- **Immutable Audit Logging:** Every incident event, AI generation, verification score, approval, and rejection is recorded in the `audit_logs` table for compliance and post-mortem review.
- **Least-Privilege GitHub Scope:** Interacts through standard GitHub REST API scopes with clear repository-level boundaries.

---

## 14. Roadmap & Future Scope

- [ ] **Multi-Agent Collaborative Debugging:** Specialized sub-agents for dependency conflicts, database migrations, and TypeScript type errors.
- [ ] **Sentry & Datadog Signal Correlation:** Correlate runtime APM traces and error exceptions with deployment failure events.
- [ ] **Automated Rollback Engine:** Recommend one-click deployment rollbacks when high-risk patches require extensive manual refactoring.
- [ ] **Multi-Service Architecture Dependency Graphs:** Understand microservice call graphs to detect cascading deployment failures across services.
- [ ] **Slack & Discord Alert Integrations:** Interactive incident alerts with one-click approve/reject actions directly from chat.

---

<p align="center">
  <sub>Built with ❤️ for resilient, self-healing software deployments.</sub>
</p>
