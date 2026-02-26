import uuid

import pytest


@pytest.mark.asyncio
async def test_ssl_not_found(client):
    """SSL endpoint returns 404 for a service with no certificate."""
    create_resp = await client.post("/api/v1/services", json={
        "name": "SSL Test Service",
        "url": "https://ssl.example.com",
    })
    service_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/services/{service_id}/ssl")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ssl_service_not_found(client):
    """SSL endpoint returns 404 for nonexistent service."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/services/{fake_id}/ssl")
    assert resp.status_code == 404
