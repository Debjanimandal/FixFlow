"""
Database Session — async SQLAlchemy engine and session factory.
"""

from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from patchr.config import get_settings

settings = get_settings()

# Supabase's managed connection pooler (port 6543) does not support
# SQLAlchemy's built-in connection pool — use NullPool for it.
# Direct Supabase connections (db.xxx.supabase.co:5432) work fine with a pool.
_is_supabase = "supabase.co" in settings.database_url or "supabase.com" in settings.database_url
_is_supabase_pooler = "pooler.supabase.com" in settings.database_url
_is_sqlite = settings.database_url.startswith("sqlite")

# asyncpg does not accept ?ssl=require in the URL string — strip it and
# pass ssl as a connect_arg instead.
_db_url = settings.database_url
_connect_args: dict = {}
_ssl_required = False
if "?ssl=require" in _db_url or "&ssl=require" in _db_url:
    _db_url = _db_url.replace("?ssl=require", "").replace("&ssl=require", "")
    _ssl_required = True

if _ssl_required:
    import ssl as _ssl_module
    _ssl_ctx = _ssl_module.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl_module.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

# Increase timeout for cloud DB connections (Supabase can be slow on first connect)
if not _is_sqlite:
    _connect_args["timeout"] = 15

# Supabase pooler (port 6543) doesn't support prepared statements —
# asyncpg needs statement_cache_size=0 to disable them
if _is_supabase_pooler:
    _connect_args["statement_cache_size"] = 0

if _is_supabase_pooler:
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(
        _db_url,
        echo=settings.is_development,
        poolclass=NullPool,
        connect_args=_connect_args,
    )
elif _is_supabase:
    # Direct Supabase connection — normal pool works fine
    engine = create_async_engine(
        _db_url,
        echo=settings.is_development,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args=_connect_args,
    )
elif _is_sqlite:
    # SQLite (used in tests) — no pool_size/max_overflow
    from sqlalchemy.pool import StaticPool
    engine = create_async_engine(
        _db_url,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(
        _db_url,
        echo=settings.is_development,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args=_connect_args,
    )


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_or_503() -> AsyncGenerator[AsyncSession, None]:
    """
    Same as get_db but catches connection errors and raises HTTP 503.
    Use this on endpoints where the DB being unreachable should return a
    clean JSON error to the client instead of a broken connection.
    """
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except HTTPException:
        raise
    except Exception as e:
        # IntegrityError / OperationalError from bad SQL should NOT be reported as
        # "Supabase unavailable" — only true connection errors should be.
        from sqlalchemy.exc import IntegrityError, OperationalError
        if isinstance(e, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail="A record with that value already exists. The repository may already be connected.",
            )
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {type(e).__name__}. Check your network connection.",
        )


async def init_db() -> None:
    """Create all database tables automatically if they do not exist."""
    from patchr.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
