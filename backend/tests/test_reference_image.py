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


async def _upload_inspiration(client, book_id=None) -> dict:
    files = [("files", ("i.png", io.BytesIO(_png()), "image/png"))]
    data = {"book_id": book_id} if book_id else {}
    return (await client.post("/api/inspiration", files=files, data=data)).json()[0]


async def test_set_sticky_reference_global_ok(client: AsyncClient):
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client)  # global
    r = await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 200
    assert r.json()["reference_image_id"] == img["id"]
    assert r.json()["reference_image_url"]


async def test_set_reference_from_same_book_ok(client: AsyncClient):
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client, book_id=book_id)
    r = await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 200


async def test_set_reference_from_other_book_400(client: AsyncClient):
    _, page = await _book_page(client)
    other_book = (await client.post("/api/books", json={"title": "Other"})).json()["id"]
    img = await _upload_inspiration(client, book_id=other_book)
    r = await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 400


async def test_clear_reference_with_null(client: AsyncClient):
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client)
    await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    r = await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": None})
    assert r.status_code == 200
    assert r.json()["reference_image_id"] is None
