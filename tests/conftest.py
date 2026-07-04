from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_api_key_settings
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

TEST_DATABASE_NAME = "payments_test"
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://payments:payments@localhost:5432/{TEST_DATABASE_NAME}"
)
ADMIN_DATABASE_URL = "postgresql://payments:payments@localhost:5432/postgres"


@pytest.fixture(scope="session", autouse=True)
async def ensure_test_database() -> None:
    connection = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            TEST_DATABASE_NAME,
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{TEST_DATABASE_NAME}"')
    finally:
        await connection.close()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        API_KEY="test-key",
        DATABASE_URL=TEST_DATABASE_URL,
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
    )


@pytest.fixture
async def session_factory(
    test_settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(test_settings.database_url)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(
    test_settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_api_key_settings] = lambda: test_settings
    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
