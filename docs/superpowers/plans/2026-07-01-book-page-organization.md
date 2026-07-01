# Book & Page Organization + Version History — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface existing backend book/page/version capabilities in the UI — rename/delete books, give pages a short title + auto page number, drag-reorder and delete pages, and browse every version of a page (view/copy prompt, restore, label, delete).

**Architecture:** Small additive backend changes (new nullable columns via the existing column-migration mechanism; a handful of new endpoints on the existing `pages` router; one shared version-recording helper to DRY the two generation paths), then a frontend layer that adds TanStack Query hooks and wires new UI into the three existing screens plus one new `VersionsPanel` component.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Pydantic, Python 3.12 (uv). React 19 + Vite + Tailwind 4 + shadcn/ui (Radix) + TanStack Query. New frontend deps: `@radix-ui/react-dropdown-menu`, `@radix-ui/react-alert-dialog`, `@dnd-kit/core`, `@dnd-kit/sortable`. Tests: pytest (backend), Vitest/RTL (frontend).

## Global Constraints

- **No Alembic.** Schema evolution is: SQLAlchemy models are source of truth; `create_all()` for fresh DBs; new columns added to existing DBs via idempotent entries in `_COLUMN_MIGRATIONS` in `backend/app/database.py` (applied on startup to both SQLite and Postgres).
- **New columns must be nullable with no DEFAULT clause** so one DDL string works for both SQLite and Postgres.
- **Run backend tests** from repo root: `uv run --directory backend pytest`. Always `export PATH="$HOME/.local/bin:$HOME/.local/node-v24.18.0-darwin-arm64/bin:$PATH"` first.
- **Run frontend tests** with the known worker-timeout workaround: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism`.
- **Image URLs:** page/version `image_path` is a storage KEY; the API serializes it to a URL via `storage.public_url(key)`. The frontend `pageImageSrc()` helper handles absolute-vs-relative.
- **"Current" version** is defined as: the `PageVersion` whose `image_path == page.image_path`. Restore copies fields; it never renumbers or deletes.
- **Page number** is derived (1-based index in `sort_order`), never stored.

### Shared contract (names used across tasks — do not drift)

**New/changed columns:**
- `Page.title: str` (nullable) — short page name.
- `PageVersion.label: str` (nullable, `VARCHAR(120)`) — short annotation chip.
- `PageVersion.dpi: int` (nullable), `PageVersion.width_px: int` (nullable), `PageVersion.height_px: int` (nullable), `PageVersion.is_pure_bw: bool` (nullable) — print metadata.

**New endpoints (all on the existing `pages` router, prefix `/api/pages`):**
- `GET /api/pages/{page_id}/versions` → `list[VersionDict]`
- `POST /api/pages/{page_id}/versions/{version_id}/restore` → `PageDict`
- `PATCH /api/pages/{page_id}/versions/{version_id}` (body `VersionUpdate{label?, notes?}`) → `VersionDict`
- `DELETE /api/pages/{page_id}/versions/{version_id}` → 204, or 409 if current
- `PATCH /api/pages/book/{book_id}/reorder` (body `ReorderIn{page_ids: list[str]}`) → `list[PageDict]`

**VersionDict shape:** `{id, page_id, version_num, image_url, svg_url, prompt, label, notes, dpi, width_px, height_px, is_pure_bw, created_at, is_current}`

**New backend helper:** `app/services/versioning.py::record_version(db, page, version_num, rel_path, svg_rel, prompt, report) -> PageVersion`

**New frontend types/hooks (in `frontend/src/lib/api.ts`):**
- `interface PageVersion { id; page_id; version_num; image_url; svg_url; prompt; label; notes; dpi; width_px; height_px; is_pure_bw; created_at; is_current }`
- `Page` gains `title: string | null`
- Hooks: `useVersions(pageId)`, `useRestoreVersion(pageId)`, `useUpdateVersion(pageId)`, `useDeleteVersion(pageId)`, `useDeleteBook()`, `useDeletePage()`, `useReorderPages(bookId)`; `CreatePageInput` gains `title?`.

**New frontend UI files:** `frontend/src/components/ui/dropdown-menu.tsx`, `frontend/src/components/ui/alert-dialog.tsx`, `frontend/src/features/editor/VersionsPanel.tsx`.

---

## Task 1: Schema columns + fix Postgres migration helper

Adds the six new nullable columns and fixes `_apply_pg_column_migrations`, which currently hardcodes `VARCHAR DEFAULT ''` for every column — that would give the integer/boolean version columns the wrong type on Neon.

**Files:**
- Modify: `backend/app/models.py` (Page ~line 114; PageVersion ~line 174)
- Modify: `backend/app/database.py:51-93` (`_COLUMN_MIGRATIONS`, `_apply_pg_column_migrations`)
- Test: `backend/tests/test_schema_migrations.py`

**Interfaces:**
- Produces: `Page.title`, `PageVersion.label/dpi/width_px/height_px/is_pure_bw` columns; a corrected PG migration helper that uses per-column DDL from `_COLUMN_MIGRATIONS`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_schema_migrations.py
from app.database import _COLUMN_MIGRATIONS, _pg_alter_statements


def test_new_columns_registered():
    assert _COLUMN_MIGRATIONS["pages"]["title"] == "VARCHAR(200)"
    pv = _COLUMN_MIGRATIONS["page_versions"]
    assert pv["label"] == "VARCHAR(120)"
    assert pv["dpi"] == "INTEGER"
    assert pv["width_px"] == "INTEGER"
    assert pv["height_px"] == "INTEGER"
    assert pv["is_pure_bw"] == "BOOLEAN"


def test_pg_alter_uses_declared_types_not_hardcoded_varchar():
    stmts = _pg_alter_statements()
    assert (
        "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS dpi INTEGER" in stmts
    )
    assert (
        "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS is_pure_bw BOOLEAN" in stmts
    )
    # Regression: no column should be forced to VARCHAR DEFAULT ''
    assert not any("VARCHAR DEFAULT ''" in s for s in stmts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_schema_migrations.py -v`
Expected: FAIL — `_pg_alter_statements` does not exist / columns not registered.

- [ ] **Step 3: Add the model columns**

In `backend/app/models.py`, inside `class Page`, after `sort_order` (line ~114) add:

```python
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
```

Inside `class PageVersion`, after `notes` (line ~178) add:

```python
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dpi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_pure_bw: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
```

- [ ] **Step 4: Register the migrations and fix the PG helper**

In `backend/app/database.py`, extend `_COLUMN_MIGRATIONS`:

```python
_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "pages": {"title": "VARCHAR(200)"},
    "page_versions": {
        "svg_path": "VARCHAR",
        "label": "VARCHAR(120)",
        "dpi": "INTEGER",
        "width_px": "INTEGER",
        "height_px": "INTEGER",
        "is_pure_bw": "BOOLEAN",
    },
    "text_layers": {"text_anchor": "VARCHAR(20) DEFAULT 'middle'"},
    "app_settings": {
        "concept_provider": "VARCHAR DEFAULT ''",
        "concept_model": "VARCHAR DEFAULT ''",
        "prompt_provider": "VARCHAR DEFAULT ''",
        "prompt_model": "VARCHAR DEFAULT ''",
    },
}


def _pg_alter_statements() -> list[str]:
    """Build idempotent Postgres ADD COLUMN statements from the migration map.

    Uses each column's declared DDL (type + optional DEFAULT) rather than
    forcing VARCHAR — so INTEGER/BOOLEAN columns get the right type.
    """
    stmts: list[str] = []
    for table, columns in _COLUMN_MIGRATIONS.items():
        for col, ddl in columns.items():
            stmts.append(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"
            )
    return stmts
```

Replace the body of `_apply_pg_column_migrations` (lines 85-93) with:

```python
def _apply_pg_column_migrations(conn) -> None:
    """Run idempotent ADD COLUMN IF NOT EXISTS migrations (Postgres only)."""
    for stmt in _pg_alter_statements():
        conn.exec_driver_sql(stmt)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --directory backend pytest tests/test_schema_migrations.py -v`
Expected: PASS.

- [ ] **Step 6: Run full backend suite to check nothing broke**

Run: `uv run --directory backend pytest -q`
Expected: all pass (existing ~130 + new).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/database.py backend/tests/test_schema_migrations.py
git commit -m "feat(db): add page title + version metadata columns; fix PG migration types"
```

---

## Task 2: Serialize title + versions; add GET versions endpoint

`_page_dict` currently emits only `version_count`. Add `title` to the page payload, add a `_version_dict` helper + `GET /pages/{id}/versions`, and accept `title` in create/update.

**Files:**
- Modify: `backend/app/routers/pages.py` (schemas ~22-35; `_page_dict` ~51-72; add helper + route)
- Test: `backend/tests/test_versions_api.py`

**Interfaces:**
- Consumes: `Page.title`, `PageVersion.*` from Task 1.
- Produces: `GET /api/pages/{page_id}/versions` → `list[VersionDict]`; `_version_dict(page, pv)`; `title` on `PageIn`/`PageUpdate`/`_page_dict`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_versions_api.py
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _make_book_and_page(client):
    book = (await client.post("/api/books", json={"title": "T"})).json()
    page = (await client.post(f"/api/pages/book/{book['id']}",
                              json={"concept": "a fox", "sort_order": 0})).json()
    return book, page


async def test_page_payload_includes_title(client):
    _, page = await _make_book_and_page(client)
    r = await client.patch(f"/api/pages/{page['id']}", json={"title": "Sleeping Fox"})
    assert r.status_code == 200
    assert r.json()["title"] == "Sleeping Fox"


async def test_list_versions_empty_then_shape(client):
    _, page = await _make_book_and_page(client)
    r = await client.get(f"/api/pages/{page['id']}/versions")
    assert r.status_code == 200
    assert r.json() == []
```

Note: if the repo lacks a client fixture, check `backend/tests/conftest.py` for an existing one and reuse its name; the async ASGI pattern above matches the app's test style.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_versions_api.py -v`
Expected: FAIL — `title` not in payload / versions route 404.

- [ ] **Step 3: Add `title` to schemas**

In `backend/app/routers/pages.py`, update:

```python
class PageIn(BaseModel):
    concept: str
    title: Optional[str] = None
    sort_order: int = 0


class PageUpdate(BaseModel):
    concept: Optional[str] = None
    title: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    status: Optional[PageStatus] = None
    critic_notes: Optional[str] = None
    print_check_notes: Optional[str] = None
    leslie_notes: Optional[str] = None
    sort_order: Optional[int] = None
```

Update `create_page` to pass title:

```python
    page = Page(book_id=book_id, concept=body.concept,
                title=body.title, sort_order=body.sort_order)
```

- [ ] **Step 4: Add `title` to `_page_dict` and add `_version_dict`**

In `_page_dict`, add after `"sort_order": page.sort_order,`:

```python
        "title": page.title,
```

Add a version serializer (import `PageVersion` at top: `from app.models import Book, Page, PageStatus, PageVersion, TextLayer`):

```python
def _version_dict(page: Page, pv: PageVersion) -> dict:
    return {
        "id": pv.id,
        "page_id": pv.page_id,
        "version_num": pv.version_num,
        "image_url": storage.public_url(pv.image_path) if pv.image_path else None,
        "svg_url": storage.public_url(pv.svg_path) if pv.svg_path else None,
        "prompt": pv.prompt,
        "label": pv.label,
        "notes": pv.notes,
        "dpi": pv.dpi,
        "width_px": pv.width_px,
        "height_px": pv.height_px,
        "is_pure_bw": pv.is_pure_bw,
        "created_at": pv.created_at.isoformat() if pv.created_at else None,
        "is_current": bool(page.image_path) and pv.image_path == page.image_path,
    }
```

- [ ] **Step 5: Add the GET versions route**

Add after `get_page` (line ~131):

```python
@router.get("/{page_id}/versions")
async def list_versions(page_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    ordered = sorted(page.versions, key=lambda v: v.version_num, reverse=True)
    return [_version_dict(page, v) for v in ordered]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_versions_api.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/pages.py backend/tests/test_versions_api.py
git commit -m "feat(api): serialize page title + add GET page versions endpoint"
```

---

## Task 3: Restore-version endpoint

**Files:**
- Modify: `backend/app/routers/pages.py`
- Test: `backend/tests/test_versions_api.py` (extend)

**Interfaces:**
- Consumes: `_version_dict`, `_page_dict` (Task 2).
- Produces: `POST /api/pages/{page_id}/versions/{version_id}/restore` → `PageDict`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_versions_api.py
from app.database import SessionLocal
from app.models import PageVersion


async def _seed_version(page_id, num, image_path, prompt, dpi=300):
    async with SessionLocal() as db:
        pv = PageVersion(page_id=page_id, version_num=num, image_path=image_path,
                         prompt=prompt, dpi=dpi, width_px=2550, height_px=3300,
                         is_pure_bw=True)
        db.add(pv)
        await db.commit()
        await db.refresh(pv)
        return pv.id


async def test_restore_makes_version_current(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "prompt one")
    v2 = await _seed_version(page["id"], 2, "books/b/p/v002.png", "prompt two")

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1}/restore")
    assert r.status_code == 200
    body = r.json()
    assert body["prompt"] == "prompt one"
    # image_path is serialized to a URL ending in the restored key
    assert body["image_path"].endswith("books/b/p/v001.png")

    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    current = [v for v in versions if v["is_current"]]
    assert len(current) == 1 and current[0]["id"] == v1


async def test_restore_unknown_version_404(client):
    _, page = await _make_book_and_page(client)
    r = await client.post(f"/api/pages/{page['id']}/versions/nope/restore")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_versions_api.py -k restore -v`
Expected: FAIL — restore route 404 for a real version id.

- [ ] **Step 3: Implement the route**

Add to `backend/app/routers/pages.py` (import `PageVersion` already added in Task 2):

```python
@router.post("/{page_id}/versions/{version_id}/restore")
async def restore_version(page_id: str, version_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")

    page.image_path = pv.image_path
    page.prompt = pv.prompt
    page.image_dpi = pv.dpi
    page.image_width_px = pv.width_px
    page.image_height_px = pv.height_px
    if pv.is_pure_bw is not None:
        page.is_pure_bw = pv.is_pure_bw
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    return _page_dict(page)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_versions_api.py -k restore -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/pages.py backend/tests/test_versions_api.py
git commit -m "feat(api): restore a page version as current"
```

---

## Task 4: Label/notes patch, delete-version endpoint, storage.delete_object

**Files:**
- Modify: `backend/app/services/storage.py` (add `delete_object` + backend helpers)
- Modify: `backend/app/routers/pages.py` (add `VersionUpdate` schema + two routes)
- Test: `backend/tests/test_versions_api.py` (extend), `backend/tests/test_storage_delete.py`

**Interfaces:**
- Consumes: `_version_dict` (Task 2).
- Produces: `storage.delete_object(key)`; `PATCH /api/pages/{page_id}/versions/{version_id}`; `DELETE /api/pages/{page_id}/versions/{version_id}` (409 if current).

- [ ] **Step 1: Write the failing storage test**

```python
# backend/tests/test_storage_delete.py
from app.services import storage


def test_delete_object_local_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    key = "books/x/pages/y/v001.png"
    (tmp_path / "books/x/pages/y").mkdir(parents=True)
    (tmp_path / key).write_bytes(b"png")
    assert storage.exists(key)
    storage.delete_object(key)
    assert not storage.exists(key)
    # second delete must not raise
    storage.delete_object(key)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_storage_delete.py -v`
Expected: FAIL — `delete_object` not defined.

- [ ] **Step 3: Implement `delete_object` in storage.py**

Add local + r2 helpers and the dispatcher:

```python
def _local_delete(key: str) -> None:
    _local_abs(key).unlink(missing_ok=True)


def _r2_delete(key: str) -> None:
    _get_s3_client().delete_object(Bucket=_R2_BUCKET, Key=key)


def delete_object(key: str) -> None:
    """Delete an object from storage. Idempotent (missing key is a no-op)."""
    if STORAGE_BACKEND == "r2":
        _r2_delete(key)
    else:
        _local_delete(key)
```

- [ ] **Step 4: Run storage test to verify it passes**

Run: `uv run --directory backend pytest tests/test_storage_delete.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing version patch/delete tests**

```python
# append to backend/tests/test_versions_api.py
async def test_patch_version_label_and_notes(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    r = await client.patch(f"/api/pages/{page['id']}/versions/{v1}",
                           json={"label": "too busy", "notes": "background cluttered"})
    assert r.status_code == 200
    assert r.json()["label"] == "too busy"
    assert r.json()["notes"] == "background cluttered"


async def test_delete_current_version_blocked(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    await client.post(f"/api/pages/{page['id']}/versions/{v1}/restore")  # v1 now current
    r = await client.delete(f"/api/pages/{page['id']}/versions/{v1}")
    assert r.status_code == 409


async def test_delete_noncurrent_version_ok(client):
    _, page = await _make_book_and_page(client)
    v1 = await _seed_version(page["id"], 1, "books/b/p/v001.png", "p1")
    v2 = await _seed_version(page["id"], 2, "books/b/p/v002.png", "p2")
    await client.post(f"/api/pages/{page['id']}/versions/{v2}/restore")  # v2 current
    r = await client.delete(f"/api/pages/{page['id']}/versions/{v1}")
    assert r.status_code == 204
    remaining = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    assert [v["id"] for v in remaining] == [v2]
```

- [ ] **Step 6: Run to verify they fail**

Run: `uv run --directory backend pytest tests/test_versions_api.py -k "patch_version or delete_current or delete_noncurrent" -v`
Expected: FAIL — routes not defined.

- [ ] **Step 7: Implement the routes**

Add `VersionUpdate` near the other schemas in `pages.py`:

```python
class VersionUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None
```

Add routes (import at top: `from app.services import storage` already present):

```python
@router.patch("/{page_id}/versions/{version_id}")
async def update_version(page_id: str, version_id: str, body: VersionUpdate,
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(pv, field, val)
    await db.commit()
    await db.refresh(pv)
    return _version_dict(page, pv)


@router.delete("/{page_id}/versions/{version_id}", status_code=204)
async def delete_version(page_id: str, version_id: str,
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")
    if page.image_path and pv.image_path == page.image_path:
        raise HTTPException(409, "Cannot delete the current version — restore another first")
    for key in (pv.image_path, pv.svg_path):
        if key:
            storage.delete_object(key)
    await db.delete(pv)
    await db.commit()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_versions_api.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/storage.py backend/app/routers/pages.py backend/tests/test_versions_api.py backend/tests/test_storage_delete.py
git commit -m "feat(api): label/notes + delete for page versions; storage.delete_object"
```

---

## Task 5: Bulk reorder endpoint

**Files:**
- Modify: `backend/app/routers/pages.py`
- Test: `backend/tests/test_reorder_api.py`

**Interfaces:**
- Consumes: `_page_dict` (Task 2).
- Produces: `PATCH /api/pages/book/{book_id}/reorder` (body `ReorderIn{page_ids}`) → `list[PageDict]` in new order.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reorder_api.py
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_reorder_api.py -v`
Expected: FAIL — reorder route 404/405.

- [ ] **Step 3: Implement the route**

Add `ReorderIn` schema and route to `pages.py`. Place the route **before** `@router.get("/{page_id}")`-style dynamic routes are not an issue here because the path is literal (`/book/{book_id}/reorder`), but define it near the other `/book/...` routes:

```python
class ReorderIn(BaseModel):
    page_ids: list[str]


@router.patch("/book/{book_id}/reorder")
async def reorder_pages(book_id: str, body: ReorderIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.book_id == book_id)
    )
    pages = {p.id: p for p in result.scalars().all()}
    if set(body.page_ids) != set(pages.keys()) or len(body.page_ids) != len(pages):
        raise HTTPException(400, "page_ids must be exactly the book's pages")
    for idx, pid in enumerate(body.page_ids):
        pages[pid].sort_order = idx
    await db.commit()
    ordered = sorted(pages.values(), key=lambda p: p.sort_order)
    return [_page_dict(p) for p in ordered]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_reorder_api.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite**

Run: `uv run --directory backend pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/pages.py backend/tests/test_reorder_api.py
git commit -m "feat(api): bulk reorder pages within a book"
```

---

## Task 6: Capture version metadata at generation time (DRY the two paths)

`generate.py` and `jobs.py` each build a `PageVersion` and update the page's image fields identically, and neither records the new metadata columns. Extract one helper, record the metadata, and call it from both.

**Files:**
- Create: `backend/app/services/versioning.py`
- Modify: `backend/app/routers/generate.py:99-116`
- Modify: `backend/app/routers/jobs.py:179-194`
- Test: `backend/tests/test_versioning_helper.py`

**Interfaces:**
- Produces: `record_version(db, page, version_num, rel_path, svg_rel, prompt, report) -> PageVersion` — creates the `PageVersion` (with `dpi/width_px/height_px/is_pure_bw` from `report`) AND updates `page.image_path/image_dpi/image_width_px/image_height_px/is_pure_bw/print_check_notes`. Does NOT commit.
- Consumes `report` objects with attributes `.dpi .width_px .height_px .is_pure_bw .issues` (the `analyse()` return, see `image_proc.py`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_versioning_helper.py
import pytest
from types import SimpleNamespace
from app.database import SessionLocal
from app.models import Book, Page, PageVersion
from app.services.versioning import record_version


async def _make_page():
    async with SessionLocal() as db:
        book = Book(title="B")
        db.add(book)
        await db.flush()
        page = Page(book_id=book.id, concept="c")
        db.add(page)
        await db.commit()
        return page.id


async def test_record_version_sets_metadata_on_version_and_page():
    page_id = await _make_page()
    report = SimpleNamespace(dpi=300, width_px=2550, height_px=3300,
                             is_pure_bw=True, issues=[])
    async with SessionLocal() as db:
        page = await db.get(Page, page_id)
        pv = record_version(db, page, 1, "books/b/p/v001.png",
                            "books/b/p/v001.svg", "the prompt", report)
        await db.commit()
        await db.refresh(pv)
        assert pv.dpi == 300 and pv.width_px == 2550 and pv.height_px == 3300
        assert pv.is_pure_bw is True and pv.prompt == "the prompt"
        assert page.image_path == "books/b/p/v001.png"
        assert page.image_dpi == 300 and page.is_pure_bw is True
        assert page.print_check_notes == "Passed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_versioning_helper.py -v`
Expected: FAIL — module `versioning` does not exist.

- [ ] **Step 3: Create the helper**

```python
# backend/app/services/versioning.py
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
```

- [ ] **Step 4: Run helper test to verify it passes**

Run: `uv run --directory backend pytest tests/test_versioning_helper.py -v`
Expected: PASS.

- [ ] **Step 5: Use the helper in generate.py**

In `backend/app/routers/generate.py`, replace lines 99-116 (the `pv = PageVersion(...)` block through `page.status = PageStatus.review`) with:

```python
    from app.services.versioning import record_version
    record_version(page, db=db, version_num=version_num, rel_path=rel_path,
                   svg_rel=svg_rel, prompt=positive, report=report)
    page.status = PageStatus.review
```

Note the helper signature is positional `(db, page, version_num, rel_path, svg_rel, prompt, report)`; call it as `record_version(db, page, version_num, rel_path, svg_rel, positive, report)`. Use:

```python
    from app.services.versioning import record_version
    record_version(db, page, version_num, rel_path, svg_rel, positive, report)
    page.status = PageStatus.review
```

- [ ] **Step 6: Use the helper in jobs.py**

In `backend/app/routers/jobs.py`, replace lines 179-194 (the `pv = PageVersion(...)` block through `page.status = PageStatus.review`) with:

```python
    from app.services.versioning import record_version
    record_version(db, page, version_num, rel_path, svg_rel, positive, report)
    page.status = PageStatus.review
```

- [ ] **Step 7: Run full backend suite**

Run: `uv run --directory backend pytest -q`
Expected: all pass (existing generation tests still green; `PageVersion` import in jobs.py/generate.py may now be unused — remove it from the import list if a linter flags it, but leaving it is harmless).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/versioning.py backend/app/routers/generate.py backend/app/routers/jobs.py backend/tests/test_versioning_helper.py
git commit -m "refactor(gen): record version metadata via shared helper"
```

---

## Task 7: Frontend API layer — types + hooks

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.tsx`

**Interfaces:**
- Consumes: the endpoints from Tasks 2–5.
- Produces: `PageVersion` type; `Page.title`; `CreatePageInput.title`; hooks `useVersions`, `useRestoreVersion`, `useUpdateVersion`, `useDeleteVersion`, `useDeleteBook`, `useDeletePage`, `useReorderPages`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/lib/api.test.tsx
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { useVersions } from "./api"

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("useVersions", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify([{ id: "v1", version_num: 1, is_current: true }]),
      { status: 200, headers: { "content-type": "application/json" } },
    )))
  })

  it("fetches versions for a page", async () => {
    const { result } = renderHook(() => useVersions("p1"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].id).toBe("v1")
    expect(fetch).toHaveBeenCalledWith("/api/pages/p1/versions", expect.anything())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/api.test.tsx`
Expected: FAIL — `useVersions` not exported.

- [ ] **Step 3: Add the `PageVersion` type and `title` fields**

In `frontend/src/lib/api.ts`, add after the `Page` interface:

```ts
export interface PageVersion {
  id: string
  page_id: string
  version_num: number
  image_url: string | null
  svg_url: string | null
  prompt: string
  label: string | null
  notes: string | null
  dpi: number | null
  width_px: number | null
  height_px: number | null
  is_pure_bw: boolean | null
  created_at: string | null
  is_current: boolean
}
```

In the `Page` interface, add after `sort_order`:

```ts
  title: string | null
```

In `CreatePageInput`, add:

```ts
  title?: string
```

Extend the `useUpdatePage` generic to accept `title`:

```ts
export function useUpdatePage() {
  const qc = useQueryClient()
  return useMutation<Page, Error, Partial<CreatePageInput> & { id: string; title?: string; status?: PageStatus; prompt?: string; negative_prompt?: string }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Page>(`/pages/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", page.id] })
    },
  })
}
```

- [ ] **Step 4: Add the new hooks**

Add a Versions section:

```ts
// ── Versions ─────────────────────────────────────────────────────────────────

export function useVersions(pageId: string) {
  return useQuery<PageVersion[]>({
    queryKey: ["versions", pageId],
    queryFn: () => apiFetch<PageVersion[]>(`/pages/${pageId}/versions`),
    enabled: !!pageId,
  })
}

export function useRestoreVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<Page, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<Page>(`/pages/${pageId}/versions/${versionId}/restore`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
    },
  })
}

export function useUpdateVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<PageVersion, Error, { versionId: string; label?: string; notes?: string }>({
    mutationFn: ({ versionId, ...data }) =>
      apiFetch<PageVersion>(`/pages/${pageId}/versions/${versionId}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
    },
  })
}

export function useDeleteVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<void>(`/pages/${pageId}/versions/${versionId}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
    },
  })
}
```

Add delete/reorder hooks in the Books/Pages sections:

```ts
export function useDeleteBook() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => apiFetch<void>(`/books/${id}`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["books"] }) },
  })
}

export function useDeletePage() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; bookId: string }>({
    mutationFn: ({ id }) => apiFetch<void>(`/pages/${id}`, { method: "DELETE" }),
    onSuccess: (_v, { bookId }) => { void qc.invalidateQueries({ queryKey: ["pages", bookId] }) },
  })
}

export function useReorderPages(bookId: string) {
  const qc = useQueryClient()
  return useMutation<Page[], Error, string[]>({
    mutationFn: (pageIds) =>
      apiFetch<Page[]>(`/pages/book/${bookId}/reorder`, { method: "PATCH", body: JSON.stringify({ page_ids: pageIds }) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["pages", bookId] }) },
  })
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/api.test.tsx`
Expected: PASS.

- [ ] **Step 6: Typecheck**

Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.tsx
git commit -m "feat(web): version + delete + reorder hooks and PageVersion type"
```

---

## Task 8: Install UI deps + add dropdown-menu and alert-dialog components

**Files:**
- Modify: `frontend/package.json` (deps)
- Create: `frontend/src/components/ui/dropdown-menu.tsx`
- Create: `frontend/src/components/ui/alert-dialog.tsx`
- Test: `frontend/src/components/ui/dropdown-menu.test.tsx`

**Interfaces:**
- Produces: shadcn `DropdownMenu*` and `AlertDialog*` exports; `@dnd-kit/core` + `@dnd-kit/sortable` available for Task 10.

- [ ] **Step 1: Install dependencies**

Run:
```bash
pnpm --dir frontend add @radix-ui/react-dropdown-menu @radix-ui/react-alert-dialog @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```
Expected: packages added to `frontend/package.json`.

- [ ] **Step 2: Add the shadcn components**

Create `frontend/src/components/ui/dropdown-menu.tsx` and `frontend/src/components/ui/alert-dialog.tsx` using the standard shadcn/ui Radix wrappers. Copy the canonical shadcn source for each (they depend only on the Radix packages installed above and the existing `cn` util). Confirm the import path for `cn` by matching an existing component:

Run: `grep -rn "cn(" frontend/src/components/ui/button.tsx | head -1`
Then use the same `import { cn } from "..."` path those files use (commonly `@/lib/utils` or a relative path).

The two files export, at minimum: `DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem` and `AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction`.

- [ ] **Step 3: Write a render smoke test**

```tsx
// frontend/src/components/ui/dropdown-menu.test.tsx
import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "./dropdown-menu"

describe("DropdownMenu", () => {
  it("renders a trigger", () => {
    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent><DropdownMenuItem>Rename</DropdownMenuItem></DropdownMenuContent>
      </DropdownMenu>,
    )
    expect(screen.getByText("Open")).toBeInTheDocument()
  })
})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/components/ui/dropdown-menu.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/components/ui/dropdown-menu.tsx frontend/src/components/ui/alert-dialog.tsx frontend/src/components/ui/dropdown-menu.test.tsx
git commit -m "feat(web): add dropdown-menu + alert-dialog components and dnd-kit deps"
```

---

## Task 9: Book rename + delete UI (BooksPage)

**Files:**
- Modify: `frontend/src/features/books/BooksPage.tsx`
- Test: `frontend/src/features/books/BooksPage.test.tsx`

**Interfaces:**
- Consumes: `useUpdateBook` (existing), `useDeleteBook` (Task 7), `DropdownMenu*`/`AlertDialog*` (Task 8).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/books/BooksPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"
import BooksPage from "./BooksPage"

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><BooksPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/books" && (!init || init.method === undefined))
      return new Response(JSON.stringify([{ id: "b1", title: "Woodland", emoji: "📖",
        theme: "", audience: "", positioning: "", target_page_count: 30,
        page_count: 0, approved_count: 0, progress_pct: 0,
        created_at: "", updated_at: "", style_guide: null }]),
        { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

describe("BooksPage book menu", () => {
  it("opens rename dialog pre-filled with the current title", async () => {
    renderPage()
    await screen.findByText("Woodland")
    await userEvent.click(screen.getByLabelText("Book actions for Woodland"))
    await userEvent.click(await screen.findByText("Rename"))
    const input = await screen.findByLabelText("Title") as HTMLInputElement
    expect(input.value).toBe("Woodland")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/BooksPage.test.tsx`
Expected: FAIL — no "Book actions" trigger.

- [ ] **Step 3: Add the `⋯` menu, rename dialog, delete confirm**

In `BooksPage.tsx`:
- Import `useDeleteBook`, `useUpdateBook`, the `DropdownMenu*` and `AlertDialog*` components, and a state for `editingBook`/`deletingBook`.
- On each book card, add a `⋯` `DropdownMenuTrigger` with `aria-label={`Book actions for ${book.title}`}` and items **Rename** and **Delete**.
- **Rename** opens a dialog reusing the create-book form fields, initialized from the book, saving via `useUpdateBook().mutate({ id, title, emoji, theme, audience, positioning, target_page_count })`. Give the title input `aria-label="Title"`.
- **Delete** opens an `AlertDialog` ("Delete \"{title}\"? This removes all its pages and versions.") whose action calls `useDeleteBook().mutate(book.id)`.
- Ensure clicking the menu does not navigate into the book (stop propagation on the trigger).

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/BooksPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/books/BooksPage.tsx frontend/src/features/books/BooksPage.test.tsx
git commit -m "feat(web): rename + delete books from the library"
```

---

## Task 10: Page grid — title/number display, rename, delete, drag-reorder (BookDetailPage)

**Files:**
- Modify: `frontend/src/features/books/BookDetailPage.tsx`
- Create: `frontend/src/features/books/pageLabel.ts` (pure helper)
- Test: `frontend/src/features/books/pageLabel.test.ts`, `frontend/src/features/books/BookDetailPage.test.tsx`

**Interfaces:**
- Consumes: `usePages`, `useUpdatePage`, `useDeletePage`, `useReorderPages`; `@dnd-kit/*`; `DropdownMenu*`/`AlertDialog*`.
- Produces: `pageDisplayName(page, index): string`.

- [ ] **Step 1: Write the failing helper test**

```ts
// frontend/src/features/books/pageLabel.test.ts
import { describe, it, expect } from "vitest"
import { pageDisplayName } from "./pageLabel"

describe("pageDisplayName", () => {
  it("uses title with zero-padded 1-based number", () => {
    expect(pageDisplayName({ title: "Sleeping Fox", concept: "x" } as any, 2)).toBe("p.03 — Sleeping Fox")
  })
  it("falls back to concept first line when no title", () => {
    expect(pageDisplayName({ title: null, concept: "a curled fox\nmore" } as any, 0)).toBe("p.01 — a curled fox")
  })
  it("falls back to Untitled when both empty", () => {
    expect(pageDisplayName({ title: null, concept: "" } as any, 0)).toBe("p.01 — Untitled")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/pageLabel.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helper**

```ts
// frontend/src/features/books/pageLabel.ts
import type { Page } from "@/lib/api"

export function pageDisplayName(page: Pick<Page, "title" | "concept">, index: number): string {
  const num = String(index + 1).padStart(2, "0")
  const name = (page.title?.trim())
    || (page.concept?.split("\n")[0].trim().slice(0, 40))
    || "Untitled"
  return `p.${num} — ${name}`
}
```

(If the project does not use the `@/` alias, import `Page` via the same relative path other files in this folder use — check with `grep -n "from \"@/lib/api\"" frontend/src/features/books/*.tsx`.)

- [ ] **Step 4: Run helper test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/pageLabel.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing reorder test**

```tsx
// frontend/src/features/books/BookDetailPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"
import BookDetailPage from "./BookDetailPage"

const PAGES = [
  { id: "p1", book_id: "b1", sort_order: 0, title: "One", concept: "one", status: "idea", prompt: null, negative_prompt: null, image_path: null, image_dpi: null, image_width_px: null, image_height_px: null, is_pure_bw: null, print_check_notes: null, created_at: "", updated_at: "", text_layers: [] },
  { id: "p2", book_id: "b1", sort_order: 1, title: "Two", concept: "two", status: "idea", prompt: null, negative_prompt: null, image_path: null, image_dpi: null, image_width_px: null, image_height_px: null, is_pure_bw: null, print_check_notes: null, created_at: "", updated_at: "", text_layers: [] },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/books/b1") return new Response(JSON.stringify({ id: "b1", title: "B", emoji: "📖", theme: "", audience: "", positioning: "", target_page_count: 30, page_count: 2, approved_count: 0, progress_pct: 0, created_at: "", updated_at: "", style_guide: null }), { status: 200, headers: { "content-type": "application/json" } })
    if (url === "/api/pages/book/b1") return new Response(JSON.stringify(PAGES), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/books/b1"]}>
        <Routes><Route path="/books/:id" element={<BookDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("BookDetailPage", () => {
  it("shows pages with derived p.NN — Title labels", async () => {
    renderPage()
    expect(await screen.findByText("p.01 — One")).toBeInTheDocument()
    expect(await screen.findByText("p.02 — Two")).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/BookDetailPage.test.tsx`
Expected: FAIL — labels not rendered in `p.NN — Title` form.

- [ ] **Step 7: Wire the UI**

In `BookDetailPage.tsx`:
- Render each page card's name via `pageDisplayName(page, index)` (index from the sorted `pages` array).
- Wrap the page grid in `@dnd-kit` `DndContext` + `SortableContext` (strategy `rectSortingStrategy`). Each card uses `useSortable({ id: page.id })`. On `onDragEnd`, compute the new id order with `arrayMove` and call `useReorderPages(bookId).mutate(newIds)`; optimistically set the query data so numbers relabel instantly.
- Add a `⋯` `DropdownMenu` per card (stop propagation so it doesn't open the editor): **Rename** → inline edit of `title` saved via `useUpdatePage().mutate({ id, title })`; **Delete** → `AlertDialog` → `useDeletePage().mutate({ id, bookId })`.
- Keep the existing status-filter tabs; disable drag while a non-"All" filter is active (reordering a filtered subset is ambiguous) — show a hint "Switch to All to reorder".

- [ ] **Step 8: Run tests to verify they pass**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/`
Expected: PASS.

- [ ] **Step 9: Typecheck + commit**

```bash
pnpm --dir frontend exec tsc --noEmit
git add frontend/src/features/books/BookDetailPage.tsx frontend/src/features/books/pageLabel.ts frontend/src/features/books/pageLabel.test.ts frontend/src/features/books/BookDetailPage.test.tsx
git commit -m "feat(web): page title/number, drag-reorder, rename, delete in book detail"
```

---

## Task 11: Page editor — title field + VersionsPanel

**Files:**
- Modify: `frontend/src/features/editor/PageEditorPage.tsx`
- Create: `frontend/src/features/editor/VersionsPanel.tsx`
- Test: `frontend/src/features/editor/VersionsPanel.test.tsx`

**Interfaces:**
- Consumes: `useVersions`, `useRestoreVersion`, `useUpdateVersion`, `useDeleteVersion` (Task 7); `useUpdatePage` with `title`; `pageImageSrc`.
- Produces: `<VersionsPanel pageId onCopyPrompt={(prompt) => void} />`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/editor/VersionsPanel.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { VersionsPanel } from "./VersionsPanel"

const VERSIONS = [
  { id: "v2", page_id: "p1", version_num: 2, image_url: "/storage/v2.png", svg_url: null, prompt: "prompt two", label: null, notes: null, dpi: 300, width_px: 2550, height_px: 3300, is_pure_bw: true, created_at: "", is_current: true },
  { id: "v1", page_id: "p1", version_num: 1, image_url: "/storage/v1.png", svg_url: null, prompt: "prompt one", label: "too busy", notes: null, dpi: 300, width_px: 2550, height_px: 3300, is_pure_bw: true, created_at: "", is_current: false },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/pages/p1/versions")
      return new Response(JSON.stringify(VERSIONS), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPanel(onCopy = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <VersionsPanel pageId="p1" onCopyPrompt={onCopy} />
    </QueryClientProvider>,
  )
  return onCopy
}

describe("VersionsPanel", () => {
  it("lists versions newest-first with a current badge", async () => {
    renderPanel()
    expect(await screen.findByText("v2")).toBeInTheDocument()
    expect(screen.getByText("Current")).toBeInTheDocument()
    expect(screen.getByText("too busy")).toBeInTheDocument()
  })

  it("copies a version's prompt to the editor", async () => {
    const onCopy = renderPanel()
    await screen.findByText("v1")
    await userEvent.click(screen.getAllByRole("button", { name: /copy prompt/i })[1])
    expect(onCopy).toHaveBeenCalledWith("prompt one")
  })

  it("disables delete on the current version", async () => {
    renderPanel()
    await screen.findByText("v2")
    const del = screen.getAllByRole("button", { name: /delete version/i })
    // v2 is current → its delete is disabled
    expect(del[0]).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/VersionsPanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `VersionsPanel`**

```tsx
// frontend/src/features/editor/VersionsPanel.tsx
import { useState } from "react"
import { useVersions, useRestoreVersion, useUpdateVersion, useDeleteVersion, pageImageSrc } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function VersionsPanel({ pageId, onCopyPrompt }: { pageId: string; onCopyPrompt: (prompt: string) => void }) {
  const { data: versions = [], isLoading } = useVersions(pageId)
  const restore = useRestoreVersion(pageId)
  const update = useUpdateVersion(pageId)
  const del = useDeleteVersion(pageId)
  const [expanded, setExpanded] = useState<string | null>(null)

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading versions…</p>
  if (versions.length === 0) return <p className="text-sm text-muted-foreground">No versions yet — generate to create v1.</p>

  return (
    <div className="space-y-3">
      {versions.map((v) => (
        <div key={v.id} className="rounded-lg border p-3">
          <div className="flex items-start gap-3">
            {v.image_url && (
              <img src={pageImageSrc(v.image_url)} alt={`v${v.version_num}`} className="h-20 w-16 object-contain border" />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">v{v.version_num}</span>
                {v.is_current && <span className="rounded bg-emerald-100 px-1.5 text-xs text-emerald-700">Current</span>}
              </div>
              <input
                aria-label={`Label for v${v.version_num}`}
                defaultValue={v.label ?? ""}
                placeholder="add a label…"
                className="mt-1 w-full bg-transparent text-sm outline-none border-b border-dashed"
                onBlur={(e) => { if (e.target.value !== (v.label ?? "")) update.mutate({ versionId: v.id, label: e.target.value }) }}
              />
              <button
                className="mt-1 text-xs underline text-muted-foreground"
                onClick={() => setExpanded(expanded === v.id ? null : v.id)}
              >{expanded === v.id ? "hide prompt" : "show prompt"}</button>
              {expanded === v.id && (
                <pre className="mt-1 whitespace-pre-wrap text-xs bg-muted p-2 rounded">{v.prompt}</pre>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" aria-label={`Copy prompt from v${v.version_num}`} onClick={() => onCopyPrompt(v.prompt)}>Copy prompt</Button>
                <Button size="sm" variant="outline" disabled={v.is_current || restore.isPending} onClick={() => restore.mutate(v.id)}>Restore as current</Button>
                <Button size="sm" variant="outline" aria-label={`Delete version v${v.version_num}`} disabled={v.is_current || del.isPending} onClick={() => del.mutate(v.id)}>Delete</Button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
```

(Match `Button`'s available `size`/`variant` props to the existing `button.tsx`; adjust if it lacks `size="sm"`. Use the project's actual import alias for `@/…`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/VersionsPanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Wire the panel + title field into PageEditorPage**

In `PageEditorPage.tsx`:
- Add a **Title** text input near the top, initialized from `page.title`, saved via `useUpdatePage().mutate({ id: page.id, title })` on blur.
- Render `<VersionsPanel pageId={page.id} onCopyPrompt={(p) => setPromptDraft(p)} />` beside the image, where `onCopyPrompt` loads the prompt into the editor's existing prompt-edit state (find the state that backs the prompt textarea and set it; if editing isn't open, open it).
- After a successful generate, `useVersions` is already invalidated by `useRestoreVersion`/generate flows; also invalidate `["versions", page.id]` in the generate `onSuccess` if not already covered (add `qc.invalidateQueries({ queryKey: ["versions", pageId] })` to `useGeneratePage().onSuccess` in `api.ts`).

- [ ] **Step 6: Add versions invalidation to generate**

In `frontend/src/lib/api.ts`, in `useGeneratePage().onSuccess`, add:

```ts
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
```

- [ ] **Step 7: Run editor tests + typecheck**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/`
Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/editor/PageEditorPage.tsx frontend/src/features/editor/VersionsPanel.tsx frontend/src/features/editor/VersionsPanel.test.tsx frontend/src/lib/api.ts
git commit -m "feat(web): page title field + version history panel in editor"
```

---

## Task 12: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `uv run --directory backend pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend suite**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism`
Expected: all pass.

- [ ] **Step 3: Typecheck + build**

Run: `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build`
Expected: clean.

- [ ] **Step 4: Manual smoke (dev servers)**

Start backend and frontend, then verify in the browser: rename a book; add two pages, drag to reorder (numbers relabel); open a page, generate twice, confirm both versions appear, copy an old prompt, restore an old version (card thumbnail updates), label a version, delete a non-current version, confirm the current version's Delete is disabled.

- [ ] **Step 5: Final commit (if any wiring tweaks were needed)**

```bash
git add -A && git commit -m "chore: verification tweaks for book/page organization feature"
```

---

## Self-Review (completed during authoring)

**Spec coverage:**
- Rename/delete book → Task 9 (UI), hooks Task 7, endpoint pre-existing.
- Page title + auto number → Tasks 1 (column), 2 (serialize), 10 (`pageDisplayName` + editor field in 11).
- Reorder pages → Task 5 (endpoint), 7 (hook), 10 (drag UI).
- Delete pages → Task 7 (hook), 10 (UI); endpoint pre-existing.
- Version view + copy prompt → Tasks 2 (GET), 11 (panel).
- Restore version → Tasks 3 (endpoint), 7 (hook), 11 (button).
- Label/annotate version → Tasks 4 (endpoint), 7 (hook), 11 (inline label).
- Delete version (blocked for current) → Tasks 4 (endpoint + 409), 11 (disabled button).
- Version metadata for faithful restore → Tasks 1 (columns), 6 (capture at generation).
- PG migration type bug (found in code) → Task 1.

**Type consistency:** `VersionDict`/`PageVersion` field names identical across Tasks 2, 4, 7, 11 (`image_url`, `svg_url`, `label`, `notes`, `is_current`, `version_num`). `record_version(db, page, version_num, rel_path, svg_rel, prompt, report)` signature consistent across Tasks 6 call sites. `useReorderPages(bookId).mutate(pageIds: string[])` consistent between Task 7 and 10. `pageDisplayName(page, index)` consistent between Tasks 10 definition and 11 usage note.

**Placeholders:** none — every code step contains complete code; UI-wiring steps that reference existing local state (prompt draft, filter) instruct how to locate it rather than guessing an exact identifier, because those identifiers live in files not fully reproduced here.
