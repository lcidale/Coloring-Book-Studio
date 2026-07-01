import io
from httpx import AsyncClient


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


async def _book_page(client: AsyncClient):
    book_id = (await client.post("/api/books", json={"title": "B"})).json()["id"]
    page = (await client.post(f"/api/pages/book/{book_id}", json={"concept": "fox"})).json()
    return book_id, page


async def test_page_payload_has_reference_fields(client: AsyncClient):
    _, page = await _book_page(client)
    assert page["reference_image_id"] is None
    assert page["reference_image_url"] is None
