import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pulsecheck.db.session import get_session
from pulsecheck.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from pulsecheck.models.incident import (
    IncidentUpdate as IncidentUpdateModel,
)
from pulsecheck.schemas.incident import (
    IncidentCreate,
    IncidentDetailResponse,
    IncidentResponse,
    IncidentUpdate,
    IncidentUpdateCreate,
    IncidentUpdateResponse,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    body: IncidentCreate,
    session: AsyncSession = Depends(get_session),
):
    incident = Incident(
        title=body.title,
        description=body.description,
        severity=body.severity,
        status=IncidentStatus.investigating,
        affected_service_ids=[str(sid) for sid in body.affected_service_ids],
        created_by=body.created_by,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    severity: IncidentSeverity | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Incident)

    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)

    stmt = stmt.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Incident)
        .options(selectinload(Incident.updates))
        .where(Incident.id == incident_id)
    )
    result = await session.execute(stmt)
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    body: IncidentUpdate,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    update_data = body.model_dump(exclude_unset=True)
    if "affected_service_ids" in update_data and update_data["affected_service_ids"] is not None:
        update_data["affected_service_ids"] = [str(sid) for sid in update_data["affected_service_ids"]]

    for field, value in update_data.items():
        setattr(incident, field, value)

    await session.commit()
    await session.refresh(incident)
    return incident


@router.post("/{incident_id}/updates", response_model=IncidentUpdateResponse, status_code=201)
async def add_incident_update(
    incident_id: uuid.UUID,
    body: IncidentUpdateCreate,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    update = IncidentUpdateModel(
        incident_id=incident_id,
        message=body.message,
        status=body.status,
        created_by=body.created_by,
    )
    session.add(update)

    # Also update the incident's status
    incident.status = body.status
    if body.status == IncidentStatus.resolved and incident.resolved_at is None:
        incident.resolved_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(update)
    return update


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status == IncidentStatus.resolved:
        raise HTTPException(status_code=409, detail="Incident already resolved")

    incident.status = IncidentStatus.resolved
    incident.resolved_at = datetime.now(timezone.utc)

    # Add a resolution update
    update = IncidentUpdateModel(
        incident_id=incident_id,
        message="Incident resolved",
        status=IncidentStatus.resolved,
        created_by="system",
    )
    session.add(update)

    await session.commit()
    await session.refresh(incident)
    return incident
