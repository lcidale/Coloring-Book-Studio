import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import books, pages, generate, export, dashboard, jobs, documents

STATIC_DIR = Path(__file__).parent / "static"
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Coloring Book Studio", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(pages.router, prefix="/api/pages", tags=["pages"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

# Serve generated images locally; on R2 the public URL points at the bucket instead.
if STORAGE_BACKEND == "local":
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=STORAGE_DIR), name="storage")

# Serve frontend — must come last
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
