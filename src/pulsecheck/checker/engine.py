import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.alerting.dispatcher import NotificationDispatcher
from pulsecheck.alerting.evaluator import AlertEvaluator
from pulsecheck.checker.ssl_checker import check_ssl_certificate, extract_host_from_url
from pulsecheck.db.session import async_session_factory
from pulsecheck.models.alert import Alert, AlertRule, ConditionType, Severity
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.ssl_certificate import SSLCertificate
from pulsecheck.models.service import Service
from pulsecheck.ws import manager as ws_manager

logger = logging.getLogger(__name__)

LOOP_INTERVAL = 10  # seconds between scheduler ticks
REQUEST_TIMEOUT = 10  # seconds
SSL_CHECK_INTERVAL = 86400  # seconds (24 hours)
SSL_WARNING_DAYS = 30
SSL_CRITICAL_DAYS = 7


class HealthCheckEngine:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._ssl_task: asyncio.Task | None = None
        self._evaluator = AlertEvaluator()
        self._dispatcher = NotificationDispatcher()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run_loop())
        self._ssl_task = asyncio.create_task(self._run_ssl_loop())
        logger.info("HealthCheckEngine started")

    async def stop(self) -> None:
        for task in (self._task, self._ssl_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._ssl_task = None
        logger.info("HealthCheckEngine stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in health check loop")
            await asyncio.sleep(LOOP_INTERVAL)

    async def _tick(self) -> None:
        async with async_session_factory() as session:
            services = await self._get_due_services(session)
            for service in services:
                await self._check_service(session, service)

    async def _get_due_services(self, session: AsyncSession) -> list[Service]:
        now = datetime.now(timezone.utc)
        # Get all active services and filter in Python for those that are due
        stmt = (
            select(Service)
            .where(Service.is_active.is_(True))
        )
        result = await session.execute(stmt)
        services = list(result.scalars().all())

        due: list[Service] = []
        for svc in services:
            # Find the most recent health check for this service
            latest_stmt = (
                select(HealthCheck.checked_at)
                .where(HealthCheck.service_id == svc.id)
                .order_by(HealthCheck.checked_at.desc())
                .limit(1)
            )
            latest_result = await session.execute(latest_stmt)
            last_checked_at = latest_result.scalar_one_or_none()

            if last_checked_at is None:
                # Never checked – due immediately
                due.append(svc)
            else:
                elapsed = (now - last_checked_at).total_seconds()
                if elapsed >= svc.check_interval_seconds:
                    due.append(svc)

        return due

    async def _check_service(self, session: AsyncSession, service: Service) -> None:
        status = HealthStatus.down
        status_code = None
        response_time_ms = None
        error_message = None

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                start = time.monotonic()
                resp = await client.get(str(service.url))
                elapsed = time.monotonic() - start

                response_time_ms = int(elapsed * 1000)
                status_code = resp.status_code

                if 200 <= status_code < 300:
                    status = HealthStatus.healthy
                elif 300 <= status_code < 500:
                    status = HealthStatus.degraded
                else:
                    status = HealthStatus.down

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            error_message = str(exc)
            status = HealthStatus.down
        except httpx.HTTPError as exc:
            error_message = str(exc)
            status = HealthStatus.down

        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=service.id,
            status=status,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message,
            checked_at=datetime.now(timezone.utc),
        )
        session.add(check)
        await session.commit()

        logger.info(
            "Checked %s (%s): status=%s code=%s time=%sms",
            service.name,
            service.url,
            status.value,
            status_code,
            response_time_ms,
        )

        # Evaluate alert rules and dispatch notifications
        try:
            new_alerts = await self._evaluator.evaluate(session, service.id, check)
            for alert in new_alerts:
                rule = alert.rule
                if rule.channels:
                    await self._dispatcher.dispatch(session, alert, rule.channels)
            if new_alerts:
                await session.commit()
        except Exception:
            logger.exception("Error evaluating alerts for service %s", service.name)

        await ws_manager.broadcast({
            "type": "health_check",
            "service_id": str(service.id),
            "status": status.value,
            "response_time_ms": response_time_ms,
            "checked_at": check.checked_at.isoformat(),
        })

    # ---- SSL certificate checking (separate daily loop) ----

    async def _run_ssl_loop(self) -> None:
        while True:
            try:
                await self._ssl_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in SSL check loop")
            await asyncio.sleep(SSL_CHECK_INTERVAL)

    async def _ssl_tick(self) -> None:
        async with async_session_factory() as session:
            stmt = select(Service).where(Service.is_active.is_(True))
            result = await session.execute(stmt)
            services = list(result.scalars().all())

            for service in services:
                host = extract_host_from_url(str(service.url))
                if host is None:
                    continue  # skip non-HTTPS services
                await self._check_ssl(session, service, host)

    async def _check_ssl(
        self, session: AsyncSession, service: Service, host: str
    ) -> None:
        now = datetime.now(timezone.utc)

        # Check if we already have a cert record and if it was checked recently
        stmt = select(SSLCertificate).where(
            SSLCertificate.service_id == service.id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            elapsed = (now - existing.last_checked_at).total_seconds()
            if elapsed < SSL_CHECK_INTERVAL:
                return  # already checked within the interval

        try:
            cert_info = await check_ssl_certificate(host)
        except Exception as exc:
            logger.warning(
                "SSL check failed for %s (%s): %s", service.name, host, exc
            )
            return

        if existing is not None:
            existing.issuer = cert_info["issuer"]
            existing.subject = cert_info["subject"]
            existing.serial_number = cert_info["serial_number"]
            existing.not_before = cert_info["not_before"]
            existing.not_after = cert_info["not_after"]
            existing.days_until_expiry = cert_info["days_until_expiry"]
            existing.last_checked_at = now
            ssl_cert = existing
        else:
            ssl_cert = SSLCertificate(
                id=uuid.uuid4(),
                service_id=service.id,
                issuer=cert_info["issuer"],
                subject=cert_info["subject"],
                serial_number=cert_info["serial_number"],
                not_before=cert_info["not_before"],
                not_after=cert_info["not_after"],
                days_until_expiry=cert_info["days_until_expiry"],
                last_checked_at=now,
            )
            session.add(ssl_cert)

        await session.commit()

        logger.info(
            "SSL checked %s (%s): expires=%s days_remaining=%d",
            service.name,
            host,
            cert_info["not_after"].isoformat(),
            cert_info["days_until_expiry"],
        )

        # Generate SSL expiry alerts
        days = cert_info["days_until_expiry"]
        if days <= SSL_CRITICAL_DAYS:
            await self._create_ssl_alert(
                session, service, days, Severity.critical
            )
        elif days <= SSL_WARNING_DAYS:
            await self._create_ssl_alert(
                session, service, days, Severity.warning
            )

        await ws_manager.broadcast({
            "type": "ssl_check",
            "service_id": str(service.id),
            "days_until_expiry": days,
            "not_after": cert_info["not_after"].isoformat(),
        })

    async def _create_ssl_alert(
        self,
        session: AsyncSession,
        service: Service,
        days: int,
        severity: Severity,
    ) -> None:
        # Deduplication: skip if a similar SSL alert was created in the last 24h
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(Alert.id)
            .where(
                Alert.service_id == service.id,
                Alert.message.like("SSL certificate%"),
                Alert.created_at >= cutoff,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return

        # Find or create an SSL expiry alert rule
        rule_stmt = select(AlertRule).where(
            AlertRule.condition_type == ConditionType.ssl_expiry,
            AlertRule.is_active.is_(True),
            AlertRule.service_id.is_(None) | (AlertRule.service_id == service.id),
        )
        rule_result = await session.execute(rule_stmt)
        rule = rule_result.scalars().first()

        if rule is None:
            # Create a default global SSL expiry rule
            rule = AlertRule(
                id=uuid.uuid4(),
                name="SSL Certificate Expiry",
                condition_type=ConditionType.ssl_expiry,
                threshold_value=SSL_WARNING_DAYS,
                is_active=True,
            )
            session.add(rule)
            await session.flush()

        message = (
            f"SSL certificate for {service.name} ({service.url}) "
            f"expires in {days} days"
        )
        alert = Alert(
            id=uuid.uuid4(),
            rule_id=rule.id,
            service_id=service.id,
            severity=severity,
            message=message,
        )
        session.add(alert)
        await session.commit()

        logger.info(
            "SSL alert created: service=%s severity=%s days=%d",
            service.name,
            severity.value,
            days,
        )
