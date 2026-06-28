"""
Tests for U4: text-provider registry endpoint and text settings fields.

Covers:
  - GET /api/text-providers returns claude + gemini with models and configured flags.
  - GET /api/settings includes concept_provider/model + prompt_provider/model
    (defaults: gemini / gemini-2.5-flash) and the three *_configured flags.
  - PUT /api/settings with concept_provider only → default model auto-set.
  - PUT with invalid model for prompt_provider → 400.
  - PUT with unknown concept_provider → 400.
  - Existing image settings behaviour is unaffected (regression).
"""
from __future__ import annotations

import pytest


# ── text-providers registry endpoint ────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_text_providers_returns_registry(client):
    r = await client.get("/api/text-providers")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    providers = body["providers"]
    ids = {p["id"] for p in providers}
    assert "claude" in ids, f"claude missing from {ids}"
    assert "gemini" in ids, f"gemini missing from {ids}"


@pytest.mark.asyncio
async def test_get_text_providers_each_has_models_and_configured(client):
    r = await client.get("/api/text-providers")
    assert r.status_code == 200
    for p in r.json()["providers"]:
        assert p.get("models"), f"{p['id']} has no models"
        assert p["default_model"] in {m["id"] for m in p["models"]}
        assert "configured" in p, f"{p['id']} missing configured flag"
        assert isinstance(p["configured"], bool)


# ── GET /api/settings text fields ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_settings_includes_text_fields(client):
    r = await client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()

    # Text fields must be present.
    assert "concept_provider" in body
    assert "concept_model" in body
    assert "prompt_provider" in body
    assert "prompt_model" in body

    # *_configured flags must be present and boolean.
    assert "image_configured" in body
    assert "concept_configured" in body
    assert "prompt_configured" in body
    assert isinstance(body["image_configured"], bool)
    assert isinstance(body["concept_configured"], bool)
    assert isinstance(body["prompt_configured"], bool)


@pytest.mark.asyncio
async def test_get_settings_text_defaults_are_gemini(client):
    r = await client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()

    assert body["concept_provider"] == "gemini"
    assert body["concept_model"] == "gemini-2.5-flash"
    assert body["prompt_provider"] == "gemini"
    assert body["prompt_model"] == "gemini-2.5-flash"


# ── PUT /api/settings text-field validation ──────────────────────────────────

@pytest.mark.asyncio
async def test_put_concept_provider_only_sets_default_model(client):
    """Changing concept_provider without specifying a model → default model applied."""
    r = await client.put("/api/settings", json={"concept_provider": "claude"})
    assert r.status_code == 200
    body = r.json()
    assert body["concept_provider"] == "claude"
    assert body["concept_model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_put_prompt_invalid_model_returns_400(client):
    """Supplying a non-existent model for prompt_provider → 400."""
    r = await client.put(
        "/api/settings",
        json={"prompt_provider": "gemini", "prompt_model": "not-a-real-model"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_concept_unknown_provider_returns_400(client):
    """Supplying an unknown concept_provider → 400."""
    r = await client.put("/api/settings", json={"concept_provider": "openai"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_prompt_unknown_provider_returns_400(client):
    """Supplying an unknown prompt_provider → 400."""
    r = await client.put("/api/settings", json={"prompt_provider": "openai"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_concept_valid_model_persists(client):
    """Supplying both concept_provider and a valid model → persisted correctly."""
    r = await client.put(
        "/api/settings",
        json={"concept_provider": "claude", "concept_model": "claude-opus-4-8"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["concept_provider"] == "claude"
    assert body["concept_model"] == "claude-opus-4-8"

    # Verify persistence via GET.
    r2 = await client.get("/api/settings")
    assert r2.json()["concept_provider"] == "claude"
    assert r2.json()["concept_model"] == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_put_concept_and_prompt_independently(client):
    """concept_* and prompt_* pairs are applied independently."""
    # Set concept to claude, prompt stays gemini.
    r = await client.put("/api/settings", json={"concept_provider": "claude"})
    assert r.status_code == 200
    body = r.json()
    assert body["concept_provider"] == "claude"
    assert body["prompt_provider"] == "gemini"

    # Now set prompt to claude, concept stays claude.
    r2 = await client.put("/api/settings", json={"prompt_provider": "claude"})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["concept_provider"] == "claude"
    assert body2["prompt_provider"] == "claude"
    assert body2["prompt_model"] == "claude-sonnet-4-6"


# ── regression: existing image settings unaffected ──────────────────────────

@pytest.mark.asyncio
async def test_image_settings_regression(client):
    """Existing image provider/model round-trip is unaffected by text-field additions."""
    r = await client.put(
        "/api/settings",
        json={"image_provider": "gemini", "image_model": "gemini-2.5-flash-image"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["image_provider"] == "gemini"
    assert body["image_model"] == "gemini-2.5-flash-image"
    # Existing `configured` field still present.
    assert "configured" in body

    r2 = await client.get("/api/settings")
    assert r2.json()["image_provider"] == "gemini"
    assert r2.json()["image_model"] == "gemini-2.5-flash-image"


@pytest.mark.asyncio
async def test_image_provider_unknown_still_400(client):
    r = await client.put("/api/settings", json={"image_provider": "midjourney"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_image_model_invalid_still_400(client):
    r = await client.put(
        "/api/settings",
        json={"image_provider": "gemini", "image_model": "flux-1.1-pro"},
    )
    assert r.status_code == 400
