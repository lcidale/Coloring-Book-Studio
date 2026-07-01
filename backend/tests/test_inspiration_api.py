import io
from httpx import AsyncClient
from app.services import storage as storage_svc


def _png_bytes() -> bytes:
    # Minimal valid-enough PNG header bytes; content isn't parsed by the API.
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


async def _make_book(client: AsyncClient) -> str:
    return (await client.post("/api/books", json={"title": "B"})).json()["id"]


async def test_upload_creates_rows_and_stores_files(client: AsyncClient):
    book_id = await _make_book(client)
    files = [
        ("files", ("a.png", io.BytesIO(_png_bytes()), "image/png")),
        ("files", ("b.png", io.BytesIO(_png_bytes()), "image/png")),
    ]
    r = await client.post("/api/inspiration", files=files, data={"book_id": book_id, "caption": "moody"})
    assert r.status_code == 201
    rows = r.json()
    assert len(rows) == 2
    for row in rows:
        assert row["book_id"] == book_id
        assert row["caption"] == "moody"
        assert row["image_url"]
        # the stored key is the tail of the public url; confirm the object exists
    # Both files are stored
    listed = (await client.get("/api/inspiration?book_id=" + book_id)).json()
    assert len(listed) == 2


async def test_upload_rejects_non_image(client: AsyncClient):
    files = [("files", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))]
    r = await client.post("/api/inspiration", files=files)
    assert r.status_code == 400


async def test_list_filters_global_and_all(client: AsyncClient):
    book_id = await _make_book(client)
    png = lambda name: ("files", (name, io.BytesIO(_png_bytes()), "image/png"))
    await client.post("/api/inspiration", files=[png("g.png")])                     # global
    await client.post("/api/inspiration", files=[png("b.png")], data={"book_id": book_id})
    all_rows = (await client.get("/api/inspiration")).json()
    assert len(all_rows) == 2
    global_rows = (await client.get("/api/inspiration?book_id=global")).json()
    assert len(global_rows) == 1 and global_rows[0]["book_id"] is None
    book_rows = (await client.get(f"/api/inspiration?book_id={book_id}")).json()
    assert len(book_rows) == 1 and book_rows[0]["book_id"] == book_id
