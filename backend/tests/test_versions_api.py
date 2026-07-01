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
