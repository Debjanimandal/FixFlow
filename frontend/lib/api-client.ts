/**
 * FixFlow API Client
 *
 * Type-safe HTTP client for the FastAPI backend.
 * All requests include the Bearer token from localStorage.
 * Never puts the token in URLs or logs.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const githubLoginUrl = `${API_BASE}/api/v1/auth/github`;
// NOTE: there is no plain "Vercel OAuth URL" constant — linking a Vercel
// account requires a short-lived link_token minted via an authenticated
// request first. Use `auth.startVercelOAuth()` instead of building this URL
// directly.
const DEMO_TOKEN_VALUE = "demo-token-patchr-local";

function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("patchr_token") === DEMO_TOKEN_VALUE;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Repository {
  id: string;
  name: string;
  full_name: string;
  github_id: number;
  default_branch: string;
  private: boolean;
  vercel_project_id: string | null;
  vercel_project_name: string | null;
  github_webhook_id: number | null;
  webhook_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IncidentListItem {
  id: string;
  title: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  source: string;
  failure_type: FailureType;
  summary: string | null;
  commit_sha: string | null;
  repository_full_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends IncidentListItem {
  repository_id: string;
  deployment_id: string | null;
  commit_message: string | null;
  resolved_at: string | null;
  time_to_resolve_seconds: number | null;
}

export interface Analysis {
  id: string;
  incident_id: string;
  model_provider: string;
  model_name: string;
  failure_type: string | null;
  root_cause: string | null;
  affected_files: string[] | null;
  evidence: string[] | null;
  confidence: number | null;
  risk_level: string | null;
  verification_plan: string[] | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  created_at: string;
}

export interface FileChange {
  path: string;
  original_content: string | null;
  patched_content: string | null;
  change_type: string;
  explanation: string;
}

export interface Patch {
  id: string;
  incident_id: string;
  analysis_id: string | null;
  model_provider: string;
  model_name: string;
  description: string | null;
  diff: string | null;
  file_changes: FileChange[] | null;
  confidence: number | null;
  risk_level: string | null;
  status: PatchStatus;
  github_pr_number: number | null;
  github_pr_url: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  incident_id: string | null;
  action: string;
  actor: string;
  details: Record<string, unknown> | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

// ─── Enums ────────────────────────────────────────────────────────────────────

export type IncidentStatus =
  | "detected"
  | "analyzing"
  | "patch_ready"
  | "verified"
  | "needs_review"
  | "resolved"
  | "dismissed";

export type IncidentSeverity = "critical" | "high" | "medium" | "low";

export type FailureType =
  | "build_error"
  | "import_error"
  | "type_error"
  | "syntax_error"
  | "env_variable"
  | "dependency_conflict"
  | "framework_error"
  | "runtime_error"
  | "unknown";

export type PatchStatus =
  | "proposed"
  | "verifying"
  | "verified"
  | "rejected"
  | "applied"
  | "pr_created";

// ─── Client ───────────────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(`API Error ${status}: ${detail}`);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("patchr_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  // ── Demo mode: return mock data without hitting network ───────────────────
  if (isDemoMode()) {
    return demoRequest<T>(path, options);
  }

  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    // ── 401: stale or invalid token — clear it and redirect to login ────────
    if (res.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("patchr_token");
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired. Redirecting to login…");
    }

    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Demo request router ────────────────────────────────────────────────────
async function demoRequest<T>(path: string, _options: RequestInit): Promise<T> {
  // Lazy import to avoid bundling demo data in production
  const demo = await import("./demo-data");
  await new Promise((r) => setTimeout(r, 120)); // simulate network latency

  // Incidents list
  if (path === "/api/v1/incidents" || path.startsWith("/api/v1/incidents?")) {
    return demo.MOCK_INCIDENTS as T;
  }
  // Incident detail
  const incDetailMatch = path.match(/^\/api\/v1\/incidents\/([\w-]+)$/);
  if (incDetailMatch && !path.includes("/analyse") && !path.includes("/simulate")) {
    const id = incDetailMatch[1];
    return (demo.MOCK_INCIDENT_DETAILS[id] ?? demo.MOCK_INCIDENTS.find(i => i.id === id)) as T;
  }
  // Analyses
  const analysesMatch = path.match(/^\/api\/v1\/incidents\/([\w-]+)\/analyses$/);
  if (analysesMatch) {
    return (demo.MOCK_ANALYSES[analysesMatch[1]] ?? []) as T;
  }
  // Patches list
  const patchesMatch = path.match(/^\/api\/v1\/incidents\/([\w-]+)\/patches$/);
  if (patchesMatch) {
    return (demo.MOCK_PATCHES[patchesMatch[1]] ?? []) as T;
  }
  // Audit logs
  const auditMatch = path.match(/^\/api\/v1\/incidents\/([\w-]+)\/audit$/);
  if (auditMatch) {
    return (demo.MOCK_AUDIT_LOGS[auditMatch[1]] ?? []) as T;
  }
  // Repositories
  if (path === "/api/v1/repositories") {
    return demo.MOCK_REPOS as T;
  }
  // Simulate / Analyze — return a canned response
  if (path.includes("/simulate-failure") || path.includes("/analyze") || path.includes("/generate")) {
    return { status: "queued", message: "Demo mode: action simulated", incident_id: "inc-001", patch_id: "ptc-001", confidence: 0.95 } as T;
  }
  // Auth
  if (path.includes("/auth/me")) {
    return { username: "owner", role: "owner" } as T;
  }
  if (path.includes("/auth/vercel-token")) {
    return { has_token: true, token_preview: "demo_vc…" } as T;
  }
  if (path.includes("/auth/vercel/status")) {
    return { connected: true, message: "Vercel account connected (demo mode)" } as T;
  }
  if (path.includes("/auth/vercel/start")) {
    return { link_token: "demo", redirect_url: "#" } as T;
  }

  return [] as T;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  async login(password: string): Promise<TokenResponse> {
    const result = await request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    localStorage.setItem("patchr_token", result.access_token);
    return result;
  },

  logout(): void {
    localStorage.removeItem("patchr_token");
  },

  isAuthenticated(): boolean {
    return !!getToken();
  },

  getVercelTokenStatus(): Promise<{ has_token: boolean; token_preview?: string }> {
    return request("/api/v1/auth/vercel-token");
  },

  saveVercelToken(token: string): Promise<{ success: boolean; has_token: boolean; message: string }> {
    return request("/api/v1/auth/vercel-token", {
      method: "PUT",
      body: JSON.stringify({ token }),
    });
  },

  getVercelConnectionStatus(): Promise<{ connected: boolean; message: string }> {
    return request("/api/v1/auth/vercel/status");
  },

  /**
   * Start the Vercel OAuth linking flow.
   *
   * A plain `<a href>`/`window.location.href` navigation can't carry the
   * Authorization: Bearer header, so we first make an authenticated fetch()
   * call to mint a short-lived link_token, then navigate the browser to the
   * returned redirect_url (which embeds that token as a query param).
   */
  async startVercelOAuth(): Promise<void> {
    const result = await request<{ link_token: string; redirect_url: string }>(
      "/api/v1/auth/vercel/start",
      { method: "POST" }
    );
    window.location.href = result.redirect_url;
  },
};

// ─── Repositories ─────────────────────────────────────────────────────────────

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  description: string;
  default_branch: string;
  updated_at: string;
  html_url: string;
  language: string;
}

export interface VercelProject {
  id: string;
  name: string;
  framework: string | null;
  linked_repo: string | null; // e.g. "AnkitBhattacherjee/my-app"
}

export interface VercelSyncResult {
  linked: number;
  already_linked: number;
  unmatched_vercel_projects: string[];
  message: string;
}

export interface DeploymentStatusItem {
  id: string;
  state: string; // READY, ERROR, BUILDING, QUEUED, CANCELED
  url: string | null;
  branch: string | null;
  commit_sha: string | null;
  commit_message: string | null;
  created_at: number; // unix ms
  error_message: string | null;
}

export interface DeploymentStatusResponse {
  linked: boolean;
  source?: string; // "vercel_api" | "github_api" | "none" | "error"
  latest_state: string | null;
  vercel_project_name: string | null;
  deployments: DeploymentStatusItem[];
}

export interface BuildLogEntry {
  text: string;
  type: string; // stdout, stderr, command, event
  is_error: boolean;
  created_at: number;
}

export interface DeploymentLogsResponse {
  deployment_id: string;
  log_count: number;
  logs: BuildLogEntry[];
}

export const repositories = {
  list(): Promise<Repository[]> {
    return request<Repository[]>("/api/v1/repositories");
  },
  get(id: string): Promise<Repository> {
    return request<Repository>(`/api/v1/repositories/${id}`);
  },
  create(data: { full_name: string; vercel_project_id?: string }): Promise<Repository> {
    return request<Repository>("/api/v1/repositories", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  delete(id: string): Promise<void> {
    return request<void>(`/api/v1/repositories/${id}`, { method: "DELETE" });
  },
  update(id: string, body: Partial<{ vercel_project_id: string; vercel_project_name: string; is_active: boolean }>): Promise<Repository> {
    return request<Repository>(`/api/v1/repositories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  listGitHubRepos(q = ""): Promise<GitHubRepo[]> {
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    return request<GitHubRepo[]>(`/api/v1/repositories/github-repos${qs}`);
  },
  listVercelProjects(): Promise<VercelProject[]> {
    return request<VercelProject[]>("/api/v1/repositories/vercel-projects");
  },
  vercelSync(): Promise<VercelSyncResult> {
    return request<VercelSyncResult>("/api/v1/repositories/vercel-sync", { method: "POST" });
  },
  linkVercel(repoId: string, vercelProjectId: string): Promise<Repository> {
    return request<Repository>(`/api/v1/repositories/${repoId}/link-vercel`, {
      method: "POST",
      body: JSON.stringify({ vercel_project_id: vercelProjectId, register_webhook: false }),
    });
  },
  unlinkVercel(repoId: string): Promise<Repository> {
    return request<Repository>(`/api/v1/repositories/${repoId}`, {
      method: "PATCH",
      body: JSON.stringify({ vercel_project_id: null, vercel_project_name: null }),
    });
  },
  getDeploymentStatus(repoId: string): Promise<DeploymentStatusResponse> {
    return request<DeploymentStatusResponse>(`/api/v1/repositories/${repoId}/deployment-status`);
  },
  getDeploymentLogs(repoId: string, deploymentId: string): Promise<DeploymentLogsResponse> {
    return request<DeploymentLogsResponse>(`/api/v1/repositories/${repoId}/deployment-logs/${deploymentId}`);
  },
  scanDeployments(repoId: string): Promise<{ scanned: boolean; incidents_created: number; message: string; incidents: Array<{ incident_id: string; title: string; commit_sha: string; status: string }> }> {
    return request(`/api/v1/repositories/${repoId}/scan-deployments`, { method: "POST" });
  },
  scanRuntime(repoId: string, sinceMinutes = 30): Promise<{ scanned: boolean; incidents_created: number; message: string; incidents: Array<{ incident_id: string; title: string; path: string; error_count: number; status: string }> }> {
    return request(`/api/v1/repositories/${repoId}/scan-runtime?since_minutes=${sinceMinutes}`, { method: "POST" });
  },
  simulateRuntime(repoId: string, payload?: { message?: string; path?: string; status_code?: number }): Promise<{ success: boolean; incident_id: string; title: string; message: string }> {
    return request(`/api/v1/repositories/${repoId}/simulate-runtime-error`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },
  scanAll(): Promise<{ repos_scanned: number; incidents_created: number; incidents: Array<{ incident_id: string; title: string; commit_sha: string; status: string }> }> {
    return request("/api/v1/repositories/scan-all", { method: "POST" });
  },
};

// ─── Incidents ────────────────────────────────────────────────────────────────

export const incidents = {
  list(params?: {
    status_filter?: IncidentStatus;
    limit?: number;
    offset?: number;
  }): Promise<IncidentListItem[]> {
    const qs = new URLSearchParams();
    if (params?.status_filter) qs.set("status_filter", params.status_filter);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return request<IncidentListItem[]>(`/api/v1/incidents${query}`);
  },
  get(id: string): Promise<IncidentDetail> {
    return request<IncidentDetail>(`/api/v1/incidents/${id}`);
  },
  update(id: string, data: { status?: string }): Promise<IncidentDetail> {
    return request<IncidentDetail>(`/api/v1/incidents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  listAnalyses(id: string): Promise<Analysis[]> {
    return request<Analysis[]>(`/api/v1/incidents/${id}/analyses`);
  },
  listPatches(id: string): Promise<Patch[]> {
    return request<Patch[]>(`/api/v1/incidents/${id}/patches`);
  },
  listAuditLogs(id: string): Promise<AuditLog[]> {
    return request<AuditLog[]>(`/api/v1/incidents/${id}/audit`);
  },
};

// ─── Patches ──────────────────────────────────────────────────────────────────

export const patches = {
  get(id: string): Promise<Patch> {
    return request<Patch>(`/api/v1/patches/${id}`);
  },
  generate(incidentId: string): Promise<{ patch_id: string; status: string; confidence: number }> {
    return request(`/api/v1/patches/generate/${incidentId}`, { method: "POST" });
  },
  approve(id: string, createPr = true): Promise<Patch> {
    return request<Patch>(`/api/v1/patches/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ create_pr: createPr }),
    });
  },
  reject(id: string, reason?: string): Promise<Patch> {
    return request<Patch>(`/api/v1/patches/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },
};

// ─── Analysis ─────────────────────────────────────────────────────────────────

export interface AnalyzeTriggerResponse {
  status: string;
  message: string;
  incident_id: string;
}

export interface SimulateFailureResponse {
  status: string;
  incident_id: string;
  message: string;
}

export const analysis = {
  trigger(
    incidentId: string,
    opts: { build_logs?: string; commit_diff?: string } = {}
  ): Promise<AnalyzeTriggerResponse> {
    return request<AnalyzeTriggerResponse>(`/api/v1/incidents/${incidentId}/reanalyze`, {
      method: "POST",
      body: JSON.stringify(opts),
    });
  },

  simulate(data: {
    repository_full_name: string;
    commit_sha?: string;
    commit_message?: string;
    error_description: string;
    build_logs?: string;
    environment?: string;
  }): Promise<SimulateFailureResponse> {
    return request<SimulateFailureResponse>("/api/v1/incidents/simulate-failure", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

// ─── Patch Arena Types ────────────────────────────────────────────────────────

export interface VerificationStage {
  stage: string;
  status: string;
  passed: boolean | null;
  evidence_label: string | null;
  duration_seconds: number | null;
  exit_code: number | null;
  stdout_excerpt: string | null;
  stderr_excerpt: string | null;
}

export interface PatchCandidate {
  candidate_id: string;
  candidate_index: number;
  strategy: string;
  status: string;
  is_eligible: boolean | null;
  is_selected: boolean;
  confidence: number | null;
  risk_level: string | null;
  risk_score: number | null;
  reproduction_passed: boolean | null;
  build_passed: boolean | null;
  tests_passed: boolean | null;
  no_new_failures: boolean | null;
  discard_reason: string | null;
  changed_files_count: number | null;
  changed_lines_count: number | null;
  description: string | null;
  verification_stages: VerificationStage[];
}

export interface RepairProof {
  incident_id: string;
  candidate_id: string;
  candidate_index: number;
  strategy: string | null;
  is_verified: boolean;
  is_selected: boolean;
  status: string | null;
  observed_evidence: Array<{ label: string; item: string; source?: string }>;
  inferred_evidence: Array<{ label: string; item: string; confidence?: number }>;
  validated_evidence: Array<{
    label: string;
    stage: string;
    status: string;
    passed: boolean | null;
    reproduction_level: string;
    exit_code: number | null;
    duration_seconds: number | null;
    stdout_excerpt: string | null;
    stderr_excerpt: string | null;
    risk_score: number | null;
    risk_explanation: string | null;
  }>;
  validation_summary: {
    reproduction_passed: boolean | null;
    build_passed: boolean | null;
    tests_passed: boolean | null;
    no_new_failures: boolean | null;
    is_eligible: boolean | null;
  };
  risk: { level: string | null; score: number | null; discard_reason: string | null };
  uncertainty: string;
  human_approval: {
    required: boolean;
    approved_at: string | null;
    rejected_at: string | null;
    rejection_reason: string | null;
    note: string;
  };
  truthfulness_note: string;
}

export interface TimelineEvent {
  id: string;
  action: string;
  actor: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

// ─── Arena API ────────────────────────────────────────────────────────────────

export const arena = {
  getCandidates(incidentId: string): Promise<PatchCandidate[]> {
    return request<PatchCandidate[]>(`/api/v1/incidents/${incidentId}/candidates`);
  },
  getVerificationProof(incidentId: string, candidateId?: string): Promise<RepairProof> {
    const qs = candidateId ? `?candidate_id=${candidateId}` : "";
    return request<RepairProof>(`/api/v1/incidents/${incidentId}/verification${qs}`);
  },
  triggerArena(incidentId: string): Promise<{ incident_id: string; status: string; message: string }> {
    return request(`/api/v1/incidents/${incidentId}/arena`, { method: "POST" });
  },
  getTimeline(incidentId: string): Promise<TimelineEvent[]> {
    return request<TimelineEvent[]>(`/api/v1/incidents/${incidentId}/timeline`);
  },
  getEvidence(incidentId: string): Promise<Record<string, unknown>> {
    return request(`/api/v1/incidents/${incidentId}/evidence`);
  },
  requestManualReview(incidentId: string): Promise<{ incident_id: string; status: string }> {
    return request(`/api/v1/incidents/${incidentId}/manual-review`, { method: "POST" });
  },
};

// ─── Journey Types ────────────────────────────────────────────────────────────

export interface JourneyStep {
  name: string;
  method: string;
  path: string;
  expected_status: number;
  body?: Record<string, unknown>;
}

export interface Journey {
  id: string;
  repository_id: string | null;
  name: string;
  description: string | null;
  enabled: boolean;
  severity: string;
  steps: JourneyStep[];
  base_url: string | null;
  timeout_ms: number;
  failure_threshold: number;
  heartbeat_cron: string | null;
  current_status: string;
  consecutive_failures: number;
  last_run_at: string | null;
  last_incident_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface JourneyStepResult {
  name: string;
  method: string;
  path: string;
  expected_status?: number;
  actual_status?: number;
  passed: boolean;
  duration_ms: number;
  error?: string;
}

export interface JourneyRun {
  id: string;
  journey_id: string;
  incident_id: string | null;
  trigger: string;
  status: string;
  failing_step: string | null;
  failing_status_code: number | null;
  duration_ms: number | null;
  base_url: string | null;
  error: string | null;
  step_results?: JourneyStepResult[];
  started_at: string;
  completed_at: string | null;
}

// ─── Journeys API ─────────────────────────────────────────────────────────────

export const journeys = {
  list(repositoryId?: string): Promise<Journey[]> {
    const qs = repositoryId ? `?repository_id=${repositoryId}` : "";
    return request<Journey[]>(`/api/v1/journeys${qs}`);
  },
  get(id: string): Promise<Journey> {
    return request<Journey>(`/api/v1/journeys/${id}`);
  },
  create(data: Partial<Journey>): Promise<Journey> {
    return request<Journey>("/api/v1/journeys", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: Partial<Journey>): Promise<Journey> {
    return request<Journey>(`/api/v1/journeys/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
  delete(id: string): Promise<void> {
    return request<void>(`/api/v1/journeys/${id}`, { method: "DELETE" });
  },
  runNow(id: string): Promise<{ journey_id: string; status: string; message: string }> {
    return request(`/api/v1/journeys/${id}/run`, { method: "POST" });
  },
  listRuns(id: string, limit = 20): Promise<JourneyRun[]> {
    return request<JourneyRun[]>(`/api/v1/journeys/${id}/runs?limit=${limit}`);
  },
  getRun(journeyId: string, runId: string): Promise<JourneyRun> {
    return request<JourneyRun>(`/api/v1/journeys/${journeyId}/runs/${runId}`);
  },
};

export { ApiError };
