"""
Global app-settings + image-provider registry endpoints.

    GET  /api/providers   → the provider/model registry with live `configured` flags
    GET  /api/settings    → the current global image_provider + image_model (+ configured)
    PUT  /api/settings    → update the global image_provider + image_model

The single AppSettings row is created on first access (get-or-create), seeded
from the IMAGE_PROVIDER / REPLICATE_MODEL / GEMINI_IMAGE_MODEL / FAL_MODEL env
defaults via services.image_gen.env_default_provider_model().
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AppSettings
from app.services import providers as _providers
from app.services.image_gen import env_default_provider_model

router = APIRouter()


# ── get-or-create helper ────────────────────────────────────────────────────

async def get_or_create_settings(db: AsyncSession) -> AppSettings:
    """Return the single AppSettings row, creating it (seeded from env) if absent."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == "global"))
    settings = result.scalar_one_or_none()
    if settings is None:
        provider, model = env_default_provider_model()
        settings = AppSettings(id="global", image_provider=provider, image_model=model)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


# ── schemas ─────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    image_provider: Optional[str] = None
    image_model: Optional[str] = None


def _serialize(settings: AppSettings) -> dict:
    provider = settings.image_provider
    return {
        "image_provider": provider,
        "image_model": settings.image_model,
        # Surface whether the *selected* provider actually has its key set, so
        # the UI can warn before the user tries to generate.
        "configured": _providers.is_configured(provider),
    }


# ── endpoints ───────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """Return the image-provider registry (providers, their models, configured flag)."""
    return {"providers": _providers.get_registry()}


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the current global image provider + model."""
    settings = await get_or_create_settings(db)
    return _serialize(settings)


@router.put("/settings")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update the global image provider and/or model.

    Validates against the provider registry:
      - provider must be a known provider (aliases like ``nanobanana`` accepted
        and normalised to their canonical id).
      - model, if given, must belong to the (resolved) provider. If the provider
        changes but no model is given, the provider's default_model is applied.
    """
    settings = await get_or_create_settings(db)

    # Resolve the target provider (incoming value, else keep current).
    raw_provider = body.image_provider if body.image_provider is not None else settings.image_provider
    if not _providers.is_known_provider(raw_provider):
        known = [p["id"] for p in _providers.get_registry()]
        raise HTTPException(400, f"Unknown provider '{raw_provider}'. Known: {known}")
    provider = _providers.canonical_provider(raw_provider)

    # Resolve the model.
    if body.image_model is not None and body.image_model != "":
        model = body.image_model
        if not _providers.is_valid_model(provider, model):
            valid = _providers.model_ids(provider)
            raise HTTPException(
                400, f"Model '{model}' is not valid for provider '{provider}'. Valid: {valid}"
            )
    elif body.image_provider is not None and body.image_provider != "":
        # Provider explicitly changed but no model supplied → use its default.
        model = _providers.default_model(provider)
    else:
        # Neither provider nor model meaningfully changed → keep current model,
        # but fall back to the provider default if it is empty/invalid.
        model = settings.image_model
        if not _providers.is_valid_model(provider, model):
            model = _providers.default_model(provider)

    settings.image_provider = provider
    settings.image_model = model or ""
    await db.commit()
    await db.refresh(settings)
    return _serialize(settings)
