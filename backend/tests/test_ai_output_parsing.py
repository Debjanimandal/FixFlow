"""
Unit tests: AI output JSON parsing and validation.

Tests that the patch service correctly handles:
- Well-formed AI output
- Malformed / partial JSON
- Missing required fields
- Edge cases (empty files list, very long output)

No real NVIDIA API calls — all AI responses are mocked strings.
"""

import json

import pytest


# ── Helpers that mirror patch_service parsing logic ────────────────────────────

def _extract_json_from_ai_output(raw: str) -> dict:
    """
    Mirror of the JSON extraction logic in patch_service.
    Finds the first {...} block in the AI output and parses it.
    """
    # Strip markdown code fences if present
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        # Remove first and last fence lines
        inner = lines[1:] if len(lines) > 1 else lines
        if inner and inner[-1].strip().startswith("```"):
            inner = inner[:-1]
        clean = "\n".join(inner).strip()

    # Find the outermost JSON object
    start = clean.find("{")
    end = clean.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in AI output")

    json_str = clean[start:end + 1]
    return json.loads(json_str)


def _validate_patch_json(data: dict) -> list[str]:
    """
    Return a list of validation errors for a parsed patch JSON.
    Empty list = valid.
    """
    errors = []
    if not isinstance(data.get("root_cause"), str) or not data["root_cause"]:
        errors.append("root_cause must be a non-empty string")
    if not isinstance(data.get("file_changes"), list):
        errors.append("file_changes must be a list")
    else:
        for i, fc in enumerate(data["file_changes"]):
            if not fc.get("path"):
                errors.append(f"file_changes[{i}] missing 'path'")
            if not fc.get("patched_content"):
                errors.append(f"file_changes[{i}] missing 'patched_content'")
    return errors


# ── Tests: JSON extraction ─────────────────────────────────────────────────────

class TestAIJsonExtraction:

    def test_clean_json_is_parsed(self):
        raw = '{"root_cause": "null pointer", "file_changes": []}'
        result = _extract_json_from_ai_output(raw)
        assert result["root_cause"] == "null pointer"

    def test_json_with_preamble_text_is_parsed(self):
        """AI often outputs explanation text before the JSON block."""
        raw = """
        Based on the error, here is my analysis:

        {"root_cause": "Missing await keyword", "file_changes": []}

        Let me know if you need more details.
        """
        result = _extract_json_from_ai_output(raw)
        assert result["root_cause"] == "Missing await keyword"

    def test_json_in_markdown_code_block_is_parsed(self):
        raw = '''```json
{"root_cause": "Type mismatch", "file_changes": []}
```'''
        result = _extract_json_from_ai_output(raw)
        assert result["root_cause"] == "Type mismatch"

    def test_json_in_plain_code_block_is_parsed(self):
        raw = '''```
{"root_cause": "Import error", "file_changes": []}
```'''
        result = _extract_json_from_ai_output(raw)
        assert result["root_cause"] == "Import error"

    def test_no_json_raises_value_error(self):
        raw = "The deployment failed because of an unknown error. No patch possible."
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json_from_ai_output(raw)

    def test_invalid_json_raises_json_decode_error(self):
        raw = "{root_cause: missing-quotes, file_changes: []}"
        with pytest.raises(json.JSONDecodeError):
            _extract_json_from_ai_output(raw)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _extract_json_from_ai_output("")

    def test_nested_json_with_file_changes(self):
        raw = json.dumps({
            "root_cause": "Unhandled promise rejection in fetchUser()",
            "confidence": 0.87,
            "file_changes": [
                {
                    "path": "src/api/user.ts",
                    "patched_content": "export async function fetchUser() { try { ... } catch(e) {} }",
                    "original_content": "export async function fetchUser() { ... }",
                    "change_type": "modify",
                    "explanation": "Added try-catch for promise rejection",
                }
            ]
        })
        result = _extract_json_from_ai_output(raw)
        assert len(result["file_changes"]) == 1
        assert result["file_changes"][0]["path"] == "src/api/user.ts"
        assert result["confidence"] == pytest.approx(0.87)


# ── Tests: Patch JSON validation ───────────────────────────────────────────────

class TestPatchJsonValidation:

    def test_valid_patch_json_has_no_errors(self):
        data = {
            "root_cause": "Unhandled exception in auth middleware",
            "file_changes": [
                {
                    "path": "middleware/auth.py",
                    "patched_content": "def auth(): pass",
                    "change_type": "modify",
                    "explanation": "Added exception handler",
                }
            ],
        }
        errors = _validate_patch_json(data)
        assert errors == []

    def test_missing_root_cause_is_an_error(self):
        data = {"file_changes": []}
        errors = _validate_patch_json(data)
        assert any("root_cause" in e for e in errors)

    def test_empty_root_cause_is_an_error(self):
        data = {"root_cause": "", "file_changes": []}
        errors = _validate_patch_json(data)
        assert any("root_cause" in e for e in errors)

    def test_missing_file_changes_is_an_error(self):
        data = {"root_cause": "Some error"}
        errors = _validate_patch_json(data)
        assert any("file_changes" in e for e in errors)

    def test_file_change_missing_path_is_an_error(self):
        data = {
            "root_cause": "Error",
            "file_changes": [{"patched_content": "code"}],
        }
        errors = _validate_patch_json(data)
        assert any("path" in e for e in errors)

    def test_file_change_missing_patched_content_is_an_error(self):
        data = {
            "root_cause": "Error",
            "file_changes": [{"path": "src/app.ts"}],
        }
        errors = _validate_patch_json(data)
        assert any("patched_content" in e for e in errors)

    def test_empty_file_changes_list_is_valid(self):
        """An empty file_changes list is technically valid (AI may refuse to patch)."""
        data = {"root_cause": "Cannot determine root cause from logs", "file_changes": []}
        errors = _validate_patch_json(data)
        assert errors == []

    def test_multiple_file_changes_all_validated(self):
        data = {
            "root_cause": "Error",
            "file_changes": [
                {"path": "a.py", "patched_content": "code"},  # valid
                {"patched_content": "code"},                   # missing path
                {"path": "c.py"},                             # missing patched_content
            ],
        }
        errors = _validate_patch_json(data)
        # Should have 2 errors (indices 1 and 2)
        assert len(errors) == 2
