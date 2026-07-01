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


async def test_generate_uses_sticky_reference(client: AsyncClient, monkeypatch):
    import app.routers.generate as gen_mod
    captured = {}

    async def fake_gla(*args, **kwargs):
        captured["reference_image_key"] = kwargs.get("reference_image_key")
        # return a real relative path with a file so downstream cleanup/analyse works
        from pathlib import Path
        rel = f"books/{kwargs['book_id']}/pages/{kwargs['page_id']}/v{kwargs['version']:03d}.png"
        p = gen_mod.STORAGE_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        from tests.conftest import make_pure_bw_png
        make_pure_bw_png(p)
        return Path(rel)
    monkeypatch.setattr(gen_mod, "generate_line_art", fake_gla)

    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client, book_id=book_id)
    await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})

    r = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert r.status_code == 200
    # the sticky reference's storage key was passed to generation
    assert captured["reference_image_key"].startswith("inspiration/")


async def test_generate_override_beats_sticky(client: AsyncClient, monkeypatch):
    import app.routers.generate as gen_mod
    captured = {}

    async def fake_gla(*args, **kwargs):
        captured["reference_image_key"] = kwargs.get("reference_image_key")
        from pathlib import Path
        rel = f"books/{kwargs['book_id']}/pages/{kwargs['page_id']}/v{kwargs['version']:03d}.png"
        p = gen_mod.STORAGE_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        from tests.conftest import make_pure_bw_png
        make_pure_bw_png(p)
        return Path(rel)
    monkeypatch.setattr(gen_mod, "generate_line_art", fake_gla)

    book_id, page = await _book_page(client)
    sticky = await _upload_inspiration(client, book_id=book_id)
    override = await _upload_inspiration(client, book_id=book_id)
    await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": sticky["id"]})

    r = await client.post(
        f"/api/generate/{page['id']}",
        json={"auto_cleanup": False, "vectorize": False, "reference_image_id": override["id"]},
    )
    assert r.status_code == 200
    # override key differs from sticky key
    sticky_key = "inspiration/" + sticky["image_url"].rsplit("/inspiration/", 1)[1]
    override_key = "inspiration/" + override["image_url"].rsplit("/inspiration/", 1)[1]
    assert captured["reference_image_key"] == override_key != sticky_key


async def test_generate_override_from_other_book_400(client: AsyncClient):
    book_id, page = await _book_page(client)
    other = (await client.post("/api/books", json={"title": "O"})).json()["id"]
    bad = await _upload_inspiration(client, book_id=other)
    r = await client.post(
        f"/api/generate/{page['id']}",
        json={"auto_cleanup": False, "vectorize": False, "reference_image_id": bad["id"]},
    )
    assert r.status_code == 400


async def test_delete_inspiration_clears_page_reference(client: AsyncClient):
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client, book_id=book_id)
    await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    # delete the inspiration image
    r = await client.delete(f"/api/inspiration/{img['id']}")
    assert r.status_code == 204
    # the page's reference is now cleared
    refreshed = (await client.get(f"/api/pages/{page['id']}")).json()
    assert refreshed["reference_image_id"] is None


async def test_delete_book_with_referenced_image_ok(client: AsyncClient):
    # Create a book+page, upload a book-scoped inspiration image, set it as reference,
    # then delete the book — should complete cleanly (no FK violation).
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client, book_id=book_id)
    r = await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 200
    assert r.json()["reference_image_id"] == img["id"]
    r = await client.delete(f"/api/books/{book_id}")
    assert r.status_code == 204
