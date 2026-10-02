"""
AI Provider Abstraction

PatchR decouples AI calls behind an abstract interface.
Concrete implementations (NvidiaNIM, OpenAI, Anthropic) are swappable.
The rest of the codebase imports get_ai_provider() — never a concrete class.

NVIDIA NIM is OpenAI-compatible:
  base_url = https://integrate.api.nvidia.com/v1
  api_key = NVIDIA_API_KEY
  The openai Python client works with zero changes.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog
from openai import AsyncOpenAI

from patchr.ai.schemas import AnalysisResult, PatchResult
from patchr.config import get_settings

logger = structlog.get_logger(__name__)


# ─── Context dataclasses passed to the AI ─────────────────────────────────────


@dataclass
class IncidentContext:
    """Everything the AI needs to analyze a failure."""

    incident_id: str
    repository_full_name: str
    default_branch: str

    # Failure signal
    build_logs: str
    error_message: str | None

    # Git context
    commit_sha: str | None
    commit_message: str | None
    commit_author: str | None
    changed_files: list[str]  # list of file paths changed in the commit

    # Repository context (populated by context engine)
    relevant_file_contents: dict[str, str]  # path → content
    package_json: dict[str, Any] | None
    framework: str | None  # "nextjs", "vite", etc.

    # Historical context (empty for now, populated later)
    previous_incidents: list[dict] | None = None


@dataclass
class PatchContext:
    """Everything the AI needs to generate a fix."""

    incident_id: str
    analysis: AnalysisResult
    incident_context: IncidentContext

    # Populated on retry — structured output from BuildValidationResult.structured_feedback
    # Contains: validation_status, stage, error, stderr_excerpt
    validation_feedback: dict | None = None


# ─── Abstract Provider ─────────────────────────────────────────────────────────


class AIProvider(ABC):
    """
    Abstract AI provider interface.
    All providers must implement analyze_incident and generate_patch.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def analyze_incident(self, ctx: IncidentContext) -> AnalysisResult:
        """Run root-cause analysis. Returns validated structured output."""
        ...

    @abstractmethod
    async def generate_patch(self, ctx: PatchContext) -> PatchResult:
        """Generate a proposed patch. Returns validated structured output."""
        ...

    async def generate_patch_with_strategy(
        self, ctx: PatchContext, strategy_instruction: str
    ) -> PatchResult:
        """
        Generate a patch with an explicit strategy instruction injected.
        Default implementation: mutate the context and call generate_patch.
        """
        # Inject strategy into validation_feedback so the prompt builder includes it
        original_feedback = ctx.validation_feedback
        ctx.validation_feedback = {
            **(original_feedback or {}),
            "strategy_instruction": strategy_instruction,
        }
        result = await self.generate_patch(ctx)
        ctx.validation_feedback = original_feedback  # restore
        return result


# ─── NVIDIA NIM Provider ───────────────────────────────────────────────────────


FALLBACK_NIM_MODELS = [
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-super-120b-a12b",
    "meta/muse-glimmer-30b",
]


class NvidiaNIMProvider(AIProvider):
    """
    NVIDIA NIM provider using OpenAI-compatible REST API.
    Supports structured JSON output via response_format / prompt engineering.
    """

    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )
        self._model = settings.nvidia_model

    @property
    def provider_name(self) -> str:
        return "nvidia_nim"

    @property
    def model_name(self) -> str:
        return self._model

    async def _chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> tuple[str, dict]:
        """
        Send a chat completion request to NVIDIA NIM with fallback support.
        Returns (response_text, usage_dict).
        Low temperature for deterministic, factual analysis.
        """
        candidates = [self._model] + [m for m in FALLBACK_NIM_MODELS if m != self._model]
        last_error = None

        for model in candidates:
            log = logger.bind(model=model, provider=self.provider_name)
            log.info("ai_request_started")
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._model = model  # cache working model
                content = response.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                }
                log.info("ai_request_completed", **usage)
                return content, usage
            except Exception as e:
                log.warning("ai_model_attempt_failed", model=model, error=str(e))
                last_error = e
                continue

        raise last_error or RuntimeError("All AI models failed")

    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from model response.
        Handles markdown code fences, surrounding prose, etc.
        """
        import re

        text = text.strip()

        # 1. Direct parse attempt
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Markdown code fences ```json ... ``` or ``` ... ```
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        # 3. Outermost curly braces { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        # Fallback to direct parse to trigger informative error
        return json.loads(text)

    async def analyze_incident(self, ctx: IncidentContext) -> AnalysisResult:
        system_prompt = _ANALYSIS_SYSTEM_PROMPT
        user_prompt = _build_analysis_user_prompt(ctx)

        raw_text, usage = await self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,  # Very low — we want factual analysis
            max_tokens=2048,
        )

        try:
            data = self._extract_json(raw_text)
            result = AnalysisResult(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(
                "ai_analysis_parse_error",
                error=str(e),
                raw_response=raw_text[:500],
                incident_id=ctx.incident_id,
            )
            raise ValueError(f"AI returned invalid structured output: {e}") from e

        return result

    async def generate_patch(self, ctx: PatchContext) -> PatchResult:
        system_prompt = _PATCH_SYSTEM_PROMPT
        user_prompt = _build_patch_user_prompt(ctx)

        raw_text, usage = await self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.15,
            max_tokens=4096,
        )

        try:
            data = self._extract_json(raw_text)
            result = PatchResult(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(
                "ai_patch_parse_error",
                error=str(e),
                raw_response=raw_text[:500],
                incident_id=ctx.incident_id,
            )
            raise ValueError(f"AI returned invalid patch output: {e}") from e

        return result

    async def generate_patch_with_strategy(
        self, ctx: PatchContext, strategy_instruction: str
    ) -> PatchResult:
        """Generate a strategy-specific patch for Patch Arena."""
        system_prompt = _PATCH_SYSTEM_PROMPT
        # Build user prompt with strategy instruction prominently placed
        base_user_prompt = _build_patch_user_prompt(ctx)
        strategy_header = (
            f"\n=== REPAIR STRATEGY INSTRUCTION ===\n"
            f"{strategy_instruction}\n"
            f"Follow this strategy. Do not deviate from the strategy unless it is\n"
            f"completely inapplicable, in which case default to minimal diff.\n"
        )
        user_prompt = strategy_header + "\n" + base_user_prompt

        raw_text, usage = await self._chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,  # Slightly higher for strategy diversity
            max_tokens=4096,
        )

        try:
            data = self._extract_json(raw_text)
            result = PatchResult(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(
                "ai_patch_strategy_parse_error",
                error=str(e),
                strategy=strategy_instruction[:100],
                raw_response=raw_text[:500],
                incident_id=ctx.incident_id,
            )
            raise ValueError(f"AI returned invalid patch output for strategy: {e}") from e

        return result


# ─── Provider Factory ──────────────────────────────────────────────────────────


def get_ai_provider() -> AIProvider:
    """
    FastAPI dependency: returns the configured AI provider.
    Currently always returns NvidiaNIMProvider.
    Later: read from settings to select provider.
    """
    return NvidiaNIMProvider()


# ─── Prompt Templates ──────────────────────────────────────────────────────────


_ANALYSIS_SYSTEM_PROMPT = """
You are PatchR's root-cause analysis engine. Your ONLY job is to diagnose software deployment failures.

RULES:
- Return ONLY valid JSON matching the exact schema below. Zero prose, zero markdown outside JSON.
- Do NOT guess. If uncertain, set a lower confidence score and say so in evidence.
- Evidence MUST quote actual log lines or error text verbatim — do not paraphrase.
- Only list files that you have direct evidence are responsible for the failure.
- Confidence 1.0 = certain. 0.3 = educated guess. Be honest.

OUTPUT SCHEMA (return this exact structure):
{
  "failure_type": "build_error|import_error|type_error|syntax_error|env_variable|dependency_conflict|framework_error|runtime_error|unknown",
  "root_cause": "One clear paragraph explaining the root cause with specific evidence.",
  "affected_files": ["path/to/file.ts"],
  "evidence": ["exact log line or error text supporting this diagnosis"],
  "confidence": 0.0,
  "risk_level": "low|medium|high|critical",
  "verification_plan": ["Step 1: ...", "Step 2: ..."],
  "summary": "1-2 sentence dashboard summary."
}
""".strip()


_PATCH_SYSTEM_PROMPT = """
You are PatchR's patch generation engine. You produce safe, minimal, build-verified code fixes.

RULES:
- Return ONLY valid JSON matching the exact schema below. Zero prose, zero markdown outside JSON.
- Minimal changes ONLY. Do not refactor unrelated code. Do not add unused imports.
- original_content MUST be an EXACT copy of the code you are replacing — character for character.
- patched_content MUST be a complete drop-in replacement for original_content.
- If validation feedback is provided below, you MUST address the specific error it describes.
- Be honest about confidence and risk.

OUTPUT SCHEMA (return this exact structure):
{
  "description": "Clear explanation of what this patch does and why it fixes the issue.",
  "file_changes": [
    {
      "path": "path/to/file.ts",
      "original_content": "exact original code being replaced",
      "patched_content": "exact replacement code",
      "change_type": "modify|create|delete",
      "explanation": "Why this specific change fixes the failure."
    }
  ],
  "confidence": 0.0,
  "risk_level": "low|medium|high|critical",
  "rollback_strategy": "How to revert if needed.",
  "side_effects": ["potential side effect 1"]
}
""".strip()


def _build_analysis_user_prompt(ctx: IncidentContext) -> str:
    """Build the user prompt for incident analysis with clearly labeled sections."""
    parts = []

    # ── INCIDENT METADATA ─────────────────────────────────────────────────────
    parts.append("=== INCIDENT METADATA ===")
    parts.append(f"Repository: {ctx.repository_full_name}")
    parts.append(f"Default Branch: {ctx.default_branch}")
    if ctx.framework:
        parts.append(f"Framework: {ctx.framework}")

    # ── COMMIT INFORMATION ────────────────────────────────────────────────────
    if ctx.commit_sha or ctx.commit_message:
        parts.append("\n=== COMMIT INFORMATION ===")
        if ctx.commit_sha:
            parts.append(f"SHA: {ctx.commit_sha[:12]}")
        if ctx.commit_message:
            parts.append(f"Message: {ctx.commit_message}")
        if ctx.commit_author:
            parts.append(f"Author: {ctx.commit_author}")

    # ── CHANGED FILES ─────────────────────────────────────────────────────────
    if ctx.changed_files:
        parts.append("\n=== CHANGED FILES IN THIS COMMIT ===")
        for f in ctx.changed_files:
            parts.append(f"  - {f}")

    # ── DEPENDENCY CONTEXT ────────────────────────────────────────────────────
    if ctx.package_json:
        deps = ctx.package_json.get("dependencies", {})
        dev_deps = ctx.package_json.get("devDependencies", {})
        parts.append("\n=== KEY DEPENDENCIES ===")
        parts.append(json.dumps({**deps, **dev_deps}, indent=2)[:1200])

    # ── BUILD FAILURE ─────────────────────────────────────────────────────────
    parts.append("\n=== BUILD FAILURE LOGS ===")
    parts.append(ctx.build_logs[:6000] if ctx.build_logs else "(no build logs available)")

    # ── EXTRACTED ERROR ───────────────────────────────────────────────────────
    if ctx.error_message:
        parts.append("\n=== EXTRACTED ERROR MESSAGE ===")
        parts.append(ctx.error_message[:2000])

    # ── RELEVANT SOURCE FILES ─────────────────────────────────────────────────
    if ctx.relevant_file_contents:
        parts.append("\n=== RELEVANT SOURCE FILES ===")
        for path, content in list(ctx.relevant_file_contents.items())[:5]:
            parts.append(f"\n--- {path} ---")
            parts.append(content[:2500])

    # ── TASK ──────────────────────────────────────────────────────────────────
    parts.append("\n=== TASK ===")
    parts.append(
        "Analyze the build failure above. Identify the exact root cause using only "
        "the evidence provided. Return valid JSON matching the output schema."
    )

    return "\n".join(parts)


def _build_patch_user_prompt(ctx: PatchContext) -> str:
    """Build the structured user prompt for patch generation."""
    analysis = ctx.analysis
    inc = ctx.incident_context
    parts = []

    # ── ROOT CAUSE SUMMARY ────────────────────────────────────────────────────
    parts.append("=== ROOT CAUSE ANALYSIS ===")
    parts.append(f"Repository: {inc.repository_full_name}")
    parts.append(f"Failure type: {analysis.failure_type}")
    parts.append(f"Root cause: {analysis.root_cause}")
    parts.append(f"Confidence: {analysis.confidence:.0%}")
    parts.append(f"Affected files: {', '.join(analysis.affected_files)}")

    # ── EVIDENCE ──────────────────────────────────────────────────────────────
    if analysis.evidence:
        parts.append("\n=== EVIDENCE ===")
        for e in analysis.evidence:
            parts.append(f"  - {e}")

    # ── VERIFICATION PLAN ─────────────────────────────────────────────────────
    if analysis.verification_plan:
        parts.append("\n=== VERIFICATION PLAN ===")
        for i, step in enumerate(analysis.verification_plan, 1):
            parts.append(f"  {i}. {step}")

    # ── VALIDATION FEEDBACK (retry context) ───────────────────────────────────
    if ctx.validation_feedback:
        fb = ctx.validation_feedback
        parts.append("\n=== PREVIOUS PATCH VALIDATION FEEDBACK ===")
        parts.append(
            f"Your previous patch attempt FAILED at stage '{fb.get('stage', 'unknown')}'.\n"
            f"You MUST fix the following error before the build can pass:\n"
            f"{fb.get('error', 'Unknown error')}"
        )
        if fb.get("stderr_excerpt"):
            parts.append("\nBuild stderr excerpt:")
            parts.append(fb["stderr_excerpt"][-1500:])
        parts.append(
            "\nAnalyze the error above carefully. Adjust your patch to fix "
            "BOTH the original root cause AND this validation error."
        )

    # ── RELEVANT SOURCE FILES ─────────────────────────────────────────────────
    if inc.relevant_file_contents:
        parts.append("\n=== RELEVANT SOURCE FILES ===")
        for path, content in inc.relevant_file_contents.items():
            # Prioritize affected files, then include others
            if path in analysis.affected_files:
                parts.append(f"\n--- {path} (AFFECTED) ---")
                parts.append(content[:4000])
        for path, content in inc.relevant_file_contents.items():
            if path not in analysis.affected_files:
                parts.append(f"\n--- {path} ---")
                parts.append(content[:1500])

    # ── BUILD LOG EXCERPT ─────────────────────────────────────────────────────
    if inc.build_logs:
        parts.append("\n=== BUILD LOG EXCERPT ===")
        parts.append(inc.build_logs[-3000:])

    # ── TASK ──────────────────────────────────────────────────────────────────
    parts.append("\n=== TASK ===")
    retry_note = (
        " Your previous attempt failed — use the VALIDATION FEEDBACK section above to correct it."
        if ctx.validation_feedback else ""
    )
    parts.append(
        f"Generate the minimal patch that fixes the root cause above.{retry_note} "
        "Return valid JSON matching the output schema. "
        "original_content must be exact — character for character from the source files shown above."
    )

    return "\n".join(parts)
