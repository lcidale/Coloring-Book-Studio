"""
Image-provider registry.

Single source of truth for which image-generation providers exist, which
models each exposes, and whether a provider is *configured* (its API key /
token is present in the environment).

Consumed by:
  - routers/settings.py  → GET /api/providers (the UI's selection menu) and
    PUT /api/settings validation.
  - services/image_gen.py → default-model lookup and provider resolution.

Each registry entry has the shape::

    {
        "id": "replicate",
        "label": "Replicate (FLUX)",
        "models": [{"id": "...", "label": "..."}, ...],
        "default_model": "...",
        "configured": True,            # computed from env at call time
    }

The Gemini provider is also reachable under the alias ``nanobanana``; both
strings resolve to the same canonical ``gemini`` entry (see ALIASES /
canonical_provider).
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
        "id": "replicate",
        "label": "Replicate (FLUX)",
        "models": [
            {"id": "black-forest-labs/flux-1.1-pro", "label": "FLUX 1.1 Pro"},
            {"id": "black-forest-labs/flux-dev", "label": "FLUX Dev"},
        ],
        "default_model": "black-forest-labs/flux-1.1-pro",
        "env_keys": ("REPLICATE_API_TOKEN",),
    },
    {
        "id": "fal",
        "label": "fal.ai (FLUX)",
        "models": [
            {"id": "fal-ai/flux/schnell", "label": "FLUX Schnell"},
            {"id": "fal-ai/flux/dev", "label": "FLUX Dev"},
        ],
        "default_model": "fal-ai/flux/schnell",
        "env_keys": ("FAL_KEY",),
    },
    {
        "id": "gemini",
        "label": "Google Nano Banana (Gemini)",
        "models": [
            {"id": "gemini-2.5-flash-image", "label": "Nano Banana (Gemini 2.5 Flash Image)"},
        ],
        "default_model": "gemini-2.5-flash-image",
        # Either var configures Gemini; the SDK auto-reads GOOGLE_API_KEY but we
        # also accept the GEMINI_API_KEY alias and pass it explicitly.
        "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    },
]

# Alias → canonical provider id.  "nanobanana" is an accepted synonym for the
# Google Gemini image provider.
ALIASES: dict[str, str] = {
    "nanobanana": "gemini",
    "nano-banana": "gemini",
    "nano_banana": "gemini",
}

DEFAULT_PROVIDER = "replicate"


def canonical_provider(provider: Optional[str]) -> Optional[str]:
    """Map an alias (e.g. ``nanobanana``) to its canonical id (``gemini``).

    Returns the lower-cased canonical id, or None if ``provider`` is falsy.
    Unknown ids are returned lower-cased unchanged (validation happens in
    is_known_provider / settings.py).
    """
    if not provider:
        return None
    p = provider.strip().lower()
    return ALIASES.get(p, p)


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
    cid = canonical_provider(provider)
    for e in _CATALOGUE:
        if e["id"] == cid:
            return e
    return None


def get_provider(provider: str) -> Optional[dict]:
    """Return the public registry entry for one provider (alias-aware), or None."""
    entry = _raw_entry(provider)
    return _public_entry(entry) if entry else None


def is_known_provider(provider: Optional[str]) -> bool:
    """True if ``provider`` (alias-aware) names a registered provider."""
    return _raw_entry(provider or "") is not None


def is_configured(provider: str) -> bool:
    """True if the (alias-aware) provider has its API key/token in the env."""
    entry = _raw_entry(provider)
    return bool(entry) and _is_configured(entry)


def model_ids(provider: str) -> list[str]:
    """List of valid model ids for a provider (alias-aware); [] if unknown."""
    entry = _raw_entry(provider)
    return [m["id"] for m in entry["models"]] if entry else []


def default_model(provider: str) -> Optional[str]:
    """Default model id for a provider (alias-aware), or None if unknown."""
    entry = _raw_entry(provider)
    return entry["default_model"] if entry else None


def is_valid_model(provider: str, model: Optional[str]) -> bool:
    """True if ``model`` is one of the provider's registered model ids."""
    return bool(model) and model in model_ids(provider)
