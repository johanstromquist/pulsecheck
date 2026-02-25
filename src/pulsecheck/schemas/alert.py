import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from pulsecheck.models.alert import ConditionType, ChannelType, Severity, NotificationStatus


# --- AlertRule schemas ---


class AlertRuleCreate(BaseModel):
    service_id: Optional[uuid.UUID] = None
    name: str
    condition_type: ConditionType
    threshold_value: int = 1
    is_active: bool = True
    channel_ids: list[uuid.UUID] = []


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition_type: Optional[ConditionType] = None
    threshold_value: Optional[int] = None
    is_active: Optional[bool] = None
    channel_ids: Optional[list[uuid.UUID]] = None


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: Optional[uuid.UUID]
    name: str
    condition_type: ConditionType
    threshold_value: int
    is_active: bool
    created_at: datetime
    channel_ids: list[uuid.UUID] = []


# --- NotificationChannel schemas ---


class ChannelCreate(BaseModel):
    name: str
    channel_type: ChannelType
    config: dict
    is_active: bool = True


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    channel_type: Optional[ChannelType] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    channel_type: ChannelType
    config: dict
    is_active: bool
    created_at: datetime


# --- Alert schemas ---


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    service_id: uuid.UUID
    severity: Severity
    message: str
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    created_at: datetime


# --- NotificationLog schemas ---


class NotificationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_id: uuid.UUID
    channel_id: uuid.UUID
    status: NotificationStatus
    error_message: Optional[str]
    sent_at: datetime
