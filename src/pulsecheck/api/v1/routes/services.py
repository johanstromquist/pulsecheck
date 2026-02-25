import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.service import Service
from pulsecheck.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(prefix="/api/v1/services", tags=["services"])


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    body: ServiceCreate,
    session: AsyncSession = Depends(get_session),
):
    service = Service(
        name=body.name,
        url=body.url,
        check_interval_seconds=body.check_interval_seconds,
    )
    session.add(service)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Service with this name already exists")
    await session.refresh(service)
    return service


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Service)
        .where(Service.is_active.is_(True))
        .order_by(Service.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdate,
    session: AsyncSession = Depends(get_session),
):
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Service with this name already exists")
    await session.refresh(service)
    return service


@router.delete("/{service_id}", status_code=200)
async def delete_service(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    service.is_active = False
    await session.commit()
    return {"detail": "Service deactivated"}
