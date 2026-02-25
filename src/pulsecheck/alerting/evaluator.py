import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pulsecheck.models.alert import (
    Alert,
    AlertRule,
    ConditionType,
    Severity,
)
from pulsecheck.models.health_check import HealthCheck, HealthStatus

logger = logging.getLogger(__name__)

DEDUP_WINDOW_MINUTES = 15


class AlertEvaluator:
    """Evaluates alert rules against health check results."""

    async def evaluate(
        self,
        session: AsyncSession,
        service_id: uuid.UUID,
        health_check: HealthCheck,
    ) -> list[Alert]:
        """Evaluate all active rules for a service after a health check.

        Returns list of newly created alerts.
        """
        # Fetch active rules: global (service_id IS NULL) or specific to this service
        stmt = (
            select(AlertRule)
            .options(selectinload(AlertRule.channels))
            .where(
                AlertRule.is_active.is_(True),
                AlertRule.service_id.is_(None) | (AlertRule.service_id == service_id),
            )
        )
        result = await session.execute(stmt)
        rules = result.scalars().all()

        new_alerts: list[Alert] = []
        for rule in rules:
            should_fire = await self._evaluate_rule(session, rule, service_id, health_check)
            if not should_fire:
                continue

            # Deduplication: skip if a recent alert exists for the same rule+service
            if await self._is_duplicate(session, rule.id, service_id):
                logger.debug(
                    "Skipping duplicate alert for rule=%s service=%s",
                    rule.name,
                    service_id,
                )
                continue

            severity = self._determine_severity(rule, health_check)
            message = self._build_message(rule, service_id, health_check)

            alert = Alert(
                id=uuid.uuid4(),
                rule_id=rule.id,
                service_id=service_id,
                severity=severity,
                message=message,
                created_at=datetime.now(timezone.utc),
            )
            session.add(alert)
            new_alerts.append(alert)
            logger.info("Alert created: rule=%s service=%s severity=%s", rule.name, service_id, severity.value)

        if new_alerts:
            await session.flush()

        return new_alerts

    async def _evaluate_rule(
        self,
        session: AsyncSession,
        rule: AlertRule,
        service_id: uuid.UUID,
        health_check: HealthCheck,
    ) -> bool:
        if rule.condition_type == ConditionType.status_change:
            return await self._check_status_change(session, service_id, health_check)
        elif rule.condition_type == ConditionType.consecutive_failures:
            return await self._check_consecutive_failures(
                session, service_id, rule.threshold_value
            )
        elif rule.condition_type == ConditionType.response_time_threshold:
            return await self._check_response_time_threshold(
                session, service_id, rule.threshold_value
            )
        return False

    async def _check_status_change(
        self,
        session: AsyncSession,
        service_id: uuid.UUID,
        current_check: HealthCheck,
    ) -> bool:
        """Fire when status transitions from healthy to non-healthy."""
        if current_check.status == HealthStatus.healthy:
            return False

        # Get the previous check (before this one)
        stmt = (
            select(HealthCheck)
            .where(
                HealthCheck.service_id == service_id,
                HealthCheck.id != current_check.id,
            )
            .order_by(HealthCheck.checked_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        previous = result.scalar_one_or_none()

        if previous is None:
            # First check ever and it's not healthy — fire
            return True

        # Fire only on transition from healthy to non-healthy
        return previous.status == HealthStatus.healthy

    async def _check_consecutive_failures(
        self,
        session: AsyncSession,
        service_id: uuid.UUID,
        threshold: int,
    ) -> bool:
        """Fire when N consecutive checks have status != healthy."""
        stmt = (
            select(HealthCheck)
            .where(HealthCheck.service_id == service_id)
            .order_by(HealthCheck.checked_at.desc())
            .limit(threshold)
        )
        result = await session.execute(stmt)
        checks = result.scalars().all()

        if len(checks) < threshold:
            return False

        return all(c.status != HealthStatus.healthy for c in checks)

    async def _check_response_time_threshold(
        self,
        session: AsyncSession,
        service_id: uuid.UUID,
        threshold_ms: int,
    ) -> bool:
        """Fire when response_time_ms exceeds threshold for 3 consecutive checks."""
        stmt = (
            select(HealthCheck)
            .where(HealthCheck.service_id == service_id)
            .order_by(HealthCheck.checked_at.desc())
            .limit(3)
        )
        result = await session.execute(stmt)
        checks = result.scalars().all()

        if len(checks) < 3:
            return False

        return all(
            c.response_time_ms is not None and c.response_time_ms > threshold_ms
            for c in checks
        )

    async def _is_duplicate(
        self,
        session: AsyncSession,
        rule_id: uuid.UUID,
        service_id: uuid.UUID,
    ) -> bool:
        """Check if an alert was already created for this rule+service within the dedup window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        stmt = (
            select(Alert.id)
            .where(
                and_(
                    Alert.rule_id == rule_id,
                    Alert.service_id == service_id,
                    Alert.created_at >= cutoff,
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _determine_severity(self, rule: AlertRule, health_check: HealthCheck) -> Severity:
        if health_check.status == HealthStatus.down:
            return Severity.critical
        return Severity.warning

    def _build_message(
        self, rule: AlertRule, service_id: uuid.UUID, health_check: HealthCheck
    ) -> str:
        if rule.condition_type == ConditionType.status_change:
            return (
                f"Service {service_id} status changed to {health_check.status.value}"
            )
        elif rule.condition_type == ConditionType.consecutive_failures:
            return (
                f"Service {service_id} has {rule.threshold_value} consecutive failures"
            )
        elif rule.condition_type == ConditionType.response_time_threshold:
            return (
                f"Service {service_id} response time exceeded {rule.threshold_value}ms "
                f"for 3 consecutive checks"
            )
        return f"Alert triggered for service {service_id}"
