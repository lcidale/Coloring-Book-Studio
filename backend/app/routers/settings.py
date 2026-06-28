"""
Global app-settings + image-provider registry endpoints.

    GET  /api/providers       → the image provider/model registry with live `configured` flags
    GET  /api/text-providers  → the text provider/model registry with live `configured` flags
    GET  /api/settings        → the current global image_provider + image_model (+ configured)
                                and concept_provider/model + prompt_provider/model
    PUT  /api/settings        → update the global image and/or text provider+model settings

The single AppSettings row is created on first access (get-or-create), seeded
from the IMAGE_PROVIDER / REPLICATE_MODEL / GEMINI_IMAGE_MODEL / FAL_MODEL env
defaults via services.image_gen.env_default_provider_model(), and text fields
seeded from text_providers.DEFAULT_PROVIDER / text_providers.default_model().
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
from app.services import text_providers as _text_providers
from app.services.image_gen import env_default_provider_model

router = APIRouter()


# ── get-or-create helper ────────────────────────────────────────────────────

async def get_or_create_settings(db: AsyncSession) -> AppSettings:
    """Return the single AppSettings row, creating it (seeded from env) if absent."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == "global"))
    settings = result.scalar_one_or_none()
    if settings is None:
        provider, model = env_default_provider_model()
        default_text_provider = _text_providers.DEFAULT_PROVIDER
        default_text_model = _text_providers.default_model(default_text_provider)
        settings = AppSettings(
            id="global",
            image_provider=provider,
            image_model=model,
            concept_provider=default_text_provider,
            concept_model=default_text_model or "",
            prompt_provider=default_text_provider,
            prompt_model=default_text_model or "",
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        return settings

    # Existing row: backfill empty text-model fields. Rows created before this
    # feature (or Postgres-migrated with DEFAULT '' columns) keep empty
    # concept/prompt provider+model, which would otherwise send model="" to the
    # LLM and 400 on partial settings updates. Seed real defaults once.
    _dp = _text_providers.DEFAULT_PROVIDER
    _dm = _text_providers.default_model(_dp) or ""
    changed = False
    if not settings.concept_provider:
        settings.concept_provider, changed = _dp, True
    if not settings.concept_model:
        settings.concept_model, changed = _dm, True
    if not settings.prompt_provider:
        settings.prompt_provider, changed = _dp, True
    if not settings.prompt_model:
        settings.prompt_model, changed = _dm, True
    if changed:
        await db.commit()
        await db.refresh(settings)
    return settings


# ── schemas ─────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    concept_provider: Optional[str] = None
    concept_model: Optional[str] = None
    prompt_provider: Optional[str] = None
    prompt_model: Optional[str] = None


def _serialize(settings: AppSettings) -> dict:
    image_provider = settings.image_provider
    concept_provider = settings.concept_provider or _text_providers.DEFAULT_PROVIDER
    prompt_provider = settings.prompt_provider or _text_providers.DEFAULT_PROVIDER
    return {
        "image_provider": image_provider,
        "image_model": settings.image_model,
        # Surface whether the *selected* provider actually has its key set, so
        # the UI can warn before the user tries to generate.
        "configured": _providers.is_configured(image_provider),
        "image_configured": _providers.is_configured(image_provider),
        "concept_provider": concept_provider,
        "concept_model": settings.concept_model or "",
        "prompt_provider": prompt_provider,
        "prompt_model": settings.prompt_model or "",
        "concept_configured": _text_providers.is_configured(concept_provider),
        "prompt_configured": _text_providers.is_configured(prompt_provider),
    }


# ── endpoints ───────────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    """Return the image-provider registry (providers, their models, configured flag)."""
    return {"providers": _providers.get_registry()}


@router.get("/text-providers")
async def list_text_providers():
    """Return the text-provider registry (providers, their models, configured flag)."""
    return {"providers": _text_providers.get_registry()}


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the current global image provider + model."""
    settings = await get_or_create_settings(db)
    return _serialize(settings)


@router.put("/settings")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update the global image and/or text provider+model settings.

    Validates against the respective provider registries:
      - Image provider: aliases like ``nanobanana`` accepted and normalised.
      - Text providers (concept, prompt): exact lower-cased id match.
      - Unknown provider → 400; invalid model for the provider → 400.
      - If the provider changes but no model is supplied, the provider's
        default_model is applied automatically.
      - concept_* and prompt_* pairs are validated and applied independently.
    """
    settings = await get_or_create_settings(db)

    # ── image provider / model ───────────────────────────────────────────────
    raw_provider = body.image_provider if body.image_provider is not None else settings.image_provider
    if not _providers.is_known_provider(raw_provider):
        known = [p["id"] for p in _providers.get_registry()]
        raise HTTPException(400, f"Unknown provider '{raw_provider}'. Known: {known}")
    provider = _providers.canonical_provider(raw_provider)

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

    # ── concept provider / model ─────────────────────────────────────────────
    if body.concept_provider is not None or body.concept_model is not None:
        raw_cp = body.concept_provider if body.concept_provider is not None else settings.concept_provider
        if not _text_providers.is_known_provider(raw_cp):
            known_text = [p["id"] for p in _text_providers.get_registry()]
            raise HTTPException(400, f"Unknown text provider '{raw_cp}'. Known: {known_text}")

        if body.concept_model is not None and body.concept_model != "":
            cm = body.concept_model
            if not _text_providers.is_valid_model(raw_cp, cm):
                valid_cm = _text_providers.model_ids(raw_cp)
                raise HTTPException(
                    400,
                    f"Model '{cm}' is not valid for text provider '{raw_cp}'. Valid: {valid_cm}",
                )
        elif body.concept_provider is not None and body.concept_provider != "":
            # Provider changed but no model → use its default.
            cm = _text_providers.default_model(raw_cp) or ""
        else:
            cm = settings.concept_model
            if not _text_providers.is_valid_model(raw_cp, cm):
                cm = _text_providers.default_model(raw_cp) or ""

        settings.concept_provider = raw_cp.strip().lower()
        settings.concept_model = cm

    # ── prompt provider / model ──────────────────────────────────────────────
    if body.prompt_provider is not None or body.prompt_model is not None:
        raw_pp = body.prompt_provider if body.prompt_provider is not None else settings.prompt_provider
        if not _text_providers.is_known_provider(raw_pp):
            known_text = [p["id"] for p in _text_providers.get_registry()]
            raise HTTPException(400, f"Unknown text provider '{raw_pp}'. Known: {known_text}")

        if body.prompt_model is not None and body.prompt_model != "":
            pm = body.prompt_model
            if not _text_providers.is_valid_model(raw_pp, pm):
                valid_pm = _text_providers.model_ids(raw_pp)
                raise HTTPException(
                    400,
                    f"Model '{pm}' is not valid for text provider '{raw_pp}'. Valid: {valid_pm}",
                )
        elif body.prompt_provider is not None and body.prompt_provider != "":
            # Provider changed but no model → use its default.
            pm = _text_providers.default_model(raw_pp) or ""
        else:
            pm = settings.prompt_model
            if not _text_providers.is_valid_model(raw_pp, pm):
                pm = _text_providers.default_model(raw_pp) or ""

        settings.prompt_provider = raw_pp.strip().lower()
        settings.prompt_model = pm

    await db.commit()
    await db.refresh(settings)
    return _serialize(settings)
