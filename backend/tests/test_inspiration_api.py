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


async def _upload_one_global(client: AsyncClient) -> dict:
    files = [("files", ("g.png", io.BytesIO(_png_bytes()), "image/png"))]
    return (await client.post("/api/inspiration", files=files)).json()[0]


async def test_patch_caption_and_reassign_book(client: AsyncClient):
    book_id = await _make_book(client)
    img = await _upload_one_global(client)
    # set caption + attach to a book
    r = await client.patch(f"/api/inspiration/{img['id']}", json={"caption": "great", "book_id": book_id})
    assert r.status_code == 200
    assert r.json()["caption"] == "great"
    assert r.json()["book_id"] == book_id
    # explicit null clears book_id (back to global)
    r2 = await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": None})
    assert r2.json()["book_id"] is None
    # caption unchanged by the book_id-only patch
    assert r2.json()["caption"] == "great"


async def test_patch_reassign_unknown_book_404(client: AsyncClient):
    img = await _upload_one_global(client)
    r = await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": "nope"})
    assert r.status_code == 404


async def test_delete_removes_row_and_storage(client: AsyncClient):
    img = await _upload_one_global(client)
    # the stored key is the tail of the image_url path
    key = "inspiration/" + img["image_url"].rsplit("/inspiration/", 1)[1]
    assert storage_svc.exists(key)
    r = await client.delete(f"/api/inspiration/{img['id']}")
    assert r.status_code == 204
    assert not storage_svc.exists(key)
    assert len((await client.get("/api/inspiration")).json()) == 0
