import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from pulsecheck.checker.engine import (
    HealthCheckEngine,
)
from pulsecheck.models.alert import Alert, AlertRule, ConditionType, Severity
from pulsecheck.models.service import Service
from pulsecheck.models.ssl_certificate import SSLCertificate


@pytest.fixture
def check_engine():
    return HealthCheckEngine()


@pytest.fixture
def mock_service(session):
    service = Service(
        id=uuid.uuid4(),
        name="ssl-test-svc",
        url="https://secure.example.com",
        check_interval_seconds=60,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return service


class TestCheckSSL:
    @pytest.mark.asyncio
    async def test_creates_new_ssl_certificate(self, session, check_engine, mock_service):
        session.add(mock_service)
        await session.commit()

        cert_info = {
            "issuer": "Test CA",
            "subject": "secure.example.com",
            "serial_number": "ABC123",
            "not_before": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime(2030, 12, 31, tzinfo=timezone.utc),
            "days_until_expiry": 2000,
        }

        with patch("pulsecheck.checker.engine.check_ssl_certificate", new_callable=AsyncMock, return_value=cert_info):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await check_engine._check_ssl(session, mock_service, "secure.example.com")

        from sqlalchemy import select
        stmt = select(SSLCertificate).where(SSLCertificate.service_id == mock_service.id)
        result = await session.execute(stmt)
        cert = result.scalar_one_or_none()
        assert cert is not None
        assert cert.issuer == "Test CA"
        assert cert.days_until_expiry == 2000

    @pytest.mark.asyncio
    async def test_updates_existing_ssl_certificate(self, session, check_engine, mock_service):
        session.add(mock_service)

        existing_cert = SSLCertificate(
            id=uuid.uuid4(),
            service_id=mock_service.id,
            issuer="Old CA",
            subject="secure.example.com",
            serial_number="OLD123",
            not_before=datetime(2023, 1, 1, tzinfo=timezone.utc),
            not_after=datetime(2025, 12, 31, tzinfo=timezone.utc),
            days_until_expiry=100,
            last_checked_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        session.add(existing_cert)
        await session.commit()

        cert_info = {
            "issuer": "New CA",
            "subject": "secure.example.com",
            "serial_number": "NEW456",
            "not_before": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime(2030, 12, 31, tzinfo=timezone.utc),
            "days_until_expiry": 1800,
        }

        with patch("pulsecheck.checker.engine.check_ssl_certificate", new_callable=AsyncMock, return_value=cert_info):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await check_engine._check_ssl(session, mock_service, "secure.example.com")

        from sqlalchemy import select
        stmt = select(SSLCertificate).where(SSLCertificate.service_id == mock_service.id)
        result = await session.execute(stmt)
        cert = result.scalar_one()
        assert cert.issuer == "New CA"
        assert cert.serial_number == "NEW456"
        assert cert.days_until_expiry == 1800

    @pytest.mark.asyncio
    async def test_skips_recently_checked_cert(self, session, check_engine, mock_service):
        session.add(mock_service)

        existing_cert = SSLCertificate(
            id=uuid.uuid4(),
            service_id=mock_service.id,
            issuer="Test CA",
            subject="secure.example.com",
            serial_number="ABC123",
            not_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
            not_after=datetime(2030, 12, 31, tzinfo=timezone.utc),
            days_until_expiry=1800,
            last_checked_at=datetime.now(timezone.utc),
        )
        session.add(existing_cert)
        await session.commit()

        with patch("pulsecheck.checker.engine.check_ssl_certificate", new_callable=AsyncMock) as mock_check:
            await check_engine._check_ssl(session, mock_service, "secure.example.com")
            mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_ssl_check_failure(self, session, check_engine, mock_service):
        session.add(mock_service)
        await session.commit()

        with patch(
            "pulsecheck.checker.engine.check_ssl_certificate",
            new_callable=AsyncMock,
            side_effect=Exception("SSL error"),
        ):
            await check_engine._check_ssl(session, mock_service, "secure.example.com")

    @pytest.mark.asyncio
    async def test_warning_alert_for_expiring_cert(self, session, check_engine, mock_service):
        session.add(mock_service)
        await session.commit()

        cert_info = {
            "issuer": "Test CA",
            "subject": "secure.example.com",
            "serial_number": "ABC123",
            "not_before": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime.now(timezone.utc) + timedelta(days=20),
            "days_until_expiry": 20,
        }

        with patch("pulsecheck.checker.engine.check_ssl_certificate", new_callable=AsyncMock, return_value=cert_info):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await check_engine._check_ssl(session, mock_service, "secure.example.com")

        from sqlalchemy import select
        stmt = select(Alert).where(Alert.service_id == mock_service.id)
        result = await session.execute(stmt)
        alerts = list(result.scalars().all())
        assert len(alerts) == 1
        assert alerts[0].severity == Severity.warning
        assert "expires in 20 days" in alerts[0].message

    @pytest.mark.asyncio
    async def test_critical_alert_for_nearly_expired_cert(self, session, check_engine, mock_service):
        session.add(mock_service)
        await session.commit()

        cert_info = {
            "issuer": "Test CA",
            "subject": "secure.example.com",
            "serial_number": "ABC123",
            "not_before": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime.now(timezone.utc) + timedelta(days=3),
            "days_until_expiry": 3,
        }

        with patch("pulsecheck.checker.engine.check_ssl_certificate", new_callable=AsyncMock, return_value=cert_info):
            with patch("pulsecheck.checker.engine.ws_manager") as mock_ws:
                mock_ws.broadcast = AsyncMock()
                await check_engine._check_ssl(session, mock_service, "secure.example.com")

        from sqlalchemy import select
        stmt = select(Alert).where(Alert.service_id == mock_service.id)
        result = await session.execute(stmt)
        alerts = list(result.scalars().all())
        assert len(alerts) == 1
        assert alerts[0].severity == Severity.critical


class TestSSLAlertDedup:
    @pytest.mark.asyncio
    async def test_dedup_suppresses_duplicate_ssl_alert(self, session, check_engine, mock_service):
        session.add(mock_service)

        rule = AlertRule(
            id=uuid.uuid4(),
            name="SSL Alert",
            condition_type=ConditionType.ssl_expiry,
            threshold_value=30,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(rule)

        existing_alert = Alert(
            id=uuid.uuid4(),
            rule_id=rule.id,
            service_id=mock_service.id,
            severity=Severity.warning,
            message="SSL certificate for ssl-test-svc (https://secure.example.com) expires in 20 days",
            created_at=datetime.now(timezone.utc) - timedelta(hours=12),
        )
        session.add(existing_alert)
        await session.commit()

        await check_engine._create_ssl_alert(session, mock_service, 20, Severity.warning)

        from sqlalchemy import select
        stmt = select(Alert).where(Alert.service_id == mock_service.id)
        result = await session.execute(stmt)
        alerts = list(result.scalars().all())
        assert len(alerts) == 1


class TestSSLTick:
    @pytest.mark.asyncio
    async def test_ssl_tick_checks_https_services(self, session, check_engine):
        service = Service(
            id=uuid.uuid4(),
            name="https-svc",
            url="https://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)
        await session.commit()

        with patch.object(check_engine, "_check_ssl", new_callable=AsyncMock) as mock_check:
            with patch("pulsecheck.checker.engine.async_session_factory") as mock_factory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__.return_value = session
                mock_ctx.__aexit__.return_value = None
                mock_factory.return_value = mock_ctx

                await check_engine._ssl_tick()
                mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_ssl_tick_skips_http_services(self, session, check_engine):
        service = Service(
            id=uuid.uuid4(),
            name="http-svc",
            url="http://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)
        await session.commit()

        with patch.object(check_engine, "_check_ssl", new_callable=AsyncMock) as mock_check:
            with patch("pulsecheck.checker.engine.async_session_factory") as mock_factory:
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__.return_value = session
                mock_ctx.__aexit__.return_value = None
                mock_factory.return_value = mock_ctx

                await check_engine._ssl_tick()
                mock_check.assert_not_called()


class TestAutoIncident:
    @pytest.mark.asyncio
    async def test_auto_create_incident(self, session, check_engine):
        service = Service(
            id=uuid.uuid4(),
            name="incident-svc",
            url="https://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)

        rule = AlertRule(
            id=uuid.uuid4(),
            name="test rule",
            condition_type=ConditionType.status_change,
            threshold_value=1,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(rule)

        alert = Alert(
            id=uuid.uuid4(),
            rule_id=rule.id,
            service_id=service.id,
            severity=Severity.critical,
            message="Service is down",
            created_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()

        await check_engine._auto_create_incident(session, service, [alert])

        from sqlalchemy import select

        from pulsecheck.models.incident import Incident
        stmt = select(Incident)
        result = await session.execute(stmt)
        incidents = list(result.scalars().all())
        assert len(incidents) == 1
        assert "incident-svc" in incidents[0].title

    @pytest.mark.asyncio
    async def test_auto_create_skips_if_open_incident_exists(self, session, check_engine):
        from pulsecheck.models.incident import Incident, IncidentSeverity, IncidentStatus

        service = Service(
            id=uuid.uuid4(),
            name="existing-incident-svc",
            url="https://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)

        incident = Incident(
            title="Existing incident",
            severity=IncidentSeverity.critical,
            status=IncidentStatus.investigating,
            affected_service_ids=[str(service.id)],
        )
        session.add(incident)

        rule = AlertRule(
            id=uuid.uuid4(),
            name="test rule",
            condition_type=ConditionType.status_change,
            threshold_value=1,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(rule)

        alert = Alert(
            id=uuid.uuid4(),
            rule_id=rule.id,
            service_id=service.id,
            severity=Severity.critical,
            message="Service is down",
            created_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()

        await check_engine._auto_create_incident(session, service, [alert])

        from sqlalchemy import select
        stmt = select(Incident)
        result = await session.execute(stmt)
        incidents = list(result.scalars().all())
        assert len(incidents) == 1


class TestAutoResolve:
    @pytest.mark.asyncio
    async def test_auto_resolve_after_5_healthy_checks(self, session, check_engine):
        from pulsecheck.models.health_check import HealthCheck, HealthStatus
        from pulsecheck.models.incident import Incident, IncidentSeverity, IncidentStatus

        service = Service(
            id=uuid.uuid4(),
            name="resolve-test-svc",
            url="https://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)

        incident = Incident(
            title="Test incident",
            severity=IncidentSeverity.critical,
            status=IncidentStatus.investigating,
            affected_service_ids=[str(service.id)],
        )
        session.add(incident)

        now = datetime.now(timezone.utc)
        for i in range(5):
            check = HealthCheck(
                id=uuid.uuid4(),
                service_id=service.id,
                status=HealthStatus.healthy,
                response_time_ms=100,
                checked_at=now - timedelta(minutes=5 - i),
            )
            session.add(check)

        await session.commit()

        await check_engine._check_auto_resolve(session, service)

        from sqlalchemy import select
        stmt = select(Incident).where(Incident.id == incident.id)
        result = await session.execute(stmt)
        updated_incident = result.scalar_one()
        assert updated_incident.status == IncidentStatus.resolved

    @pytest.mark.asyncio
    async def test_no_auto_resolve_with_recent_failures(self, session, check_engine):
        from pulsecheck.models.health_check import HealthCheck, HealthStatus
        from pulsecheck.models.incident import Incident, IncidentSeverity, IncidentStatus

        service = Service(
            id=uuid.uuid4(),
            name="no-resolve-svc",
            url="https://example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(service)

        incident = Incident(
            title="Test incident",
            severity=IncidentSeverity.critical,
            status=IncidentStatus.investigating,
            affected_service_ids=[str(service.id)],
        )
        session.add(incident)

        now = datetime.now(timezone.utc)
        for i in range(4):
            check = HealthCheck(
                id=uuid.uuid4(),
                service_id=service.id,
                status=HealthStatus.healthy,
                response_time_ms=100,
                checked_at=now - timedelta(minutes=5 - i),
            )
            session.add(check)

        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=service.id,
            status=HealthStatus.down,
            response_time_ms=None,
            checked_at=now,
        )
        session.add(check)
        await session.commit()

        await check_engine._check_auto_resolve(session, service)

        from sqlalchemy import select
        stmt = select(Incident).where(Incident.id == incident.id)
        result = await session.execute(stmt)
        updated_incident = result.scalar_one()
        assert updated_incident.status == IncidentStatus.investigating


class TestEngineStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_tasks(self, check_engine):
        with patch.object(check_engine, "_run_loop", new_callable=AsyncMock):
            with patch.object(check_engine, "_run_ssl_loop", new_callable=AsyncMock):
                await check_engine.start()
                assert check_engine._task is not None
                assert check_engine._ssl_task is not None
                await check_engine.stop()
                assert check_engine._task is None
                assert check_engine._ssl_task is None

    @pytest.mark.asyncio
    async def test_stop_without_start(self, check_engine):
        await check_engine.stop()
