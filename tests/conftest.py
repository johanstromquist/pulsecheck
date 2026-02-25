import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pulsecheck.db.base import Base
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.service import Service
from pulsecheck.models.alert import (
    AlertRule,
    NotificationChannel,
    ConditionType,
    ChannelType,
)


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
