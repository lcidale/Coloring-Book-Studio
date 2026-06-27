"""Canva Connect REST API service.

Wraps the Canva Connect API (https://api.canva.com/rest/v1/) to create
cover/marketing designs and export them as PDF or PNG.

Verified API reference (2025):
  Base URL:       https://api.canva.com/rest/v1
  Auth header:    Authorization: Bearer <CANVA_ACCESS_TOKEN>
  Create design:  POST /designs
  Create export:  POST /exports          (async job)
  Poll export:    GET  /exports/{jobId}
  Autofill:       POST /autofills        (brand-template text/image fill)
  Auth docs:      https://www.canva.dev/docs/connect/authentication/
  Designs ref:    https://www.canva.dev/docs/connect/api-reference/designs/create-design/
  Exports ref:    https://www.canva.dev/docs/connect/api-reference/exports/create-design-export-job/
  Get export:     https://www.canva.dev/docs/connect/api-reference/exports/get-design-export-job/

Environment variables required:
    CANVA_ACCESS_TOKEN   – OAuth2 Bearer token (raises RuntimeError if absent)
    CANVA_API_BASE_URL   – Override base URL (optional; defaults to
                           https://api.canva.com/rest/v1)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.canva.com/rest/v1"

# Polling config for async export jobs
_POLL_INTERVAL_S = 2.0
_POLL_MAX_ATTEMPTS = 30  # 30 * 2s = 60 s timeout


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> tuple[str, httpx.AsyncClient]:
    """Return (base_url, configured httpx.AsyncClient).

    Raises RuntimeError if CANVA_ACCESS_TOKEN is not set.
    """
    token = os.environ.get("CANVA_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "CANVA_ACCESS_TOKEN is not configured. "
            "Set it in your .env file to enable Canva integration."
        )
    base_url = os.environ.get("CANVA_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return base_url, client


def _raise_for_canva(response: httpx.Response) -> None:
    """Raise a descriptive RuntimeError for non-2xx Canva responses."""
    if response.is_success:
        return
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    raise RuntimeError(
        f"Canva API error {response.status_code}: {detail}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_cover(
    book_title: str,
    subtitle: str = "",
    brand_template_id: str | None = None,
) -> dict[str, Any]:
    """Create a Canva cover design for a coloring book.

    If *brand_template_id* is provided the design is created from that brand
    template (POST /designs with type=brand_template).  Otherwise a blank
    custom A4-portrait design is created and titled with *book_title*.

    Args:
        book_title:         The coloring book title (used as the design title
                            and, when autofilling a template, as the headline
                            text field value).
        subtitle:           Optional subtitle / tagline string.
        brand_template_id:  Optional Canva brand template ID to clone.

    Returns:
        dict with keys:
            design_id  – Canva design identifier
            edit_url   – 30-day temporary direct-edit URL
            view_url   – 30-day temporary view URL (may be absent)

    Raises:
        RuntimeError: if CANVA_ACCESS_TOKEN is not set or the API call fails.
    """
    _, client = _get_client()

    async with client:
        if brand_template_id:
            # Create from brand template — the user can then customise in Canva
            body: dict[str, Any] = {
                "design_type": {
                    "type": "brand_template",
                    "brand_template_id": brand_template_id,
                },
                "title": book_title[:255],
            }
        else:
            # Blank custom design at 6 x 9 inch cover (@ 96 dpi logical units
            # Canva accepts width/height in px; we use a standard KDP cover
            # aspect ratio: 1800 x 2700 px ≈ 6 x 9 in @ 300 dpi)
            body = {
                "design_type": {
                    "type": "custom",
                    "width": 1800,
                    "height": 2700,
                },
                "title": book_title[:255],
            }

        resp = await client.post("/designs", json=body)
        _raise_for_canva(resp)
        data = resp.json()

    design = data.get("design", {})
    urls = design.get("urls", {})

    return {
        "design_id": design.get("id", ""),
        "edit_url": urls.get("edit_url", ""),
        "view_url": urls.get("view_url", ""),
    }


async def export_asset(
    design_id: str,
    format: str = "png",  # noqa: A002
) -> dict[str, Any]:
    """Export a Canva design to PDF or PNG and return the download URL.

    The Canva export API is asynchronous — this function creates the export
    job then polls GET /exports/{jobId} until status is 'success' or 'failed'.

    Args:
        design_id:  The Canva design ID (from create_cover).
        format:     Export format string — 'pdf' or 'png' (default 'png').
                    Any Canva-supported format is accepted (jpg, gif, pptx …).

    Returns:
        dict with keys:
            job_id       – Canva export job ID
            download_url – First download URL from the completed job
            all_urls     – Full list of download URLs (one per page for PDFs)
            format       – The format that was requested

    Raises:
        RuntimeError: if CANVA_ACCESS_TOKEN is not set, the API call fails,
                      the job fails, or the job does not complete within the
                      poll timeout.
    """
    _, client = _get_client()

    async with client:
        # Step 1 — create the export job
        export_body: dict[str, Any] = {
            "design_id": design_id,
            "format": {"type": format},
        }
        create_resp = await client.post("/exports", json=export_body)
        _raise_for_canva(create_resp)

        job = create_resp.json().get("job", {})
        job_id: str = job.get("id", "")
        status: str = job.get("status", "in_progress")

        # Step 2 — poll until done
        attempts = 0
        while status == "in_progress" and attempts < _POLL_MAX_ATTEMPTS:
            await asyncio.sleep(_POLL_INTERVAL_S)
            poll_resp = await client.get(f"/exports/{job_id}")
            _raise_for_canva(poll_resp)
            job = poll_resp.json().get("job", {})
            status = job.get("status", "in_progress")
            attempts += 1

        if status == "failed":
            err = job.get("error", {})
            raise RuntimeError(
                f"Canva export job {job_id} failed: "
                f"{err.get('code', 'unknown')} — {err.get('message', '')}"
            )

        if status == "in_progress":
            raise RuntimeError(
                f"Canva export job {job_id} did not complete within "
                f"{_POLL_MAX_ATTEMPTS * _POLL_INTERVAL_S:.0f} seconds."
            )

        all_urls: list[str] = job.get("urls", [])
        return {
            "job_id": job_id,
            "download_url": all_urls[0] if all_urls else "",
            "all_urls": all_urls,
            "format": format,
        }
