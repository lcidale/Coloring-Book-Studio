"""
Tests for Task 2: page title serialization + GET /api/pages/{id}/versions endpoint.

Uses the existing `client` fixture from conftest.py (per-test isolated SQLite DB,
patched STORAGE_DIR, faked image generation).
"""
from __future__ import annotations

import asyncio
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


# ── Task: storage cleanup on page/book delete ─────────────────────────────────

from app.services import storage as storage_svc


async def test_delete_page_removes_version_storage(client: AsyncClient):
    """DELETE /pages/{page_id} must delete version storage objects."""
    book, page = await _make_book_and_page(client)
    image_path = f"books/{book['id']}/pages/{page['id']}/v001.png"
    await _seed_version(page["id"], 1, image_path, "p1")
    # Write a real file so exists() can confirm it's there
    storage_svc.put_bytes(image_path, b"x")
    assert storage_svc.exists(image_path), "precondition: file must exist before delete"

    r = await client.delete(f"/api/pages/{page['id']}")
    assert r.status_code == 204
    assert not storage_svc.exists(image_path), "storage object must be removed after page delete"

    r2 = await client.get(f"/api/pages/{page['id']}")
    assert r2.status_code == 404


async def test_delete_book_removes_version_storage(client: AsyncClient):
    """DELETE /books/{book_id} must delete all version storage objects."""
    book, page = await _make_book_and_page(client)
    image_path = f"books/{book['id']}/pages/{page['id']}/v001.png"
    await _seed_version(page["id"], 1, image_path, "p1")
    # Write a real file so exists() can confirm it's there
    storage_svc.put_bytes(image_path, b"x")
    assert storage_svc.exists(image_path), "precondition: file must exist before delete"

    r = await client.delete(f"/api/books/{book['id']}")
    assert r.status_code == 204
    assert not storage_svc.exists(image_path), "storage object must be removed after book delete"


async def test_delete_middle_version_then_regenerate_does_not_collide(client: AsyncClient):
    """ce-review #1 (P0): version_num must never be reused after a middle version
    is deleted, or the new generation overwrites a surviving version's file."""
    _, page = await _make_book_and_page(client)

    v1 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    v2 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    v3 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert [v1.json()["version"], v2.json()["version"], v3.json()["version"]] == [1, 2, 3]

    versions_before = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v2_id = next(v["id"] for v in versions_before if v["version_num"] == 2)

    r = await client.delete(f"/api/pages/{page['id']}/versions/{v2_id}")
    assert r.status_code == 204

    v4 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert v4.json()["version"] == 4, "must not reuse version_num=3, which the surviving v3 row still holds"

    versions_after = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    nums = [v["version_num"] for v in versions_after]
    assert sorted(nums) == [1, 3, 4], "no duplicate version_num across surviving rows"
    assert len(set(v["image_path"] if "image_path" in v else v["image_url"] for v in versions_after)) == 3, (
        "every surviving version must have a distinct image (no overwrite)"
    )


async def test_delete_page_cascades_generation_jobs(client: AsyncClient):
    """ce-review #2 (P0): a page that was generated at least once has a
    GenerationJob row; deleting the page must remove it too (Page.generation_jobs
    cascade), not just succeed by accident because SQLite doesn't enforce FKs."""
    _, page = await _make_book_and_page(client)

    gen_resp = await client.post(
        f"/api/pages/{page['id']}/generate",
        json={"auto_cleanup": False, "vectorize": False},
    )
    assert gen_resp.status_code == 202
    job_id = gen_resp.json()["job_id"]

    for _ in range(20):
        await asyncio.sleep(0.15)
        job_resp = await client.get(f"/api/jobs/{job_id}")
        if job_resp.json()["status"] in ("done", "failed"):
            break
    assert job_resp.json()["status"] == "done"

    r = await client.delete(f"/api/pages/{page['id']}")
    assert r.status_code == 204

    # The job row itself must be gone — not just orphaned — proving the ORM
    # cascade actually ran (a bare 204 would pass even without the fix, since
    # SQLite doesn't enforce the FK either way).
    after = await client.get(f"/api/jobs/{job_id}")
    assert after.status_code == 404


async def test_delete_book_cascades_generation_jobs(client: AsyncClient):
    """Same as above, via the book-delete path."""
    book, page = await _make_book_and_page(client)

    gen_resp = await client.post(
        f"/api/pages/{page['id']}/generate",
        json={"auto_cleanup": False, "vectorize": False},
    )
    job_id = gen_resp.json()["job_id"]
    for _ in range(20):
        await asyncio.sleep(0.15)
        job_resp = await client.get(f"/api/jobs/{job_id}")
        if job_resp.json()["status"] in ("done", "failed"):
            break
    assert job_resp.json()["status"] == "done"

    r = await client.delete(f"/api/books/{book['id']}")
    assert r.status_code == 204

    after = await client.get(f"/api/jobs/{job_id}")
    assert after.status_code == 404
