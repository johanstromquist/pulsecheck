import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.alerting.dispatcher import NotificationDispatcher
from pulsecheck.alerting.evaluator import AlertEvaluator
from pulsecheck.db.session import async_session_factory
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.incident import Incident, IncidentStatus, IncidentSeverity, IncidentUpdate as IncidentUpdateModel
from pulsecheck.models.service import Service
from pulsecheck.ws import manager as ws_manager

logger = logging.getLogger(__name__)

LOOP_INTERVAL = 10  # seconds between scheduler ticks
REQUEST_TIMEOUT = 10  # seconds


class HealthCheckEngine:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._evaluator = AlertEvaluator()
        self._dispatcher = NotificationDispatcher()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run_loop())
        logger.info("HealthCheckEngine started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
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
                # Auto-create incident if alert fires and no open incident exists for this service
                await self._auto_create_incident(session, service, new_alerts)
        except Exception:
            logger.exception("Error evaluating alerts for service %s", service.name)

        # Auto-resolve: check if service is healthy for 5 consecutive checks
        try:
            await self._check_auto_resolve(session, service)
        except Exception:
            logger.exception("Error checking auto-resolve for service %s", service.name)

        await ws_manager.broadcast({
            "type": "health_check",
            "service_id": str(service.id),
            "status": status.value,
            "response_time_ms": response_time_ms,
            "checked_at": check.checked_at.isoformat(),
        })

    async def _auto_create_incident(
        self, session: AsyncSession, service: Service, new_alerts: list
    ) -> None:
        """Auto-create an incident when an alert fires and no open incident exists for the service."""
        service_id_str = str(service.id)

        # Check if there's already an open incident for this service
        stmt = (
            select(Incident)
            .where(
                and_(
                    Incident.status != IncidentStatus.resolved,
                    Incident.affected_service_ids.contains([service_id_str]),
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            return

        # Determine severity from the alert
        alert = new_alerts[0]
        if alert.severity.value == "critical":
            incident_severity = IncidentSeverity.critical
        else:
            incident_severity = IncidentSeverity.major

        incident = Incident(
            title=f"Auto-detected issue with {service.name}",
            description=f"Automatically created incident due to alert: {alert.message}",
            severity=incident_severity,
            status=IncidentStatus.investigating,
            affected_service_ids=[service_id_str],
            created_by="system",
        )
        session.add(incident)
        await session.flush()

        update = IncidentUpdateModel(
            incident_id=incident.id,
            message=f"Incident automatically created. Alert: {alert.message}",
            status=IncidentStatus.investigating,
            created_by="system",
        )
        session.add(update)
        await session.commit()

        logger.info(
            "Auto-created incident '%s' for service %s",
            incident.title,
            service.name,
        )

    async def _check_auto_resolve(
        self, session: AsyncSession, service: Service
    ) -> None:
        """Auto-resolve incidents when all affected services have 5 consecutive healthy checks."""
        service_id_str = str(service.id)

        # Find open incidents that include this service
        stmt = (
            select(Incident)
            .where(
                and_(
                    Incident.status != IncidentStatus.resolved,
                    Incident.affected_service_ids.contains([service_id_str]),
                )
            )
        )
        result = await session.execute(stmt)
        open_incidents = result.scalars().all()

        if not open_incidents:
            return

        for incident in open_incidents:
            all_healthy = True
            for sid_str in incident.affected_service_ids:
                try:
                    sid = uuid.UUID(sid_str)
                except (ValueError, AttributeError):
                    continue

                # Get the last 5 checks for this service
                checks_stmt = (
                    select(HealthCheck)
                    .where(HealthCheck.service_id == sid)
                    .order_by(HealthCheck.checked_at.desc())
                    .limit(5)
                )
                checks_result = await session.execute(checks_stmt)
                recent_checks = checks_result.scalars().all()

                if len(recent_checks) < 5:
                    all_healthy = False
                    break

                if not all(c.status == HealthStatus.healthy for c in recent_checks):
                    all_healthy = False
                    break

            if all_healthy:
                incident.status = IncidentStatus.resolved
                incident.resolved_at = datetime.now(timezone.utc)

                update = IncidentUpdateModel(
                    incident_id=incident.id,
                    message="Incident auto-resolved: all affected services healthy for 5 consecutive checks",
                    status=IncidentStatus.resolved,
                    created_by="system",
                )
                session.add(update)
                await session.commit()

                logger.info(
                    "Auto-resolved incident '%s'",
                    incident.title,
                )
