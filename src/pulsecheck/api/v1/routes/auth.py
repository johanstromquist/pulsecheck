import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.auth import generate_api_key, hash_api_key
from pulsecheck.db.session import get_session
from pulsecheck.models.api_key import ApiKey
from pulsecheck.schemas.auth import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse

router = APIRouter(prefix="/api/v1/auth/keys", tags=["auth"])


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new API key. The plaintext key is returned only once."""
    plaintext_key = generate_api_key()
    key_hash = hash_api_key(plaintext_key)

    api_key = ApiKey(
        name=body.name,
        key_hash=key_hash,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        key=plaintext_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: AsyncSession = Depends(get_session),
):
    """List all API keys (without the plaintext key)."""
    stmt = select(ApiKey).order_by(ApiKey.created_at)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.delete("/{key_id}", status_code=200)
async def revoke_api_key(
    key_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Revoke (deactivate) an API key."""
    api_key = await session.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await session.commit()
    return {"detail": "API key revoked"}
