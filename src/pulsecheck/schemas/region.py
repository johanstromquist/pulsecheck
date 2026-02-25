import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RegionCreate(BaseModel):
    name: str
    endpoint_url: str
    is_active: bool = True


class RegionUpdate(BaseModel):
    name: Optional[str] = None
    endpoint_url: Optional[str] = None
    is_active: Optional[bool] = None


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    endpoint_url: str
    is_active: bool
    created_at: datetime


class RegionCheckResult(BaseModel):
    region_id: uuid.UUID
    region_name: str
    status: str
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    checked_at: datetime


class ByRegionResponse(BaseModel):
    service_id: uuid.UUID
    consensus_status: Optional[str] = None
    regions: list[RegionCheckResult]
