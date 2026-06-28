# Tech Stack — Coloring Book Studio

The approved stack for the studio. Drives the refactor plan in `docs/plans/2026-06-27-002-refactor-studio-opus-plan.md`.

## Frontend

| Layer | Choice | Notes |
|---|---|---|
| Framework | React 18 + TypeScript + Vite | Fast HMR, typed, owns the design system. |
| Styling / components | Tailwind CSS + shadcn/ui (Radix primitives) | Accessible, in-repo components, token-driven. |
| Server state | TanStack Query | Caching + polling for async generation jobs. |
| UI state | Zustand (only where needed) | Most state stays in Query + URL. |
| Routing | React Router | Sidebar views map to routes. |
| Design→code | Figma Dev Mode MCP + Code Connect | Maps React components to Figma. |

## Backend

| Layer | Choice | Notes |
|---|---|---|
| Runtime | **Python 3.12** (upgrade from 3.9) | Removes `X \| None` / greenlet friction; faster. |
| Framework | FastAPI + Pydantic v2 | Keep. |
| ORM / DB | SQLAlchemy 2.0 async + SQLite (local) / Postgres (hosted) | SQLite for local single-user. |
| Async jobs | Job-status endpoint + polling → RQ + Redis later | Generation must not block the UI. |
| Packaging | uv | Fast, reproducible. |

## Generation + print pipeline

| Stage | Choice | Notes |
|---|---|---|
| Generation | Replicate FLUX 1.1 Pro (swappable → fal.ai) | Keep provider abstraction. |
| Raster cleanup | Pillow | Pure-B&W threshold, despeckle, trim, DPI. |
| Vectorization | vtracer (primary), potrace (alt) | Raster→SVG = infinite-DPI crisp print. |
| SVG render | CairoSVG | SVG→PDF/PNG at exact DPI. |
| Text layers | SVG `<text>` elements | Editable vector text, composited at export. |
| Book assembly | PyMuPDF (fitz) | Multi-page print PDF with trim/bleed/margins. |

## Design assets

- Figma — UI design + Dev Mode MCP for design→code.
- Canva MCP — covers and marketing exports (PDF/PNG).

## Quality & delivery

- Backend: pytest + httpx, Ruff + Black, mypy.
- Frontend: Vitest + React Testing Library, Playwright (core loop), ESLint + Prettier.
- Repo: pre-commit hooks; pnpm; uv.
- Deploy: Docker; Railway/Render/Fly. Hosted needs Postgres + object storage (R2/S3) — Railway disk is ephemeral.

## Highest-impact upgrades vs. current

1. **Python 3.9 → 3.12** — removes recurring friction.
2. **Vectorization (vtracer → PyMuPDF)** — genuinely print-crisp output with editable vector text. (PyMuPDF used instead of CairoSVG — no system cairo/pango needed on this machine.)

## Confirmed infrastructure (this build)

| Concern | Service | How it's wired |
|---|---|---|
| Relational DB + vectors | **Neon Postgres + pgvector** | `DATABASE_URL` set → async Postgres (asyncpg) + `CREATE EXTENSION vector`; unset → local SQLite. `PageEmbedding` + `services/vectors.py` (Mistral `mistral-embed`, Postgres-only, no-op on SQLite). |
| Object storage | **Cloudflare R2** (S3 via boto3) | `STORAGE_BACKEND=r2` → `services/storage.py` reads/writes R2; `local` → filesystem. `public_url()` serves from `R2_PUBLIC_BASE_URL`. |
| PDF parsing / OCR | **Mistral** (`mistral-ocr-latest`) | `services/pdf_ocr.py` + `POST /api/documents/ocr`; 503 when `MISTRAL_API_KEY` unset. |
| Hosting | **Railway** (API already deployed) | Set the env vars below in the Railway service. |

### Required env vars (set in Railway)

- Neon: `DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DB?sslmode=require`
- R2: `STORAGE_BACKEND=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL` (opt: `R2_ENDPOINT`, `R2_REGION=auto`)
- Mistral: `MISTRAL_API_KEY` (opt: `MISTRAL_OCR_MODEL=mistral-ocr-latest`)
- Generation: `REPLICATE_API_TOKEN` (+ existing image vars)

Full template: `backend/.env.example`.

---

## Text LLM layer (Admin LLM Selection feature)

### Provider abstraction

`backend/app/services/text_providers.py` is a registry mirroring the image `providers.py` pattern. Currently registered providers:

| Provider ID | Display name | SDK |
|---|---|---|
| `gemini` | Google Gemini | `google-genai` |
| `claude` | Anthropic Claude | `anthropic` (new dep) |

Each provider entry declares available models. The registry is exposed via `GET /api/text-providers` (returns list of `{id, name, models}`).

`backend/app/services/text_gen.py` provides three async functions that dispatch to the correct provider SDK:

| Function | Purpose |
|---|---|
| `complete(provider, model, prompt)` | Raw completion (internal utility) |
| `refine_concept(provider, model, concept)` | Returns a refined concept string |
| `write_prompt(provider, model, concept, style)` | Returns `{positive, negative}` prompt pair |

### New + extended API endpoints

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/text-providers` | Returns text-LLM registry. |
| `POST` | `/api/pages/{id}/refine-concept` | Returns `{refined_concept}`; does **not** save. 400 if provider not configured. |
| `POST` | `/api/pages/{id}/write-prompt` | Returns `{positive, negative}`; does **not** save. 400 if provider not configured. |

`GET /api/settings` and `PUT /api/settings` now also carry:

| Field | Type | Notes |
|---|---|---|
| `concept_provider` / `concept_model` | string | Which text provider/model to use for concept refinement |
| `prompt_provider` / `prompt_model` | string | Which text provider/model to use for prompt writing |
| `image_configured` | bool | True when image provider credentials are present |
| `concept_configured` | bool | True when the selected concept provider's API key is set |
| `prompt_configured` | bool | True when the selected prompt provider's API key is set |

Defaults: `concept_provider=gemini`, `concept_model=gemini-2.5-flash`, `prompt_provider=gemini`, `prompt_model=gemini-2.5-flash`.

### Generation prompt authority

`backend/app/services/jobs.py` / `generate.py`: a page's saved `prompt` and `negative_prompt` fields are now the authoritative source for image generation. The deterministic `build_prompt()` function is used as the fallback only when those fields are empty. The negative prompt safety rail (coloring-book-safe terms) remains hard-coded regardless of LLM output.

### New dependency + env var

| Item | Value |
|---|---|
| Python package | `anthropic` |
| Env var | `ANTHROPIC_API_KEY` |

Add `ANTHROPIC_API_KEY` to Railway env vars when using the Claude provider. Gemini provider continues to use the existing `GEMINI_API_KEY` / `GOOGLE_API_KEY`.
