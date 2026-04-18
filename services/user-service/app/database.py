from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models in this service."""

    pass


async def connect_db() -> None:
    """Ping the database to verify the connection is alive."""
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)  # ping to verify connection


async def close_db() -> None:
    """Dispose of all connections in the async engine pool."""
    await engine.dispose()


async def get_db() -> AsyncSession:  # type: ignore[override]
    """Yield a scoped async database session for a single request.

    Yields:
        An AsyncSession that is automatically closed after the request.
    """
    async with AsyncSessionFactory() as session:
        yield session
