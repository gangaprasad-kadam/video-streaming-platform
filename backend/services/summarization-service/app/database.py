from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base class shared by all ORM models in this service."""


async def connect_db() -> None:
    """Open the database engine and verify the connection is reachable."""
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)


async def close_db() -> None:
    """Dispose the database engine and release all connections."""
    await engine.dispose()


async def get_db() -> AsyncSession:  # type: ignore[override]
    """Yield a scoped async database session for a single request.

    Yields:
        AsyncSession: An active SQLAlchemy async session.
    """
    async with AsyncSessionFactory() as session:
        yield session
