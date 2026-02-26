import pytest


@pytest.mark.asyncio
async def test_status_page_empty(client):
    """Status page returns successfully with no services or incidents."""
    resp = await client.get("/api/v1/status-page")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "All Systems Operational"
    assert data["services"] == []
    assert data["active_incidents"] == []
    assert data["recent_incidents"] == []


@pytest.mark.asyncio
async def test_status_page_with_service(client):
    """Status page includes active services."""
    await client.post("/api/v1/services", json={
        "name": "Status Test Service",
        "url": "https://status.example.com",
    })

    resp = await client.get("/api/v1/status-page")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["services"]) == 1
    assert data["services"][0]["name"] == "Status Test Service"
    assert data["services"][0]["current_status"] == "unknown"  # no checks yet


@pytest.mark.asyncio
async def test_status_page_with_active_incident(client):
    """Status page reflects active incidents in overall status."""
    await client.post("/api/v1/incidents", json={
        "title": "Active incident",
        "severity": "minor",
    })

    resp = await client.get("/api/v1/status-page")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "Partial Outage"
    assert len(data["active_incidents"]) >= 1


@pytest.mark.asyncio
async def test_status_page_critical_incident(client):
    """Critical incident shows Major Outage."""
    await client.post("/api/v1/incidents", json={
        "title": "Critical incident",
        "severity": "critical",
    })

    resp = await client.get("/api/v1/status-page")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "Major Outage"
