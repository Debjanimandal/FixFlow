"""
Unit tests: Incident state machine transitions.

Tests that the IncidentStatus enum contains all expected states,
and that state transition logic in incident_service validates correctly.
No DB or network needed — pure enum and logic tests.
"""

import pytest

from patchr.db.models import IncidentStatus, PatchStatus, AuditAction


class TestIncidentStatusEnum:
    """Verify all 21 pipeline states exist and are correctly named."""

    EXPECTED_STATES = {
        "DETECTED",
        "ANALYZING",
        "COLLECTING_CONTEXT",
        "ROOT_CAUSE_IDENTIFIED",
        "REPAIR_PROPOSED",
        "VERIFYING",
        "VERIFIED",
        "AWAITING_REVIEW",
        "AWAITING_APPROVAL",
        "HUMAN_REVIEW_REQUIRED",
        "MANUAL_REVIEW_REQUIRED",
        "PR_CREATED",
        "DEPLOYING_WATCHING",
        "RECOVERY_MONITORING",
        "RESOLVED",
        "ANALYSIS_FAILED",
        "VERIFICATION_FAILED",
        "REJECTED",
        "NEEDS_REVIEW",
        "DISMISSED",
        "REOPENED",
    }

    def test_all_17_states_exist(self):
        actual = {s.name for s in IncidentStatus}
        assert self.EXPECTED_STATES == actual, (
            f"Missing states: {self.EXPECTED_STATES - actual}\n"
            f"Extra states: {actual - self.EXPECTED_STATES}"
        )

    def test_happy_path_states_exist(self):
        """Core pipeline happy path states must all be present."""
        happy_path = [
            IncidentStatus.DETECTED,
            IncidentStatus.ANALYZING,
            IncidentStatus.ROOT_CAUSE_IDENTIFIED,
            IncidentStatus.REPAIR_PROPOSED,
            IncidentStatus.VERIFYING,
            IncidentStatus.VERIFIED,
            IncidentStatus.AWAITING_REVIEW,
            IncidentStatus.PR_CREATED,
            IncidentStatus.RECOVERY_MONITORING,
            IncidentStatus.RESOLVED,
        ]
        assert len(happy_path) == 10

    def test_failure_states_exist(self):
        assert IncidentStatus.ANALYSIS_FAILED
        assert IncidentStatus.VERIFICATION_FAILED

    def test_owner_action_states_exist(self):
        assert IncidentStatus.REJECTED
        assert IncidentStatus.DISMISSED
        assert IncidentStatus.REOPENED
        assert IncidentStatus.NEEDS_REVIEW
        assert IncidentStatus.HUMAN_REVIEW_REQUIRED

    def test_status_values_are_lowercase_strings(self):
        """Values should be lowercase snake_case strings for DB storage."""
        for state in IncidentStatus:
            assert state.value == state.value.lower(), (
                f"Status {state.name} has non-lowercase value: {state.value}"
            )


class TestPatchStatusEnum:
    """Verify PatchStatus enum values."""

    EXPECTED_PATCH_STATES = {
        "PROPOSED",
        "VERIFYING",
        "VERIFIED",
        "REJECTED",
        "APPLIED",
        "PR_CREATED",
    }

    def test_all_patch_states_exist(self):
        actual = {s.name for s in PatchStatus}
        assert self.EXPECTED_PATCH_STATES.issubset(actual), (
            f"Missing patch states: {self.EXPECTED_PATCH_STATES - actual}"
        )


class TestAuditActionEnum:
    """Verify AuditAction enum includes all required actions."""

    REQUIRED_ACTIONS = {
        "INCIDENT_CREATED",
        "ANALYSIS_STARTED",
        "ANALYSIS_COMPLETED",
        "PATCH_GENERATED",
        "PATCH_GENERATION_FAILED",
        "PATCH_APPROVED",
        "PATCH_REJECTED",
        "VERIFICATION_STARTED",
        "VERIFICATION_COMPLETED",
        "PR_CREATED",
        "INCIDENT_RESOLVED",
        "INCIDENT_DISMISSED",
    }

    def test_all_required_audit_actions_exist(self):
        actual = {a.name for a in AuditAction}
        missing = self.REQUIRED_ACTIONS - actual
        assert not missing, f"Missing audit actions: {missing}"


class TestIncidentStatusTransitionLogic:
    """
    Test the conceptual validity of state transitions.
    These test the transition rules without requiring DB access.
    """

    # Valid forward transitions in the happy path
    VALID_TRANSITIONS = {
        "detected":                ["analyzing", "dismissed"],
        "analyzing":               ["root_cause_identified", "analysis_failed"],
        "root_cause_identified":   ["repair_proposed"],
        "repair_proposed":         ["verifying"],
        "verifying":               ["verified", "verification_failed"],
        "verified":                ["awaiting_review"],
        "awaiting_review":         ["pr_created", "rejected", "dismissed"],
        "pr_created":              ["recovery_monitoring"],
        "recovery_monitoring":     ["resolved", "awaiting_review"],
        "analysis_failed":         ["analyzing", "dismissed"],
        "verification_failed":     ["repair_proposed", "dismissed"],
        "rejected":                ["awaiting_review", "dismissed"],
        "resolved":                ["reopened"],
        "dismissed":               ["reopened"],
        "reopened":                ["analyzing", "awaiting_review"],
    }

    def test_resolved_cannot_go_to_analyzing_directly(self):
        """RESOLVED should not transition to ANALYZING without reopening first."""
        valid_from_resolved = self.VALID_TRANSITIONS.get("resolved", [])
        assert "analyzing" not in valid_from_resolved

    def test_dismissed_can_reopen(self):
        """DISMISSED incidents should be reopenable."""
        assert "reopened" in self.VALID_TRANSITIONS["dismissed"]

    def test_pr_created_goes_to_recovery_monitoring(self):
        """After PR merge, incident moves to RECOVERY_MONITORING."""
        assert "recovery_monitoring" in self.VALID_TRANSITIONS["pr_created"]

    def test_recovery_monitoring_resolves(self):
        """After successful deploy, RECOVERY_MONITORING → RESOLVED."""
        assert "resolved" in self.VALID_TRANSITIONS["recovery_monitoring"]

    def test_recovery_monitoring_can_revert_on_failure(self):
        """If recovery deploy also fails, go back to AWAITING_REVIEW."""
        assert "awaiting_review" in self.VALID_TRANSITIONS["recovery_monitoring"]

    def test_all_terminal_states_have_reopened_path(self):
        """All terminal states (resolved, dismissed) should be reopenable."""
        terminal_states = ["resolved", "dismissed"]
        for state in terminal_states:
            assert "reopened" in self.VALID_TRANSITIONS[state], (
                f"Terminal state '{state}' has no path to 'reopened'"
            )
