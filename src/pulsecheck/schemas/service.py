import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    name: str
    url: str
    check_interval_seconds: int = 60


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    check_interval_seconds: Optional[int] = None
    is_active: Optional[bool] = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    check_interval_seconds: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
