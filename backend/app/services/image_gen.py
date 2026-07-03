"""
Image generation service.

Provider + model are resolved per call in this order (first hit wins):
    1. explicit ``provider`` / ``model`` arguments to generate_line_art()
    2. the global AppSettings row (when a DB session is passed)
    3. environment defaults (IMAGE_PROVIDER + per-provider model env vars)

Supported providers (see services/providers.py for the registry):
    replicate | fal | gemini (aka nanobanana)

Returns a storage key (relative path) for the generated image.  Files are
written through the storage service so that switching STORAGE_BACKEND=r2
transparently uploads to Cloudflare R2.

Provider contract
-----------------
URL-based providers (replicate, fal) return a remote URL that
generate_line_art() downloads.  The Gemini provider returns raw PNG bytes
inline (the SDK gives us image bytes in the response, not a URL), so it returns
a ``bytes`` object instead of a URL string.  generate_line_art() handles both
shapes transparently.
"""
import logging
import os
import httpx
from pathlib import Path
from typing import Optional

from app.services import providers as _providers
from app.services import storage as _storage

_log = logging.getLogger(__name__)

_MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _mime_for_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


# Aspect ratios Gemini's image generation API accepts (as of 2026). Passing an
# unsupported string is rejected by the API, so callers must snap to one of
# these rather than send an arbitrary page ratio.
_GEMINI_ASPECT_RATIOS: dict[str, float] = {
    "1:1": 1.0,
    "2:3": 2 / 3,
    "3:2": 3 / 2,
    "3:4": 3 / 4,
    "4:3": 4 / 3,
    "4:5": 4 / 5,
    "5:4": 5 / 4,
    "9:16": 9 / 16,
    "16:9": 16 / 9,
    "21:9": 21 / 9,
}


def _aspect_ratio_bucket(width: int, height: int) -> str:
    """Snap a pixel width/height to the nearest Gemini-supported aspect ratio.

    Root cause of "images come out square": _generate_gemini never told the
    model what aspect ratio to use, so it defaulted to 1:1 regardless of the
    width/height the caller requested.
    """
    if not width or not height:
        return "1:1"
    ratio = width / height
    return min(_GEMINI_ASPECT_RATIOS, key=lambda k: abs(_GEMINI_ASPECT_RATIOS[k] - ratio))


STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

# Emphatic lead phrase prepended to every positive prompt. Generation models
# weight the opening tokens heavily, so we restate the core constraint up front.
_POSITIVE_LEAD = "clean black and white line art coloring book page"

# Always-on negative reinforcement, merged with the caller's negative prompt so a
# misconfigured style guide can never drop these print-critical exclusions.
_NEGATIVE_FLOOR = "color, grayscale, shading, gradient, text, watermark, blurry"

# Gemini has no negative-prompt parameter, so its negatives are folded into a
# strong positive constraint appended to the prompt (see _generate_gemini).
_GEMINI_POSITIVE_CONSTRAINT = (
    "Render as pure black and white line art only: clean crisp black outlines, "
    "no shading, no grayscale, no color, no fill, on a plain white background. "
    "Keep the entire design fully contained within the frame with a small internal "
    "safety margin — nothing should bleed, run off, or be cropped at the edge of "
    "the canvas; every element must appear whole and complete on the page."
)


def reinforce_prompts(positive: str, negative: str) -> tuple[str, str]:
    """Strengthen prompts at the generation seam (idempotent-ish, dedup-safe)."""
    positive = positive.strip()
    if _POSITIVE_LEAD.lower() not in positive.lower():
        positive = f"{_POSITIVE_LEAD}, {positive}" if positive else _POSITIVE_LEAD

    neg_terms = [t.strip() for t in (negative or "").split(",") if t.strip()]
    seen = {t.lower() for t in neg_terms}
    for term in _NEGATIVE_FLOOR.split(","):
        term = term.strip()
        if term and term.lower() not in seen:
            neg_terms.append(term)
            seen.add(term.lower())
    return positive, ", ".join(neg_terms)


# ---------------------------------------------------------------------------
# Provider + model resolution
# ---------------------------------------------------------------------------

def env_default_provider_model() -> tuple[str, str]:
    """Resolve the (provider, model) defaults from environment variables.

    Used to seed the AppSettings row on first access and as the final fallback
    when no explicit arg and no global setting is available.
    """
    provider = _providers.canonical_provider(os.getenv("IMAGE_PROVIDER")) or _providers.DEFAULT_PROVIDER
    if not _providers.is_known_provider(provider):
        provider = _providers.DEFAULT_PROVIDER
    model = _env_model_for(provider) or _providers.default_model(provider) or ""
    return provider, model


def _env_model_for(provider: str) -> Optional[str]:
    """Per-provider model override env var (falls back to registry default)."""
    if provider == "replicate":
        return os.getenv("REPLICATE_MODEL")
    if provider == "fal":
        return os.getenv("FAL_MODEL")
    if provider == "gemini":
        return os.getenv("GEMINI_IMAGE_MODEL")
    return None


async def _resolve_provider_model(
    provider: Optional[str],
    model: Optional[str],
    db,
) -> tuple[str, str]:
    """Resolve the effective (provider, model) for a generation call.

    Order: explicit arg -> global AppSettings (if db given) -> env default.
    The model is validated against the registry and falls back to the
    provider's default model if missing/invalid.
    """
    # 1) explicit provider arg
    resolved_provider = _providers.canonical_provider(provider)

    # 2) global AppSettings
    if not resolved_provider and db is not None:
        try:
            from sqlalchemy import select
            from app.models import AppSettings
            row = (
                await db.execute(select(AppSettings).where(AppSettings.id == "global"))
            ).scalar_one_or_none()
            if row and row.image_provider:
                resolved_provider = _providers.canonical_provider(row.image_provider)
                if model is None and row.image_model:
                    model = row.image_model
        except Exception:
            # Never let settings lookup break generation — fall through to env.
            resolved_provider = resolved_provider or None

    # 3) env default
    if not resolved_provider or not _providers.is_known_provider(resolved_provider):
        resolved_provider, env_model = env_default_provider_model()
        if model is None:
            model = env_model

    # Validate / default the model for the resolved provider.
    if not _providers.is_valid_model(resolved_provider, model):
        model = _env_model_for(resolved_provider) or _providers.default_model(resolved_provider)

    return resolved_provider, model or ""


async def generate_line_art(
    positive_prompt: str,
    negative_prompt: str,
    book_id: str,
    page_id: str,
    version: int = 1,
    width: int = 2550,   # 8.5" × 300 DPI
    height: int = 3300,  # 11" × 300 DPI
    provider: Optional[str] = None,
    model: Optional[str] = None,
    db=None,
    reference_image_key: Optional[str] = None,
) -> Path:
    """Generate line art and save to storage. Returns path relative to STORAGE_DIR.

    provider/model are resolved via _resolve_provider_model():
        explicit arg -> global AppSettings (when ``db`` is passed) -> env default.

    The file is written through the storage service:
      - local backend: downloaded directly into STORAGE_DIR (same as before).
      - r2 backend: written locally for in-process post-processing then uploaded.
    """
    key = f"books/{book_id}/pages/{page_id}/v{version:03d}.png"

    positive_prompt, negative_prompt = reinforce_prompts(positive_prompt, negative_prompt)

    resolved_provider, resolved_model = await _resolve_provider_model(provider, model, db)

    reference: Optional[tuple[bytes, str]] = None
    if reference_image_key:
        reference = (_storage.get_bytes(reference_image_key), _mime_for_key(reference_image_key))

    if resolved_provider == "replicate":
        if reference is not None:
            _log.info("reference image supplied but replicate does not support it; ignoring")
        result = await _generate_replicate(positive_prompt, negative_prompt, width, height, resolved_model)
    elif resolved_provider == "fal":
        if reference is not None:
            _log.info("reference image supplied but fal does not support it; ignoring")
        result = await _generate_fal(positive_prompt, negative_prompt, width, height, resolved_model)
    elif resolved_provider == "gemini":
        result = await _generate_gemini(positive_prompt, negative_prompt, width, height, resolved_model, reference)
    else:
        raise ValueError(f"Unknown image provider: {resolved_provider}")

    # Always materialise the image at the local path so that callers (cleanup,
    # analyse, vectorize) can work on the file synchronously.
    local_path = STORAGE_DIR / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(result, (bytes, bytearray)):
        # Inline-bytes providers (gemini): write the image data straight to disk.
        local_path.write_bytes(bytes(result))
    else:
        # URL-based providers (replicate, fal): fetch the remote artifact.
        await _download(result, local_path)

    # local backend: put_file is a no-op (source == dest).
    # r2 backend: upload now; caller may mutate the local copy then put_file again.
    _storage.put_file(key, local_path, "image/png")

    return Path(key)


async def _generate_replicate(
    positive: str, negative: str, width: int, height: int, model: str
) -> str:
    import replicate

    model = model or _providers.default_model("replicate")

    output = await replicate.async_run(
        model,
        input={
            "prompt": positive,
            "negative_prompt": negative,
            "width": width,
            "height": height,
            "num_inference_steps": 28,
            "guidance_scale": 7.5,
            "output_format": "png",
            "output_quality": 100,
        },
    )
    # replicate returns a list or a single FileOutput
    if isinstance(output, list):
        return str(output[0])
    return str(output)


async def _generate_fal(
    positive: str, negative: str, width: int, height: int, model: str
) -> str:
    import fal_client  # type: ignore

    model = model or _providers.default_model("fal")

    result = await fal_client.run_async(
        model,
        arguments={
            "prompt": positive,
            "negative_prompt": negative,
            "image_size": {"width": width, "height": height},
            "num_inference_steps": 4,
            "num_images": 1,
            "enable_safety_checker": False,
        },
    )
    return result["images"][0]["url"]


async def _generate_gemini(
    positive: str, negative: str, width: int, height: int, model: str,
    reference: Optional[tuple[bytes, str]] = None,
) -> bytes:
    """Generate line art with Google's Nano Banana (Gemini image model).

    Uses the google-genai SDK's ``client.aio.models.generate_content`` with
    ``response_modalities=["IMAGE"]``.  Gemini has no negative-prompt parameter,
    so the negatives are folded into a strong positive constraint appended to the
    prompt.  The image comes back as inline bytes in a response part
    (``part.inline_data.data``), which we return directly.

    Raises a clear, non-500 error when no API key is configured.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Gemini (Nano Banana) image provider is not configured: set "
            "GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment."
        )

    from google import genai
    from google.genai import types

    model = model or _providers.default_model("gemini")

    # Fold the negative prompt into a strong positive constraint, since Gemini
    # does not accept a separate negative prompt.
    prompt_parts = [positive, _GEMINI_POSITIVE_CONSTRAINT]
    if negative:
        prompt_parts.append(f"Avoid: {negative}.")
    prompt = " ".join(p for p in prompt_parts if p)

    client = genai.Client(api_key=api_key)
    if reference is not None:
        ref_bytes, ref_mime = reference
        contents = [types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime), prompt]
    else:
        contents = prompt
    aspect_ratio = _aspect_ratio_bucket(width, height)
    response = await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )

    image_bytes = _extract_image_bytes(response)
    if image_bytes is None:
        raise RuntimeError(
            f"Gemini ({model}) returned no image data in the response."
        )
    return image_bytes


def _extract_image_bytes(response) -> Optional[bytes]:
    """Pull the first inline image blob out of a GenerateContentResponse."""
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline else None
            if data:
                return bytes(data)
    return None


async def _download(url: str, dest: Path) -> None:
    """Download URL to a local file path (used internally; storage upload handled by caller)."""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
