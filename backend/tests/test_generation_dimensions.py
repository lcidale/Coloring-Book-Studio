"""
Verifies that /api/generate/{page_id} actually drives the generator's
pixel dimensions and the cleanup border from the book's style guide,
instead of always using the hardcoded 8.5x11 @ 300 DPI / 40px defaults.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_book_with_style_guide(client: AsyncClient, **sg_overrides) -> dict:
    payload = {
        "title": "Custom Trim Book",
        "style_guide": {
            "trim_width_in": 6.0,
            "trim_height_in": 9.0,
            "margin_in": 0.5,
            "target_dpi": 150,
            **sg_overrides,
        },
    }
    resp = await client.post("/api/books", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_page(client: AsyncClient, book_id: str) -> dict:
    resp = await client.post(
        f"/api/pages/book/{book_id}",
        json={"concept": "a fox reading a book", "sort_order": 0},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_generate_passes_style_guide_dimensions_to_generator(
    client: AsyncClient, monkeypatch
) -> None:
    """A book with a custom trim size and DPI must drive the actual pixel
    dimensions requested from the image generator, not the hardcoded default."""
    book = await _create_book_with_style_guide(client)
    page = await _create_page(client, book["id"])

    import app.routers.generate as gen_router

    original = gen_router.generate_line_art
    captured: dict = {}

    async def _spy(*args, **kwargs):
        captured["width"] = kwargs.get("width")
        captured["height"] = kwargs.get("height")
        return await original(*args, **kwargs)

    monkeypatch.setattr(gen_router, "generate_line_art", _spy)

    resp = await client.post(
        f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False}
    )
    assert resp.status_code == 200
    assert captured["width"] == 900  # 6.0in * 150dpi
    assert captured["height"] == 1350  # 9.0in * 150dpi


async def test_generate_passes_style_guide_margin_to_cleanup(
    client: AsyncClient, monkeypatch
) -> None:
    """A book's configured margin must drive the cleanup border, not
    autocrop's own hardcoded 40px default."""
    book = await _create_book_with_style_guide(client)
    page = await _create_page(client, book["id"])

    import app.routers.generate as gen_router

    original = gen_router.cleanup
    captured: dict = {}

    def _spy(*args, **kwargs):
        captured["border_px"] = kwargs.get("border_px")
        return original(*args, **kwargs)

    monkeypatch.setattr(gen_router, "cleanup", _spy)

    resp = await client.post(
        f"/api/generate/{page['id']}", json={"auto_cleanup": True, "vectorize": False}
    )
    assert resp.status_code == 200
    assert captured["border_px"] == 75  # 0.5in * 150dpi
