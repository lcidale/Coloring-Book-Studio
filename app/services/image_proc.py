"""
Image processing: DPI verification, B&W threshold, print-readiness checks.
All operations work on Pillow Images or file paths.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps


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
    dpi_info = img.info.get("dpi", (72, 72))
    dpi = int(dpi_info[0]) if isinstance(dpi_info, tuple) else int(dpi_info)
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


def set_dpi(image_path: Path, dpi: int = 300) -> Path:
    """Re-save the image with the correct DPI metadata."""
    img = Image.open(image_path)
    img.save(image_path, format="PNG", dpi=(dpi, dpi))
    return image_path
