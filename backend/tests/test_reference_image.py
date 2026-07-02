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


async def test_reassigning_image_to_another_book_clears_cross_book_reference(client: AsyncClient):
    """ce-review #5 (P1): a page in book B holds a global image as its sticky
    reference (valid at the time). Reassigning that image to book A must clear
    book B's now-invalid reference, not leave it dangling."""
    book_b, page_b = await _book_page(client)
    img = await _upload_inspiration(client)  # global at first
    r = await client.patch(f"/api/pages/{page_b['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 200 and r.json()["reference_image_id"] == img["id"]

    book_a, _ = await _book_page(client)
    r = await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": book_a})
    assert r.status_code == 200

    refreshed = (await client.get(f"/api/pages/{page_b['id']}")).json()
    assert refreshed["reference_image_id"] is None, (
        "page in book B must have its now-invalid cross-book reference cleared"
    )


async def test_delete_book_removes_cross_book_dangling_reference(client: AsyncClient):
    """Companion to the above: even if a cross-book reference were to exist,
    deleting the image's owning book must clean it up regardless of which
    book the referencing page belongs to (not just Page.book_id == book_id)."""
    book_b, page_b = await _book_page(client)
    img = await _upload_inspiration(client)  # global
    r = await client.patch(f"/api/pages/{page_b['id']}", json={"reference_image_id": img["id"]})
    assert r.status_code == 200

    book_a, _ = await _book_page(client)
    await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": book_a})
    # (the reassignment fix above already clears page_b's reference at this point;
    # this test's real assertion is that deleting book_a — which now owns the
    # image — never fails, and any residual reference from another book is gone.)

    r = await client.delete(f"/api/books/{book_a}")
    assert r.status_code == 204

    refreshed = (await client.get(f"/api/pages/{page_b['id']}")).json()
    assert refreshed["reference_image_id"] is None


async def test_reorder_response_includes_reference_image_url(client: AsyncClient):
    """ce-review #3 (P1): reorder_pages must not silently drop reference_image_url
    from its response (it was previously missing the _attach_reference call)."""
    book_id, page1 = await _book_page(client)
    page2 = (await client.post(f"/api/pages/book/{book_id}", json={"concept": "bear", "sort_order": 1})).json()
    img = await _upload_inspiration(client, book_id=book_id)
    await client.patch(f"/api/pages/{page1['id']}", json={"reference_image_id": img["id"]})

    r = await client.patch(f"/api/pages/book/{book_id}/reorder", json={"page_ids": [page2["id"], page1["id"]]})
    assert r.status_code == 200
    reordered_page1 = next(p for p in r.json() if p["id"] == page1["id"])
    assert reordered_page1["reference_image_id"] == img["id"]
    assert reordered_page1["reference_image_url"] is not None, (
        "reorder response must include reference_image_url when a reference is set"
    )


async def test_restore_version_response_includes_reference_image_url(client: AsyncClient):
    """Companion to the above for restore_version, which had the same gap."""
    book_id, page = await _book_page(client)
    img = await _upload_inspiration(client, book_id=book_id)
    await client.patch(f"/api/pages/{page['id']}", json={"reference_image_id": img["id"]})

    gen = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert gen.status_code == 200
    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v1_id = versions[0]["id"]

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1_id}/restore")
    assert r.status_code == 200
    assert r.json()["reference_image_id"] == img["id"]
    assert r.json()["reference_image_url"] is not None, (
        "restore response must include reference_image_url when a reference is set"
    )


async def test_use_version_as_reference_sets_sticky_reference(client: AsyncClient):
    book_id, page = await _book_page(client)
    gen = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert gen.status_code == 200
    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v1_id = versions[0]["id"]

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1_id}/use-as-reference")
    assert r.status_code == 200
    body = r.json()
    assert body["reference_image_id"] is not None
    assert body["reference_image_url"] is not None

    # the new inspiration image is scoped to this page's book
    listed = (await client.get(f"/api/inspiration?book_id={book_id}")).json()
    assert any(img["id"] == body["reference_image_id"] for img in listed)


async def test_use_version_as_reference_copies_bytes_independently(client: AsyncClient):
    """Deleting the SOURCE version afterward must not affect the new reference —
    proves the new inspiration image has its own storage object, not a shared key."""
    from app.services import storage as storage_svc

    book_id, page = await _book_page(client)
    gen1 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    gen2 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert gen1.status_code == 200 and gen2.status_code == 200
    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v1_id = next(v["id"] for v in versions if v["version_num"] == 1)  # not current (v2 is)

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1_id}/use-as-reference")
    assert r.status_code == 200
    ref_url = r.json()["reference_image_url"]
    ref_key = "inspiration/" + ref_url.rsplit("/inspiration/", 1)[1]
    assert storage_svc.exists(ref_key)

    del_resp = await client.delete(f"/api/pages/{page['id']}/versions/{v1_id}")
    assert del_resp.status_code == 204

    refreshed = (await client.get(f"/api/pages/{page['id']}")).json()
    assert refreshed["reference_image_id"] == r.json()["reference_image_id"], (
        "the reference must survive deletion of the source version"
    )
    assert storage_svc.exists(ref_key), "the new inspiration image's own file must be untouched"


async def test_use_version_as_reference_404_unknown_version(client: AsyncClient):
    _, page = await _book_page(client)
    r = await client.post(f"/api/pages/{page['id']}/versions/nope/use-as-reference")
    assert r.status_code == 404


async def test_use_version_as_reference_404_unknown_page(client: AsyncClient):
    r = await client.post("/api/pages/nope/versions/nope/use-as-reference")
    assert r.status_code == 404
