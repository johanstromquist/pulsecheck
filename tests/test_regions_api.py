import uuid

import pytest


@pytest.mark.asyncio
async def test_create_region(client):
    resp = await client.post("/api/v1/regions", json={
        "name": "us-east-1",
        "endpoint_url": "http://region-worker-1:8001",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "us-east-1"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_regions(client):
    await client.post("/api/v1/regions", json={
        "name": "eu-west-1",
        "endpoint_url": "http://region-worker-2:8001",
    })
    resp = await client.get("/api/v1/regions")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_region(client):
    create_resp = await client.post("/api/v1/regions", json={
        "name": "ap-south-1",
        "endpoint_url": "http://region-worker-3:8001",
    })
    region_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/regions/{region_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "ap-south-1"


@pytest.mark.asyncio
async def test_get_region_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/regions/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_region(client):
    create_resp = await client.post("/api/v1/regions", json={
        "name": "us-west-2",
        "endpoint_url": "http://region-worker-4:8001",
    })
    region_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/regions/{region_id}", json={
        "endpoint_url": "http://new-worker-4:8001",
    })
    assert resp.status_code == 200
    assert resp.json()["endpoint_url"] == "http://new-worker-4:8001"


@pytest.mark.asyncio
async def test_delete_region(client):
    create_resp = await client.post("/api/v1/regions", json={
        "name": "delete-region",
        "endpoint_url": "http://region-delete:8001",
    })
    region_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/regions/{region_id}")
    assert resp.status_code == 200
