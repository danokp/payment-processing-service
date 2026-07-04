from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_api_key_settings
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://payments:payments@localhost:5432/payments"


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
