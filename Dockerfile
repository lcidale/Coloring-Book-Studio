# ── Stage 1: build the React frontend ─────────────────────────────────────────
FROM node:24-slim AS frontend-builder

# Enable corepack so pnpm is available without a separate install step
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app/frontend

# Install deps first (layer-cache friendly)
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and build
COPY frontend/ ./
RUN pnpm run build
# Output: /app/frontend/dist


# ── Stage 2: production Python image ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

# uv is the fastest way to install from pyproject.toml / uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install backend dependencies (no project package — tool.uv.package = false)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend source
COPY backend/ .

# Copy the compiled frontend into the directory FastAPI mounts as StaticFiles("/")
# main.py: STATIC_DIR = Path(__file__).parent / "static"  →  app/static/
COPY --from=frontend-builder /app/frontend/dist/ ./app/static/

# Ensure the local storage directory exists (used when STORAGE_BACKEND=local)
RUN mkdir -p storage

# Default port; Railway / docker-compose override via $PORT env var
ENV PORT=8000

EXPOSE ${PORT}

# Activate the uv-managed venv and start uvicorn
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
