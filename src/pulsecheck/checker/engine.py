import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import async_session_factory
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.service import Service
from pulsecheck.ws import manager as ws_manager

logger = logging.getLogger(__name__)

LOOP_INTERVAL = 10  # seconds between scheduler ticks
REQUEST_TIMEOUT = 10  # seconds


class HealthCheckEngine:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

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

        await ws_manager.broadcast({
            "type": "health_check",
            "service_id": str(service.id),
            "status": status.value,
            "response_time_ms": response_time_ms,
            "checked_at": check.checked_at.isoformat(),
        })
