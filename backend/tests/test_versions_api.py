"""
Tests for Task 2: page title serialization + GET /api/pages/{id}/versions endpoint.

Uses the existing `client` fixture from conftest.py (per-test isolated SQLite DB,
patched STORAGE_DIR, faked image generation).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _make_book_and_page(client: AsyncClient) -> tuple[dict, dict]:
    book = (await client.post("/api/books", json={"title": "T"})).json()
    page = (
        await client.post(
            f"/api/pages/book/{book['id']}",
            json={"concept": "a fox", "sort_order": 0},
        )
    ).json()
    return book, page


async def test_page_payload_includes_title(client: AsyncClient):
    """title round-trips through PATCH and is present in the response."""
    _, page = await _make_book_and_page(client)
    r = await client.patch(f"/api/pages/{page['id']}", json={"title": "Sleeping Fox"})
    assert r.status_code == 200
    assert r.json()["title"] == "Sleeping Fox"


async def test_page_create_title_field_present(client: AsyncClient):
    """title field is present in the create response (may be None)."""
    _, page = await _make_book_and_page(client)
    assert "title" in page


async def test_create_page_with_title(client: AsyncClient):
    """title passed at creation time is round-tripped."""
    book = (await client.post("/api/books", json={"title": "T"})).json()
    page = (
        await client.post(
            f"/api/pages/book/{book['id']}",
            json={"concept": "a fox", "title": "The Fox", "sort_order": 0},
        )
    ).json()
    assert page["title"] == "The Fox"


async def test_list_versions_empty(client: AsyncClient):
    """GET /api/pages/{id}/versions returns [] when no versions exist."""
    _, page = await _make_book_and_page(client)
    r = await client.get(f"/api/pages/{page['id']}/versions")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_versions_404_unknown_page(client: AsyncClient):
    """GET /api/pages/{id}/versions returns 404 for an unknown page id."""
    r = await client.get("/api/pages/nonexistent-page-id/versions")
    assert r.status_code == 404


# ── Task 3: restore-version endpoint ─────────────────────────────────────────

import app.database as db_mod
from app.models import PageVersion


async def _seed_version(page_id, num, image_path, prompt, dpi=300):
    async with db_mod.SessionLocal() as db:
        pv = PageVersion(page_id=page_id, version_num=num, image_path=image_path,
                         prompt=prompt, dpi=dpi, width_px=2550, height_px=3300,
                         is_pure_bw=True)
        db.add(pv)
        await db.commit()
        await db.refresh(pv)
        return pv.id


async def test_restore_makes_version_current(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "prompt one")
    v2 = await _seed_version(page["id"], 2, "books/b/p/v002.png", "prompt two")

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1}/restore")
    assert r.status_code == 200
    body = r.json()
    assert body["prompt"] == "prompt one"
    # image_path is serialized to a URL ending in the restored key
    assert body["image_path"].endswith("books/b/p/v001.png")

    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    current = [v for v in versions if v["is_current"]]
    assert len(current) == 1 and current[0]["id"] == v1


async def test_restore_unknown_version_404(client):
    _, page = await _make_book_and_page(client)
    r = await client.post(f"/api/pages/{page['id']}/versions/nope/restore")
    assert r.status_code == 404


# ── Task 4: label/notes PATCH + delete-version endpoint ──────────────────────

async def test_patch_version_label_and_notes(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    r = await client.patch(f"/api/pages/{page['id']}/versions/{v1}",
                           json={"label": "too busy", "notes": "background cluttered"})
    assert r.status_code == 200
    assert r.json()["label"] == "too busy"
    assert r.json()["notes"] == "background cluttered"


async def test_delete_current_version_blocked(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    await client.post(f"/api/pages/{page['id']}/versions/{v1}/restore")  # v1 now current
    r = await client.delete(f"/api/pages/{page['id']}/versions/{v1}")
    assert r.status_code == 409


async def test_delete_noncurrent_version_ok(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    v2 = await _seed_version(page["id"], 2, "books/b/p/v002.png", "p2")
    await client.post(f"/api/pages/{page['id']}/versions/{v2}/restore")  # v2 current
    r = await client.delete(f"/api/pages/{page['id']}/versions/{v1}")
    assert r.status_code == 204
    remaining = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    assert [v["id"] for v in remaining] == [v2]
