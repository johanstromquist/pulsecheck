import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulsecheck.db.base import Base


class CheckRegion(Base):
    __tablename__ = "check_regions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    health_checks: Mapped[list["HealthCheck"]] = relationship(  # noqa: F821
        back_populates="region"
    )
