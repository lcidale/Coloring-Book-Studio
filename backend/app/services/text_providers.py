"""
Text-LLM provider registry.

Single source of truth for which text-generation providers exist, which
models each exposes, and whether a provider is *configured* (its API key
is present in the environment).

Each registry entry has the shape::

    {
        "id": "claude",
        "label": "Anthropic Claude",
        "models": [{"id": "...", "label": "..."}, ...],
        "default_model": "...",
        "configured": True,            # computed from env at call time
    }

Provider lookup is a plain lower-cased exact match (no alias machinery).
"""
from __future__ import annotations

import os
from typing import Optional


# ---------------------------------------------------------------------------
# Static provider/model catalogue.  ``configured`` is filled in at call time
# from the environment by get_registry() / get_provider().
# ---------------------------------------------------------------------------

_CATALOGUE: list[dict] = [
    {
        "id": "claude",
        "label": "Anthropic Claude",
        "models": [
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6 (recommended)"},
            {"id": "claude-opus-4-8", "label": "Claude Opus 4.8"},
        ],
        "default_model": "claude-sonnet-4-6",
        "env_keys": ("ANTHROPIC_API_KEY",),
    },
    {
        "id": "gemini",
        "label": "Google Gemini",
        "models": [
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
        ],
        "default_model": "gemini-2.5-flash",
        # Either var configures Gemini; the SDK auto-reads GOOGLE_API_KEY but we
        # also accept the GEMINI_API_KEY alias and pass it explicitly.
        "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    },
]

DEFAULT_PROVIDER = "gemini"


def _is_configured(entry: dict) -> bool:
    """True when at least one of the provider's env keys is set & non-empty."""
    return any(os.getenv(k) for k in entry.get("env_keys", ()))


def _public_entry(entry: dict) -> dict:
    """Strip internal fields and stamp the live ``configured`` flag."""
    return {
        "id": entry["id"],
        "label": entry["label"],
        "models": [dict(m) for m in entry["models"]],
        "default_model": entry["default_model"],
        "configured": _is_configured(entry),
    }


def get_registry() -> list[dict]:
    """Return the full provider registry with live ``configured`` flags."""
    return [_public_entry(e) for e in _CATALOGUE]


def _raw_entry(provider: str) -> Optional[dict]:
    cid = provider.strip().lower() if provider else ""
    for e in _CATALOGUE:
        if e["id"] == cid:
            return e
    return None


def get_provider(provider: str) -> Optional[dict]:
    """Return the public registry entry for one provider, or None."""
    entry = _raw_entry(provider)
    return _public_entry(entry) if entry else None


def is_known_provider(provider: Optional[str]) -> bool:
    """True if ``provider`` names a registered provider."""
    return _raw_entry(provider or "") is not None


def is_configured(provider: str) -> bool:
    """True if the provider has its API key in the env."""
    entry = _raw_entry(provider)
    return bool(entry) and _is_configured(entry)


def model_ids(provider: str) -> list[str]:
    """List of valid model ids for a provider; [] if unknown."""
    entry = _raw_entry(provider)
    return [m["id"] for m in entry["models"]] if entry else []


def default_model(provider: str) -> Optional[str]:
    """Default model id for a provider, or None if unknown."""
    entry = _raw_entry(provider)
    return entry["default_model"] if entry else None


def is_valid_model(provider: str, model: Optional[str]) -> bool:
    """True if ``model`` is one of the provider's registered model ids."""
    return bool(model) and model in model_ids(provider)
