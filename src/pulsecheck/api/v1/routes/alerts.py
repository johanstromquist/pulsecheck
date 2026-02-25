import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.alert import Alert, Severity
from pulsecheck.schemas.alert import AlertResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    service_id: uuid.UUID | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Alert)

    if service_id is not None:
        stmt = stmt.where(Alert.service_id == service_id)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged == acknowledged)

    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.acknowledged:
        raise HTTPException(status_code=409, detail="Alert already acknowledged")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(alert)
    return alert
