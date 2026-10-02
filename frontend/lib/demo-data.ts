/**
 * Demo Mode — Mock data and auth bypass
 *
 * When NEXT_PUBLIC_DEMO_MODE=true, the app works entirely in the browser
 * with no backend or database required. Great for UI development and demos.
 *
 * Demo login password: "demo"
 */

import {
  IncidentListItem,
  IncidentDetail,
  Analysis,
  Patch,
  AuditLog,
  Repository,
} from "./api-client";

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export const DEMO_PASSWORD = "demo";
export const DEMO_TOKEN = "demo-token-patchr-local";

// ─── Mock Repositories ────────────────────────────────────────────────────────

export const MOCK_REPOS: Repository[] = [
  {
    id: "repo-001",
    name: "my-saas-app",
    full_name: "acme-inc/my-saas-app",
    github_id: 12345678,
    default_branch: "main",
    private: false,
    vercel_project_id: "prj_abc123",
    vercel_project_name: "my-saas-app",
    webhook_active: true,
    created_at: "2024-01-15T10:00:00Z",
    updated_at: "2024-03-10T14:22:00Z",
  },
  {
    id: "repo-002",
    name: "landing-page",
    full_name: "acme-inc/landing-page",
    github_id: 87654321,
    default_branch: "main",
    private: false,
    vercel_project_id: null,
    vercel_project_name: null,
    webhook_active: false,
    created_at: "2024-02-01T09:00:00Z",
    updated_at: "2024-02-01T09:00:00Z",
  },
];


// ─── Mock Incidents ───────────────────────────────────────────────────────────

export const MOCK_INCIDENTS: IncidentListItem[] = [
  {
    id: "inc-001",
    title: "Module not found: Can't resolve '@/components/UserProfile'",
    status: "patch_ready",
    severity: "high",
    source: "github_deployment_status",
    failure_type: "import_error",
    summary: "Import path broken after directory restructure",
    commit_sha: "a3f8d2c1",
    repository_full_name: "acme-inc/my-saas-app",
    created_at: "2024-03-12T08:15:00Z",
    updated_at: "2024-03-12T08:22:00Z",
  },
  {
    id: "inc-002",
    title: "TS2339: Property 'user' does not exist on type 'Session'",
    status: "analyzing",
    severity: "medium",
    source: "github_deployment_status",
    failure_type: "type_error",
    summary: null,
    commit_sha: "b7e4a192",
    repository_full_name: "acme-inc/my-saas-app",
    created_at: "2024-03-12T10:30:00Z",
    updated_at: "2024-03-12T10:31:00Z",
  },
  {
    id: "inc-003",
    title: "ERESOLVE: peer dependency conflict — react@18 vs react@17",
    status: "needs_review",
    severity: "critical",
    source: "vercel_webhook",
    failure_type: "dependency_conflict",
    summary: "react-pdf requires react@17 but project uses react@18",
    commit_sha: "c1d5f830",
    repository_full_name: "acme-inc/my-saas-app",
    created_at: "2024-03-11T23:45:00Z",
    updated_at: "2024-03-11T23:50:00Z",
  },
  {
    id: "inc-004",
    title: "Environment variable NEXT_PUBLIC_STRIPE_KEY is not defined",
    status: "resolved",
    severity: "high",
    source: "vercel_webhook",
    failure_type: "env_variable",
    summary: "Missing env var in Vercel project settings",
    commit_sha: "d9a2b561",
    repository_full_name: "acme-inc/landing-page",
    created_at: "2024-03-10T15:20:00Z",
    updated_at: "2024-03-10T16:00:00Z",
  },
  {
    id: "inc-005",
    title: "SyntaxError: Unexpected token '<' in JSX expression",
    status: "detected",
    severity: "medium",
    source: "github_deployment_status",
    failure_type: "syntax_error",
    summary: null,
    commit_sha: "e4c7f023",
    repository_full_name: "acme-inc/my-saas-app",
    created_at: "2024-03-12T11:55:00Z",
    updated_at: "2024-03-12T11:55:00Z",
  },
];


// ─── Mock Incident Details ────────────────────────────────────────────────────

export const MOCK_INCIDENT_DETAILS: Record<string, IncidentDetail> = {
  "inc-001": {
    id: "inc-001",
    title: "Module not found: Can't resolve '@/components/UserProfile'",
    summary: "A recent refactor moved UserProfile.tsx to a nested directory, but the import path in 3 files was not updated. The build fails during webpack module resolution.",
    status: "patch_ready",
    severity: "high",
    source: "github_deployment_status",
    failure_type: "import_error",
    commit_sha: "a3f8d2c1e9b4d6f7c2a8e3b5d1f9c4a7",
    commit_message: "refactor: reorganize component directory structure",
    repository_full_name: "acme-inc/my-saas-app",
    deployment_id: "dep-001",
    repository_id: "repo-001",
    resolved_at: null,
    time_to_resolve_seconds: null,
    created_at: "2024-03-12T08:15:00Z",
    updated_at: "2024-03-12T08:22:00Z",
  },
  "inc-002": {
    id: "inc-002",
    title: "TS2339: Property 'user' does not exist on type 'Session'",
    summary: "The next-auth Session type was updated in v4.24 but the type augmentation in types/next-auth.d.ts was not updated to match the new interface shape.",
    status: "analyzing",
    severity: "medium",
    source: "github_deployment_status",
    failure_type: "type_error",
    commit_sha: "b7e4a192c3d8f1e5a9b2d7f4c6e1a8b3",
    commit_message: "chore: upgrade next-auth to 4.24.0",
    repository_full_name: "acme-inc/my-saas-app",
    deployment_id: null,
    repository_id: "repo-001",
    resolved_at: null,
    time_to_resolve_seconds: null,
    created_at: "2024-03-12T10:30:00Z",
    updated_at: "2024-03-12T10:31:00Z",
  },
  "inc-003": {
    id: "inc-003",
    title: "ERESOLVE: peer dependency conflict — react@18 vs react@17",
    summary: "A newly added package (react-pdf) requires react@17 as a peer dependency, conflicting with the project's react@18. npm cannot resolve the dependency tree.",
    status: "needs_review",
    severity: "critical",
    source: "vercel_webhook",
    failure_type: "dependency_conflict",
    commit_sha: "c1d5f83042e7a9b6c3d8f2e1a5b7d4f0",
    commit_message: "feat: add PDF export functionality",
    repository_full_name: "acme-inc/my-saas-app",
    deployment_id: "dep-003",
    repository_id: "repo-001",
    resolved_at: null,
    time_to_resolve_seconds: null,
    created_at: "2024-03-11T23:45:00Z",
    updated_at: "2024-03-11T23:50:00Z",
  },
};


// ─── Mock Analyses ────────────────────────────────────────────────────────────

export const MOCK_ANALYSES: Record<string, Analysis[]> = {
  "inc-001": [
    {
      id: "anl-001",
      incident_id: "inc-001",
      model_provider: "nvidia_nim",
      model_name: "meta/llama-3.1-70b-instruct",
      failure_type: "import_error",
      root_cause:
        "The file `src/components/UserProfile.tsx` was moved to `src/components/user/UserProfile.tsx` during the directory restructure, but 3 import statements still reference the old path `@/components/UserProfile`. Webpack fails during module resolution because the path no longer exists at the module registry level.",
      affected_files: [
        "src/pages/dashboard.tsx",
        "src/pages/settings.tsx",
        "src/components/Sidebar.tsx",
      ],
      evidence: [
        "Module not found: Can't resolve '@/components/UserProfile' at ./src/pages/dashboard.tsx:12",
        "Module not found: Can't resolve '@/components/UserProfile' at ./src/pages/settings.tsx:8",
        "Module not found: Can't resolve '@/components/UserProfile' at ./src/components/Sidebar.tsx:24",
        "git diff a3f8d2c shows: rename components/UserProfile.tsx → components/user/UserProfile.tsx",
      ],
      confidence: 0.96,
      risk_level: "low",
      verification_plan: [
        "Update import in src/pages/dashboard.tsx line 12",
        "Update import in src/pages/settings.tsx line 8",
        "Update import in src/components/Sidebar.tsx line 24",
        "Run `npx next build` locally to verify",
      ],
      prompt_tokens: 1842,
      completion_tokens: 384,
      created_at: "2024-03-12T08:18:00Z",
    },
  ],
  "inc-002": [],
  "inc-003": [
    {
      id: "anl-003",
      incident_id: "inc-003",
      model_provider: "nvidia_nim",
      model_name: "meta/llama-3.1-70b-instruct",
      failure_type: "dependency_conflict",
      root_cause:
        "react-pdf@3.1.14 declares `react: ^17.0.0` as a required peer dependency. The project uses react@18.2.0. npm's strict peer dependency resolution (default in npm 7+) refuses to install conflicting versions. The fix is to either use react-pdf@4.x (which supports React 18) or add an explicit override in package.json.",
      affected_files: ["package.json", "package-lock.json"],
      evidence: [
        "npm ERR! ERESOLVE unable to resolve dependency tree",
        "npm ERR! peer react@\"^17.0.0\" from react-pdf@3.1.14",
        "npm ERR! Conflicting peer dependency: react@17.0.2",
        "Found: react@18.2.0 in package.json",
      ],
      confidence: 0.91,
      risk_level: "medium",
      verification_plan: [
        "Upgrade react-pdf to ^4.0.0 which supports React 18",
        "Or add overrides: { 'react-pdf': { 'react': '^18' } } to package.json",
        "Run npm install and verify no peer dep warnings",
        "Test PDF export functionality in dev environment",
      ],
      prompt_tokens: 1265,
      completion_tokens: 298,
      created_at: "2024-03-11T23:48:00Z",
    },
  ],
};

// ─── Mock Patches ─────────────────────────────────────────────────────────────

export const MOCK_PATCHES: Record<string, Patch[]> = {
  "inc-001": [
    {
      id: "ptc-001",
      incident_id: "inc-001",
      analysis_id: "anl-001",
      model_provider: "nvidia_nim",
      model_name: "meta/llama-3.1-70b-instruct",
      description:
        "Update 3 import statements to use the new component path after directory restructure. Change `@/components/UserProfile` to `@/components/user/UserProfile` in dashboard.tsx, settings.tsx, and Sidebar.tsx.",
      diff: null,
      file_changes: [
        {
          path: "src/pages/dashboard.tsx",
          original_content: "import UserProfile from '@/components/UserProfile';",
          patched_content: "import UserProfile from '@/components/user/UserProfile';",
          change_type: "modify",
          explanation: "Update import path to new component location after directory restructure",
        },
        {
          path: "src/pages/settings.tsx",
          original_content: "import UserProfile from '@/components/UserProfile';",
          patched_content: "import UserProfile from '@/components/user/UserProfile';",
          change_type: "modify",
          explanation: "Update import path to new component location after directory restructure",
        },
        {
          path: "src/components/Sidebar.tsx",
          original_content: "import { UserProfile } from '@/components/UserProfile';",
          patched_content: "import { UserProfile } from '@/components/user/UserProfile';",
          change_type: "modify",
          explanation: "Update named import path to new component location",
        },
      ],
      confidence: 0.97,
      risk_level: "low",
      status: "proposed",
      github_pr_number: null,
      github_pr_url: null,
      approved_at: null,
      rejected_at: null,
      rejection_reason: null,
      created_at: "2024-03-12T08:22:00Z",
      updated_at: "2024-03-12T08:22:00Z",
    },
  ],
  "inc-002": [],
  "inc-003": [],
};

// ─── Mock Audit Logs ──────────────────────────────────────────────────────────

export const MOCK_AUDIT_LOGS: Record<string, AuditLog[]> = {
  "inc-001": [
    {
      id: "aud-001",
      incident_id: "inc-001",
      action: "incident_created",
      actor: "system:webhook",
      details: { source: "github_deployment_status", environment: "production" },
      entity_type: "incident",
      entity_id: "inc-001",
      created_at: "2024-03-12T08:15:00Z",
    },
    {
      id: "aud-002",
      incident_id: "inc-001",
      action: "analysis_started",
      actor: "system:ai",
      details: { model: "meta/llama-3.1-70b-instruct" },
      entity_type: "incident",
      entity_id: "inc-001",
      created_at: "2024-03-12T08:16:00Z",
    },
    {
      id: "aud-003",
      incident_id: "inc-001",
      action: "analysis_completed",
      actor: "system:ai",
      details: { confidence: 0.96, failure_type: "import_error" },
      entity_type: "analysis",
      entity_id: "anl-001",
      created_at: "2024-03-12T08:18:00Z",
    },
    {
      id: "aud-004",
      incident_id: "inc-001",
      action: "patch_generated",
      actor: "system:ai",
      details: { confidence: 0.97, risk_level: "low", files_changed: 3 },
      entity_type: "patch",
      entity_id: "ptc-001",
      created_at: "2024-03-12T08:22:00Z",
    },
  ],
  "inc-002": [
    {
      id: "aud-010",
      incident_id: "inc-002",
      action: "incident_created",
      actor: "system:webhook",
      details: { source: "github_deployment_status" },
      entity_type: "incident",
      entity_id: "inc-002",
      created_at: "2024-03-12T10:30:00Z",
    },
    {
      id: "aud-011",
      incident_id: "inc-002",
      action: "analysis_started",
      actor: "system:ai",
      details: { model: "meta/llama-3.1-70b-instruct" },
      entity_type: "incident",
      entity_id: "inc-002",
      created_at: "2024-03-12T10:31:00Z",
    },
  ],
  "inc-003": [
    {
      id: "aud-020",
      incident_id: "inc-003",
      action: "incident_created",
      actor: "system:webhook",
      details: { source: "vercel_webhook", environment: "production" },
      entity_type: "incident",
      entity_id: "inc-003",
      created_at: "2024-03-11T23:45:00Z",
    },
    {
      id: "aud-021",
      incident_id: "inc-003",
      action: "analysis_completed",
      actor: "system:ai",
      details: { confidence: 0.91, failure_type: "dependency_conflict" },
      entity_type: "analysis",
      entity_id: "anl-003",
      created_at: "2024-03-11T23:48:00Z",
    },
  ],
};
