"""
Auth Router — GitHub OAuth login + Vercel OAuth linking + legacy password login.

GitHub OAuth flow:
  1. Frontend redirects user to GET /auth/github
  2. GitHub redirects back to GET /auth/github/callback?code=xxx
  3. Backend exchanges code for GitHub access token
  4. Backend fetches GitHub user profile
  5. Backend issues a PatchR JWT and redirects frontend to /dashboard?token=xxx
  6. Frontend stores token in localStorage

Vercel OAuth flow (account linking — requires an existing PatchR session):
  1. Frontend calls POST /auth/vercel/start (Bearer JWT) → { redirect_url }
  2. Frontend navigates the browser to redirect_url, i.e. GET /auth/vercel?link_token=...
     (a plain navigation can't carry an Authorization header, so identity is
     handed off via this short-lived, purpose-scoped link_token instead)
  3. Backend redirects to Vercel Integration authorization URL, embedding
     user_id (validated from link_token) in a state cookie
  4. Vercel redirects back to GET /auth/vercel/callback?code=xxx&state=xxx
  5. Backend exchanges code → Vercel access token via POST /v2/oauth/access_token
     (Integration OAuth — token has full API access to user's Vercel resources)
  6. Backend stores token + team_id per-user, redirects to /dashboard/settings?vercel=connected

Legacy:
  POST /auth/login  { password } → { access_token }   (kept for backwards compat)
"""

import secrets
import urllib.parse
import uuid as _uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patchr.auth import (
    create_access_token,
    create_access_token_for_user,
    create_vercel_link_token,
    decode_vercel_link_token,
    get_current_owner,
    verify_owner_password,
)
from patchr.config import Settings, get_settings
from patchr.db.models import User
from patchr.db.session import get_db
from patchr.schemas.api import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
OAUTH_STATE_COOKIE = "patchr_oauth_state"
GITHUB_CALLBACK_PATH = "/api/v1/auth/github/callback"

# Vercel Integration OAuth
# Use a Vercel Integration (oac_ client ID) — NOT a Vercel App (cl_ client ID).
# Integration tokens have full API access; App tokens are identity/OIDC only.
# Create at: https://vercel.com/{team}/settings/integrations → Integrations Console → Create
VERCEL_TOKEN_URL = "https://api.vercel.com/v2/oauth/access_token"
VERCEL_CALLBACK_PATH = "/api/v1/auth/vercel/callback"
VERCEL_STATE_COOKIE = "patchr_vercel_state"


def _login_error_redirect(settings: Settings, error: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.frontend_url}/login?error={urllib.parse.quote(error)}"
    )


def _github_user_is_allowed(settings: Settings, github_login: str) -> bool:
    """Apply the optional comma-separated GitHub user allow-list."""
    allowed = settings.github_allowed_users.strip()
    if not allowed:
        return True
    allowed_logins = {user.strip().lower() for user in allowed.split(",") if user.strip()}
    return github_login.lower() in allowed_logins


async def _get_user_by_id(db, user_id: str | None) -> "User | None":
    """
    Look up a User by the user_id string stored in JWT claims.
    Handles two formats:
      - Proper UUID string  → look up by User.id
      - "github_{numeric}"  → look up by User.github_id (stateless fallback session)
    Returns None if not found or user_id is None/invalid.
    """
    if not user_id:
        return None
    if user_id.startswith("github_"):
        try:
            gh_id = int(user_id[len("github_"):])
        except ValueError:
            return None
        result = await db.execute(select(User).where(User.github_id == gh_id))
        return result.scalar_one_or_none()
    try:
        uid = _uuid.UUID(user_id)
    except (ValueError, AttributeError):
        return None
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


def _get_request_origin(request: Request, settings: Settings) -> str:
    """
    Derive the scheme+host origin of the current request.

    This is used to build OAuth redirect_uri values that match the domain
    the browser originally navigated to. It ensures cookies set during the
    OAuth initiation will be present when the provider redirects back.

    Prefers the `X-Forwarded-Proto` / `X-Forwarded-Host` headers (set by
    ngrok, Cloudflare, or any reverse proxy) so that the correct public
    HTTPS URL is used even when the backend is listening on plain HTTP
    behind a tunnel. Falls back to the request's own URL.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    # Remove any trailing port from host if it's the default for the scheme
    origin = f"{proto}://{host}"
    return origin.rstrip("/")


# ─── GitHub OAuth ─────────────────────────────────────────────────────────────


@router.get("/github", summary="Start GitHub OAuth login")
async def github_login(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """
    Redirect the user to GitHub to authorize PatchR.
    Frontend navigates here directly — this returns a 302 redirect to GitHub.

    The redirect_uri sent to GitHub is derived from the request's own origin
    (scheme + host) so that the state cookie and callback stay on the same
    domain. This avoids the common problem where the cookie is set on
    localhost but the callback comes back on the ngrok tunnel domain.
    """
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env",
        )

    # Determine the base URL for the callback. Use the same origin the
    # browser used to reach *this* endpoint, so the state cookie domain
    # and the callback redirect land on the same host.
    request_origin = _get_request_origin(request, settings)

    oauth_state = secrets.token_urlsafe(32)
    params = urllib.parse.urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": f"{request_origin}{GITHUB_CALLBACK_PATH}",
        "scope": "read:user user:email repo",
        "allow_signup": "true",
        "state": oauth_state,
    })
    response = RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{params}")
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=oauth_state,
        httponly=True,
        secure=request_origin.startswith("https"),
        samesite="lax",
        max_age=600,
        path="/",
    )
    # Allow ngrok tunnel traffic to bypass the browser interstitial warning page
    response.headers["ngrok-skip-browser-warning"] = "1"
    return response


@router.get("/github/callback", summary="GitHub OAuth callback")
async def github_callback(
    request: Request,
    code: str = Query(..., description="OAuth code from GitHub"),
    state: str | None = Query(default=None, description="OAuth CSRF state"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """
    GitHub redirects here after the user authorizes.
    Exchanges code → GitHub token → user profile → PatchR JWT.
    Then redirects to frontend /dashboard?token=<jwt>.
    """
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return _login_error_redirect(settings, "GitHub sign-in expired or could not be verified. Please try again.")

    async with httpx.AsyncClient() as client:
        # 1. Exchange code for GitHub access token
        # redirect_uri in the token exchange MUST match what was sent in the
        # authorize request. Since we derive it from the request origin in
        # both places, it will always be consistent.
        request_origin = _get_request_origin(request, settings)
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{request_origin}{GITHUB_CALLBACK_PATH}",
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = token_resp.json()
        github_access_token = token_data.get("access_token")

        if not github_access_token:
            error = token_data.get("error_description", "Failed to get access token from GitHub")
            return _login_error_redirect(settings, error)

        # 2. Fetch GitHub user profile
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        github_user = user_resp.json()

    github_id = github_user.get("id")
    github_login_name: str = github_user.get("login", "")
    github_name: str = github_user.get("name") or github_login_name
    github_avatar: str = github_user.get("avatar_url", "")

    if not github_id or not github_login_name:
        return _login_error_redirect(settings, "Could not fetch GitHub user profile")

    if not _github_user_is_allowed(settings, github_login_name):
        return _login_error_redirect(settings, f"GitHub user '{github_login_name}' is not authorized")

    # Upsert the GitHub identity into the DB.
    # If the DB is unreachable, fall back to a JWT-only session (no persistence)
    # so the user can still access the dashboard.
    import logging
    from datetime import datetime, timezone

    user_id_str = f"github_{github_id}"  # fallback ID when DB unavailable
    is_owner_flag = True

    try:
        result = await db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                github_id=github_id,
                github_login=github_login_name,
                github_name=github_name,
                github_email=github_user.get("email"),
                github_avatar_url=github_avatar,
                is_owner=True,
                is_active=True,
            )
            db.add(user)
        else:
            user.github_login = github_login_name
            user.github_name = github_name
            user.github_email = github_user.get("email")
            user.github_avatar_url = github_avatar

        if not user.is_active:
            return _login_error_redirect(settings, "This PatchR account has been disabled")

        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        user_id_str = str(user.id)
        is_owner_flag = user.is_owner

    except Exception as db_err:
        # DB is unreachable — log and continue with a stateless JWT session
        logging.warning(
            f"DB unavailable during OAuth callback for {github_login_name}: {db_err}. "
            "Issuing stateless JWT."
        )

    # 4. Issue PatchR JWT
    jwt_token = create_access_token_for_user(
        settings,
        user_id=user_id_str,
        github_login=github_login_name,
        github_name=github_name,
        github_avatar=github_avatar,
        github_access_token=github_access_token,
        is_owner=is_owner_flag,
    )
    response = RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?token={urllib.parse.quote(jwt_token)}"
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response


@router.post("/vercel/start", summary="Mint a short-lived token to start Vercel OAuth")
async def vercel_start(
    current_user: dict = Depends(get_current_owner),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Authenticated (Bearer-token) endpoint the frontend calls via `fetch()` before
    redirecting the browser to `GET /auth/vercel`. This is necessary because a
    plain browser navigation cannot carry an `Authorization` header, so the
    identity of the logged-in user has to be handed off through a short-lived,
    single-purpose token instead.

    Returns `{ "link_token": "...", "redirect_url": "/api/v1/auth/vercel?link_token=..." }`.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your session has no persisted user record. Please sign in again with GitHub.",
        )
    link_token = create_vercel_link_token(settings, user_id=user_id)
    redirect_url = (
        f"{settings.api_base_url.rstrip('/')}/api/v1/auth/vercel"
        f"?link_token={urllib.parse.quote(link_token)}"
    )
    return {"link_token": link_token, "redirect_url": redirect_url}


@router.get("/vercel", summary="Start Vercel OAuth connection")
async def vercel_login(
    request: Request,
    link_token: str = Query(..., description="Short-lived token minted by POST /auth/vercel/start"),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """
    Redirect the user to Vercel to authorize PatchR.

    Requires a `link_token` (from `POST /auth/vercel/start`) rather than a
    Bearer header, since this route is reached via a plain browser redirect
    which cannot carry custom headers. The link token is validated here and
    its user_id is carried forward (embedded in the state cookie) so the
    callback knows whose account to attach the Vercel token to.
    """
    if not settings.vercel_client_id or not settings.vercel_integration_slug:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vercel Integration is not configured. Set VERCEL_CLIENT_ID and VERCEL_INTEGRATION_SLUG in .env",
        )

    user_id = decode_vercel_link_token(link_token, settings)
    if not user_id:
        return _login_error_redirect(
            settings, "Your Vercel connection link expired or is invalid. Please try connecting again."
        )

    oauth_state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.api_base_url.rstrip('/')}{VERCEL_CALLBACK_PATH}"

    # Build the Vercel Integration authorization URL.
    # Format: https://vercel.com/integrations/{slug}/new?state={state}
    # The redirect_uri is registered in the integration settings on Vercel.
    params = urllib.parse.urlencode({
        "state": oauth_state,
        "redirect_uri": redirect_uri,
    })
    vercel_integration_url = (
        f"https://vercel.com/integrations/{settings.vercel_integration_slug}/new?{params}"
    )

    response = RedirectResponse(url=vercel_integration_url)
    # Store state + user_id in a short-lived cookie for callback validation.
    response.set_cookie(
        key=VERCEL_STATE_COOKIE,
        value=f"{oauth_state}:{user_id}",
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/vercel/callback", summary="Vercel OAuth callback")
async def vercel_callback(
    request: Request,
    code: str = Query(..., description="OAuth code from Vercel"),
    state: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """
    Vercel redirects here after the user authorizes.
    Exchanges code → Vercel access token → stores on user record.
    Then redirects to frontend /dashboard/settings?vercel=connected.
    """
    if not settings.vercel_client_id or not settings.vercel_client_secret:
        raise HTTPException(status_code=503, detail="Vercel Integration not configured")

    # Validate state + extract user_id from cookie
    cookie_value = request.cookies.get(VERCEL_STATE_COOKIE, "")
    parts = cookie_value.split(":", 1)
    if len(parts) != 2:
        return RedirectResponse(
            url=f"{settings.frontend_url}/dashboard/settings?vercel=error&reason=invalid_state"
        )
    expected_state, user_id = parts

    if not state or not secrets.compare_digest(state, expected_state):
        return RedirectResponse(
            url=f"{settings.frontend_url}/dashboard/settings?vercel=error&reason=state_mismatch"
        )

    redirect_uri = f"{settings.api_base_url.rstrip('/')}{VERCEL_CALLBACK_PATH}"

    # Exchange code for Vercel access token via Integration OAuth endpoint
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            VERCEL_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.vercel_client_id,
                "client_secret": settings.vercel_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )

        if token_resp.status_code != 200:
            return RedirectResponse(
                url=f"{settings.frontend_url}/dashboard/settings?vercel=error&reason=token_exchange_failed"
            )

        token_data = token_resp.json()
        vercel_access_token = token_data.get("access_token")
        # Integration OAuth also returns the team_id the user authorized for
        vercel_team_id = token_data.get("team_id") or token_data.get("teamId")

        if not vercel_access_token:
            return RedirectResponse(
                url=f"{settings.frontend_url}/dashboard/settings?vercel=error&reason=no_token"
            )

    # Store token + team_id per user
    # user_id may be a real UUID string or the fallback "github_{github_id}" format
    # from when the DB was unavailable at login time — handle both.
    user = await _get_user_by_id(db, user_id)
    if not user and user_id.startswith("github_"):
        # User was never persisted (full fallback session) — create them now
        try:
            gh_numeric_id_int = int(user_id[len("github_"):])
        except ValueError:
            gh_numeric_id_int = None
        user = User(
            github_id=gh_numeric_id_int,
            github_login="",
            is_owner=True,
            is_active=True,
        )
        db.add(user)
        await db.flush()

    if not user:
        return RedirectResponse(
            url=f"{settings.frontend_url}/dashboard/settings?vercel=error&reason=user_not_found"
        )

    user.vercel_access_token = vercel_access_token
    # Store the team_id the integration was authorized for (needed for team projects)
    if vercel_team_id:
        user.vercel_team_id = vercel_team_id
    await db.commit()

    response = RedirectResponse(
        url=f"{settings.frontend_url}/dashboard/settings?vercel=connected"
    )
    response.delete_cookie(VERCEL_STATE_COOKIE, path="/")
    return response


@router.get("/vercel/status", summary="Check if current user has Vercel connected")
async def vercel_connection_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """Check if the current user has a Vercel OAuth token stored."""
    user_id = current_user.get("user_id")
    user = await _get_user_by_id(db, user_id)
    if user and user.vercel_access_token:
        return {"connected": True, "message": "Vercel account connected"}

    return {"connected": False, "message": "Vercel not connected. Click 'Connect Vercel' to authorize."}


@router.get("/me", summary="Get current user info from JWT")
async def get_me(current_user: dict = Depends(get_current_owner)):
    """Return the current user's profile from their JWT."""
    return current_user


# ─── Vercel Token (per-user) ──────────────────────────────────────────────────


@router.get("/vercel-token", summary="Check if user has a Vercel token saved")
async def get_vercel_token_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """Returns whether the user has a Vercel token saved (never exposes the actual token)."""
    user_id = current_user.get("user_id")
    user = await _get_user_by_id(db, user_id)
    if not user:
        return {"has_token": False}
    has = bool(user.vercel_access_token)
    token_preview = f"{user.vercel_access_token[:8]}…" if has else None
    return {"has_token": has, "token_preview": token_preview}


@router.put("/vercel-token", summary="Save the user's Vercel API token")
async def save_vercel_token(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_owner),
) -> dict:
    """
    Save or update the user's personal Vercel API token.
    Send { "token": "vcp_..." } to save, or { "token": "" } to remove.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="No user_id in token")

    token_value = body.get("token", "").strip()

    user = await _get_user_by_id(db, user_id)
    if not user:
        if user_id.startswith("github_"):
            try:
                gh_id = int(user_id[len("github_"):])
            except ValueError:
                gh_id = None
            user = User(
                github_id=gh_id,
                github_login=current_user.get("login", ""),
                is_owner=True,
                is_active=True,
            )
            db.add(user)
            await db.flush()
        else:
            raise HTTPException(status_code=404, detail="User not found")

    user.vercel_access_token = token_value or None
    await db.commit()

    return {
        "success": True,
        "has_token": bool(token_value),
        "message": "Vercel token saved." if token_value else "Vercel token removed.",
    }


# ─── Legacy password login (backwards compat) ─────────────────────────────────


@router.post("/login", response_model=TokenResponse, summary="Legacy password login")
async def login(body: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    """Single-owner password login. Still works alongside GitHub OAuth."""
    if not verify_owner_password(body.password, settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_access_token(settings)
    return TokenResponse(access_token=token)
