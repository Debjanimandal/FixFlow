/**
 * Design Tokens for FixFlow
 *
 * Single source of truth for all design values.
 * Matches design.md exactly: light, premium SaaS aesthetic.
 */

export const tokens = {
  // ─── Color ────────────────────────────────────────────────
  color: {
    background: "#F7F7FA",
    surface: "#FFFFFF",
    surface2: "#F9FAFB",
    surface3: "#F3F4F6",
    border: "#E2E8F0",
    borderSubtle: "#F1F5F9",

    textPrimary: "#0F172A",
    textSecondary: "#475569",
    textMuted: "#64748B",
    textDim: "#94A3B8",

    // Accent
    accent: "#5A67D8",

    // Severity
    severityCritical: "#EF4444",
    severityHigh: "#F59E0B",
    severityMedium: "#EAB308",
    severityLow: "#64748B",
  },

  // ─── Typography ───────────────────────────────────────────
  font: {
    sans: "var(--font-sans)",
    mono: "var(--font-mono)",
  },

  // ─── Spacing ──────────────────────────────────────────────
  spacing: {
    section: "64px",
    card: "24px",
  },

  // ─── Border Radius ────────────────────────────────────────
  radius: {
    sm: "6px",
    md: "8px",
    lg: "12px",
    xl: "16px",
  },
} as const;

// ─── Status label helpers ──────────────────────────────────────────────────────

export const STATUS_LABELS: Record<string, string> = {
  // Detection
  detected: "DETECTED",
  // Analysis
  analyzing: "ANALYZING",
  root_cause_identified: "ROOT CAUSE",
  analysis_failed: "ANALYSIS FAILED",
  // Repair
  repair_proposed: "REPAIR PROPOSED",
  verifying: "VERIFYING",
  verified: "VERIFIED",
  verification_failed: "VERIFY FAILED",
  // Review
  needs_review: "NEEDS REVIEW",
  awaiting_review: "AWAITING REVIEW",
  rejected: "REJECTED",
  // Recovery
  pr_created: "PR CREATED",
  recovery_monitoring: "MONITORING",
  resolved: "RESOLVED",
  // Terminal
  dismissed: "DISMISSED",
  reopened: "REOPENED",
};

export const SEVERITY_LABELS: Record<string, string> = {
  critical: "CRITICAL",
  high: "HIGH",
  medium: "MEDIUM",
  low: "LOW",
};

export const FAILURE_TYPE_LABELS: Record<string, string> = {
  build_error: "Build Error",
  import_error: "Import Error",
  type_error: "Type Error",
  syntax_error: "Syntax Error",
  env_variable: "Environment Variable",
  dependency_conflict: "Dependency Conflict",
  framework_error: "Framework Error",
  runtime_error: "Runtime Error",
  unknown: "Unknown",
};

export const PATCH_STATUS_LABELS: Record<string, string> = {
  proposed: "PROPOSED",
  verifying: "VERIFYING",
  verified: "VERIFIED",
  rejected: "REJECTED",
  applied: "APPLIED",
  pr_created: "PR CREATED",
};
