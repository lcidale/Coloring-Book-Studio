import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))
DB_PATH = STORAGE_DIR / "studio.sqlite"

# ---------------------------------------------------------------------------
# Engine selection: Neon/Postgres when DATABASE_URL is set, else SQLite.
# DATABASE_URL must be a postgresql+asyncpg:// URL (sslmode=require is
# embedded in the URL or connect_args; Neon requires SSL).
# ---------------------------------------------------------------------------

_DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# Detect which dialect we're running so other modules can gate Postgres-only
# features (e.g. pgvector) without importing the engine directly.
IS_POSTGRES: bool = bool(_DATABASE_URL and _DATABASE_URL.startswith("postgresql"))

if IS_POSTGRES:
    # Neon requires SSL; pass sslmode via connect_args so asyncpg picks it up.
    # Neon's serverless tier closes idle connections server-side, leaving stale
    # entries in the pool. pool_pre_ping tests (and transparently replaces) a
    # connection before each use; pool_recycle drops connections older than the
    # idle window. Together these prevent the "connection is closed" error on the
    # first request after an idle period.
    engine = create_async_engine(
        _DATABASE_URL,
        echo=False,
        connect_args={"ssl": "require"},
        pool_pre_ping=True,
        pool_recycle=300,
    )
else:
    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Lightweight additive column migrations for existing SQLite dev databases.
# create_all() adds new *tables* but never new *columns*, so columns added to
# an existing model are listed here as idempotent ADD COLUMN statements.
# This block is ONLY applied on the SQLite path.
# ---------------------------------------------------------------------------
_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "page_versions": {"svg_path": "VARCHAR"},
    "text_layers": {"text_anchor": "VARCHAR(20) DEFAULT 'middle'"},
}


def _apply_column_migrations(conn) -> None:
    """Run idempotent ADD COLUMN migrations (SQLite only)."""
    for table, columns in _COLUMN_MIGRATIONS.items():
        existing = {
            row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        }
        if not existing:
            continue  # table created fresh by create_all with the right columns
        for col, ddl in columns.items():
            if col not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def _ensure_vector_extension(conn) -> None:
    """Enable pgvector extension (Postgres only). Called inside begin() so DDL auto-commits."""
    conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")


async def init_db():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    (STORAGE_DIR / "books").mkdir(exist_ok=True)
    async with engine.begin() as conn:
        if IS_POSTGRES:
            # Enable vector extension before create_all so Vector columns exist.
            await conn.run_sync(_ensure_vector_extension)
        await conn.run_sync(Base.metadata.create_all)
        if not IS_POSTGRES:
            # SQLite-only additive column migrations.
            await conn.run_sync(_apply_column_migrations)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
