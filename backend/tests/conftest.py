"""
Shared pytest fixtures for the backend test suite.

Key design decisions:
- A temporary SQLite DB is created per-test via a fresh engine so tests are isolated.
- STORAGE_DIR is pointed at a tmp directory BEFORE the app module is imported; the
  app reads it at module load time, so we patch via the env and monkeypatch the
  module-level Path objects that were already resolved.
- The ASGI client is built with httpx.ASGITransport so no real server port is used.
- The paid generate_line_art call is monkeypatched to return a synthetic local PNG.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Event-loop policy — pytest-asyncio 0.24 uses per-test loops by default;
# we keep that default (no custom policy needed).
# ---------------------------------------------------------------------------
pytest_plugins = ("pytest_asyncio",)


# ---------------------------------------------------------------------------
# Synthetic image helpers
# ---------------------------------------------------------------------------

def make_pure_bw_png(path: Path, width: int = 200, height: int = 200, dpi: int = 300) -> Path:
    """
    Create a pure black-and-white test PNG (white background with a black rectangle).
    No gray pixels — passes the analyse() is_pure_bw check.
    """
    img = Image.new("L", (width, height), color=255)
    # Draw a solid black rectangle in the centre
    px = img.load()
    for y in range(height // 4, 3 * height // 4):
        for x in range(width // 4, 3 * width // 4):
            px[x, y] = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG", dpi=(dpi, dpi))
    return path


def make_gray_png(path: Path, width: int = 200, height: int = 200, dpi: int = 72) -> Path:
    """
    Create a grayscale PNG with lots of mid-gray pixels (fails is_pure_bw).
    """
    img = Image.new("L", (width, height), color=128)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG", dpi=(dpi, dpi))
    return path


def make_speckled_png(path: Path, width: int = 200, height: int = 200, dpi: int = 300) -> Path:
    """
    Pure-white image with a few tiny isolated single-pixel black specks.
    After despeckle(min_size=12) these should be erased.
    """
    img = Image.new("L", (width, height), color=255)
    px = img.load()
    # Plant isolated 1-pixel specks
    for x, y in [(10, 10), (50, 50), (100, 100), (150, 150), (180, 30)]:
        px[x, y] = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG", dpi=(dpi, dpi))
    return path


def make_bordered_png(path: Path, border: int = 40, dpi: int = 300) -> Path:
    """
    White canvas with a thick uniform white border surrounding a black rectangle.
    autocrop() should trim the border.
    """
    size = 300
    img = Image.new("L", (size, size), color=255)
    px = img.load()
    # Draw content only inside the border
    for y in range(border + 5, size - border - 5):
        for x in range(border + 5, size - border - 5):
            px[x, y] = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG", dpi=(dpi, dpi))
    return path


# ---------------------------------------------------------------------------
# Storage tmp dir fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_tmp(tmp_path: Path) -> Path:
    """Return a temporary storage directory with the standard sub-layout."""
    sd = tmp_path / "storage"
    (sd / "books").mkdir(parents=True, exist_ok=True)
    return sd


# ---------------------------------------------------------------------------
# Async DB fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def async_engine(storage_tmp: Path):
    """Ephemeral async SQLite engine per test."""
    db_path = storage_tmp / "test.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    # Import Base after STORAGE_DIR is set to ensure the module picks up the tmp path.
    from app.database import Base  # noqa: PLC0415
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a single async DB session for a test; rolls back on exit."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# ASGI / httpx client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(storage_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTPX client wired to the FastAPI app with:
      - a temp storage dir
      - a temp in-memory SQLite DB (per-test isolation)
      - generate_line_art monkeypatched to return a synthetic local PNG
    """
    # Must set the env var before importing anything that reads it at module level.
    monkeypatch.setenv("STORAGE_DIR", str(storage_tmp))

    # Re-point module-level STORAGE_DIR constants that were already resolved.
    import app.database as db_mod
    import app.routers.books as books_mod
    import app.routers.export as export_mod
    import app.routers.generate as gen_mod
    import app.routers.jobs as jobs_mod
    import app.main as main_mod
    import app.services.storage as storage_mod
    import app.services.vectorize as vectorize_mod

    monkeypatch.setattr(db_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(db_mod, "DB_PATH", storage_tmp / "test.sqlite")
    monkeypatch.setattr(gen_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(jobs_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(export_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(main_mod, "STORAGE_DIR", storage_tmp)
    # app.services.storage.STORAGE_DIR was never repointed here, so any code
    # calling storage.get_bytes()/exists() on a file the fake generator wrote
    # (below) could silently resolve against a stale path from whichever test
    # first imported this module in the session, rather than THIS test's tmp
    # dir — found while adding the use-as-reference endpoint, the first code
    # path to read back generated bytes via storage.get_bytes() in a test.
    monkeypatch.setattr(storage_mod, "STORAGE_DIR", storage_tmp)
    # Same class of gap: vectorize_page_by_key()'s local-backend branch
    # resolves paths against its own module-level _STORAGE_DIR, not
    # app.services.storage's — found while switching the generate routers
    # from vectorize_page() to the storage-aware vectorize_page_by_key().
    monkeypatch.setattr(vectorize_mod, "_STORAGE_DIR", storage_tmp)

    # Rebuild the engine to point at the test DB.
    from sqlalchemy.ext.asyncio import create_async_engine as _make_engine, async_sessionmaker as _make_sm
    from app.database import Base

    test_db = storage_tmp / "test.sqlite"
    test_engine = _make_engine(f"sqlite+aiosqlite:///{test_db}", echo=False)
    test_sm = _make_sm(test_engine, expire_on_commit=False)

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_sm)
    # CRITICAL: jobs.py imports SessionLocal at module level into its own namespace.
    # The background task _run_pipeline() uses that local reference directly, so it
    # bypasses the db_mod patch above and hits the original (empty) DB.  Patch the
    # jobs module's own binding so the background task uses the test session factory.
    monkeypatch.setattr(jobs_mod, "SessionLocal", test_sm)

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override get_db dependency to use the test session factory.
    async def _override_get_db():
        async with test_sm() as session:
            yield session

    from app.main import app as fastapi_app
    from app.database import get_db

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    # Monkeypatch generate_line_art to avoid any network/API call.
    async def _fake_generate_line_art(
        positive_prompt, negative_prompt, book_id, page_id, version=1, **kwargs
    ) -> Path:
        out_dir = storage_tmp / "books" / book_id / "pages" / page_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"v{version:03d}.png"
        make_pure_bw_png(out)
        return out.relative_to(storage_tmp)

    import app.services.image_gen as igen_mod
    import app.routers.generate as gen_router_mod
    import app.routers.jobs as jobs_router_mod

    monkeypatch.setattr(igen_mod, "generate_line_art", _fake_generate_line_art)
    monkeypatch.setattr(gen_router_mod, "generate_line_art", _fake_generate_line_art)
    monkeypatch.setattr(jobs_router_mod, "generate_line_art", _fake_generate_line_art)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
    await test_engine.dispose()
