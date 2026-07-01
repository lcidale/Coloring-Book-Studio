# Inspiration Image as a Generation Reference (Spec B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a page use an inspiration image as a visual reference for AI generation — a sticky reference on the page plus a per-run override — fed to the Gemini image model as an input image.

**Architecture:** Add a nullable `Page.reference_image_id` (FK → inspiration_images). Setting/clearing it is a set-aware PATCH validated for eligibility (image must be global or belong to the page's book). Both generate endpoints accept an optional per-run `reference_image_id` override (falls back to the page's sticky one). `generate_line_art` gains an optional `reference_image_key`; the Gemini path fetches those bytes and includes them as an input image part; other providers ignore it. Deleting an inspiration image nulls any page referencing it.

**Tech Stack:** FastAPI + async SQLAlchemy + Pydantic (Python 3.12/uv). React 19 + Vite + TanStack Query. Image provider: Google Gemini (`google-genai` SDK, already used). Tests: pytest, Vitest/RTL.

**Depends on:** Spec A (inspiration images) — already merged on the working branch. `InspirationImage` model, the `inspiration` router, and the storage service all exist.

## Global Constraints

- **No Alembic.** `Page.reference_image_id` is a column ADDED to an existing table → register it in `_COLUMN_MIGRATIONS` in `backend/app/database.py` as `{"pages": {"reference_image_id": "VARCHAR"}}` (merge into the existing `pages` entry which already has `title`). The type-aware `_pg_alter_statements()` emits it for Postgres; the SQLite path reads the map. Nullable, no DEFAULT.
- **Backend tests:** `export PATH="$HOME/.local/bin:$HOME/.local/node-v24.18.0-darwin-arm64/bin:$PATH"` then `uv run --directory backend pytest`. Use the conftest `client` fixture (isolated DB + tmp storage; it also monkeypatches `generate_line_art` to a fake). For direct-DB seeding in a test, reference `app.database.SessionLocal` as a module attribute at call time (`import app.database as db_mod; async with db_mod.SessionLocal() as db:`), never a top-level `from app.database import SessionLocal`. `asyncio_mode="auto"`.
- **Frontend tests:** `pnpm --dir frontend test --run --pool=forks --no-file-parallelism`. Tests in `__tests__/`. `globals: true`, jsdom, `@`→src.
- **Frontend "green" = `pnpm --dir frontend build` passes** (stricter `tsc -b`: no unused imports; cast incomplete test mocks via `as unknown as <T>`), not just `tsc --noEmit`.
- **Eligibility rule:** a reference image is eligible for a page iff it exists AND (`book_id IS NULL` OR `book_id == page.book_id`). Ineligible → HTTP 400.
- **Effective reference:** `override_reference_id if the generate body provided one else page.reference_image_id`.
- **Provider scope:** only the **Gemini** path consumes the reference image; `replicate`/`fal` ignore it and log one info line. Only Gemini is configured in production.
- **Set-aware PATCH:** explicit JSON `null` clears `reference_image_id`; an omitted field leaves it unchanged (use Pydantic `model_fields_set`, matching the existing inspiration PATCH).
- **No per-version reference persistence** (YAGNI) — the reference lives on the page; `PageVersion` is unchanged.

### Shared contract (names used across tasks — do not drift)

- Column: `Page.reference_image_id: Optional[str]` (nullable FK → inspiration_images.id).
- `_page_dict` gains `reference_image_id` and `reference_image_url` (public_url of the referenced image, or null).
- Backend helper (in `backend/app/routers/pages.py`): `async def _eligible_reference_or_400(image_id: str, page: Page, db) -> InspirationImage` — 400 if missing/ineligible; returns the row.
- `PageUpdate` gains `reference_image_id: Optional[str] = None` (set-aware).
- `GenerateRequest` (in BOTH `generate.py` and `jobs.py`) gains `reference_image_id: Optional[str] = None`.
- `generate_line_art(..., reference_image_key: Optional[str] = None)`; `_generate_gemini(..., reference: Optional[tuple[bytes, str]] = None)` where the tuple is `(bytes, mime_type)`.
- Inspiration `DELETE` nulls `Page.reference_image_id` for referencing pages before deleting the image.
- Frontend `Page` gains `reference_image_id: string | null` and `reference_image_url: string | null`; `useUpdatePage` accepts `reference_image_id`; `useGeneratePage` options accept `reference_image_id`.

---

## Task 1: `Page.reference_image_id` column + migration + serialization

**Files:**
- Modify: `backend/app/models.py` (Page)
- Modify: `backend/app/database.py` (`_COLUMN_MIGRATIONS` — the `pages` entry)
- Modify: `backend/app/routers/pages.py` (`_page_dict`)
- Test: `backend/tests/test_reference_image.py`

**Interfaces:**
- Produces: `Page.reference_image_id`; `_page_dict` keys `reference_image_id`, `reference_image_url`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_image.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/test_reference_image.py -v`
Expected: FAIL — `KeyError: 'reference_image_id'`.

- [ ] **Step 3: Add the column**

In `backend/app/models.py`, in `class Page`, after the `title` column add:

```python
    reference_image_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("inspiration_images.id"), nullable=True
    )
```

- [ ] **Step 4: Register the migration**

In `backend/app/database.py`, merge into the existing `pages` entry of `_COLUMN_MIGRATIONS` so it reads:

```python
    "pages": {"title": "VARCHAR(200)", "reference_image_id": "VARCHAR"},
```

- [ ] **Step 5: Serialize it**

In `backend/app/routers/pages.py`, `_page_dict` needs the reference id and a resolved URL. The page's `reference_image` is not a relationship, so resolve the URL from the loaded value. Add a helper and use it. First add to `_page_dict` (after the `image_path` line):

```python
        "reference_image_id": page.reference_image_id,
        "reference_image_url": _reference_url(page),
```

And add this module-level helper (it reads a cached attribute set by the loaders; default None):

```python
def _reference_url(page: Page) -> str | None:
    img = getattr(page, "_reference_image", None)
    return storage.public_url(img.image_path) if img and img.image_path else None
```

To populate `_reference_image` without a relationship, the GET/list/patch handlers that call `_page_dict` will attach it. Add a helper used by those handlers:

```python
async def _attach_reference(page: Page, db: AsyncSession) -> None:
    """Load the page's reference InspirationImage onto page._reference_image (or None)."""
    from app.models import InspirationImage
    page._reference_image = (
        await db.get(InspirationImage, page.reference_image_id)
        if page.reference_image_id else None
    )
```

In `get_page`, `list_pages` (per page), `update_page`, and `restore_version` — anywhere `_page_dict(page)` is returned — call `await _attach_reference(page, db)` first (for `list_pages`, loop the pages). For this task, wire it into `get_page` and `create_page` and `update_page` and `list_pages`; the generate/restore handlers are updated in their own tasks.

- [ ] **Step 6: Run to verify it passes**

Run: `uv run --directory backend pytest tests/test_reference_image.py -v`
Expected: PASS.

- [ ] **Step 7: Full suite + commit**

Run: `uv run --directory backend pytest -q` → all pass.

```bash
git add backend/app/models.py backend/app/database.py backend/app/routers/pages.py backend/tests/test_reference_image.py
git commit -m "feat(db): Page.reference_image_id column + serialize reference on page"
```

---

## Task 2: Eligibility helper + set-aware PATCH of the sticky reference

**Files:**
- Modify: `backend/app/routers/pages.py` (`PageUpdate`, `update_page`, add `_eligible_reference_or_400`)
- Test: `backend/tests/test_reference_image.py` (extend)

**Interfaces:**
- Consumes: `_attach_reference` (Task 1), `InspirationImage`.
- Produces: `_eligible_reference_or_400(image_id, page, db)`; `PageUpdate.reference_image_id` (set-aware).

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_reference_image.py
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory backend pytest tests/test_reference_image.py -k reference -v`
Expected: FAIL — `reference_image_id` not accepted / not validated.

- [ ] **Step 3: Add the eligibility helper**

In `backend/app/routers/pages.py` (import `InspirationImage` in the models import line):

```python
async def _eligible_reference_or_400(image_id: str, page: Page, db: AsyncSession) -> InspirationImage:
    img = await db.get(InspirationImage, image_id)
    if img is None:
        raise HTTPException(400, "Reference image not found")
    if img.book_id is not None and img.book_id != page.book_id:
        raise HTTPException(400, "Reference image is not available for this book")
    return img
```

- [ ] **Step 4: Make `PageUpdate` set-aware for the reference**

Add to `PageUpdate`:

```python
    reference_image_id: Optional[str] = None
```

In `update_page`, the current code does `for field, val in body.model_dump(exclude_none=True).items(): setattr(page, field, val)`. That drops explicit `null`, so handle `reference_image_id` explicitly and exclude it from the generic loop. Replace the field-application block with:

```python
    data = body.model_dump(exclude_none=True)
    ref_provided = "reference_image_id" in body.model_fields_set
    data.pop("reference_image_id", None)  # handled explicitly below
    for field, val in data.items():
        setattr(page, field, val)
    if ref_provided:
        if body.reference_image_id is not None:
            await _eligible_reference_or_400(body.reference_image_id, page, db)
        page.reference_image_id = body.reference_image_id
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    await _attach_reference(page, db)
    return _page_dict(page)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_reference_image.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/pages.py backend/tests/test_reference_image.py
git commit -m "feat(api): set/clear sticky page reference image with eligibility check"
```

---

## Task 3: Generation pipeline — reference image fed to Gemini

**Files:**
- Modify: `backend/app/services/image_gen.py`
- Test: `backend/tests/test_image_gen_reference.py`

**Interfaces:**
- Produces: `generate_line_art(..., reference_image_key=None)`; `_generate_gemini(..., reference=None)`; `_mime_for_key(key)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_image_gen_reference.py
import pytest
from app.services import image_gen


def test_mime_for_key():
    assert image_gen._mime_for_key("inspiration/x.png") == "image/png"
    assert image_gen._mime_for_key("inspiration/x.jpg") == "image/jpeg"
    assert image_gen._mime_for_key("inspiration/x.webp") == "image/webp"


async def test_generate_line_art_passes_reference_to_gemini(monkeypatch, tmp_path):
    # storage.get_bytes returns fake reference bytes; capture what _generate_gemini receives
    from app.services import storage
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(image_gen, "STORAGE_DIR", tmp_path)
    storage.put_bytes("inspiration/ref.png", b"REFBYTES")

    captured = {}

    async def fake_gemini(pos, neg, w, h, model, reference=None):
        captured["reference"] = reference
        return b"\x89PNG\r\n\x1a\n" + b"0" * 8  # fake png bytes

    monkeypatch.setattr(image_gen, "_generate_gemini", fake_gemini)

    async def fake_resolve(provider, model, db):
        return "gemini", "gemini-2.5-flash-image"
    monkeypatch.setattr(image_gen, "_resolve_provider_model", fake_resolve)

    await image_gen.generate_line_art(
        positive_prompt="p", negative_prompt="n", book_id="b", page_id="pg",
        version=1, reference_image_key="inspiration/ref.png",
    )
    assert captured["reference"] == (b"REFBYTES", "image/png")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory backend pytest tests/test_image_gen_reference.py -v`
Expected: FAIL — `_mime_for_key` missing / `generate_line_art` has no `reference_image_key`.

- [ ] **Step 3: Implement in `image_gen.py`**

Add a module logger and mime helper near the top (after imports):

```python
import logging
_log = logging.getLogger(__name__)

_MIME_BY_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


def _mime_for_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return _MIME_BY_EXT.get(ext, "application/octet-stream")
```

Change `generate_line_art`'s signature to add `reference_image_key: Optional[str] = None` (last param). After resolving the provider, before the provider dispatch, fetch the reference:

```python
    reference: Optional[tuple[bytes, str]] = None
    if reference_image_key:
        reference = (_storage.get_bytes(reference_image_key), _mime_for_key(reference_image_key))
```

Update the dispatch: pass `reference` to Gemini; for the others, log-and-ignore:

```python
    if resolved_provider == "replicate":
        if reference is not None:
            _log.info("reference image supplied but replicate does not support it; ignoring")
        result = await _generate_replicate(positive_prompt, negative_prompt, width, height, resolved_model)
    elif resolved_provider == "fal":
        if reference is not None:
            _log.info("reference image supplied but fal does not support it; ignoring")
        result = await _generate_fal(positive_prompt, negative_prompt, width, height, resolved_model)
    elif resolved_provider == "gemini":
        result = await _generate_gemini(positive_prompt, negative_prompt, width, height, resolved_model, reference)
    else:
        raise ValueError(f"Unknown image provider: {resolved_provider}")
```

Change `_generate_gemini` to accept `reference` and include it as an input image part:

```python
async def _generate_gemini(
    positive: str, negative: str, width: int, height: int, model: str,
    reference: Optional[tuple[bytes, str]] = None,
) -> bytes:
    ...
    # (unchanged prompt assembly up to building `prompt`)
    client = genai.Client(api_key=api_key)
    if reference is not None:
        ref_bytes, ref_mime = reference
        # google-genai image-part constructor; matches the SDK already imported as `types`.
        contents = [types.Part.from_bytes(data=ref_bytes, mime_type=ref_mime), prompt]
    else:
        contents = prompt
    response = await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    ...
```

If the installed `google-genai` version exposes a different image-part constructor than `types.Part.from_bytes(data=..., mime_type=...)`, use that version's equivalent (the module already does `from google.genai import types`). The behavioral contract (a reference tuple produces list-contents with an image part first) is what the test in Step 1 checks via the captured `reference`; add a second focused test only if you can mock `genai.Client` cleanly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_image_gen_reference.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `uv run --directory backend pytest -q` → all pass (existing generation tests unaffected — they pass no reference).

```bash
git add backend/app/services/image_gen.py backend/tests/test_image_gen_reference.py
git commit -m "feat(gen): generate_line_art accepts a reference image; Gemini uses it as input"
```

---

## Task 4: Generate endpoints accept a per-run reference override

**Files:**
- Modify: `backend/app/routers/generate.py` (`GenerateRequest`, `generate_page`)
- Modify: `backend/app/routers/jobs.py` (`GenerateRequest`, `enqueue_generation` → thread to `_run_pipeline`/`_generate`)
- Test: `backend/tests/test_reference_image.py` (extend)

**Interfaces:**
- Consumes: `generate_line_art(reference_image_key=...)` (Task 3); `Page.reference_image_id` (Task 1); eligibility (Task 2 helper is in pages.py — replicate the check inline here or import it).
- Produces: `GenerateRequest.reference_image_id` in both routers; effective-reference resolution.

Note: the conftest `client` fixture monkeypatches `generate_line_art` to a fake that accepts `**kwargs`, so passing `reference_image_key` will not break the fake. To assert the resolved key, the test uses the SYNC endpoint (`POST /api/generate/{page_id}`) and a monkeypatched capture (see below), avoiding the async job's background timing.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_reference_image.py
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory backend pytest tests/test_reference_image.py -k generate -v`
Expected: FAIL — body field ignored / reference not passed.

- [ ] **Step 3: Implement in `generate.py`**

Add to `GenerateRequest`:

```python
    reference_image_id: Optional[str] = None
```

(ensure `from typing import Optional` is imported.) In `generate_page`, after loading `page` and before calling `generate_line_art`, resolve + validate the effective reference and fetch its key:

```python
    from app.models import InspirationImage
    effective_ref_id = body.reference_image_id or page.reference_image_id
    reference_image_key = None
    if effective_ref_id:
        ref = await db.get(InspirationImage, effective_ref_id)
        if ref is None or (ref.book_id is not None and ref.book_id != page.book_id):
            raise HTTPException(400, "Reference image is not available for this page")
        reference_image_key = ref.image_path
```

Pass it into the call: add `reference_image_key=reference_image_key` to the `generate_line_art(...)` keyword args.

- [ ] **Step 4: Implement in `jobs.py`**

Add `reference_image_id: Optional[str] = None` to `jobs.py`'s `GenerateRequest`. The async path validates at enqueue time (so a bad override returns 400 to the caller synchronously) and passes the resolved key through the background task:

In `enqueue_generation`, after the `page`/concept checks, resolve + validate exactly as in Step 3 (compute `reference_image_key`), then pass it into the background task:

```python
    background_tasks.add_task(
        _run_pipeline, job.id, page_id, body.auto_cleanup, body.vectorize, reference_image_key,
    )
```

Thread the parameter through `_run_pipeline(job_id, page_id, auto_cleanup, do_vectorize, reference_image_key)` and `_generate(db, page_id, auto_cleanup, do_vectorize, reference_image_key)`, and add `reference_image_key=reference_image_key` to that function's `generate_line_art(...)` call. (Compute `reference_image_key` in `enqueue_generation` using the request `db` session before the background task starts; import `InspirationImage`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_reference_image.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite + commit**

Run: `uv run --directory backend pytest -q` → all pass.

```bash
git add backend/app/routers/generate.py backend/app/routers/jobs.py backend/tests/test_reference_image.py
git commit -m "feat(api): generate endpoints accept a per-run reference override"
```

---

## Task 5: Deleting an inspiration image clears referencing pages

**Files:**
- Modify: `backend/app/routers/inspiration.py` (`delete_inspiration`)
- Test: `backend/tests/test_reference_image.py` (extend)

**Interfaces:**
- Consumes: `Page.reference_image_id`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_reference_image.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/test_reference_image.py -k delete_inspiration_clears -v`
Expected: FAIL — page still references the deleted image (or a FK error on Postgres).

- [ ] **Step 3: Null out referencing pages in `delete_inspiration`**

In `backend/app/routers/inspiration.py`, in `delete_inspiration`, before deleting the storage object + row, clear any page pointing at this image. Add imports (`from sqlalchemy import update`; `from app.models import Page`) and:

```python
    await db.execute(
        update(Page).where(Page.reference_image_id == image_id).values(reference_image_id=None)
    )
```

(Place it right after the 404 check, before `storage.delete_object(...)`. The final `db.commit()` persists both the null-out and the row delete.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_reference_image.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `uv run --directory backend pytest -q` → all pass.

```bash
git add backend/app/routers/inspiration.py backend/tests/test_reference_image.py
git commit -m "feat(api): clear page reference when its inspiration image is deleted"
```

---

## Task 6: Frontend API layer — reference fields + hook params

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/__tests__/api.test.tsx` (extend)

**Interfaces:**
- Produces: `Page.reference_image_id`, `Page.reference_image_url`; `useUpdatePage` accepts `reference_image_id`; `useGeneratePage` options accept `reference_image_id`.

- [ ] **Step 1: Write the failing test**

```tsx
// add to frontend/src/lib/__tests__/api.test.tsx
describe("useUpdatePage reference", () => {
  it("PATCHes reference_image_id", async () => {
    const fetchMock = vi.fn(async () => new Response(
      JSON.stringify({ id: "p1", book_id: "b1", reference_image_id: "i1" }),
      { status: 200, headers: { "content-type": "application/json" } },
    ))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useUpdatePage(), { wrapper })
    result.current.mutate({ id: "p1", reference_image_id: "i1" })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init.body)).toEqual({ reference_image_id: "i1" })
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/__tests__/api.test.tsx`
Expected: FAIL — `useUpdatePage`'s type rejects `reference_image_id` (compile) or the test asserts a field the type doesn't carry.

- [ ] **Step 3: Add the fields + params**

In `frontend/src/lib/api.ts`, in the `Page` interface add (after `image_path` fields):

```ts
  reference_image_id: string | null
  reference_image_url: string | null
```

Extend `useUpdatePage`'s mutation generic to include `reference_image_id?: string | null`:

```ts
  return useMutation<Page, Error, Partial<CreatePageInput> & { id: string; title?: string; status?: PageStatus; prompt?: string; negative_prompt?: string; reference_image_id?: string | null }>({
```

Extend `GenerateOptions`:

```ts
export interface GenerateOptions {
  auto_cleanup?: boolean
  vectorize?: boolean
  reference_image_id?: string | null
}
```

`useGeneratePage` already spreads `options` into the POST body, so `reference_image_id` flows through automatically — verify the body construction includes it (`const body = { auto_cleanup: true, vectorize: true, ...options }`).

- [ ] **Step 4: Run test + typecheck**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/__tests__/api.test.tsx`
Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/__tests__/api.test.tsx
git commit -m "feat(web): page reference fields + reference param on update/generate hooks"
```

---

## Task 7: Page editor — reference control (sticky + per-run override)

**Files:**
- Create: `frontend/src/features/editor/ReferencePicker.tsx`
- Modify: `frontend/src/features/editor/PageEditorPage.tsx`
- Test: `frontend/src/features/editor/__tests__/ReferencePicker.test.tsx`

**Interfaces:**
- Consumes: `useInspiration`, `useUpdatePage`, `useGeneratePage`, `pageImageSrc`, the `Page` type.
- Produces: `<ReferencePicker page={page} />` (sticky control) and a per-run override on generate.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/editor/__tests__/ReferencePicker.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { ReferencePicker } from "../ReferencePicker"

const PAGE = { id: "p1", book_id: "b1", reference_image_id: null, reference_image_url: null } as any
const ELIGIBLE = [
  { id: "i1", book_id: "b1", image_url: "/storage/inspiration/a.png", caption: "fox ref", created_at: "" },
  { id: "i2", book_id: null, image_url: "/storage/inspiration/b.png", caption: null, created_at: "" },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.startsWith("/api/inspiration")) return new Response(JSON.stringify(ELIGIBLE), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPicker(page = PAGE) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ReferencePicker page={page} /></QueryClientProvider>)
}

describe("ReferencePicker", () => {
  it("lists eligible images and sets one as the sticky reference", async () => {
    renderPicker()
    await userEvent.click(await screen.findByRole("button", { name: /set reference/i }))
    await userEvent.click(await screen.findByText("fox ref"))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/pages/p1", expect.objectContaining({ method: "PATCH" })),
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/__tests__/ReferencePicker.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ReferencePicker`**

Build eligibility from this book's inspiration + global. The simplest correct query is two `useInspiration` calls merged (this book's + global), de-duplicated:

```tsx
// frontend/src/features/editor/ReferencePicker.tsx
import { useState } from "react"
import { useInspiration, useUpdatePage, pageImageSrc, type Page, type InspirationImage } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function ReferencePicker({ page }: { page: Page }) {
  const update = useUpdatePage()
  const bookImages = useInspiration(page.book_id)
  const globalImages = useInspiration("global")
  const [open, setOpen] = useState(false)

  const eligible: InspirationImage[] = [
    ...(bookImages.data ?? []),
    ...(globalImages.data ?? []),
  ]

  function choose(id: string | null) {
    update.mutate({ id: page.id, reference_image_id: id })
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Reference image</span>
        {page.reference_image_url ? (
          <>
            <img src={pageImageSrc(page.reference_image_url)} alt="reference" className="h-10 w-8 object-contain border" />
            <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Change</Button>
            <Button size="sm" variant="outline" onClick={() => choose(null)}>Clear</Button>
          </>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Set reference</Button>
        )}
      </div>
      {open && (
        <div className="grid grid-cols-4 gap-2 rounded border p-2">
          {eligible.length === 0 && <p className="text-xs text-muted-foreground">No eligible images. Add inspiration to this book or Global.</p>}
          {eligible.map((img) => (
            <button key={img.id} type="button" className="border p-1 text-left" onClick={() => choose(img.id)}>
              {img.image_url && <img src={pageImageSrc(img.image_url)} alt={img.caption ?? "inspiration"} className="aspect-square w-full object-contain" />}
              <span className="block truncate text-[10px]">{img.caption ?? "—"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Wire into PageEditorPage + per-run override**

In `frontend/src/features/editor/PageEditorPage.tsx`:
- Render `<ReferencePicker page={page} />` near the Generate action.
- For the per-run override: keep it minimal — a small checkbox/select "use a different reference this time" that, when set, holds an `overrideRefId` state; pass it into the existing generate call as `useGeneratePage().mutate({ pageId, options: { reference_image_id: overrideRefId } })`. If unset (undefined), the backend falls back to the sticky reference automatically — so only include `reference_image_id` in options when the user picked an override. Reuse the same eligible-image list logic (a second `ReferencePicker`-like inline control or a shared list); do not duplicate the eligibility query logic more than necessary.

- [ ] **Step 5: Run tests + typecheck + build**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/ src/lib/`
Run: `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build`
Expected: PASS, build exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/editor/ReferencePicker.tsx frontend/src/features/editor/PageEditorPage.tsx frontend/src/features/editor/__tests__/ReferencePicker.test.tsx
git commit -m "feat(web): page reference picker (sticky) + per-run override on generate"
```

---

## Task 8: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend** — `uv run --directory backend pytest -q` → all pass.
- [ ] **Step 2: Frontend** — `pnpm --dir frontend test --run --pool=forks --no-file-parallelism` → all pass.
- [ ] **Step 3: Typecheck + build** — `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build` → clean, exit 0.
- [ ] **Step 4: Manual smoke** — start backend + frontend; add an inspiration image to a book; open a page in that book, set it as the sticky reference (the thumbnail shows); generate and confirm it succeeds; set a per-run override and generate; clear the reference; delete the inspiration image and confirm the page's reference clears.
- [ ] **Step 5: Final commit (if any tweaks)** — `git add -A && git commit -m "chore: verification tweaks for generation reference"`

---

## Self-Review (completed during authoring)

**Spec coverage:** sticky reference column + serialize → T1; set/clear + eligibility (this-book+global) → T2; Gemini fed the reference, others ignore → T3; per-run override on both generate paths + effective-reference resolution → T4; inspiration-delete nulls referencing pages → T5; frontend types + hook params → T6; editor sticky picker + per-run override → T7. Non-goal (no per-version reference persistence) respected — `PageVersion` untouched.

**Placeholders:** none — code steps carry complete code. Task 3 explicitly allows the implementer to match the installed `google-genai` image-part API if it differs from `types.Part.from_bytes`, with the behavioral test (captured reference tuple) as the real contract. Task 7's per-run override references existing PageEditor state/among-the-generate-action wiring by description because that component isn't reproduced here.

**Type consistency:** `reference_image_id`/`reference_image_url` identical across T1 (`_page_dict`), T6 (TS `Page`). `_eligible_reference_or_400(image_id, page, db)` defined T2, its inline equivalent used in T4 generate endpoints (same rule: exists AND (global OR same book)). `generate_line_art(reference_image_key=...)` (T3) matches the call sites in T4. `_generate_gemini(..., reference=(bytes, mime))` tuple shape consistent T3. `GenerateOptions.reference_image_id` (T6) matches the backend `GenerateRequest.reference_image_id` (T4).
