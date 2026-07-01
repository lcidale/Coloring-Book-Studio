"""Shared page-version recording used by both the sync and async generation paths."""
from __future__ import annotations

from app.models import Page, PageVersion


def record_version(db, page: Page, version_num: int, rel_path: str,
                   svg_rel: str | None, prompt: str, report) -> PageVersion:
    """Create a PageVersion snapshot and update the page's current-image fields.

    Does not commit — the caller owns the transaction.
    """
    pv = PageVersion(
        page_id=page.id,
        version_num=version_num,
        image_path=str(rel_path),
        svg_path=svg_rel,
        prompt=prompt,
        dpi=report.dpi,
        width_px=report.width_px,
        height_px=report.height_px,
        is_pure_bw=report.is_pure_bw,
    )
    db.add(pv)

    page.image_path = str(rel_path)
    page.image_dpi = report.dpi
    page.image_width_px = report.width_px
    page.image_height_px = report.height_px
    page.is_pure_bw = report.is_pure_bw
    page.print_check_notes = "; ".join(report.issues) if report.issues else "Passed"
    return pv
