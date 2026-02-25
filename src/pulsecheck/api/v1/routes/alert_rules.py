import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pulsecheck.db.session import get_session
from pulsecheck.models.alert import AlertRule, NotificationChannel
from pulsecheck.schemas.alert import AlertRuleCreate, AlertRuleResponse, AlertRuleUpdate

router = APIRouter(prefix="/api/v1/alert-rules", tags=["alert-rules"])


def _to_response(rule: AlertRule) -> AlertRuleResponse:
    return AlertRuleResponse(
        id=rule.id,
        service_id=rule.service_id,
        name=rule.name,
        condition_type=rule.condition_type,
        threshold_value=rule.threshold_value,
        is_active=rule.is_active,
        created_at=rule.created_at,
        channel_ids=[ch.id for ch in rule.channels],
    )


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
):
    rule = AlertRule(
        name=body.name,
        service_id=body.service_id,
        condition_type=body.condition_type,
        threshold_value=body.threshold_value,
        is_active=body.is_active,
    )

    if body.channel_ids:
        channels = await _fetch_channels(session, body.channel_ids)
        rule.channels = channels

    session.add(rule)
    await session.commit()
    await session.refresh(rule, attribute_names=["channels"])
    return _to_response(rule)


@router.get("", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(AlertRule)
        .options(selectinload(AlertRule.channels))
        .order_by(AlertRule.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rules = result.scalars().all()
    return [_to_response(r) for r in rules]


@router.get("/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    rule = await _get_rule_or_404(session, rule_id)
    return _to_response(rule)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
):
    rule = await _get_rule_or_404(session, rule_id)

    update_data = body.model_dump(exclude_unset=True)
    channel_ids = update_data.pop("channel_ids", None)

    for field, value in update_data.items():
        setattr(rule, field, value)

    if channel_ids is not None:
        channels = await _fetch_channels(session, channel_ids)
        rule.channels = channels

    await session.commit()
    await session.refresh(rule, attribute_names=["channels"])
    return _to_response(rule)


@router.delete("/{rule_id}", status_code=200)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    rule = await _get_rule_or_404(session, rule_id)
    await session.delete(rule)
    await session.commit()
    return {"detail": "Alert rule deleted"}


async def _get_rule_or_404(session: AsyncSession, rule_id: uuid.UUID) -> AlertRule:
    stmt = (
        select(AlertRule)
        .options(selectinload(AlertRule.channels))
        .where(AlertRule.id == rule_id)
    )
    result = await session.execute(stmt)
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


async def _fetch_channels(
    session: AsyncSession, channel_ids: list[uuid.UUID]
) -> list[NotificationChannel]:
    stmt = select(NotificationChannel).where(NotificationChannel.id.in_(channel_ids))
    result = await session.execute(stmt)
    return list(result.scalars().all())
