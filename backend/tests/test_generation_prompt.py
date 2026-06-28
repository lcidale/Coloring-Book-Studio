"""
Tests for U6: generation uses the page's SAVED prompt when present,
falling back to build_prompt only when the saved prompt is empty.

All tests exercise the async job path (POST /api/pages/{id}/generate
→ background _run_pipeline → _generate) via the ``client`` fixture from
conftest.py, which monkeypatches generate_line_art to avoid any real
API call and uses a temp SQLite DB per test.

We install a capturing wrapper on top of the existing monkeypatch so we
can assert what positive/negative prompt was passed to generate_line_art.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import make_pure_bw_png


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_book(client: AsyncClient, title: str = "Prompt Test Book") -> dict:
    resp = await client.post("/api/books", json={"title": title})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_page(
    client: AsyncClient,
    book_id: str,
    concept: str = "A dragon",
    prompt: str = "",
    negative_prompt: str = "",
) -> dict:
    # The create endpoint only accepts concept/sort_order; a saved prompt must
    # be set via PATCH so it persists on the page row the job later reloads.
    resp = await client.post(
        f"/api/pages/book/{book_id}",
        json={"concept": concept},
    )
    assert resp.status_code == 201, resp.text
    page = resp.json()
    if prompt or negative_prompt:
        patch = await client.patch(
            f"/api/pages/{page['id']}",
            json={"prompt": prompt, "negative_prompt": negative_prompt},
        )
        assert patch.status_code == 200, patch.text
        page = patch.json()
    return page


async def _enqueue_and_wait(client: AsyncClient, page_id: str) -> dict:
    """Enqueue generation and poll until the job reaches a terminal state."""
    gen_resp = await client.post(
        f"/api/pages/{page_id}/generate",
        json={"auto_cleanup": False, "vectorize": False},
    )
    assert gen_resp.status_code == 202, gen_resp.text
    job_id = gen_resp.json()["job_id"]

    for _ in range(30):
        await asyncio.sleep(0.1)
        job_resp = await client.get(f"/api/jobs/{job_id}")
        assert job_resp.status_code == 200
        status = job_resp.json()["status"]
        if status in ("done", "failed"):
            break

    return job_resp.json()


# ---------------------------------------------------------------------------
# Capturing fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def capturing_client(
    storage_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[tuple[AsyncClient, list[dict]], None]:
    """
    Like the base ``client`` fixture but also installs a capturing wrapper
    around generate_line_art so tests can inspect the exact prompts passed.

    Yields (client, calls) where ``calls`` is a list of dicts with keys
    ``positive_prompt`` and ``negative_prompt`` for each invocation.
    """
    monkeypatch.setenv("STORAGE_DIR", str(storage_tmp))

    import app.database as db_mod
    import app.routers.books as books_mod  # noqa: F401 — ensure import
    import app.routers.export as export_mod
    import app.routers.generate as gen_mod
    import app.routers.jobs as jobs_mod
    import app.main as main_mod

    monkeypatch.setattr(db_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(db_mod, "DB_PATH", storage_tmp / "test.sqlite")
    monkeypatch.setattr(gen_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(jobs_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(export_mod, "STORAGE_DIR", storage_tmp)
    monkeypatch.setattr(main_mod, "STORAGE_DIR", storage_tmp)

    from sqlalchemy.ext.asyncio import (
        create_async_engine as _make_engine,
        async_sessionmaker as _make_sm,
    )
    from app.database import Base

    test_db = storage_tmp / "test.sqlite"
    test_engine = _make_engine(f"sqlite+aiosqlite:///{test_db}", echo=False)
    test_sm = _make_sm(test_engine, expire_on_commit=False)

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_sm)
    monkeypatch.setattr(jobs_mod, "SessionLocal", test_sm)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db():
        async with test_sm() as session:
            yield session

    from app.main import app as fastapi_app
    from app.database import get_db

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    calls: list[dict] = []

    async def _capturing_generate_line_art(
        positive_prompt, negative_prompt, book_id, page_id, version=1, **kwargs
    ) -> Path:
        calls.append(
            {"positive_prompt": positive_prompt, "negative_prompt": negative_prompt}
        )
        out_dir = storage_tmp / "books" / book_id / "pages" / page_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"v{version:03d}.png"
        make_pure_bw_png(out)
        return out.relative_to(storage_tmp)

    import app.services.image_gen as igen_mod
    import app.routers.generate as gen_router_mod
    import app.routers.jobs as jobs_router_mod

    monkeypatch.setattr(igen_mod, "generate_line_art", _capturing_generate_line_art)
    monkeypatch.setattr(gen_router_mod, "generate_line_art", _capturing_generate_line_art)
    monkeypatch.setattr(jobs_router_mod, "generate_line_art", _capturing_generate_line_art)

    from httpx import ASGITransport, AsyncClient as _AC

    transport = ASGITransport(app=fastapi_app)
    async with _AC(transport=transport, base_url="http://test") as ac:
        yield ac, calls

    fastapi_app.dependency_overrides.clear()
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saved_positive_prompt_used_verbatim(capturing_client):
    """
    When a page has a non-empty saved prompt, generate_line_art receives
    that exact prompt and the page.prompt remains unchanged after generation.
    """
    client, calls = capturing_client

    book = await _create_book(client)
    saved_prompt = "MY HAND-WRITTEN POSITIVE PROMPT"
    page = await _add_page(
        client,
        book["id"],
        concept="A dragon",
        prompt=saved_prompt,
    )

    job = await _enqueue_and_wait(client, page["id"])
    assert job["status"] == "done", f"Job failed: {job}"

    assert len(calls) == 1, "generate_line_art should have been called once"
    assert calls[0]["positive_prompt"] == saved_prompt, (
        f"Expected saved prompt '{saved_prompt}', "
        f"got '{calls[0]['positive_prompt']}'"
    )


@pytest.mark.asyncio
async def test_empty_positive_prompt_falls_back_to_builder(capturing_client):
    """
    When a page has an empty saved prompt, generation falls back to
    build_prompt output (page.prompt becomes the built positive, which is
    non-empty given any non-empty concept).
    """
    client, calls = capturing_client

    book = await _create_book(client)
    page = await _add_page(
        client,
        book["id"],
        concept="A sleeping cat",
        prompt="",  # explicitly empty — must fall back
    )

    job = await _enqueue_and_wait(client, page["id"])
    assert job["status"] == "done", f"Job failed: {job}"

    assert len(calls) == 1
    # The built prompt should be non-empty (build_prompt always produces something
    # from a non-empty concept).
    assert calls[0]["positive_prompt"], (
        "Expected a non-empty built prompt when saved prompt is empty"
    )
    # And it must NOT equal the empty string that was saved.
    assert calls[0]["positive_prompt"] != "", (
        "generate_line_art received an empty positive prompt — fallback did not fire"
    )


@pytest.mark.asyncio
async def test_saved_negative_prompt_used_verbatim(capturing_client):
    """
    When a page has a non-empty saved negative_prompt, generate_line_art
    receives that exact negative prompt.
    """
    client, calls = capturing_client

    book = await _create_book(client)
    saved_negative = "NO COLOR NO SHADING NEVER"
    page = await _add_page(
        client,
        book["id"],
        concept="A robot",
        negative_prompt=saved_negative,
    )

    job = await _enqueue_and_wait(client, page["id"])
    assert job["status"] == "done", f"Job failed: {job}"

    assert len(calls) == 1
    assert calls[0]["negative_prompt"] == saved_negative, (
        f"Expected saved negative '{saved_negative}', "
        f"got '{calls[0]['negative_prompt']}'"
    )


@pytest.mark.asyncio
async def test_empty_negative_prompt_falls_back_to_builder(capturing_client):
    """
    When a page has an empty saved negative_prompt, generation falls back
    to the built negative from build_prompt.
    """
    client, calls = capturing_client

    book = await _create_book(client)
    page = await _add_page(
        client,
        book["id"],
        concept="A castle",
        negative_prompt="",  # empty — must fall back
    )

    job = await _enqueue_and_wait(client, page["id"])
    assert job["status"] == "done", f"Job failed: {job}"

    assert len(calls) == 1
    # build_prompt always produces a non-empty negative for coloring-book pages.
    assert calls[0]["negative_prompt"], (
        "Expected a non-empty built negative prompt when saved negative_prompt is empty"
    )


@pytest.mark.asyncio
async def test_both_saved_prompts_used_together(capturing_client):
    """
    When both positive and negative prompts are saved, both are passed
    through to generate_line_art without modification.
    """
    client, calls = capturing_client

    book = await _create_book(client)
    saved_pos = "CUSTOM POSITIVE"
    saved_neg = "CUSTOM NEGATIVE"
    page = await _add_page(
        client,
        book["id"],
        concept="A wizard",
        prompt=saved_pos,
        negative_prompt=saved_neg,
    )

    job = await _enqueue_and_wait(client, page["id"])
    assert job["status"] == "done", f"Job failed: {job}"

    assert len(calls) == 1
    assert calls[0]["positive_prompt"] == saved_pos
    assert calls[0]["negative_prompt"] == saved_neg
