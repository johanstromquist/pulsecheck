import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import async_session_factory
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.region import CheckRegion
from pulsecheck.models.service import Service
from pulsecheck.ws import manager as ws_manager

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # seconds for region worker requests
LOOP_INTERVAL = 10  # seconds between scheduler ticks


class DistributedChecker:
    """Fans out health checks to all active regions and uses consensus to determine status."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run_loop())
        logger.info("DistributedChecker started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("DistributedChecker stopped")

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in distributed check loop")
            await asyncio.sleep(LOOP_INTERVAL)

    async def _tick(self) -> None:
        async with async_session_factory() as session:
            regions = await self._get_active_regions(session)
            if not regions:
                return

            services = await self._get_due_services(session, regions)
            for service in services:
                await self._check_service_distributed(session, service, regions)

    async def _get_active_regions(self, session: AsyncSession) -> list[CheckRegion]:
        stmt = select(CheckRegion).where(CheckRegion.is_active.is_(True))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _get_due_services(
        self, session: AsyncSession, regions: list[CheckRegion]
    ) -> list[Service]:
        now = datetime.now(timezone.utc)
        stmt = select(Service).where(Service.is_active.is_(True))
        result = await session.execute(stmt)
        services = list(result.scalars().all())

        due: list[Service] = []
        for svc in services:
            latest_stmt = (
                select(HealthCheck.checked_at)
                .where(HealthCheck.service_id == svc.id)
                .where(HealthCheck.region_id.isnot(None))
                .order_by(HealthCheck.checked_at.desc())
                .limit(1)
            )
            latest_result = await session.execute(latest_stmt)
            last_checked_at = latest_result.scalar_one_or_none()

            if last_checked_at is None:
                due.append(svc)
            else:
                elapsed = (now - last_checked_at).total_seconds()
                if elapsed >= svc.check_interval_seconds:
                    due.append(svc)

        return due

    async def _check_service_distributed(
        self,
        session: AsyncSession,
        service: Service,
        regions: list[CheckRegion],
    ) -> None:
        """Fan out check requests to all regions in parallel and apply consensus."""
        tasks = [
            self._check_via_region(region, service) for region in regions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        checked_at = datetime.now(timezone.utc)
        region_checks: list[HealthCheck] = []

        for region, result in zip(regions, results):
            if isinstance(result, Exception):
                logger.error(
                    "Region %s failed for service %s: %s",
                    region.name, service.name, result,
                )
                check = HealthCheck(
                    id=uuid.uuid4(),
                    service_id=service.id,
                    region_id=region.id,
                    status=HealthStatus.down,
                    response_time_ms=None,
                    status_code=None,
                    error_message=f"Region worker error: {result}",
                    checked_at=checked_at,
                )
            else:
                check = HealthCheck(
                    id=uuid.uuid4(),
                    service_id=service.id,
                    region_id=region.id,
                    status=result["status"],
                    response_time_ms=result.get("response_time_ms"),
                    status_code=result.get("status_code"),
                    error_message=result.get("error_message"),
                    checked_at=checked_at,
                )
            region_checks.append(check)
            session.add(check)

        # Apply consensus logic
        consensus_status = self._compute_consensus(region_checks)

        # Store a consensus health check (without region_id) for backward compat
        consensus_check = HealthCheck(
            id=uuid.uuid4(),
            service_id=service.id,
            region_id=None,
            status=consensus_status,
            response_time_ms=self._avg_response_time(region_checks),
            status_code=None,
            error_message=None,
            checked_at=checked_at,
        )
        session.add(consensus_check)
        await session.commit()

        logger.info(
            "Distributed check %s: consensus=%s (regions: %s)",
            service.name,
            consensus_status.value,
            ", ".join(
                f"{c.region_id}={c.status.value}" for c in region_checks
            ),
        )

        await ws_manager.broadcast({
            "type": "health_check",
            "service_id": str(service.id),
            "status": consensus_status.value,
            "response_time_ms": consensus_check.response_time_ms,
            "checked_at": consensus_check.checked_at.isoformat(),
        })

    async def _check_via_region(
        self, region: CheckRegion, service: Service
    ) -> dict:
        """Send a check request to a region worker and return the result."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{region.endpoint_url}/check",
                json={"url": str(service.url), "service_id": str(service.id)},
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _compute_consensus(checks: list[HealthCheck]) -> HealthStatus:
        """
        Consensus logic:
        - 'down' only if majority of regions report down
        - 'degraded' if any region reports issues but majority is healthy
        - 'healthy' if all regions are healthy
        """
        if not checks:
            return HealthStatus.down

        total = len(checks)
        down_count = sum(1 for c in checks if c.status == HealthStatus.down)
        degraded_count = sum(1 for c in checks if c.status == HealthStatus.degraded)

        if down_count > total / 2:
            return HealthStatus.down
        elif down_count > 0 or degraded_count > 0:
            return HealthStatus.degraded
        else:
            return HealthStatus.healthy

    @staticmethod
    def _avg_response_time(checks: list[HealthCheck]) -> int | None:
        times = [c.response_time_ms for c in checks if c.response_time_ms is not None]
        if not times:
            return None
        return int(sum(times) / len(times))
