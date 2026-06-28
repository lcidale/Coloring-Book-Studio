"""
Unit U2 tests — AppSettings new columns + migration idempotence.

Covers:
1. AppSettings row can be created and read back with all four new fields
   defaulting to empty strings (new-table path via the async_engine fixture).
2. Re-running _apply_column_migrations twice is a no-op (no error).
3. Legacy-table simulation: create app_settings without the four new columns,
   run _apply_column_migrations, assert all four columns now exist via PRAGMA.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import _apply_column_migrations
from app.models import AppSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NEW_COLUMNS = {"concept_provider", "concept_model", "prompt_provider", "prompt_model"}


def _get_column_names(conn) -> set[str]:
    """Return the set of column names for app_settings via PRAGMA (SQLite)."""
    rows = conn.exec_driver_sql("PRAGMA table_info(app_settings)").fetchall()
    return {row[1] for row in rows}


# ---------------------------------------------------------------------------
# Test 1: new-table path — all four fields default to empty string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_appsettings_new_columns_default_empty(async_engine):
    """
    Create an AppSettings row via the ORM and read it back; the four new
    fields must exist and default to empty strings.
    """
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        row = AppSettings(id="global")
        session.add(row)
        await session.commit()

    async with factory() as session:
        fetched = await session.get(AppSettings, "global")
        assert fetched is not None
        assert fetched.concept_provider == ""
        assert fetched.concept_model == ""
        assert fetched.prompt_provider == ""
        assert fetched.prompt_model == ""


# ---------------------------------------------------------------------------
# Test 2: running _apply_column_migrations twice is a no-op
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_column_migrations_idempotent(async_engine):
    """
    Calling _apply_column_migrations twice on a freshly-created schema must
    not raise any error — the PRAGMA check prevents duplicate ADD COLUMN.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(_apply_column_migrations)

    # Second call — should be completely silent.
    async with async_engine.begin() as conn:
        await conn.run_sync(_apply_column_migrations)


# ---------------------------------------------------------------------------
# Test 3: legacy table simulation — columns are added by migration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legacy_table_migration_adds_columns(storage_tmp):
    """
    Simulate an old SQLite database that has app_settings but without the four
    new LLM-selection columns.  After running _apply_column_migrations the
    columns must be present in PRAGMA table_info.
    """
    db_path = storage_tmp / "legacy_test.sqlite"
    legacy_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    try:
        # Create the table manually in its "old" form — only the original three
        # columns (id, image_provider, image_model, updated_at) — no LLM cols.
        async with legacy_engine.begin() as conn:
            await conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    id          VARCHAR PRIMARY KEY,
                    image_provider VARCHAR(50) DEFAULT 'replicate',
                    image_model    VARCHAR(200) DEFAULT '',
                    updated_at     DATETIME
                )
                """
            )
            # Also create the other tables referenced by _COLUMN_MIGRATIONS so
            # PRAGMA doesn't fail on missing tables.
            await conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS page_versions (
                    id VARCHAR PRIMARY KEY,
                    page_id VARCHAR,
                    version_num INTEGER,
                    image_path VARCHAR,
                    prompt TEXT,
                    notes TEXT,
                    created_at DATETIME
                )
                """
            )
            await conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS text_layers (
                    id VARCHAR PRIMARY KEY,
                    page_id VARCHAR,
                    label VARCHAR(200),
                    content TEXT,
                    font_name VARCHAR(100),
                    font_size_pt INTEGER,
                    x_pct REAL,
                    y_pct REAL,
                    visible INTEGER
                )
                """
            )

        # Verify the new columns are absent before the migration.
        async with legacy_engine.begin() as conn:
            pre_cols = await conn.run_sync(_get_column_names)
        assert _NEW_COLUMNS.isdisjoint(pre_cols), (
            f"Expected new columns to be absent before migration; found: {_NEW_COLUMNS & pre_cols}"
        )

        # Run the migration.
        async with legacy_engine.begin() as conn:
            await conn.run_sync(_apply_column_migrations)

        # Verify all four new columns now exist.
        async with legacy_engine.begin() as conn:
            post_cols = await conn.run_sync(_get_column_names)
        assert _NEW_COLUMNS.issubset(post_cols), (
            f"Expected all new columns after migration; missing: {_NEW_COLUMNS - post_cols}"
        )

    finally:
        await legacy_engine.dispose()
