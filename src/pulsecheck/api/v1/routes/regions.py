import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.health_check import HealthCheck
from pulsecheck.models.region import CheckRegion
from pulsecheck.models.service import Service
from pulsecheck.schemas.region import (
    ByRegionResponse,
    RegionCheckResult,
    RegionCreate,
    RegionResponse,
    RegionUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["regions"])


# --- Region CRUD ---


@router.post("/regions", response_model=RegionResponse, status_code=201)
async def create_region(
    body: RegionCreate,
    session: AsyncSession = Depends(get_session),
):
    region = CheckRegion(
        name=body.name,
        endpoint_url=body.endpoint_url,
        is_active=body.is_active,
    )
    session.add(region)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Region with this name already exists")
    await session.refresh(region)
    return region


@router.get("/regions", response_model=list[RegionResponse])
async def list_regions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(CheckRegion)
        .order_by(CheckRegion.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/regions/{region_id}", response_model=RegionResponse)
async def get_region(
    region_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    region = await session.get(CheckRegion, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return region


@router.patch("/regions/{region_id}", response_model=RegionResponse)
async def update_region(
    region_id: uuid.UUID,
    body: RegionUpdate,
    session: AsyncSession = Depends(get_session),
):
    region = await session.get(CheckRegion, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(region, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Region with this name already exists")
    await session.refresh(region)
    return region


@router.delete("/regions/{region_id}", status_code=200)
async def delete_region(
    region_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    region = await session.get(CheckRegion, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    region.is_active = False
    await session.commit()
    return {"detail": "Region deactivated"}


# --- By-region checks endpoint ---


@router.get(
    "/services/{service_id}/checks/by-region",
    response_model=ByRegionResponse,
)
async def get_checks_by_region(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Returns the latest check results for a service grouped by region."""
    svc = await session.get(Service, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")

    # Get all active regions
    region_stmt = select(CheckRegion).where(CheckRegion.is_active.is_(True))
    region_result = await session.execute(region_stmt)
    regions = list(region_result.scalars().all())

    region_checks: list[RegionCheckResult] = []

    for region in regions:
        # Get the latest health check for this service from this region
        check_stmt = (
            select(HealthCheck)
            .where(HealthCheck.service_id == service_id)
            .where(HealthCheck.region_id == region.id)
            .order_by(HealthCheck.checked_at.desc())
            .limit(1)
        )
        check_result = await session.execute(check_stmt)
        check = check_result.scalar_one_or_none()

        if check is not None:
            region_checks.append(
                RegionCheckResult(
                    region_id=region.id,
                    region_name=region.name,
                    status=check.status.value,
                    response_time_ms=check.response_time_ms,
                    status_code=check.status_code,
                    error_message=check.error_message,
                    checked_at=check.checked_at,
                )
            )

    # Get the latest consensus check (no region_id)
    consensus_stmt = (
        select(HealthCheck)
        .where(HealthCheck.service_id == service_id)
        .where(HealthCheck.region_id.is_(None))
        .order_by(HealthCheck.checked_at.desc())
        .limit(1)
    )
    consensus_result = await session.execute(consensus_stmt)
    consensus_check = consensus_result.scalar_one_or_none()

    return ByRegionResponse(
        service_id=service_id,
        consensus_status=consensus_check.status.value if consensus_check else None,
        regions=region_checks,
    )
