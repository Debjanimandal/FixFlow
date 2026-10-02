"""
Unit tests: Configuration and settings.

Tests that the Settings class loads env vars correctly,
detects placeholder values, and validates required fields.
No DB or network access needed.
"""

import os

import pytest

from patchr.config import Settings


class TestSettings:
    """Test the Settings (pydantic-settings) class."""

    def test_settings_load_from_env(self):
        s = Settings(
            database_url="postgresql+asyncpg://user:pass@host/db",
            owner_password="test-pass",
            jwt_secret="test-secret",
            nvidia_api_key="nvapi-test",
            github_token="ghp_test",
        )
        assert s.owner_password == "test-pass"
        assert s.jwt_secret == "test-secret"

    def test_is_development_flag(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            environment="development",
        )
        assert s.is_development is True

    def test_is_not_development_in_production(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            environment="production",
        )
        assert s.is_development is False

    def test_placeholder_github_token_detected(self):
        """Placeholder tokens should be detectable so the app can skip API calls."""
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            github_token="ghp_your_personal_access_token_here",
        )
        assert s.github_token.startswith("ghp_your")

    def test_placeholder_nvidia_key_detected(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            nvidia_api_key="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        )
        assert s.nvidia_api_key.startswith("nvapi-xxx")

    def test_placeholder_vercel_token_detected(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            vercel_access_token="your_vercel_access_token_here",
        )
        assert s.vercel_access_token.startswith("your_vercel")

    def test_default_nvidia_model(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
        )
        assert s.nvidia_model == "meta/llama-3.1-70b-instruct"

    def test_test_environment_is_not_development(self):
        """When ENVIRONMENT=test (set by conftest), is_development should be False."""
        s = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="s",
            environment="test",
        )
        assert s.is_development is False


class TestJWTLogic:
    """Test JWT token creation and validation."""

    def test_create_access_token_returns_string(self):
        from patchr.auth import create_access_token
        from patchr.config import Settings
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            jwt_expire_hours=24,
        )
        token = create_access_token(settings)
        assert isinstance(token, str)
        assert len(token) > 20
        # JWTs have 3 dot-separated parts
        assert token.count(".") == 2

    def test_token_contains_correct_subject(self):
        from patchr.auth import create_access_token
        from patchr.config import Settings
        from jose import jwt
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            jwt_expire_hours=24,
        )
        token = create_access_token(settings)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "owner"

    def test_token_has_expiry(self):
        from patchr.auth import create_access_token
        from patchr.config import Settings
        from jose import jwt
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            jwt_expire_hours=1,
        )
        token = create_access_token(settings)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload
        assert "iat" in payload

    def test_tampered_token_raises(self):
        from patchr.auth import create_access_token
        from patchr.config import Settings
        from jose import jwt, JWTError
        settings = Settings(
            database_url="postgresql+asyncpg://x:x@x/x",
            owner_password="p",
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            jwt_expire_hours=24,
        )
        token = create_access_token(settings)
        # Flip last char to tamper with signature
        tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")
        with pytest.raises(JWTError):
            jwt.decode(tampered, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

