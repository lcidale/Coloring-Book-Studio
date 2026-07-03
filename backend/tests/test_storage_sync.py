"""
Regression tests for a production-only bug: under STORAGE_BACKEND=r2,
generate_line_art() uploads the RAW (pre-cleanup) bytes to storage immediately,
then cleanup() mutates the LOCAL file only (threshold-to-pure-bw, despeckle,
autocrop/margin, DPI stamp). Nothing re-uploaded the cleaned file, so R2 kept
serving the raw, unprocessed image forever — no margin, no despeckle, no DPI —
regardless of what analyse() correctly measured on the local copy and recorded
in the database. This was invisible in the test suite because STORAGE_BACKEND
defaults to "local", where put_file() is a same-path no-op and local mutations
are trivially "already uploaded".
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image

pytestmark = pytest.mark.asyncio


async def _make_book_and_page(client: AsyncClient) -> tuple[dict, dict]:
    book = (await client.post("/api/books", json={"title": "T"})).json()
    page = (
        await client.post(
            f"/api/pages/book/{book['id']}",
            json={"concept": "a fox", "sort_order": 0},
        )
    ).json()
    return book, page


async def test_generate_reuploads_cleaned_file_to_storage(client: AsyncClient, monkeypatch):
    """The synchronous /api/generate/{id} endpoint must push the post-cleanup
    file back to storage — not just rely on generate_line_art's earlier
    raw-bytes upload — or STORAGE_BACKEND=r2 never sees the cleanup at all."""
    _, page = await _make_book_and_page(client)

    import app.routers.generate as gen_router

    calls: list[tuple[str, bytes]] = []
    original_put_file = gen_router.storage.put_file

    def _spy(key, local_path, content_type):
        calls.append((key, Path(local_path).read_bytes()))
        return original_put_file(key, local_path, content_type)

    monkeypatch.setattr(gen_router.storage, "put_file", _spy)

    resp = await client.post(
        f"/api/generate/{page['id']}", json={"auto_cleanup": True, "vectorize": False}
    )
    assert resp.status_code == 200
    rel_path = resp.json()["image_url"].removeprefix("/storage/")

    matching = [c for c in calls if c[0] == rel_path]
    assert matching, (
        "no re-upload happened for the generated image's key — under "
        "STORAGE_BACKEND=r2 this means R2 keeps serving the raw, "
        "unprocessed image forever"
    )

    img = Image.open(io.BytesIO(matching[-1][1]))
    assert img.info.get("dpi") is not None, (
        "the re-uploaded copy must be the POST-cleanup file — cleanup() "
        "stamps DPI metadata as its last step"
    )


async def test_generation_job_reuploads_cleaned_file_to_storage(client: AsyncClient, monkeypatch):
    """Same fix, for the async job pipeline the UI actually uses
    (POST /api/pages/{id}/generate)."""
    _, page = await _make_book_and_page(client)

    import app.routers.jobs as jobs_router

    calls: list[tuple[str, bytes]] = []
    original_put_file = jobs_router.storage.put_file

    def _spy(key, local_path, content_type):
        calls.append((key, Path(local_path).read_bytes()))
        return original_put_file(key, local_path, content_type)

    monkeypatch.setattr(jobs_router.storage, "put_file", _spy)

    gen_resp = await client.post(
        f"/api/pages/{page['id']}/generate",
        json={"auto_cleanup": True, "vectorize": False},
    )
    assert gen_resp.status_code == 202
    job_id = gen_resp.json()["job_id"]

    import asyncio

    job_resp = None
    for _ in range(20):
        await asyncio.sleep(0.15)
        job_resp = await client.get(f"/api/jobs/{job_id}")
        if job_resp.json()["status"] in ("done", "failed"):
            break
    assert job_resp.json()["status"] == "done", job_resp.json()

    page_resp = await client.get(f"/api/pages/{page['id']}")
    rel_path = page_resp.json()["image_path"].removeprefix("/storage/")

    matching = [c for c in calls if c[0] == rel_path]
    assert matching, (
        "no re-upload happened for the generated image's key — under "
        "STORAGE_BACKEND=r2 this means R2 keeps serving the raw, "
        "unprocessed image forever"
    )

    img = Image.open(io.BytesIO(matching[-1][1]))
    assert img.info.get("dpi") is not None, (
        "the re-uploaded copy must be the POST-cleanup file — cleanup() "
        "stamps DPI metadata as its last step"
    )


async def test_generate_with_vectorize_uses_storage_aware_path(client: AsyncClient):
    """vectorize_page() is explicitly documented as 'does not touch storage
    directly' — calling it straight from the router silently drops the SVG
    under STORAGE_BACKEND=r2. Must use vectorize_page_by_key() instead, whose
    local-backend branch behaves identically (regression guard for that swap)."""
    _, page = await _make_book_and_page(client)

    resp = await client.post(
        f"/api/generate/{page['id']}", json={"auto_cleanup": True, "vectorize": True}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["svg_url"], "vectorize=True must produce a usable svg_url"

    from app.services import storage

    svg_key = data["svg_url"].removeprefix("/storage/")
    assert storage.exists(svg_key), "the SVG must be reachable through the storage layer, not just on local disk"
