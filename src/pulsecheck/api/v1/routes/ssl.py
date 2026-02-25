import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.service import Service
from pulsecheck.models.ssl_certificate import SSLCertificate
from pulsecheck.schemas.ssl import SSLCertificateResponse

router = APIRouter(prefix="/api/v1/services", tags=["ssl"])


@router.get(
    "/{service_id}/ssl",
    response_model=SSLCertificateResponse,
)
async def get_ssl_certificate(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    # Verify the service exists
    svc = await session.get(Service, service_id)
    if svc is None:
        raise HTTPException(status_code=404, detail="Service not found")

    stmt = select(SSLCertificate).where(SSLCertificate.service_id == service_id)
    result = await session.execute(stmt)
    ssl_cert = result.scalar_one_or_none()

    if ssl_cert is None:
        raise HTTPException(
            status_code=404,
            detail="No SSL certificate data available for this service",
        )

    return ssl_cert
