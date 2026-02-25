import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pulsecheck.db.session import get_session
from pulsecheck.models.health_check import HealthCheck, HealthStatus
from pulsecheck.models.incident import Incident, IncidentStatus
from pulsecheck.models.service import Service

router = APIRouter(prefix="/api/v1/status-page", tags=["status-page"])


@router.get("")
async def get_status_page(
    session: AsyncSession = Depends(get_session),
):
    """Public status page data - no auth required."""
    now = datetime.now(timezone.utc)

    # Get all active services
    stmt = select(Service).where(Service.is_active.is_(True)).order_by(Service.name)
    result = await session.execute(stmt)
    services = result.scalars().all()

    # Build service status data with 90-day uptime
    service_data = []
    for svc in services:
        # Get latest health check for current status
        latest_stmt = (
            select(HealthCheck)
            .where(HealthCheck.service_id == svc.id)
            .order_by(HealthCheck.checked_at.desc())
            .limit(1)
        )
        latest_result = await session.execute(latest_stmt)
        latest_check = latest_result.scalar_one_or_none()

        # Calculate 90-day uptime
        ninety_days_ago = now - timedelta(days=90)
        uptime_stmt = select(
            func.count().label("total"),
            func.count(case((HealthCheck.status == HealthStatus.healthy, 1))).label("healthy_count"),
        ).where(
            and_(
                HealthCheck.service_id == svc.id,
                HealthCheck.checked_at >= ninety_days_ago,
            )
        )
        uptime_result = await session.execute(uptime_stmt)
        uptime_row = uptime_result.one()
        total = uptime_row.total
        healthy_count = uptime_row.healthy_count

        uptime_90d = (healthy_count / total * 100) if total > 0 else None

        # Get daily uptime for the 90-day bar chart
        daily_uptime = []
        for days_ago in range(89, -1, -1):
            day_start = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_stmt = select(
                func.count().label("total"),
                func.count(case((HealthCheck.status == HealthStatus.healthy, 1))).label("healthy"),
            ).where(
                and_(
                    HealthCheck.service_id == svc.id,
                    HealthCheck.checked_at >= day_start,
                    HealthCheck.checked_at < day_end,
                )
            )
            day_result = await session.execute(day_stmt)
            day_row = day_result.one()
            if day_row.total > 0:
                daily_uptime.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "uptime": round(day_row.healthy / day_row.total * 100, 2),
                })
            else:
                daily_uptime.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "uptime": None,
                })

        service_data.append({
            "id": str(svc.id),
            "name": svc.name,
            "url": svc.url,
            "current_status": latest_check.status.value if latest_check else "unknown",
            "uptime_90d": round(uptime_90d, 4) if uptime_90d is not None else None,
            "daily_uptime": daily_uptime,
        })

    # Get active incidents
    active_stmt = (
        select(Incident)
        .options(selectinload(Incident.updates))
        .where(Incident.status != IncidentStatus.resolved)
        .order_by(Incident.created_at.desc())
    )
    active_result = await session.execute(active_stmt)
    active_incidents = active_result.scalars().all()

    # Get recent resolved incidents (last 14 days)
    fourteen_days_ago = now - timedelta(days=14)
    recent_stmt = (
        select(Incident)
        .options(selectinload(Incident.updates))
        .where(
            and_(
                Incident.status == IncidentStatus.resolved,
                Incident.created_at >= fourteen_days_ago,
            )
        )
        .order_by(Incident.created_at.desc())
    )
    recent_result = await session.execute(recent_stmt)
    recent_incidents = recent_result.scalars().all()

    # Determine overall status
    has_critical = any(
        i.severity.value == "critical" for i in active_incidents
    )
    has_major = any(
        i.severity.value == "major" for i in active_incidents
    )
    any_service_down = any(s["current_status"] == "down" for s in service_data)

    if has_critical or any_service_down:
        overall_status = "Major Outage"
    elif has_major or len(active_incidents) > 0:
        overall_status = "Partial Outage"
    else:
        overall_status = "All Systems Operational"

    def format_incident(inc):
        return {
            "id": str(inc.id),
            "title": inc.title,
            "description": inc.description,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "affected_service_ids": inc.affected_service_ids,
            "started_at": inc.started_at.isoformat(),
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "created_at": inc.created_at.isoformat(),
            "updates": [
                {
                    "id": str(u.id),
                    "message": u.message,
                    "status": u.status.value,
                    "created_by": u.created_by,
                    "created_at": u.created_at.isoformat(),
                }
                for u in sorted(inc.updates, key=lambda x: x.created_at, reverse=True)
            ],
        }

    return {
        "overall_status": overall_status,
        "services": service_data,
        "active_incidents": [format_incident(i) for i in active_incidents],
        "recent_incidents": [format_incident(i) for i in recent_incidents],
    }
