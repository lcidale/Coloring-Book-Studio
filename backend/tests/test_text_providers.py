"""
Tests for the text-LLM provider registry (text_providers.py).

Mirrors the style of test_settings_providers.py.  These are pure unit tests
that call into the registry directly; no ASGI client or database is needed.
"""
from __future__ import annotations

import pytest

from app.services import text_providers as TP


# ── registry structure ───────────────────────────────────────────────────────

def test_registry_has_exactly_claude_and_gemini():
    reg = TP.get_registry()
    ids = {p["id"] for p in reg}
    assert ids == {"claude", "gemini"}


def test_registry_entries_are_well_formed():
    for p in TP.get_registry():
        assert p["models"], f"{p['id']} has no models"
        model_id_set = {m["id"] for m in p["models"]}
        assert p["default_model"] in model_id_set, (
            f"{p['id']}: default_model {p['default_model']!r} not in model list"
        )
        assert "configured" in p


# ── default_model ─────────────────────────────────────────────────────────────

def test_default_model_claude():
    assert TP.default_model("claude") == "claude-sonnet-4-6"


def test_default_model_gemini():
    assert TP.default_model("gemini") == "gemini-2.5-flash"


def test_default_model_unknown_returns_none():
    assert TP.default_model("openai") is None


# ── is_valid_model ────────────────────────────────────────────────────────────

def test_valid_model_claude_opus():
    assert TP.is_valid_model("claude", "claude-opus-4-8") is True


def test_valid_model_claude_sonnet():
    assert TP.is_valid_model("claude", "claude-sonnet-4-6") is True


def test_invalid_model_claude_opus_for_gemini():
    assert TP.is_valid_model("gemini", "claude-opus-4-8") is False


def test_valid_model_gemini_flash():
    assert TP.is_valid_model("gemini", "gemini-2.5-flash") is True


def test_valid_model_gemini_pro():
    assert TP.is_valid_model("gemini", "gemini-2.5-pro") is True


def test_invalid_model_none():
    assert TP.is_valid_model("claude", None) is False


# ── is_configured ─────────────────────────────────────────────────────────────

def test_claude_configured_with_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert TP.is_configured("claude") is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert TP.is_configured("claude") is True


def test_gemini_configured_with_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert TP.is_configured("gemini") is False
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    assert TP.is_configured("gemini") is True


def test_gemini_configured_with_google_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert TP.is_configured("gemini") is False
    monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
    assert TP.is_configured("gemini") is True


def test_gemini_configured_reflects_in_registry_entry(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    reg = {p["id"]: p for p in TP.get_registry()}
    assert reg["gemini"]["configured"] is False
    monkeypatch.setenv("GEMINI_API_KEY", "gk-test")
    reg2 = {p["id"]: p for p in TP.get_registry()}
    assert reg2["gemini"]["configured"] is True


# ── is_known_provider ─────────────────────────────────────────────────────────

def test_known_providers():
    assert TP.is_known_provider("claude") is True
    assert TP.is_known_provider("gemini") is True


def test_unknown_provider_openai():
    assert TP.is_known_provider("openai") is False


def test_unknown_provider_empty():
    assert TP.is_known_provider("") is False


def test_unknown_provider_none():
    assert TP.is_known_provider(None) is False


# ── no alias machinery ────────────────────────────────────────────────────────

def test_no_alias_nanobanana():
    """text_providers has no alias map; nanobanana must not resolve to gemini."""
    assert TP.is_known_provider("nanobanana") is False
    assert TP.get_provider("nanobanana") is None
