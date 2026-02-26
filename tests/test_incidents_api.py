import uuid

import pytest


@pytest.mark.asyncio
async def test_create_incident(client):
    resp = await client.post("/api/v1/incidents", json={
        "title": "Service outage",
        "description": "API is returning 500s",
        "severity": "critical",
        "affected_service_ids": [],
        "created_by": "admin",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Service outage"
    assert data["severity"] == "critical"
    assert data["status"] == "investigating"


@pytest.mark.asyncio
async def test_list_incidents(client):
    await client.post("/api/v1/incidents", json={
        "title": "Incident 1",
        "severity": "minor",
    })
    await client.post("/api/v1/incidents", json={
        "title": "Incident 2",
        "severity": "major",
    })

    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_list_incidents_filter_by_severity(client):
    await client.post("/api/v1/incidents", json={
        "title": "Critical incident",
        "severity": "critical",
    })
    await client.post("/api/v1/incidents", json={
        "title": "Minor incident",
        "severity": "minor",
    })

    resp = await client.get("/api/v1/incidents", params={"severity": "critical"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["severity"] == "critical" for i in data)


@pytest.mark.asyncio
async def test_get_incident(client):
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Get Test",
        "severity": "minor",
    })
    incident_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/incidents/{incident_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Test"
    assert "updates" in resp.json()


@pytest.mark.asyncio
async def test_get_incident_not_found(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/incidents/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_incident(client):
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Update Test",
        "severity": "minor",
    })
    incident_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/incidents/{incident_id}", json={
        "severity": "major",
        "status": "identified",
    })
    assert resp.status_code == 200
    assert resp.json()["severity"] == "major"
    assert resp.json()["status"] == "identified"


@pytest.mark.asyncio
async def test_incident_lifecycle(client):
    """Test the full incident lifecycle: create -> update -> resolve."""
    # 1. Create incident
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Full lifecycle test",
        "description": "Testing the complete flow",
        "severity": "critical",
        "created_by": "test",
    })
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "investigating"

    # 2. Add an update (identified)
    update_resp = await client.post(f"/api/v1/incidents/{incident_id}/updates", json={
        "message": "Root cause identified: database connection pool exhausted",
        "status": "identified",
        "created_by": "engineer",
    })
    assert update_resp.status_code == 201
    assert update_resp.json()["status"] == "identified"

    # Verify incident status changed
    get_resp = await client.get(f"/api/v1/incidents/{incident_id}")
    assert get_resp.json()["status"] == "identified"

    # 3. Add monitoring update
    update_resp2 = await client.post(f"/api/v1/incidents/{incident_id}/updates", json={
        "message": "Fix deployed, monitoring for stability",
        "status": "monitoring",
        "created_by": "engineer",
    })
    assert update_resp2.status_code == 201

    # 4. Resolve incident
    resolve_resp = await client.post(f"/api/v1/incidents/{incident_id}/resolve")
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
    assert resolve_resp.json()["resolved_at"] is not None

    # 5. Verify full incident with updates
    detail_resp = await client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "resolved"
    assert len(detail["updates"]) >= 3  # identified + monitoring + resolved

    # 6. Cannot resolve again
    re_resolve_resp = await client.post(f"/api/v1/incidents/{incident_id}/resolve")
    assert re_resolve_resp.status_code == 409


@pytest.mark.asyncio
async def test_add_update_to_nonexistent_incident(client):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/incidents/{fake_id}/updates", json={
        "message": "test",
        "status": "investigating",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_nonexistent_incident(client):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/incidents/{fake_id}/resolve")
    assert resp.status_code == 404
