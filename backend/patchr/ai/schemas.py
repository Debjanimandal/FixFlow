"""
AI Structured Output Schemas

These Pydantic models define what the AI must return.
The AI is never allowed to return free-form text for analysis or patches.
All output is validated before being stored or surfaced to the user.
"""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class AnalysisResult(BaseModel):
    """
    Structured root-cause analysis from the AI reasoning model.
    Maps directly to the Analysis DB model.
    """

    failure_type: str = Field(
        description=(
            "One of: build_error, import_error, type_error, syntax_error, "
            "env_variable, dependency_conflict, framework_error, runtime_error, unknown"
        )
    )
    root_cause: str = Field(
        description="One clear paragraph explaining the most likely root cause of the failure."
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="List of file paths most likely responsible for or affected by the failure.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Specific log lines, error messages, or code references that support the root cause.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 (no confidence) to 1.0 (fully confident).",
    )
    risk_level: str = Field(
        description="One of: low, medium, high, critical — risk of the identified root cause being incorrect."
    )
    verification_plan: list[str] = Field(
        default_factory=list,
        description="Ordered list of steps to verify the root cause and validate any proposed fix.",
    )
    summary: str = Field(
        description="A 1-2 sentence human-readable summary suitable for display in the incident dashboard."
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        try:
            if isinstance(v, str):
                v = v.replace("%", "").strip()
            val = float(v)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "medium"
        v_clean = v.strip().lower()
        if "crit" in v_clean:
            return "critical"
        if "high" in v_clean:
            return "high"
        if "low" in v_clean:
            return "low"
        return "medium"

    @field_validator("failure_type", mode="before")
    @classmethod
    def normalize_failure_type(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "unknown"
        v_clean = v.strip().lower()
        allowed = {
            "build_error",
            "import_error",
            "type_error",
            "syntax_error",
            "env_variable",
            "dependency_conflict",
            "framework_error",
            "runtime_error",
            "unknown",
        }
        if v_clean in allowed:
            return v_clean
        for a in allowed:
            if a in v_clean or v_clean in a:
                return a
        return "unknown"


class FileChange(BaseModel):
    """A single file modification in a patch."""

    path: str = Field(description="File path relative to repository root.")
    original_content: str | None = Field(
        default=None, description="Original file content (or relevant excerpt)."
    )
    patched_content: str | None = Field(
        default=None, description="Proposed replacement content (or relevant excerpt)."
    )
    change_type: str = Field(
        default="modify",
        description="One of: modify, create, delete",
    )
    explanation: str = Field(
        description="Why this specific change is needed."
    )


class PatchResult(BaseModel):
    """
    Structured patch proposal from the AI.
    Maps directly to the Patch DB model.
    The patch is UNTRUSTED until verification passes.
    """

    description: str = Field(
        description="A clear explanation of what this patch does and why it fixes the issue."
    )
    file_changes: list[FileChange] = Field(
        description="All file changes required to apply this patch."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that this patch will resolve the incident.",
    )
    risk_level: str = Field(
        description="One of: low, medium, high, critical — risk of applying this patch."
    )
    rollback_strategy: str | None = Field(
        default=None,
        description="How to revert this patch if it causes issues.",
    )
    side_effects: list[str] = Field(
        default_factory=list,
        description="Known potential side effects of applying this patch.",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        try:
            if isinstance(v, str):
                v = v.replace("%", "").strip()
            val = float(v)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.8

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "medium"
        v_clean = v.strip().lower()
        if "crit" in v_clean:
            return "critical"
        if "high" in v_clean:
            return "high"
        if "low" in v_clean:
            return "low"
        return "medium"

