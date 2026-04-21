from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all trending-service ORM models."""

    pass


async def connect_db() -> None:
    """Verify the async database engine can reach PostgreSQL."""
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)


async def close_db() -> None:
    """Dispose of all connections in the async engine pool."""
    await engine.dispose()


async def get_db() -> AsyncSession:  # type: ignore[override]
    """FastAPI dependency that yields a database session per request."""
    async with AsyncSessionFactory() as session:
        yield session
