import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.service import Service
from pulsecheck.schemas.metrics import MetricsBucket, UptimePeriod

router = APIRouter(prefix="/api/v1/services", tags=["metrics"])

# Period string -> timedelta
PERIOD_DELTAS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# Auto bucket selection: period -> bucket size in seconds
AUTO_BUCKET: dict[str, int] = {
    "1h": 60,        # 1 minute
    "6h": 300,       # 5 minutes
    "24h": 900,      # 15 minutes
    "7d": 3600,      # 1 hour
    "30d": 86400,    # 1 day
}

# Named bucket -> seconds
BUCKET_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}


@router.get("/{service_id}/metrics", response_model=list[MetricsBucket])
async def get_service_metrics(
    service_id: uuid.UUID,
    period: Literal["1h", "6h", "24h", "7d", "30d"] = Query(default="24h"),
    bucket: Literal["auto", "1m", "5m", "15m", "1h", "1d"] = Query(default="auto"),
    session: AsyncSession = Depends(get_session),
) -> list[MetricsBucket]:
    svc = await session.get(Service, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")

    bucket_seconds = AUTO_BUCKET[period] if bucket == "auto" else BUCKET_SECONDS[bucket]
    start_time = datetime.now(timezone.utc) - PERIOD_DELTAS[period]

    # Use epoch-based bucketing for arbitrary bucket sizes with SQL aggregation.
    # FILTER (WHERE ...) is used for per-status counts in a single pass.
    stmt = text("""
        SELECT
            to_timestamp(
                FLOOR(EXTRACT(EPOCH FROM checked_at) / :bucket_seconds) * :bucket_seconds
            ) AT TIME ZONE 'UTC' AS bucket_time,
            AVG(response_time_ms)::float AS avg_response_time_ms,
            MIN(response_time_ms) AS min_response_time_ms,
            MAX(response_time_ms) AS max_response_time_ms,
            COUNT(*) AS check_count,
            COUNT(*) FILTER (WHERE status = 'healthy') AS healthy_count,
            COUNT(*) FILTER (WHERE status = 'degraded') AS degraded_count,
            COUNT(*) FILTER (WHERE status = 'down') AS down_count,
            CASE
                WHEN COUNT(*) > 0
                THEN (COUNT(*) FILTER (WHERE status = 'healthy'))::float / COUNT(*) * 100
                ELSE 0
            END AS uptime_percentage
        FROM health_checks
        WHERE service_id = :service_id
          AND checked_at >= :start_time
        GROUP BY bucket_time
        ORDER BY bucket_time
    """)

    result = await session.execute(
        stmt,
        {
            "bucket_seconds": bucket_seconds,
            "service_id": str(service_id),
            "start_time": start_time,
        },
    )

    return [
        MetricsBucket(
            timestamp=row.bucket_time.replace(tzinfo=timezone.utc),
            avg_response_time_ms=round(row.avg_response_time_ms, 2) if row.avg_response_time_ms is not None else None,
            min_response_time_ms=row.min_response_time_ms,
            max_response_time_ms=row.max_response_time_ms,
            check_count=row.check_count,
            healthy_count=row.healthy_count,
            degraded_count=row.degraded_count,
            down_count=row.down_count,
            uptime_percentage=round(row.uptime_percentage, 2),
        )
        for row in result
    ]


@router.get("/{service_id}/uptime", response_model=list[UptimePeriod])
async def get_service_uptime(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[UptimePeriod]:
    svc = await session.get(Service, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")

    now = datetime.now(timezone.utc)
    periods = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "90d": now - timedelta(days=90),
    }

    # Compute uptime for all periods in a single query using conditional aggregation.
    # Each period is calculated as a window over all checks, filtered by time range.
    stmt = text("""
        SELECT
            COUNT(*) FILTER (WHERE checked_at >= :start_24h) AS total_24h,
            COUNT(*) FILTER (WHERE checked_at >= :start_24h AND status = 'healthy') AS healthy_24h,
            COUNT(*) FILTER (WHERE checked_at >= :start_7d) AS total_7d,
            COUNT(*) FILTER (WHERE checked_at >= :start_7d AND status = 'healthy') AS healthy_7d,
            COUNT(*) FILTER (WHERE checked_at >= :start_30d) AS total_30d,
            COUNT(*) FILTER (WHERE checked_at >= :start_30d AND status = 'healthy') AS healthy_30d,
            COUNT(*) AS total_90d,
            COUNT(*) FILTER (WHERE status = 'healthy') AS healthy_90d
        FROM health_checks
        WHERE service_id = :service_id
          AND checked_at >= :start_90d
    """)

    result = await session.execute(
        stmt,
        {
            "service_id": str(service_id),
            "start_24h": periods["24h"],
            "start_7d": periods["7d"],
            "start_30d": periods["30d"],
            "start_90d": periods["90d"],
        },
    )
    row = result.one()

    def calc_uptime(healthy: int, total: int) -> float | None:
        if total == 0:
            return None
        return round(healthy / total * 100, 2)

    return [
        UptimePeriod(
            period="24h",
            uptime_percentage=calc_uptime(row.healthy_24h, row.total_24h),
            total_checks=row.total_24h,
        ),
        UptimePeriod(
            period="7d",
            uptime_percentage=calc_uptime(row.healthy_7d, row.total_7d),
            total_checks=row.total_7d,
        ),
        UptimePeriod(
            period="30d",
            uptime_percentage=calc_uptime(row.healthy_30d, row.total_30d),
            total_checks=row.total_30d,
        ),
        UptimePeriod(
            period="90d",
            uptime_percentage=calc_uptime(row.healthy_90d, row.total_90d),
            total_checks=row.total_90d,
        ),
    ]
