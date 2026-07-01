"""
Tests for PATCH /api/pages/book/{book_id}/reorder — bulk reorder endpoint.

Uses the shared ``client`` fixture from conftest.py (isolated DB per test).
asyncio_mode="auto" — no marker needed.
"""
from __future__ import annotations


async def test_reorder_rewrites_sort_order_contiguously(client):
    book = (await client.post("/api/books", json={"title": "B"})).json()
    ids = []
    for i in range(3):
        p = (await client.post(f"/api/pages/book/{book['id']}",
                               json={"concept": f"c{i}", "sort_order": i})).json()
        ids.append(p["id"])
    new_order = [ids[2], ids[0], ids[1]]
    r = await client.patch(f"/api/pages/book/{book['id']}/reorder",
                           json={"page_ids": new_order})
    assert r.status_code == 200
    returned = r.json()
    assert [p["id"] for p in returned] == new_order
    assert [p["sort_order"] for p in returned] == [0, 1, 2]


async def test_reorder_rejects_foreign_page(client):
    book = (await client.post("/api/books", json={"title": "B"})).json()
    p = (await client.post(f"/api/pages/book/{book['id']}",
                           json={"concept": "c"})).json()
    r = await client.patch(f"/api/pages/book/{book['id']}/reorder",
                           json={"page_ids": [p["id"], "not-in-book"]})
    assert r.status_code == 400


async def test_reorder_rejects_subset(client):
    book = (await client.post("/api/books", json={"title": "B"})).json()
    ids = []
    for i in range(2):
        p = (await client.post(f"/api/pages/book/{book['id']}",
                               json={"concept": f"c{i}"})).json()
        ids.append(p["id"])
    r = await client.patch(f"/api/pages/book/{book['id']}/reorder",
                           json={"page_ids": [ids[0]]})
    assert r.status_code == 400


async def test_reorder_rejects_duplicate(client):
    book = (await client.post("/api/books", json={"title": "B"})).json()
    ids = []
    for i in range(2):
        p = (await client.post(f"/api/pages/book/{book['id']}",
                               json={"concept": f"c{i}"})).json()
        ids.append(p["id"])
    r = await client.patch(f"/api/pages/book/{book['id']}/reorder",
                           json={"page_ids": [ids[0], ids[0]]})
    assert r.status_code == 400
