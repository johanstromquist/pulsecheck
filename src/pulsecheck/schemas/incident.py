import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from pulsecheck.models.incident import IncidentSeverity, IncidentStatus


class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity
    affected_service_ids: list[uuid.UUID] = []
    created_by: str = "system"


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    affected_service_ids: Optional[list[uuid.UUID]] = None


class IncidentUpdateCreate(BaseModel):
    message: str
    status: IncidentStatus
    created_by: str = "system"


class IncidentUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    message: str
    status: IncidentStatus
    created_by: str
    created_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    severity: IncidentSeverity
    status: IncidentStatus
    affected_service_ids: list
    started_at: datetime
    resolved_at: Optional[datetime]
    created_by: str
    created_at: datetime
    updated_at: datetime


class IncidentDetailResponse(IncidentResponse):
    updates: list[IncidentUpdateResponse] = []
