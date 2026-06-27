"""
Image generation service. Provider is selected via IMAGE_PROVIDER env var.
Supported: replicate | fal
Returns a storage key (relative path) for the downloaded image.
Files are written through the storage service so that switching
STORAGE_BACKEND=r2 transparently uploads to Cloudflare R2.
"""
import os
import httpx
from pathlib import Path

from app.services import storage as _storage

PROVIDER = os.getenv("IMAGE_PROVIDER", "replicate")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

# Emphatic lead phrase prepended to every positive prompt. Generation models
# weight the opening tokens heavily, so we restate the core constraint up front.
_POSITIVE_LEAD = "clean black and white line art coloring book page"

# Always-on negative reinforcement, merged with the caller's negative prompt so a
# misconfigured style guide can never drop these print-critical exclusions.
_NEGATIVE_FLOOR = "color, grayscale, shading, gradient, text, watermark, blurry"


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


async def generate_line_art(
    positive_prompt: str,
    negative_prompt: str,
    book_id: str,
    page_id: str,
    version: int = 1,
    width: int = 2550,   # 8.5" × 300 DPI
    height: int = 3300,  # 11" × 300 DPI
) -> Path:
    """Generate line art and save to storage. Returns path relative to STORAGE_DIR.

    The file is written through the storage service:
      - local backend: downloaded directly into STORAGE_DIR (same as before).
      - r2 backend: downloaded to a temp file, then uploaded to R2, then the
        temp file is removed. Callers that need a local path for post-processing
        (cleanup, analyse, vectorize) must resolve STORAGE_DIR / key, which the
        local backend fulfils; for R2 the file is also kept locally for those
        in-process steps and then re-uploaded after mutation by the caller.
    """
    key = f"books/{book_id}/pages/{page_id}/v{version:03d}.png"

    positive_prompt, negative_prompt = reinforce_prompts(positive_prompt, negative_prompt)

    if PROVIDER == "replicate":
        url = await _generate_replicate(positive_prompt, negative_prompt, width, height)
    elif PROVIDER == "fal":
        url = await _generate_fal(positive_prompt, negative_prompt, width, height)
    else:
        raise ValueError(f"Unknown IMAGE_PROVIDER: {PROVIDER}")

    # Always download to the local path so that callers (cleanup, analyse,
    # vectorize) can work on the file synchronously.  For the local backend
    # this is the final resting place; for r2 the caller is responsible for
    # calling storage.put_file after post-processing (see generate.py / jobs.py).
    local_path = STORAGE_DIR / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    await _download(url, local_path)

    # For local backend: put_file is a no-op (source == dest).
    # For r2 backend: upload the freshly-downloaded file now; the caller may
    # still mutate the local copy (cleanup/vectorize), after which they should
    # call storage.put_file again to push the final version.
    _storage.put_file(key, local_path, "image/png")

    return Path(key)


async def _generate_replicate(
    positive: str, negative: str, width: int, height: int
) -> str:
    import replicate

    model = os.getenv("REPLICATE_MODEL", "black-forest-labs/flux-1.1-pro")

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
    positive: str, negative: str, width: int, height: int
) -> str:
    import fal_client  # type: ignore

    result = await fal_client.run_async(
        "fal-ai/flux/schnell",
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


async def _download(url: str, dest: Path) -> None:
    """Download URL to a local file path (used internally; storage upload handled by caller)."""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
