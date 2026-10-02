"""
Owner Authentication

PatchR Phase 1 uses single-owner auth: one password stored as env var.
No user database table. The owner is the operator of this instance.

Flow:
  POST /auth/login  { password } → { access_token }
  Protected routes use: Depends(get_current_owner)

Later: replace with NextAuth.js / GitHub OAuth for multi-user support.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from patchr.config import Settings, get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=True)


def verify_owner_password(plain_password: str, settings: Settings) -> bool:
    """
    Check if the provided password matches the configured owner password.
    The owner password is stored in plaintext in env for simplicity.
    bcrypt hashing is available for production hardening via hash_password().
    """
    return plain_password == settings.owner_password


def create_access_token(settings: Settings) -> str:
    """Create a signed JWT for the owner (legacy password login)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": "owner",
        "is_owner": True,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token_for_user(
    settings: Settings,
    user_id: str,
    github_login: str,
    github_name: str = "",
    github_avatar: str = "",
    github_access_token: str = "",
    is_owner: bool = True,
) -> str:
    """Create a signed JWT for a persisted GitHub OAuth user."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": "owner" if is_owner else "user",
        "user_id": user_id,
        "is_owner": is_owner,
        "github_login": github_login,
        "github_name": github_name,
        "github_avatar": github_avatar,
        "github_access_token": github_access_token,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_owner(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    FastAPI dependency: validates Bearer token.
    Returns a dict with sub + optional github fields. Raises 401 otherwise.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub: str = payload.get("sub")
        if sub != "owner":
            raise credentials_exception
        return {
            "sub": sub,
            "user_id": payload.get("user_id"),
            "is_owner": payload.get("is_owner", sub == "owner"),
            "github_login": payload.get("github_login", ""),
            "github_name": payload.get("github_name", ""),
            "github_avatar": payload.get("github_avatar", ""),
            "github_access_token": payload.get("github_access_token", ""),
        }
    except JWTError:
        raise credentials_exception


def actor_name(current_user: dict) -> str:
    """Return a stable, human-readable audit actor for a JWT user."""
    github_login = current_user.get("github_login")
    return f"github:{github_login}" if github_login else "owner"


def decode_token(token: str, settings: Settings) -> dict:
    """Decode a PatchR JWT token without raising — returns empty dict on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return {}


VERCEL_LINK_TOKEN_PURPOSE = "vercel_link"


def create_vercel_link_token(settings: Settings, user_id: str) -> str:
    """
    Create a short-lived, purpose-scoped token used ONLY to carry the current
    user's identity through the Vercel OAuth browser-redirect round trip.

    A plain browser navigation (e.g. `<a href>` or `window.location.href = ...`)
    cannot send an `Authorization: Bearer` header, so we cannot protect
    `GET /auth/vercel` with the normal `get_current_owner` dependency. Instead,
    the frontend first calls `POST /auth/vercel/start` (an authenticated,
    fetch-based request that DOES carry the Bearer header) to mint this token,
    then navigates to `/auth/vercel?link_token=...`.

    The token is deliberately narrow: 5 minute expiry, single declared
    purpose, and only a user_id claim — it cannot be used to authenticate
    API requests generally.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {
        "purpose": VERCEL_LINK_TOKEN_PURPOSE,
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_vercel_link_token(token: str, settings: Settings) -> str | None:
    """Validate a Vercel link token and return the embedded user_id, or None."""
    payload = decode_token(token, settings)
    if payload.get("purpose") != VERCEL_LINK_TOKEN_PURPOSE:
        return None
    return payload.get("user_id")
