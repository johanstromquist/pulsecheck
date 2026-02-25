import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SSLCertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    issuer: str
    subject: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    days_until_expiry: int
    last_checked_at: datetime
    created_at: datetime
    updated_at: datetime
