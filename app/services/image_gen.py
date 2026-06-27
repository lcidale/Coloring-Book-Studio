"""
Image generation service. Provider is selected via IMAGE_PROVIDER env var.
Supported: replicate | fal
Returns a local file path to the downloaded image.
"""
import os
import uuid
import httpx
from pathlib import Path

PROVIDER = os.getenv("IMAGE_PROVIDER", "replicate")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))


async def generate_line_art(
    positive_prompt: str,
    negative_prompt: str,
    book_id: str,
    page_id: str,
    version: int = 1,
    width: int = 2550,   # 8.5" × 300 DPI
    height: int = 3300,  # 11" × 300 DPI
) -> Path:
    """Generate line art and save to storage. Returns path relative to STORAGE_DIR."""
    out_dir = STORAGE_DIR / "books" / book_id / "pages" / page_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"v{version:03d}.png"

    if PROVIDER == "replicate":
        url = await _generate_replicate(positive_prompt, negative_prompt, width, height)
    elif PROVIDER == "fal":
        url = await _generate_fal(positive_prompt, negative_prompt, width, height)
    else:
        raise ValueError(f"Unknown IMAGE_PROVIDER: {PROVIDER}")

    await _download(url, out_path)
    return out_path.relative_to(STORAGE_DIR)


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
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
