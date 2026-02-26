import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pulsecheck.db.base import Base
from pulsecheck.db.session import get_session
from pulsecheck.main import app
from pulsecheck.models.alert import (
    ChannelType,
    NotificationChannel,
)
from pulsecheck.models.service import Service


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def sample_service(session):
    service = Service(
        id=uuid.uuid4(),
        name="test-service",
        url="https://example.com",
        check_interval_seconds=60,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(service)
    await session.commit()
    return service


@pytest_asyncio.fixture
async def sample_channel(session):
    channel = NotificationChannel(
        id=uuid.uuid4(),
        name="test-webhook",
        channel_type=ChannelType.webhook,
        config={"url": "https://hooks.example.com/test"},
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(channel)
    await session.commit()
    return channel


@pytest_asyncio.fixture
async def client(engine):
    """Test client with overridden database session."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(engine):
    """Alias for session that shares the same engine as the test client."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
