"""
Image processing: DPI verification, B&W threshold, print-readiness checks.
All operations work on Pillow Images or file paths.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageFilter


@dataclass
class ImageReport:
    width_px: int
    height_px: int
    dpi: int
    is_pure_bw: bool
    gray_pixel_pct: float      # % of pixels that are not pure black or white
    thin_line_warning: bool    # heuristic: many isolated single-pixel lines
    issues: list[str]
    passed: bool


def analyse(image_path: Path, target_dpi: int = 300) -> ImageReport:
    """Run all print-readiness checks. Returns a report."""
    img = Image.open(image_path)
    issues: list[str] = []

    # --- DPI ---
    # Pillow stores DPI as a rational, so 300 round-trips as ~299.9994; round
    # rather than truncate so a correctly-stamped image isn't flagged.
    dpi_info = img.info.get("dpi", (72, 72))
    dpi = round(dpi_info[0]) if isinstance(dpi_info, tuple) else round(dpi_info)
    if dpi < target_dpi:
        issues.append(f"DPI is {dpi} — needs {target_dpi}+")

    # --- Mode ---
    if img.mode not in ("L", "1", "RGB", "RGBA"):
        issues.append(f"Unexpected image mode: {img.mode}")

    # Convert to grayscale for analysis
    gray = img.convert("L")
    w, h = gray.size

    # --- Gray pixel check ---
    pixels = list(gray.getdata())
    total = len(pixels)
    gray_pixels = sum(1 for p in pixels if 5 < p < 250)
    gray_pct = round(gray_pixels / total * 100, 2)
    is_pure_bw = gray_pct < 1.0  # allow <1% for anti-aliasing at edges
    if not is_pure_bw:
        issues.append(f"{gray_pct}% gray pixels — image must be pure B&W")

    # --- Thin line heuristic ---
    # Erode then compare: if many lines disappear, they are thin
    bw = gray.point(lambda p: 0 if p < 128 else 255, "1")
    eroded = bw.filter(ImageFilter.MinFilter(3))
    bw_arr = list(bw.getdata())
    er_arr = list(eroded.getdata())
    disappeared = sum(1 for a, b in zip(bw_arr, er_arr) if a == 0 and b != 0)
    thin_pct = disappeared / max(sum(1 for p in bw_arr if p == 0), 1)
    thin_line_warning = thin_pct > 0.4  # >40% of black pixels are single-pixel wide
    if thin_line_warning:
        issues.append("Many thin lines detected — may not print cleanly at small sizes")

    passed = len(issues) == 0
    return ImageReport(
        width_px=w,
        height_px=h,
        dpi=dpi,
        is_pure_bw=is_pure_bw,
        gray_pixel_pct=gray_pct,
        thin_line_warning=thin_line_warning,
        issues=issues,
        passed=passed,
    )


def threshold_to_pure_bw(image_path: Path, threshold: int = 128) -> Path:
    """
    Convert an image to pure black and white (no grays).
    Overwrites the file in-place and returns the path.
    """
    img = Image.open(image_path).convert("L")
    bw = img.point(lambda p: 0 if p < threshold else 255, "1")
    # Save as PNG, preserving DPI info
    dpi = img.info.get("dpi", (300, 300))
    bw.convert("RGB").save(image_path, format="PNG", dpi=dpi)
    return image_path


def despeckle(image_path: Path, min_size: int = 12, median: int = 3) -> Path:
    """
    Remove tiny black specks/artifacts from a B&W line drawing.

    Two passes: a light median filter to knock out 1-px noise, then connected-
    component removal of any black blob smaller than ``min_size`` pixels.
    Overwrites the file in-place and returns the path.
    """
    img = Image.open(image_path).convert("L")
    dpi = img.info.get("dpi", (300, 300))

    # Pass 1: median filter smooths isolated single-pixel noise.
    if median and median >= 3:
        img = img.filter(ImageFilter.MedianFilter(size=median))

    # Re-threshold so we are working on clean pure B&W.
    bw = img.point(lambda p: 0 if p < 128 else 255, "L")
    w, h = bw.size
    px = bw.load()

    # Pass 2: flood-fill connected black components; drop the small ones.
    visited = bytearray(w * h)
    for sy in range(h):
        row = sy * w
        for sx in range(w):
            if px[sx, sy] != 0 or visited[row + sx]:
                continue
            # BFS over this black component.
            comp: list[tuple[int, int]] = []
            stack = [(sx, sy)]
            visited[row + sx] = 1
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                if len(comp) > min_size:
                    # Big enough — keep it; stop tracking to save work, but
                    # finish marking neighbours so we don't revisit.
                    pass
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        idx = ny * w + nx
                        if not visited[idx] and px[nx, ny] == 0:
                            visited[idx] = 1
                            stack.append((nx, ny))
            if len(comp) < min_size:
                for cx, cy in comp:
                    px[cx, cy] = 255  # erase the speck

    bw.convert("RGB").save(image_path, format="PNG", dpi=dpi)
    return image_path


def autocrop(image_path: Path, border_px: int = 40, threshold: int = 250) -> Path:
    """
    Trim uniform (near-white) borders, then re-pad with an even white margin so
    the artwork sits centered. Overwrites in-place and returns the path.
    """
    img = Image.open(image_path).convert("L")
    dpi = img.info.get("dpi", (300, 300))

    # Anything darker than ``threshold`` is considered content.
    mask = img.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return image_path  # blank image — nothing to crop

    cropped = img.crop(bbox)
    cw, ch = cropped.size
    canvas = Image.new("L", (cw + 2 * border_px, ch + 2 * border_px), color=255)
    canvas.paste(cropped, (border_px, border_px))
    canvas.convert("RGB").save(image_path, format="PNG", dpi=dpi)
    return image_path


def set_dpi(image_path: Path, dpi: int = 300) -> Path:
    """Re-save the image with the correct DPI metadata."""
    img = Image.open(image_path)
    img.save(image_path, format="PNG", dpi=(dpi, dpi))
    return image_path


def cleanup(
    image_path: Path,
    target_dpi: int = 300,
    threshold: int = 128,
    despeckle_min_size: int = 12,
    do_autocrop: bool = True,
    border_px: int = 40,
) -> Path:
    """
    Full raster cleanup pipeline for a generated page, in order:
      1. grayscale -> pure B&W threshold
      2. despeckle (remove tiny specks)
      3. autocrop/trim uniform borders (optional)
      4. stamp target DPI metadata
    Overwrites the file in-place and returns the path.
    """
    threshold_to_pure_bw(image_path, threshold=threshold)
    despeckle(image_path, min_size=despeckle_min_size)
    if do_autocrop:
        autocrop(image_path, border_px=border_px)
    set_dpi(image_path, target_dpi)
    return image_path
