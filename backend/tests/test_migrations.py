"""Startup migrations: fresh databases, and adopting ones created by create_all() before Alembic."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import Base
from app.core.migrations import AUTH_STATE_TABLES, BASELINE_TABLES, revision_for_unversioned, upgrade_database


async def _tables_and_version(url: str) -> tuple:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
        version = (await conn.execute(text("select version_num from alembic_version"))).scalar_one()
    await engine.dispose()
    return tables, version


@pytest.mark.parametrize(
    ("tables", "expected"),
    [
        (set(), None),
        ({"alembic_version", *BASELINE_TABLES}, None),
        (set(BASELINE_TABLES), "0001"),
        (BASELINE_TABLES | AUTH_STATE_TABLES, "0002"),
    ],
)
def test_revision_for_unversioned(tables: set, expected: str) -> None:
    assert revision_for_unversioned(tables) == expected


async def test_fresh_database_is_migrated_to_head(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}"
    engine = create_async_engine(url)
    await upgrade_database(engine, url)
    await engine.dispose()

    tables, version = await _tables_and_version(url)
    assert version == "0002"
    assert BASELINE_TABLES | AUTH_STATE_TABLES <= tables


async def test_pre_migration_database_keeps_its_data(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}"
    engine = create_async_engine(url)
    baseline = [t for t in Base.metadata.sorted_tables if t.name in BASELINE_TABLES]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=baseline))
        await conn.execute(
            text(
                "insert into users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at) "
                "values ('u1', 'kept@vivaiq.edu', 'x', 'Kept', 'STUDENT', 1, '2026-01-01', '2026-01-01')"
            )
        )

    await upgrade_database(engine, url)  # stamps 0001, then applies 0002

    async with engine.connect() as conn:
        assert (await conn.execute(text("select email from users"))).scalar_one() == "kept@vivaiq.edu"
    await engine.dispose()
    tables, version = await _tables_and_version(url)
    assert version == "0002" and AUTH_STATE_TABLES <= tables


async def test_database_already_holding_new_tables_is_stamped_at_head(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'current.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await upgrade_database(engine, url)  # must not try to re-create the auth tables
    await engine.dispose()
    assert (await _tables_and_version(url))[1] == "0002"
