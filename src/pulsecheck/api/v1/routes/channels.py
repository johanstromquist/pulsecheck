import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.db.session import get_session
from pulsecheck.models.alert import NotificationChannel
from pulsecheck.schemas.alert import ChannelCreate, ChannelResponse, ChannelUpdate

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


@router.post("", response_model=ChannelResponse, status_code=201)
async def create_channel(
    body: ChannelCreate,
    session: AsyncSession = Depends(get_session),
):
    channel = NotificationChannel(
        name=body.name,
        channel_type=body.channel_type,
        config=body.config,
        is_active=body.is_active,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(NotificationChannel)
        .order_by(NotificationChannel.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    channel = await session.get(NotificationChannel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    body: ChannelUpdate,
    session: AsyncSession = Depends(get_session),
):
    channel = await session.get(NotificationChannel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)

    await session.commit()
    await session.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=200)
async def delete_channel(
    channel_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    channel = await session.get(NotificationChannel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    await session.delete(channel)
    await session.commit()
    return {"detail": "Channel deleted"}
