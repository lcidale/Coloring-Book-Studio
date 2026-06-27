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
