import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

from app.main import app
from app.database import Base, get_db
from app.redis_client import get_redis

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(DATABASE_URL)
TestSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.zrevrange.return_value = []
    redis.zincrby.return_value = 1.0
    redis.zrange.return_value = []
    redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)
    return redis


@pytest_asyncio.fixture
async def client(db_session, mock_redis):
    async def override_db():
        yield db_session

    def override_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
