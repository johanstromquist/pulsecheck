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
    Alert,
    AlertRule,
    ConditionType,
    Severity,
)


@pytest_asyncio.fixture
async def db_engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# --- Alert Rules API tests ---


@pytest.mark.asyncio
async def test_create_alert_rule(client):
    resp = await client.post("/api/v1/alert-rules", json={
        "name": "Test rule",
        "condition_type": "status_change",
        "threshold_value": 1,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test rule"
    assert data["condition_type"] == "status_change"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_alert_rules(client):
    await client.post("/api/v1/alert-rules", json={
        "name": "Rule A",
        "condition_type": "status_change",
    })
    await client.post("/api/v1/alert-rules", json={
        "name": "Rule B",
        "condition_type": "consecutive_failures",
        "threshold_value": 5,
    })

    resp = await client.get("/api/v1/alert-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_alert_rule(client):
    create_resp = await client.post("/api/v1/alert-rules", json={
        "name": "Test rule",
        "condition_type": "status_change",
    })
    rule_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/alert-rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rule_id


@pytest.mark.asyncio
async def test_get_alert_rule_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/alert-rules/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_alert_rule(client):
    create_resp = await client.post("/api/v1/alert-rules", json={
        "name": "Test rule",
        "condition_type": "status_change",
    })
    rule_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/alert-rules/{rule_id}", json={
        "name": "Updated name",
        "is_active": False,
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated name"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_alert_rule(client):
    create_resp = await client.post("/api/v1/alert-rules", json={
        "name": "Test rule",
        "condition_type": "status_change",
    })
    rule_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/alert-rules/{rule_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/alert-rules/{rule_id}")
    assert resp.status_code == 404


# --- Notification Channels API tests ---


@pytest.mark.asyncio
async def test_create_channel(client):
    resp = await client.post("/api/v1/channels", json={
        "name": "My Webhook",
        "channel_type": "webhook",
        "config": {"url": "https://hooks.example.com/test"},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Webhook"
    assert data["channel_type"] == "webhook"


@pytest.mark.asyncio
async def test_list_channels(client):
    await client.post("/api/v1/channels", json={
        "name": "Ch1",
        "channel_type": "webhook",
        "config": {"url": "https://example.com"},
    })
    await client.post("/api/v1/channels", json={
        "name": "Ch2",
        "channel_type": "email",
        "config": {"email": "admin@example.com"},
    })

    resp = await client.get("/api/v1/channels")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_channel(client):
    create_resp = await client.post("/api/v1/channels", json={
        "name": "Old Name",
        "channel_type": "webhook",
        "config": {"url": "https://example.com"},
    })
    channel_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/channels/{channel_id}", json={
        "name": "New Name",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_channel(client):
    create_resp = await client.post("/api/v1/channels", json={
        "name": "To Delete",
        "channel_type": "slack",
        "config": {"webhook_url": "https://hooks.slack.com/test"},
    })
    channel_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/channels/{channel_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/channels/{channel_id}")
    assert resp.status_code == 404


# --- Alerts API tests ---


@pytest.mark.asyncio
async def test_list_alerts_empty(client):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_alerts_with_filters(client, db_session):
    """Test alert filtering by service_id, severity, and acknowledged status."""
    # Create a service first
    from pulsecheck.models.service import Service
    service = Service(
        id=uuid.uuid4(),
        name="filter-test-service",
        url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(service)

    rule = AlertRule(
        id=uuid.uuid4(),
        name="filter-test-rule",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(rule)

    alert1 = Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        service_id=service.id,
        severity=Severity.critical,
        message="Critical alert",
        acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    alert2 = Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        service_id=service.id,
        severity=Severity.warning,
        message="Warning alert",
        acknowledged=True,
        acknowledged_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([alert1, alert2])
    await db_session.commit()

    # Filter by severity
    resp = await client.get("/api/v1/alerts", params={"severity": "critical"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["severity"] == "critical"

    # Filter by acknowledged
    resp = await client.get("/api/v1/alerts", params={"acknowledged": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["acknowledged"] is True


@pytest.mark.asyncio
async def test_acknowledge_alert(client, db_session):
    """Acknowledging an alert sets acknowledged flag and timestamp."""
    from pulsecheck.models.service import Service
    service = Service(
        id=uuid.uuid4(),
        name="ack-test-service",
        url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(service)

    rule = AlertRule(
        id=uuid.uuid4(),
        name="ack-test-rule",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(rule)

    alert = Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        service_id=service.id,
        severity=Severity.critical,
        message="Alert to acknowledge",
        acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    resp = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert data["acknowledged"] is True
    assert data["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/alerts/{fake_id}/acknowledge")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_acknowledge_already_acknowledged(client, db_session):
    """Cannot acknowledge an already-acknowledged alert."""
    from pulsecheck.models.service import Service
    service = Service(
        id=uuid.uuid4(),
        name="ack-dup-service",
        url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(service)

    rule = AlertRule(
        id=uuid.uuid4(),
        name="ack-dup-rule",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(rule)

    alert = Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        service_id=service.id,
        severity=Severity.critical,
        message="Already acknowledged",
        acknowledged=True,
        acknowledged_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    resp = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 409
