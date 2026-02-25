import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulsecheck.db.base import Base


class HealthStatus(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    down = "down"


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("check_regions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus, name="health_status"), nullable=False
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    service: Mapped["Service"] = relationship(back_populates="health_checks")  # noqa: F821
    region: Mapped["CheckRegion | None"] = relationship(back_populates="health_checks")  # noqa: F821
