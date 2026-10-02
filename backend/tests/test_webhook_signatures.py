"""
Unit tests: Webhook HMAC signature verification.

Tests both GitHub (SHA-256) and Vercel (SHA-1) signature logic.
No DB or network access needed — pure crypto logic.
"""

import hashlib
import hmac
import json

import pytest

from patchr.routers.webhooks import _verify_github_signature, _verify_vercel_signature


# ── GitHub Signature ───────────────────────────────────────────────────────────

class TestGitHubSignatureVerification:
    """Tests for _verify_github_signature."""

    SECRET = "test-webhook-secret"

    def _make_sig(self, payload: bytes) -> str:
        mac = hmac.new(self.SECRET.encode(), payload, hashlib.sha256)
        return f"sha256={mac.hexdigest()}"

    def test_valid_signature_returns_true(self):
        payload = b'{"action":"push"}'
        sig = self._make_sig(payload)
        assert _verify_github_signature(payload, sig, self.SECRET) is True

    def test_tampered_payload_returns_false(self):
        """Changing even one byte in payload must fail verification."""
        payload = b'{"action":"push"}'
        sig = self._make_sig(payload)
        tampered = b'{"action":"PUSH"}'  # capital P — different hash
        assert _verify_github_signature(tampered, sig, self.SECRET) is False

    def test_wrong_secret_returns_false(self):
        payload = b'{"action":"push"}'
        sig = self._make_sig(payload)
        assert _verify_github_signature(payload, sig, "wrong-secret") is False

    def test_missing_signature_header_returns_false(self):
        payload = b'{"action":"push"}'
        assert _verify_github_signature(payload, None, self.SECRET) is False

    def test_empty_signature_header_returns_false(self):
        payload = b'{"action":"push"}'
        assert _verify_github_signature(payload, "", self.SECRET) is False

    def test_signature_without_sha256_prefix_returns_false(self):
        payload = b'{"action":"push"}'
        mac = hmac.new(self.SECRET.encode(), payload, hashlib.sha256)
        raw_hex = mac.hexdigest()  # Missing 'sha256=' prefix
        assert _verify_github_signature(payload, raw_hex, self.SECRET) is False

    def test_large_payload_verification(self):
        """Ensure large payloads (real webhook sizes) work correctly."""
        payload = json.dumps({"commits": [{"id": "x" * 40}] * 100}).encode()
        sig = self._make_sig(payload)
        assert _verify_github_signature(payload, sig, self.SECRET) is True

    def test_empty_payload_with_valid_sig(self):
        """Empty payload should still be verifiable."""
        payload = b""
        sig = self._make_sig(payload)
        assert _verify_github_signature(payload, sig, self.SECRET) is True


# ── Vercel Signature ───────────────────────────────────────────────────────────

class TestVercelSignatureVerification:
    """Tests for _verify_vercel_signature."""

    SECRET = "test-vercel-secret"

    def _make_sig(self, payload: bytes) -> str:
        mac = hmac.new(self.SECRET.encode(), payload, hashlib.sha1)
        return mac.hexdigest()

    def test_valid_signature_returns_true(self):
        payload = b'{"type":"deployment.error"}'
        sig = self._make_sig(payload)
        assert _verify_vercel_signature(payload, sig, self.SECRET) is True

    def test_tampered_payload_returns_false(self):
        payload = b'{"type":"deployment.error"}'
        sig = self._make_sig(payload)
        assert _verify_vercel_signature(b'{"type":"deployment.ready"}', sig, self.SECRET) is False

    def test_wrong_secret_returns_false(self):
        payload = b'{"type":"deployment.error"}'
        sig = self._make_sig(payload)
        assert _verify_vercel_signature(payload, sig, "wrong-secret") is False

    def test_missing_signature_returns_false(self):
        payload = b'{"type":"deployment.error"}'
        assert _verify_vercel_signature(payload, None, self.SECRET) is False

    def test_empty_signature_returns_false(self):
        payload = b'{"type":"deployment.error"}'
        assert _verify_vercel_signature(payload, "", self.SECRET) is False
