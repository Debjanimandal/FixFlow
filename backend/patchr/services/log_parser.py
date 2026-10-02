"""
Build Log Parser

Extracts structured error information from raw Vercel/Next.js build logs.
Turns noisy multi-hundred-line output into a concise, AI-ready error context.

The parser understands:
- Next.js compilation errors
- TypeScript errors
- Module resolution errors
- ESLint / type checker output
- npm/pnpm install errors
- Runtime crash traces
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─── Output Structures ────────────────────────────────────────────────────────


@dataclass
class ParsedError:
    """A single extracted error from build logs."""
    error_type: str          # "module_not_found", "type_error", "syntax_error", etc.
    message: str             # The primary error message
    file_path: str | None    # Which file the error came from
    line_number: int | None  # Line number in the file
    column: int | None       # Column number
    code_snippet: str | None # Surrounding code context
    raw_lines: list[str]     # The original log lines that produced this error

    @property
    def short_description(self) -> str:
        if self.file_path and self.line_number:
            return f"{self.file_path}:{self.line_number} — {self.message[:120]}"
        return self.message[:150]


@dataclass
class ParsedBuildLog:
    """Result of parsing a complete build log."""
    errors: list[ParsedError]
    framework: str | None          # "nextjs", "vite", "cra", "remix", etc.
    failure_type: str              # best guess at the overall failure category
    error_summary: str             # condensed human-readable summary
    affected_files: list[str]      # all files mentioned in errors
    key_log_excerpt: str           # the most relevant 40 lines for AI consumption

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def primary_error(self) -> ParsedError | None:
        return self.errors[0] if self.errors else None


# ─── Patterns ─────────────────────────────────────────────────────────────────

# Next.js / webpack module resolution
_MODULE_NOT_FOUND = re.compile(
    r"(Module not found|Can't resolve|Cannot find module)[:\s]+['\"]?([^'\"\n]+)['\"]?",
    re.IGNORECASE,
)

# TypeScript errors: path(line,col): error TSxxxx: message
_TS_ERROR = re.compile(
    r"^(.+\.tsx?)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)$"
)

# Next.js compilation error block: "error - ./path/to/file"
_NEXTJS_COMPILE_ERROR = re.compile(
    r"^(?:error|Error)\s*[-–]\s*(\./[^\s]+|[a-zA-Z]:[^\s]+)",
)

# General file reference: "  at ./src/app/page.tsx:42" or "in ./src/file.ts"
_FILE_REFERENCE = re.compile(
    r"(?:at\s+|in\s+|from\s+)?(?:\./|/)?(src/[\w./]+\.[jt]sx?|app/[\w./]+\.[jt]sx?|pages/[\w./]+\.[jt]sx?|components/[\w./]+\.[jt]sx?|lib/[\w./]+\.[jt]sx?)"
)

# Line number reference
_LINE_REFERENCE = re.compile(r":(\d+)(?::(\d+))?(?:\s|$)")

# npm/yarn/pnpm errors
_NPM_ERROR = re.compile(r"^npm (ERR!|error)", re.IGNORECASE)
_PEER_DEP_ERROR = re.compile(r"peer dep|peer dependency|ERESOLVE|resolution failed", re.IGNORECASE)

# Environment variable references
_ENV_VAR_MISSING = re.compile(
    r"(process\.env\.\w+|NEXT_PUBLIC_\w+|[\w_]+) is (undefined|not defined|required|missing)",
    re.IGNORECASE,
)

# Exit code
_EXIT_CODE = re.compile(r"exited with (?:code\s+)?(\d+)", re.IGNORECASE)


# ─── Framework Detection ──────────────────────────────────────────────────────

def _detect_framework(lines: list[str]) -> str | None:
    text = "\n".join(lines[:50]).lower()
    if "next.js" in text or "next build" in text or "creating an optimized" in text:
        return "nextjs"
    if "vite" in text or "vite v" in text:
        return "vite"
    if "react-scripts" in text or "create react app" in text:
        return "cra"
    if "remix" in text:
        return "remix"
    if "nuxt" in text:
        return "nuxt"
    return None


# ─── Error Extraction ─────────────────────────────────────────────────────────

def _extract_errors(lines: list[str]) -> list[ParsedError]:
    errors: list[ParsedError] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # TypeScript error (highest precision)
        m = _TS_ERROR.match(line.strip())
        if m:
            file_path, line_num, col, _, ts_code, message = m.groups()
            errors.append(ParsedError(
                error_type="type_error",
                message=f"{ts_code}: {message.strip()}",
                file_path=file_path,
                line_number=int(line_num),
                column=int(col),
                code_snippet=None,
                raw_lines=[line],
            ))
            i += 1
            continue

        # Module not found
        m = _MODULE_NOT_FOUND.search(line)
        if m:
            # Collect next few lines for context
            context_lines = [line]
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip() and not lines[j].startswith("Module not found"):
                    context_lines.append(lines[j])

            # Try to find the file from preceding/following lines
            file_path = _find_file_reference_near(lines, i)

            errors.append(ParsedError(
                error_type="import_error",
                message=line.strip(),
                file_path=file_path,
                line_number=None,
                column=None,
                code_snippet="\n".join(context_lines[:4]),
                raw_lines=context_lines,
            ))
            i += 1
            continue

        # Next.js "error - ./path/to/file" pattern
        m = _NEXTJS_COMPILE_ERROR.match(line.strip())
        if m:
            file_path = m.group(1).lstrip("./")
            context_lines = [line]
            for j in range(i + 1, min(i + 8, len(lines))):
                next_line = lines[j]
                context_lines.append(next_line)
                if next_line.strip().startswith("error") or not next_line.strip():
                    break

            message = " ".join(l.strip() for l in context_lines[1:3] if l.strip())
            errors.append(ParsedError(
                error_type="build_error",
                message=message or line.strip(),
                file_path=file_path,
                line_number=None,
                column=None,
                code_snippet="\n".join(context_lines[:6]),
                raw_lines=context_lines,
            ))
            i += 1
            continue

        # Environment variable missing
        m = _ENV_VAR_MISSING.search(line)
        if m:
            errors.append(ParsedError(
                error_type="env_variable",
                message=line.strip(),
                file_path=None,
                line_number=None,
                column=None,
                code_snippet=None,
                raw_lines=[line],
            ))
            i += 1
            continue

        # NPM peer dep error
        if _PEER_DEP_ERROR.search(line):
            context_lines = [line]
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j].strip():
                    context_lines.append(lines[j])
            errors.append(ParsedError(
                error_type="dependency_conflict",
                message=line.strip(),
                file_path=None,
                line_number=None,
                column=None,
                code_snippet="\n".join(context_lines[:5]),
                raw_lines=context_lines,
            ))
            i += 1
            continue

        i += 1

    return errors


def _find_file_reference_near(lines: list[str], index: int) -> str | None:
    """Search nearby lines for a file path reference."""
    search_range = range(max(0, index - 3), min(len(lines), index + 5))
    for i in search_range:
        m = _FILE_REFERENCE.search(lines[i])
        if m:
            return m.group(1)
    return None


def _infer_failure_type(errors: list[ParsedError], raw_text: str) -> str:
    """Infer the overall failure type from parsed errors."""
    if not errors:
        # Fall back to keyword scanning
        lower = raw_text.lower()
        if "module not found" in lower or "cannot find module" in lower:
            return "import_error"
        if "typeerror" in lower or " ts" in lower:
            return "type_error"
        if "syntaxerror" in lower:
            return "syntax_error"
        if "process.env" in lower or "environment variable" in lower:
            return "env_variable"
        if "peer dep" in lower or "eresolve" in lower:
            return "dependency_conflict"
        return "build_error"

    # Use most frequent error type
    from collections import Counter
    types = Counter(e.error_type for e in errors)
    return types.most_common(1)[0][0]


def _extract_key_excerpt(lines: list[str], errors: list[ParsedError], max_lines: int = 50) -> str:
    """
    Extract the most relevant lines from a long build log for the AI prompt.
    Prioritizes error lines and their context.
    """
    if not lines:
        return ""

    # If log is short enough, return as-is
    if len(lines) <= max_lines:
        return "\n".join(lines)

    # Collect indices of important lines
    important: set[int] = set()

    # Error line indices from parsed errors
    for error in errors:
        for j, line in enumerate(lines):
            if error.raw_lines and line in error.raw_lines:
                # Add ±3 lines of context
                for k in range(max(0, j - 3), min(len(lines), j + 4)):
                    important.add(k)

    # Always include last 20 lines (most recent output)
    for k in range(max(0, len(lines) - 20), len(lines)):
        important.add(k)

    # Fill up to max_lines with error-keyword lines
    for j, line in enumerate(lines):
        if len(important) >= max_lines:
            break
        lower = line.lower()
        if any(kw in lower for kw in ["error", "failed", "cannot", "invalid", "unexpected"]):
            important.add(j)
            for k in range(max(0, j - 1), min(len(lines), j + 2)):
                important.add(k)

    # Reconstruct in order with ellipsis between gaps
    sorted_indices = sorted(important)
    result_lines: list[str] = []
    prev = -2
    for idx in sorted_indices:
        if idx > prev + 1:
            if result_lines:
                result_lines.append("  ... (truncated)")
        result_lines.append(lines[idx])
        prev = idx

    return "\n".join(result_lines[:max_lines])


# ─── Main Entry Point ─────────────────────────────────────────────────────────


def parse_build_log(raw_log: str) -> ParsedBuildLog:
    """
    Parse a raw build log string into structured error information.

    This is the primary entry point for the log parser.
    Call this before passing logs to the AI for analysis.
    """
    if not raw_log or not raw_log.strip():
        return ParsedBuildLog(
            errors=[],
            framework=None,
            failure_type="unknown",
            error_summary="No build log available",
            affected_files=[],
            key_log_excerpt="",
        )

    lines = raw_log.splitlines()
    framework = _detect_framework(lines)
    errors = _extract_errors(lines)
    failure_type = _infer_failure_type(errors, raw_log)
    key_excerpt = _extract_key_excerpt(lines, errors)

    # Collect unique affected files
    affected_files: list[str] = []
    seen: set[str] = set()
    for error in errors:
        if error.file_path and error.file_path not in seen:
            affected_files.append(error.file_path)
            seen.add(error.file_path)

    # Build a human-readable summary
    if errors:
        primary = errors[0]
        summary = primary.short_description
        if len(errors) > 1:
            summary += f" (+{len(errors) - 1} more errors)"
    else:
        # Try to find the exit line
        for line in reversed(lines[-20:]):
            if "error" in line.lower() or "failed" in line.lower():
                summary = line.strip()[:200]
                break
        else:
            summary = f"Build failed ({failure_type.replace('_', ' ')})"

    return ParsedBuildLog(
        errors=errors,
        framework=framework,
        failure_type=failure_type,
        error_summary=summary,
        affected_files=affected_files,
        key_log_excerpt=key_excerpt,
    )
