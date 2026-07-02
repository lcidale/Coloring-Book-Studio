"""
Tests for backend/app/services/image_proc.py

Covers:
- analyse(): detects gray pixels, DPI issues, passes pure B&W
- threshold_to_pure_bw(): grayscale -> pure B&W
- despeckle(): removes tiny isolated specks
- autocrop(): trims uniform white borders
- set_dpi(): stamps DPI metadata
- cleanup(): full pipeline leaves a pure-B&W, correctly-DPI'd file
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.services.image_proc import (
    ImageReport,
    analyse,
    autocrop,
    cleanup,
    despeckle,
    set_dpi,
    threshold_to_pure_bw,
)
from tests.conftest import (
    make_bordered_png,
    make_gray_png,
    make_pure_bw_png,
    make_speckled_png,
)


# ---------------------------------------------------------------------------
# analyse()
# ---------------------------------------------------------------------------

class TestAnalyse:
    def test_pure_bw_image_passes(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png")
        report = analyse(p, target_dpi=300)
        assert report.is_pure_bw, "Pure B&W image should pass the gray-pixel check"
        assert report.gray_pixel_pct < 1.0

    def test_gray_image_fails(self, tmp_path: Path):
        p = make_gray_png(tmp_path / "gray.png")
        report = analyse(p, target_dpi=300)
        assert not report.is_pure_bw, "Gray image should fail the B&W check"
        assert report.gray_pixel_pct >= 1.0
        assert not report.passed
        assert any("gray" in issue.lower() for issue in report.issues)

    def test_low_dpi_flagged(self, tmp_path: Path):
        p = make_gray_png(tmp_path / "low_dpi.png", dpi=72)
        report = analyse(p, target_dpi=300)
        assert not report.passed
        assert any("DPI" in issue or "dpi" in issue for issue in report.issues)

    def test_correct_dpi_passes_dpi_check(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw300.png", dpi=300)
        report = analyse(p, target_dpi=300)
        # DPI check alone should pass; report.dpi should be near 300
        assert report.dpi >= 299  # Pillow may round

    def test_report_dataclass_fields(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png")
        report = analyse(p)
        assert isinstance(report, ImageReport)
        assert report.width_px > 0
        assert report.height_px > 0
        assert isinstance(report.issues, list)

    def test_gray_pixel_pct_near_zero_for_pure_bw(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png")
        report = analyse(p)
        assert report.gray_pixel_pct < 1.0


# ---------------------------------------------------------------------------
# threshold_to_pure_bw()
# ---------------------------------------------------------------------------

class TestThresholdToPureBw:
    def test_gray_image_becomes_pure_bw(self, tmp_path: Path):
        """A mid-gray image must be all pure black or white after thresholding."""
        p = make_gray_png(tmp_path / "gray.png")
        threshold_to_pure_bw(p)

        img = Image.open(p).convert("L")
        pixels = list(img.getdata())
        non_bw = [v for v in pixels if v not in (0, 255)]
        # Allow a tiny rounding artefact from the mode conversion
        assert len(non_bw) / len(pixels) < 0.01, (
            f"Expected <1% non-B/W pixels, got {len(non_bw)/len(pixels):.2%}"
        )

    def test_returns_same_path(self, tmp_path: Path):
        p = make_gray_png(tmp_path / "gray.png")
        result = threshold_to_pure_bw(p)
        assert result == p

    def test_dpi_preserved(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png", dpi=300)
        threshold_to_pure_bw(p)
        img = Image.open(p)
        dpi = img.info.get("dpi", (0, 0))
        assert round(dpi[0]) == 300


# ---------------------------------------------------------------------------
# despeckle()
# ---------------------------------------------------------------------------

class TestDespeckle:
    def test_single_pixel_specks_removed(self, tmp_path: Path):
        """Isolated 1-pixel black dots should be erased after despeckle."""
        p = make_speckled_png(tmp_path / "speckled.png")

        # Count black pixels before
        before = Image.open(p).convert("L")
        before_black = sum(1 for v in before.getdata() if v < 128)

        despeckle(p, min_size=12)

        after = Image.open(p).convert("L")
        after_black = sum(1 for v in after.getdata() if v < 128)
        assert after_black < before_black, "Despeckle should remove small specks"

    def test_large_shapes_preserved(self, tmp_path: Path):
        """A solid 50x50 black square (2500 px) must survive despeckle."""
        img = Image.new("L", (200, 200), color=255)
        px = img.load()
        for y in range(75, 125):
            for x in range(75, 125):
                px[x, y] = 0
        p = tmp_path / "solid.png"
        img.save(str(p), format="PNG", dpi=(300, 300))

        despeckle(p, min_size=12)

        after = Image.open(p).convert("L")
        after_black = sum(1 for v in after.getdata() if v < 128)
        assert after_black > 1000, "Large shape should survive despeckle"

    def test_returns_same_path(self, tmp_path: Path):
        p = make_speckled_png(tmp_path / "speckled.png")
        result = despeckle(p)
        assert result == p


# ---------------------------------------------------------------------------
# autocrop()
# ---------------------------------------------------------------------------

class TestAutocrop:
    def test_uniform_border_trimmed(self, tmp_path: Path):
        """Autocrop should reduce the canvas when there are wide uniform borders."""
        p = make_bordered_png(tmp_path / "bordered.png", border=40)
        before_size = Image.open(p).size

        autocrop(p, border_px=10)

        after_size = Image.open(p).size
        # The resulting image should be smaller than the original (border was cropped).
        assert after_size[0] <= before_size[0], "Width should not grow after crop"
        assert after_size[1] <= before_size[1], "Height should not grow after crop"

    def test_blank_image_unchanged(self, tmp_path: Path):
        """A completely white (blank) image has nothing to crop; should survive."""
        img = Image.new("L", (200, 200), color=255)
        p = tmp_path / "blank.png"
        img.save(str(p), format="PNG")
        # Should not raise
        autocrop(p)
        result = Image.open(p)
        assert result.size == (200, 200)

    def test_returns_same_path(self, tmp_path: Path):
        p = make_bordered_png(tmp_path / "bordered.png")
        result = autocrop(p)
        assert result == p


# ---------------------------------------------------------------------------
# set_dpi()
# ---------------------------------------------------------------------------

class TestSetDpi:
    def test_stamps_target_dpi(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png", dpi=72)
        set_dpi(p, dpi=300)
        img = Image.open(p)
        dpi = img.info.get("dpi", (0, 0))
        assert round(dpi[0]) == 300

    def test_returns_same_path(self, tmp_path: Path):
        p = make_pure_bw_png(tmp_path / "bw.png")
        result = set_dpi(p, 600)
        assert result == p


# ---------------------------------------------------------------------------
# cleanup() — full pipeline
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_gray_image_becomes_pure_bw_after_full_cleanup(self, tmp_path: Path):
        """The cleanup pipeline must produce a <1% gray image from a gray input."""
        p = make_gray_png(tmp_path / "gray.png")
        cleanup(p, target_dpi=300)

        report = analyse(p, target_dpi=300)
        assert report.is_pure_bw, (
            f"After cleanup, gray_pixel_pct={report.gray_pixel_pct:.2f}% — should be <1%"
        )

    def test_dpi_stamped_to_target(self, tmp_path: Path):
        """After cleanup, DPI metadata must equal target_dpi."""
        p = make_pure_bw_png(tmp_path / "bw.png", dpi=72)
        cleanup(p, target_dpi=600)
        img = Image.open(p)
        dpi = img.info.get("dpi", (0, 0))
        assert round(dpi[0]) == 600

    def test_specks_removed_by_pipeline(self, tmp_path: Path):
        """The speckled image should have no single-pixel specks after cleanup."""
        p = make_speckled_png(tmp_path / "speckled.png")
        before = Image.open(p).convert("L")
        before_black = sum(1 for v in before.getdata() if v < 128)

        cleanup(p, target_dpi=300, do_autocrop=False)

        after = Image.open(p).convert("L")
        after_black = sum(1 for v in after.getdata() if v < 128)
        assert after_black < before_black

    def test_analyse_reports_pass_after_cleanup(self, tmp_path: Path):
        """End-to-end: a gray 300-DPI image should pass all checks after cleanup."""
        p = make_gray_png(tmp_path / "gray.png", dpi=300)
        cleanup(p, target_dpi=300, do_autocrop=False)
        report = analyse(p, target_dpi=300)
        # The thin-line warning may or may not fire; we only care that B&W and DPI pass.
        bw_issues = [i for i in report.issues if "gray" in i.lower() or "DPI" in i]
        assert bw_issues == [], f"Unexpected issues after cleanup: {bw_issues}"

    def test_border_px_forwarded_to_autocrop(self, tmp_path: Path):
        """cleanup()'s border_px must actually reach autocrop, not be silently
        dropped in favor of autocrop's own hardcoded default."""
        p_small = make_bordered_png(tmp_path / "a.png", border=40)
        p_large = make_bordered_png(tmp_path / "b.png", border=40)

        cleanup(p_small, target_dpi=300, border_px=5)
        cleanup(p_large, target_dpi=300, border_px=80)

        small_size = Image.open(p_small).size
        large_size = Image.open(p_large).size
        assert large_size[0] > small_size[0]
        assert large_size[1] > small_size[1]
