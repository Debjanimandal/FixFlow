"""
Alembic environment configuration for async SQLAlchemy.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from patchr.config import get_settings
from patchr.db.models import Base

config = context.config
settings = get_settings()

# Override the sqlalchemy.url with our async-compatible URL
# Strip ssl=require (handled via connect_args) and escape % for configparser
_db_url_for_alembic = settings.database_url
_db_url_for_alembic = _db_url_for_alembic.replace("?ssl=require", "").replace("&ssl=require", "")
_db_url_for_alembic = _db_url_for_alembic.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _db_url_for_alembic)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Build connect_args for SSL (same logic as session.py)
    connect_args: dict = {}
    db_url = settings.database_url
    if "?ssl=require" in db_url or "&ssl=require" in db_url:
        import ssl as _ssl_module
        _ssl_ctx = _ssl_module.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = _ssl_module.CERT_NONE
        connect_args["ssl"] = _ssl_ctx

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
