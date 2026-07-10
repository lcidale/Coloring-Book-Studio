"""
Regression test for POST /api/export/book/{book_id}/pdf.

The router's page query only eager-loaded Page.text_layers; pdf_export.py
also reads page.versions, which triggered a lazy load on the async session
outside of an async context (sqlalchemy.exc.MissingGreenlet) and turned into
a 500 for every real export attempt.
"""
from __future__ import annotations

from httpx import AsyncClient


async def test_export_pdf_for_approved_page_succeeds(client: AsyncClient):
    book = (await client.post("/api/books", json={"title": "T"})).json()
    page = (
        await client.post(
            f"/api/pages/book/{book['id']}",
            json={"concept": "a fox", "sort_order": 0},
        )
    ).json()

    gen = await client.post(
        f"/api/pages/{page['id']}/generate",
        json={"auto_cleanup": False, "vectorize": False},
    )
    assert gen.status_code == 202
    job_id = gen.json()["job_id"]

    import asyncio
    for _ in range(20):
        await asyncio.sleep(0.15)
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            break
    assert job["status"] == "done"

    patched = await client.patch(f"/api/pages/{page['id']}", json={"status": "approved"})
    assert patched.status_code == 200

    r = await client.post(f"/api/export/book/{book['id']}/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
