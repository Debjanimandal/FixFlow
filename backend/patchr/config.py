"""
FixFlow API — Application Settings

All configuration is loaded from environment variables.
Never hardcode secrets. Always use .env for local dev.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────
    environment: str = "development"
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://patchr:patchr_dev@localhost:5432/patchr"

    # ── Redis ──────────────────────────────────────────────────────
    redis_url: str = "redis://:patchr_dev@localhost:6379/0"

    # ── Owner Auth ─────────────────────────────────────────────────
    owner_password: str = "change_me"
    jwt_secret: str = "change_me_jwt_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # ── NVIDIA NIM ─────────────────────────────────────────────────
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.1-70b-instruct"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # ── GitHub Integration ─────────────────────────────────────────────────────
    # Phase 2: Use a Personal Access Token for initial integration.
    # Permissions needed: repo (read), deployments (read)
    github_token: str = ""
    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_webhook_secret: str = ""

    # ── GitHub OAuth (for dashboard login) ───────────────────────────────────
    github_client_id: str = ""
    github_client_secret: str = ""
    # Optional: comma-separated GitHub usernames allowed to log in.
    # Leave empty to allow ANY GitHub user who completes OAuth.
    github_allowed_users: str = ""  # e.g. "alice,bob"

    # ── Vercel Integration ─────────────────────────────────────────
    vercel_access_token: str = ""
    vercel_team_id: str = ""
    vercel_webhook_secret: str = ""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
    # ── Vercel OAuth (Integration — for user-level Vercel access) ───────────────
    # Create a Vercel Integration (not App) at:
    #   https://vercel.com/{team}/settings/integrations → Integrations Console → Create
    # This gives an oac_xxx Client ID with full API access (not just identity).
    vercel_client_id: str = ""
    vercel_client_secret: str = ""
    vercel_integration_slug: str = ""   # the slug set when creating the integration

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


_settings_cache: "Settings | None" = None
_settings_env_mtime: float = 0.0


def get_settings() -> "Settings":
    """Return cached settings. Re-reads if .env was modified since last load."""
    global _settings_cache, _settings_env_mtime
    import os
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        mtime = os.path.getmtime(env_path)
    except OSError:
        mtime = 0.0
    if _settings_cache is None or mtime != _settings_env_mtime:
        _settings_cache = Settings()
        _settings_env_mtime = mtime
    return _settings_cache


def clear_settings_cache() -> None:
    """Force a reload on next get_settings() call."""
    global _settings_cache
    _settings_cache = None
