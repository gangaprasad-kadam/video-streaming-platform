from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def connect_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)  # ping to verify connection


async def close_db() -> None:
    await engine.dispose()


async def get_db() -> AsyncSession:  # type: ignore[override]
    async with AsyncSessionFactory() as session:
        yield session
