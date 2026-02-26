import uuid
from datetime import datetime, timezone

import pytest

from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.service import Service


@pytest.mark.asyncio
async def test_get_service_checks(client, db_session):
    """Get health checks for a service."""
    service = Service(
        id=uuid.uuid4(),
        name="checks-test-svc",
        url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(service)

    check = HealthCheck(
        id=uuid.uuid4(),
        service_id=service.id,
        status=HealthStatus.healthy,
        response_time_ms=150,
        status_code=200,
        checked_at=datetime.now(timezone.utc),
    )
    db_session.add(check)
    await db_session.commit()

    resp = await client.get(f"/api/v1/services/{service.id}/checks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "healthy"
    assert data[0]["response_time_ms"] == 150


@pytest.mark.asyncio
async def test_get_checks_for_nonexistent_service(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/services/{fake_id}/checks")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_checks_empty(client, db_session):
    """Service exists but has no health checks."""
    service = Service(
        id=uuid.uuid4(),
        name="no-checks-svc",
        url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(service)
    await db_session.commit()

    resp = await client.get(f"/api/v1/services/{service.id}/checks")
    assert resp.status_code == 200
    assert resp.json() == []
