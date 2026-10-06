from collections.abc import Generator
from urllib.parse import urlparse

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# One FastAPI process. Small enough that a Supabase session pooler is not exhausted.
POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_TIMEOUT_SECONDS = 30
POOL_RECYCLE_SECONDS = 1800


class Base(DeclarativeBase):
    """Shared metadata for ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def normalized_database_url() -> str:
    """Return DATABASE_URL with the psycopg driver, without logging the value."""
    raw = settings.database_url.strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    if not raw.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection string")
    return raw


def _parsed_database_url() -> str:
    return normalized_database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def uses_transaction_pooler(url: str | None = None) -> bool:
    """True for Supavisor transaction mode (port 6543)."""
    parsed = urlparse(_parsed_database_url() if url is None else url)
    return parsed.port == 6543


def _is_local_database(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def connect_args_for(url: str) -> dict[str, object]:
    """SSL for hosted Postgres. Disable prepared statements on the transaction pooler."""
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    args: dict[str, object] = {}
    if "sslmode=" not in parsed.query and not _is_local_database(url):
        args["sslmode"] = "require"
    if parsed.port == 6543:
        args["prepare_threshold"] = None
    return args


def create_app_engine() -> Engine:
    """Engine for the API.

    Session mode and direct connections keep a small SQLAlchemy pool.
    Transaction mode (port 6543) uses NullPool because Supavisor does not
    support prepared statements or holding a server connection per client.
    """
    url = normalized_database_url()
    connect_args = connect_args_for(url)
    if uses_transaction_pooler(url):
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_recycle=POOL_RECYCLE_SECONDS,
        connect_args=connect_args,
    )


def create_migration_engine() -> Engine:
    """NullPool engine for Alembic. Requires a session-capable connection."""
    url = normalized_database_url()
    if uses_transaction_pooler(url):
        raise RuntimeError(
            "DATABASE_URL uses the Supabase transaction pooler on port 6543. "
            "Alembic needs the session pooler on port 5432 or the direct database connection."
        )
    return create_engine(url, poolclass=NullPool, connect_args=connect_args_for(url))


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
