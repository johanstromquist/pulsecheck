import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Table,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulsecheck.db.base import Base


class ConditionType(str, enum.Enum):
    status_change = "status_change"
    consecutive_failures = "consecutive_failures"
    response_time_threshold = "response_time_threshold"
    ssl_expiry = "ssl_expiry"


class ChannelType(str, enum.Enum):
    webhook = "webhook"
    email = "email"
    slack = "slack"


class Severity(str, enum.Enum):
    warning = "warning"
    critical = "critical"


class NotificationStatus(str, enum.Enum):
    sent = "sent"
    failed = "failed"


# Join table for AlertRule <-> NotificationChannel (many-to-many)
alert_rule_channels = Table(
    "alert_rule_channels",
    Base.metadata,
    Column("rule_id", ForeignKey("alert_rules.id", ondelete="CASCADE"), primary_key=True),
    Column("channel_id", ForeignKey("notification_channels.id", ondelete="CASCADE"), primary_key=True),
)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_type: Mapped[ConditionType] = mapped_column(
        Enum(ConditionType, name="condition_type"), nullable=False
    )
    threshold_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    service: Mapped["Service"] = relationship()  # noqa: F821
    channels: Mapped[list["NotificationChannel"]] = relationship(
        secondary=alert_rule_channels, back_populates="rules"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="rule")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"), nullable=False
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    rules: Mapped[list["AlertRule"]] = relationship(
        secondary=alert_rule_channels, back_populates="channels"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="alert_severity"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    rule: Mapped["AlertRule"] = relationship(back_populates="alerts")
    service: Mapped["Service"] = relationship()  # noqa: F821
    notification_logs: Mapped[list["NotificationLog"]] = relationship(back_populates="alert")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    alert: Mapped["Alert"] = relationship(back_populates="notification_logs")
    channel: Mapped["NotificationChannel"] = relationship()
