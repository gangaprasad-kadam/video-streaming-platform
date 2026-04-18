from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all video-service ORM models."""

    pass


async def connect_db() -> None:
    """Verify the async database engine can reach PostgreSQL.

    Opens a connection and immediately releases it to confirm the engine
    is healthy. Called during application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)


async def close_db() -> None:
    """Dispose of all connections in the async engine pool.

    Called during application shutdown to release database resources cleanly.
    """
    await engine.dispose()


async def get_db() -> AsyncSession:  # type: ignore[override]
    """FastAPI dependency that yields a database session per request.

    Yields:
        An async SQLAlchemy session that is automatically closed after
        the request completes.
    """
    async with AsyncSessionFactory() as session:
        yield session
