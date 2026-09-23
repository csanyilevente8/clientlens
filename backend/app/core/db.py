"""Database engine, session factory, and the declarative Base.

Java/Spring analog:
- `engine`         ≈ the DataSource / connection pool.
- `SessionLocal`   ≈ EntityManagerFactory; a session ≈ an EntityManager.
- `Base`           ≈ the mapped-superclass all @Entity classes extend.
- `get_session()`  ≈ how a request obtains a transactional persistence context;
                     here it is a FastAPI dependency (request-scoped).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,  # validate connections before use (avoids stale-connection errors)
        future=True,
    )


engine: AsyncEngine = _create_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with SessionLocal() as session:
        yield session
