import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pulsecheck.checker.engine import HealthCheckEngine
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.service import Service


@pytest.fixture
def mock_service():
    return Service(
        id=uuid.uuid4(),
        name="mock-svc",
        url="https://example.com",
        check_interval_seconds=60,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestCheckService:
    """Test _check_service with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_healthy_200_response(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)

        # Verify a health check was created
        from sqlalchemy import select
        stmt = select(HealthCheck).where(HealthCheck.service_id == mock_service.id)
        result = await session.execute(stmt)
        checks = list(result.scalars().all())
        assert len(checks) == 1
        assert checks[0].status == HealthStatus.healthy
        assert checks[0].response_time_ms is not None

    @pytest.mark.asyncio
    async def test_degraded_on_4xx(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)

        from sqlalchemy import select
        stmt = select(HealthCheck).where(HealthCheck.service_id == mock_service.id)
        result = await session.execute(stmt)
        checks = list(result.scalars().all())
        assert len(checks) == 1
        assert checks[0].status == HealthStatus.degraded

    @pytest.mark.asyncio
    async def test_down_on_500(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)

        from sqlalchemy import select
        stmt = select(HealthCheck).where(HealthCheck.service_id == mock_service.id)
        result = await session.execute(stmt)
        checks = list(result.scalars().all())
        assert len(checks) == 1
        assert checks[0].status == HealthStatus.down

    @pytest.mark.asyncio
    async def test_down_on_timeout(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)

        from sqlalchemy import select
        stmt = select(HealthCheck).where(HealthCheck.service_id == mock_service.id)
        result = await session.execute(stmt)
        checks = list(result.scalars().all())
        assert len(checks) == 1
        assert checks[0].status == HealthStatus.down
        assert "timed out" in checks[0].error_message

    @pytest.mark.asyncio
    async def test_down_on_connect_error(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)

        from sqlalchemy import select
        stmt = select(HealthCheck).where(HealthCheck.service_id == mock_service.id)
        result = await session.execute(stmt)
        checks = list(result.scalars().all())
        assert len(checks) == 1
        assert checks[0].status == HealthStatus.down
        assert checks[0].error_message is not None

    @pytest.mark.asyncio
    async def test_broadcasts_websocket_message(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("pulsecheck.checker.engine.httpx.AsyncClient", return_value=mock_client):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await engine._check_service(session, mock_service)
                mock_ws.broadcast.assert_called_once()
                broadcast_msg = mock_ws.broadcast.call_args[0][0]
                assert broadcast_msg["type"] == "health_check"
                assert broadcast_msg["service_id"] == str(mock_service.id)
                assert broadcast_msg["status"] == "healthy"


class TestGetDueServices:
    @pytest.mark.asyncio
    async def test_never_checked_service_is_due(self, session, mock_service):
        session.add(mock_service)
        await session.commit()

        engine = HealthCheckEngine()
        due = await engine._get_due_services(session)
        assert len(due) == 1
        assert due[0].id == mock_service.id

    @pytest.mark.asyncio
    async def test_recently_checked_service_not_due(self, session, mock_service):
        session.add(mock_service)

        # Use naive datetime since SQLite strips timezone info
        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=mock_service.id,
            status=HealthStatus.healthy,
            response_time_ms=100,
            checked_at=datetime.utcnow(),
        )
        session.add(check)
        await session.commit()

        engine = HealthCheckEngine()
        # Patch datetime.now to return naive UTC for SQLite compat
        naive_now = datetime.utcnow()
        with patch("pulsecheck.checker.engine.datetime") as mock_dt:
            mock_dt.now.return_value = naive_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            due = await engine._get_due_services(session)
        assert len(due) == 0

    @pytest.mark.asyncio
    async def test_overdue_service_is_due(self, session, mock_service):
        session.add(mock_service)

        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=mock_service.id,
            status=HealthStatus.healthy,
            response_time_ms=100,
            checked_at=datetime.utcnow() - timedelta(minutes=5),
        )
        session.add(check)
        await session.commit()

        engine = HealthCheckEngine()
        naive_now = datetime.utcnow()
        with patch("pulsecheck.checker.engine.datetime") as mock_dt:
            mock_dt.now.return_value = naive_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            due = await engine._get_due_services(session)
        assert len(due) == 1

    @pytest.mark.asyncio
    async def test_inactive_service_not_due(self, session):
        service = Service(
            id=uuid.uuid4(),
            name="inactive-svc",
            url="https://example.com",
            check_interval_seconds=60,
            is_active=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)
        await session.commit()

        engine = HealthCheckEngine()
        due = await engine._get_due_services(session)
        assert len(due) == 0
