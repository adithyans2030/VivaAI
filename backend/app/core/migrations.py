"""Apply Alembic migrations at startup, adopting databases created before migrations existed."""

import asyncio
from pathlib import Path
from typing import Optional, Set

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import logger

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# Tables introduced by each revision, used to recognise unversioned databases built by create_all().
BASELINE_TABLES = {"users", "subjects", "documents", "viva_sessions", "turns", "audit_logs", "score_overrides"}
AUTH_STATE_TABLES = {"revoked_tokens", "ws_tickets", "rate_limit_events"}


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["configure_logger"] = False
    return cfg


def revision_for_unversioned(tables: Set[str]) -> Optional[str]:
    """Which revision an unversioned schema already matches (None = empty DB, migrate from scratch)."""
    if "alembic_version" in tables or not tables & BASELINE_TABLES:
        return None
    return "0002" if AUTH_STATE_TABLES <= tables else "0001"


async def upgrade_database(engine: AsyncEngine, database_url: str) -> None:
    """Bring the database to the latest revision. Never drops existing data."""
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))

    cfg = _alembic_config(database_url)
    stamp = revision_for_unversioned(tables)

    def run() -> None:
        # Alembic's async env calls asyncio.run(), so it needs a thread without a running loop.
        if stamp:
            logger.info(f"Existing database has no migration history; recording it as revision {stamp}")
            command.stamp(cfg, stamp)
        command.upgrade(cfg, "head")

    await asyncio.to_thread(run)
