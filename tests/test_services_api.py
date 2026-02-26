import uuid

import pytest


@pytest.mark.asyncio
async def test_create_service(client):
    resp = await client.post("/api/v1/services", json={
        "name": "My Service",
        "url": "https://example.com",
        "check_interval_seconds": 30,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Service"
    assert data["url"] == "https://example.com"
    assert data["check_interval_seconds"] == 30
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_service_duplicate_name(client):
    await client.post("/api/v1/services", json={
        "name": "Unique Service",
        "url": "https://example.com",
    })
    resp = await client.post("/api/v1/services", json={
        "name": "Unique Service",
        "url": "https://other.com",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_services(client):
    await client.post("/api/v1/services", json={
        "name": "Service A",
        "url": "https://a.com",
    })
    await client.post("/api/v1/services", json={
        "name": "Service B",
        "url": "https://b.com",
    })

    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_service(client):
    create_resp = await client.post("/api/v1/services", json={
        "name": "Get Test",
        "url": "https://get.example.com",
    })
    service_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/services/{service_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_get_service_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/services/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_service(client):
    create_resp = await client.post("/api/v1/services", json={
        "name": "Update Test",
        "url": "https://update.example.com",
    })
    service_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/services/{service_id}", json={
        "name": "Updated Name",
        "check_interval_seconds": 120,
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["check_interval_seconds"] == 120


@pytest.mark.asyncio
async def test_delete_service(client):
    create_resp = await client.post("/api/v1/services", json={
        "name": "Delete Test",
        "url": "https://delete.example.com",
    })
    service_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/services/{service_id}")
    assert resp.status_code == 200

    # Deleted = deactivated, so list should not include it
    list_resp = await client.get("/api/v1/services")
    ids = [s["id"] for s in list_resp.json()]
    assert service_id not in ids


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_status_endpoint(client):
    resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_seconds" in data
    assert "request_count" in data


@pytest.mark.asyncio
async def test_version_endpoint(client):
    resp = await client.get("/api/v1/version")
    assert resp.status_code == 200
    assert "version" in resp.json()
