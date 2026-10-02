"""
Shared pytest fixtures for PatchR test suite.

Uses an in-memory SQLite database for fast, isolated tests.
No real network calls — GitHub/NVIDIA/Vercel APIs are mocked.
"""

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Set test env vars before importing app ────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OWNER_PASSWORD", "test-password")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-testing-only-not-prod")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_HOURS", "24")
os.environ.setdefault("NVIDIA_API_KEY", "nvapi-test-key")
os.environ.setdefault("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
os.environ.setdefault("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("VERCEL_ACCESS_TOKEN", "vcp_test_vercel_token")
os.environ.setdefault("VERCEL_WEBHOOK_SECRET", "test-vercel-secret")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from patchr.db.models import Base


# ── In-memory async SQLite engine ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    """Create an async in-memory SQLite engine for the test session."""
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )


@pytest_asyncio.fixture(scope="session")
async def create_tables(engine):
    """Create all DB tables once per test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(engine, create_tables):
    """Provide a fresh DB session per test, rolled back after each test."""
    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


# ── JWT helper ─────────────────────────────────────────────────────────────────

@pytest.fixture
def owner_token():
    """Generate a valid JWT token for the owner."""
    from patchr.auth import create_access_token
    from patchr.config import get_settings
    return create_access_token(get_settings())


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(db_session, owner_token):
    """Async HTTP client with DB session override."""
    from patchr.main import create_app
    from patchr.db.session import get_db
    from patchr.config import get_settings

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {owner_token}"},
    ) as client:
        yield client


# ── Webhook signature helper ───────────────────────────────────────────────────

def make_github_signature(payload: bytes, secret: str = "test-webhook-secret") -> str:
    """Compute valid GitHub HMAC-SHA256 signature for a payload."""
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def make_vercel_signature(payload: bytes, secret: str = "test-vercel-secret") -> str:
    """Compute valid Vercel HMAC-SHA1 signature for a payload."""
    mac = hmac.new(secret.encode(), payload, hashlib.sha1)
    return mac.hexdigest()


# ── Sample payloads ────────────────────────────────────────────────────────────

@pytest.fixture
def github_deployment_failure_payload():
    return {
        "action": "failure",
        "deployment_status": {
            "state": "failure",
            "description": "Build failed: TypeScript compile error",
            "environment": "production",
            "target_url": "https://vercel.com/deploys/dpl_test123",
        },
        "deployment": {
            "sha": "abc123def456abc123def456abc123def456abc1",
            "ref": "main",
            "environment": "production",
        },
        "repository": {
            "full_name": "AyushmanGupta21/webchat",
            "id": 12345,
            "default_branch": "main",
        },
    }


@pytest.fixture
def github_deployment_success_payload():
    return {
        "deployment_status": {
            "state": "success",
            "description": "Deployment successful",
            "environment": "production",
        },
        "deployment": {
            "sha": "abc123def456abc123def456abc123def456abc1",
            "ref": "main",
            "environment": "production",
        },
        "repository": {
            "full_name": "AyushmanGupta21/webchat",
            "id": 12345,
            "default_branch": "main",
        },
    }
