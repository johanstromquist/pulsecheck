from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from pulsecheck.checker.region_worker import app as worker_app


@pytest.mark.asyncio
async def test_worker_health():
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_worker_check_healthy_service():
    transport = ASGITransport(app=worker_app)

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("pulsecheck.checker.region_worker.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/check", json={
                "url": "https://example.com",
                "service_id": "test-svc-id",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["response_time_ms"] is not None


@pytest.mark.asyncio
async def test_worker_check_degraded_service():
    transport = ASGITransport(app=worker_app)

    mock_response = MagicMock()
    mock_response.status_code = 403

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("pulsecheck.checker.region_worker.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/check", json={
                "url": "https://example.com",
                "service_id": "test-svc-id",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_worker_check_down_service():
    transport = ASGITransport(app=worker_app)

    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("pulsecheck.checker.region_worker.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/check", json={
                "url": "https://example.com",
                "service_id": "test-svc-id",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "down"


@pytest.mark.asyncio
async def test_worker_check_timeout():
    import httpx

    transport = ASGITransport(app=worker_app)

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("timeout")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("pulsecheck.checker.region_worker.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/check", json={
                "url": "https://example.com",
                "service_id": "test-svc-id",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "down"
    assert data["error_message"] is not None
