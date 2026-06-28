"""
Tests for U5: POST /{page_id}/refine-concept and POST /{page_id}/write-prompt.

Covers:
- refine-concept returns {"refined_concept": ...} from the stub; page unchanged.
- write-prompt returns {"positive": ..., "negative": ...}; negative is non-empty; page unchanged.
- When the selected provider is unconfigured → 400 with a message naming the missing key.
- Unknown page id → 404.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_book_and_page(client) -> tuple[str, str]:
    """Create a book and one page, return (book_id, page_id)."""
    r_book = await client.post("/api/books", json={"title": "Test Book"})
    assert r_book.status_code == 201, r_book.text
    book_id = r_book.json()["id"]

    r_page = await client.post(
        f"/api/pages/book/{book_id}",
        json={"concept": "A cat sitting on a cloud", "sort_order": 0},
    )
    assert r_page.status_code == 201, r_page.text
    page_id = r_page.json()["id"]
    return book_id, page_id


# ---------------------------------------------------------------------------
# POST /{page_id}/refine-concept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refine_concept_returns_result_and_does_not_save(client, monkeypatch):
    """
    The endpoint returns {"refined_concept": ...} from the stub and leaves
    the page concept unchanged on disk.
    """
    # Stub out the LLM call.
    async def _fake_refine_concept(concept, style_guide, provider, model):
        return f"REFINED: {concept}"

    import app.services.text_gen as tg_mod
    import app.routers.pages as pages_mod
    import app.services.text_providers as tp_mod

    monkeypatch.setattr(tg_mod, "refine_concept", _fake_refine_concept)
    monkeypatch.setattr(pages_mod, "text_gen", tg_mod)
    # Ensure is_configured always returns True for the happy path.
    monkeypatch.setattr(tp_mod, "is_configured", lambda provider: True)
    monkeypatch.setattr(pages_mod, "text_providers", tp_mod)

    book_id, page_id = await _create_book_and_page(client)
    original_concept = "A cat sitting on a cloud"

    r = await client.post(f"/api/pages/{page_id}/refine-concept")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "refined_concept" in body
    assert body["refined_concept"] == f"REFINED: {original_concept}"

    # Page concept must be unchanged.
    r_get = await client.get(f"/api/pages/{page_id}")
    assert r_get.status_code == 200
    assert r_get.json()["concept"] == original_concept


@pytest.mark.asyncio
async def test_refine_concept_unknown_page_returns_404(client):
    r = await client.post("/api/pages/nonexistent-page-id/refine-concept")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_refine_concept_unconfigured_provider_returns_400(client, monkeypatch):
    """
    When the concept provider is not configured, the endpoint returns 400
    with a message naming the missing API key.
    """
    import app.services.text_providers as tp_mod
    import app.routers.pages as pages_mod

    # Force is_configured to return False for every provider.
    monkeypatch.setattr(tp_mod, "is_configured", lambda provider: False)
    monkeypatch.setattr(pages_mod, "text_providers", tp_mod)

    # Set concept_provider to claude so we get a specific key name in the message.
    r_settings = await client.put("/api/settings", json={"concept_provider": "claude"})
    assert r_settings.status_code == 200

    book_id, page_id = await _create_book_and_page(client)

    r = await client.post(f"/api/pages/{page_id}/refine-concept")
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    # The error message must name the missing key.
    assert "ANTHROPIC_API_KEY" in detail or "claude" in detail.lower(), (
        f"Expected key name in error detail, got: {detail!r}"
    )


# ---------------------------------------------------------------------------
# POST /{page_id}/write-prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_prompt_returns_positive_and_negative(client, monkeypatch):
    """
    The endpoint returns {"positive": ..., "negative": ...}.
    The negative prompt is non-empty (built by prompt_builder).
    The page is NOT saved.
    """
    async def _fake_write_prompt(concept, style_guide, provider, model):
        return f"PROMPT FOR: {concept}"

    import app.services.text_gen as tg_mod
    import app.routers.pages as pages_mod
    import app.services.text_providers as tp_mod

    monkeypatch.setattr(tg_mod, "write_prompt", _fake_write_prompt)
    monkeypatch.setattr(pages_mod, "text_gen", tg_mod)
    monkeypatch.setattr(tp_mod, "is_configured", lambda provider: True)
    monkeypatch.setattr(pages_mod, "text_providers", tp_mod)

    book_id, page_id = await _create_book_and_page(client)
    original_concept = "A cat sitting on a cloud"

    r = await client.post(f"/api/pages/{page_id}/write-prompt")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "positive" in body
    assert "negative" in body
    assert body["positive"] == f"PROMPT FOR: {original_concept}"
    # negative comes from prompt_builder — must be non-empty.
    assert body["negative"], "negative prompt must be non-empty"

    # Page must NOT have been saved with the generated prompt.
    r_get = await client.get(f"/api/pages/{page_id}")
    assert r_get.status_code == 200
    page_data = r_get.json()
    assert page_data["concept"] == original_concept
    # prompt field should still be None / not updated.
    assert page_data.get("prompt") is None or page_data.get("prompt") != body["positive"]


@pytest.mark.asyncio
async def test_write_prompt_unknown_page_returns_404(client):
    r = await client.post("/api/pages/nonexistent-page-id/write-prompt")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_write_prompt_unconfigured_provider_returns_400(client, monkeypatch):
    """
    When the prompt provider is not configured, 400 is returned with a
    message naming the missing API key.
    """
    import app.services.text_providers as tp_mod
    import app.routers.pages as pages_mod

    monkeypatch.setattr(tp_mod, "is_configured", lambda provider: False)
    monkeypatch.setattr(pages_mod, "text_providers", tp_mod)

    # Set prompt_provider to claude so the error message names ANTHROPIC_API_KEY.
    r_settings = await client.put("/api/settings", json={"prompt_provider": "claude"})
    assert r_settings.status_code == 200

    book_id, page_id = await _create_book_and_page(client)

    r = await client.post(f"/api/pages/{page_id}/write-prompt")
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "ANTHROPIC_API_KEY" in detail or "claude" in detail.lower(), (
        f"Expected key name in error detail, got: {detail!r}"
    )


@pytest.mark.asyncio
async def test_write_prompt_negative_contains_universal_terms(client, monkeypatch):
    """
    The negative prompt returned by write-prompt must contain known coloring-book
    terms from UNIVERSAL_NEGATIVE (e.g. 'color', 'shading').
    """
    async def _fake_write_prompt(concept, style_guide, provider, model):
        return "clean black line art of a cat on a cloud"

    import app.services.text_gen as tg_mod
    import app.routers.pages as pages_mod
    import app.services.text_providers as tp_mod

    monkeypatch.setattr(tg_mod, "write_prompt", _fake_write_prompt)
    monkeypatch.setattr(pages_mod, "text_gen", tg_mod)
    monkeypatch.setattr(tp_mod, "is_configured", lambda provider: True)
    monkeypatch.setattr(pages_mod, "text_providers", tp_mod)

    book_id, page_id = await _create_book_and_page(client)

    r = await client.post(f"/api/pages/{page_id}/write-prompt")
    assert r.status_code == 200, r.text
    negative = r.json()["negative"]
    # UNIVERSAL_NEGATIVE includes "color" and "shading".
    assert "color" in negative.lower()
    assert "shading" in negative.lower()
