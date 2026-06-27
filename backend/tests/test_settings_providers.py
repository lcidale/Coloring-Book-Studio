"""
Tests for the image-provider registry, global AppSettings, and the
provider/model resolution order in services.image_gen.

These use the shared `client` fixture (ASGI, temp SQLite, generate_line_art
monkeypatched) from conftest.py, plus direct unit calls into providers.py and
image_gen.py for the resolution logic and the no-key Gemini error path.
"""
from __future__ import annotations

import pytest

from app.services import providers as P


# ── providers registry ───────────────────────────────────────────────────────

def test_registry_has_three_providers_with_models():
    reg = P.get_registry()
    ids = {p["id"] for p in reg}
    assert ids == {"replicate", "fal", "gemini"}
    for p in reg:
        assert p["models"], f"{p['id']} has no models"
        assert p["default_model"] in {m["id"] for m in p["models"]}
        assert "configured" in p


def test_nanobanana_alias_maps_to_gemini():
    assert P.canonical_provider("nanobanana") == "gemini"
    assert P.canonical_provider("nano-banana") == "gemini"
    assert P.is_known_provider("nanobanana")
    assert P.get_provider("nanobanana")["id"] == "gemini"


def test_gemini_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert P.is_configured("gemini") is False
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert P.is_configured("gemini") is True


def test_model_validation_helpers():
    assert P.is_valid_model("gemini", "gemini-2.5-flash-image")
    assert not P.is_valid_model("gemini", "flux-1.1-pro")
    assert P.default_model("gemini") == "gemini-2.5-flash-image"


# ── settings endpoints (via ASGI client) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_get_providers_endpoint(client):
    r = await client.get("/api/providers")
    assert r.status_code == 200
    providers = r.json()["providers"]
    assert {p["id"] for p in providers} == {"replicate", "fal", "gemini"}


@pytest.mark.asyncio
async def test_settings_defaults_and_roundtrip(client):
    # First GET creates the row seeded from env defaults.
    r = await client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["image_provider"] in {"replicate", "fal", "gemini"}

    # PUT to gemini + model persists and round-trips.
    r = await client.put(
        "/api/settings",
        json={"image_provider": "gemini", "image_model": "gemini-2.5-flash-image"},
    )
    assert r.status_code == 200
    assert r.json()["image_provider"] == "gemini"
    assert r.json()["image_model"] == "gemini-2.5-flash-image"

    r = await client.get("/api/settings")
    assert r.json()["image_provider"] == "gemini"
    assert r.json()["image_model"] == "gemini-2.5-flash-image"


@pytest.mark.asyncio
async def test_settings_alias_and_default_model(client):
    r = await client.put("/api/settings", json={"image_provider": "nanobanana"})
    assert r.status_code == 200
    assert r.json()["image_provider"] == "gemini"
    assert r.json()["image_model"] == "gemini-2.5-flash-image"


@pytest.mark.asyncio
async def test_settings_rejects_unknown_provider(client):
    r = await client.put("/api/settings", json={"image_provider": "midjourney"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_settings_rejects_invalid_model(client):
    r = await client.put(
        "/api/settings",
        json={"image_provider": "gemini", "image_model": "flux-1.1-pro"},
    )
    assert r.status_code == 400


# ── resolution order + no-key Gemini error ───────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_explicit_provider_overrides(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "replicate")
    from app.services.image_gen import _resolve_provider_model

    prov, model = await _resolve_provider_model("nanobanana", None, db=None)
    assert prov == "gemini"
    assert model == "gemini-2.5-flash-image"


@pytest.mark.asyncio
async def test_resolve_env_default_fallback(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "fal")
    monkeypatch.delenv("FAL_MODEL", raising=False)
    from app.services.image_gen import _resolve_provider_model

    prov, model = await _resolve_provider_model(None, None, db=None)
    assert prov == "fal"
    assert model == "fal-ai/flux/schnell"  # registry default


@pytest.mark.asyncio
async def test_gemini_no_key_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    # Import the real (un-monkeypatched) generate_line_art module directly.
    import importlib
    import app.services.image_gen as igen
    importlib.reload(igen)

    with pytest.raises(RuntimeError) as exc:
        await igen.generate_line_art(
            positive_prompt="a cat",
            negative_prompt="color",
            book_id="b", page_id="p", version=1,
            provider="gemini",
        )
    msg = str(exc.value).lower()
    assert "not configured" in msg
    assert "gemini_api_key" in msg or "google_api_key" in msg
