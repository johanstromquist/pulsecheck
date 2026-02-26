import uuid
from datetime import datetime, timedelta, timezone

import pytest

from pulsecheck.alerting.evaluator import AlertEvaluator
from pulsecheck.models.alert import Alert, AlertRule, ConditionType, Severity
from pulsecheck.models.health_check import HealthCheck, HealthStatus


@pytest.fixture
def evaluator():
    return AlertEvaluator()


# --- Status change tests ---


@pytest.mark.asyncio
async def test_status_change_fires_on_healthy_to_down(session, sample_service, evaluator):
    """Alert fires when a service transitions from healthy to down."""
    # Create a previous healthy check
    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    session.add(prev_check)

    # Create current "down" check
    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        error_message="Connection refused",
        checked_at=datetime.now(timezone.utc),
    )
    session.add(current_check)

    # Create a status_change rule
    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Status change alert",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 1
    assert alerts[0].severity == Severity.critical
    assert "status changed" in alerts[0].message


@pytest.mark.asyncio
async def test_status_change_does_not_fire_when_still_healthy(session, sample_service, evaluator):
    """No alert when service stays healthy."""
    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    session.add(prev_check)

    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=80,
        checked_at=datetime.now(timezone.utc),
    )
    session.add(current_check)

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Status change alert",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_status_change_does_not_fire_when_already_down(session, sample_service, evaluator):
    """No alert on down->down (no transition)."""
    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    session.add(prev_check)

    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=datetime.now(timezone.utc),
    )
    session.add(current_check)

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Status change alert",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 0


# --- Consecutive failures tests ---


@pytest.mark.asyncio
async def test_consecutive_failures_fires_at_threshold(session, sample_service, evaluator):
    """Consecutive failure rules work correctly with configurable threshold."""
    threshold = 3
    now = datetime.now(timezone.utc)

    # Create 3 consecutive failure checks
    for i in range(threshold):
        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=sample_service.id,
            status=HealthStatus.down,
            response_time_ms=None,
            checked_at=now - timedelta(minutes=threshold - i),
        )
        session.add(check)

    current_check = check  # last one

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="3 consecutive failures",
        condition_type=ConditionType.consecutive_failures,
        threshold_value=threshold,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 1
    assert "consecutive failures" in alerts[0].message


@pytest.mark.asyncio
async def test_consecutive_failures_does_not_fire_below_threshold(session, sample_service, evaluator):
    """No alert when consecutive failures are below threshold."""
    now = datetime.now(timezone.utc)

    # Create 1 healthy + 2 down (not enough for threshold of 3)
    check1 = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=now - timedelta(minutes=3),
    )
    check2 = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=now - timedelta(minutes=2),
    )
    check3 = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=now - timedelta(minutes=1),
    )
    session.add_all([check1, check2, check3])

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="3 consecutive failures",
        condition_type=ConditionType.consecutive_failures,
        threshold_value=3,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, check3)
    assert len(alerts) == 0


# --- Response time threshold tests ---


@pytest.mark.asyncio
async def test_response_time_threshold_fires(session, sample_service, evaluator):
    """Alert when response time exceeds threshold for 3 consecutive checks."""
    now = datetime.now(timezone.utc)

    for i in range(3):
        check = HealthCheck(
            id=uuid.uuid4(),
            service_id=sample_service.id,
            status=HealthStatus.healthy,
            response_time_ms=5000,  # exceeds 1000ms threshold
            checked_at=now - timedelta(minutes=3 - i),
        )
        session.add(check)

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Slow responses",
        condition_type=ConditionType.response_time_threshold,
        threshold_value=1000,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, check)
    assert len(alerts) == 1
    assert "response time exceeded" in alerts[0].message


# --- Deduplication tests ---


@pytest.mark.asyncio
async def test_dedup_suppresses_duplicate_alerts(session, sample_service, evaluator):
    """Duplicate alerts are suppressed within the dedup window."""
    now = datetime.now(timezone.utc)

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Status change alert",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=now,
    )
    session.add(rule)

    # Existing recent alert for same rule+service
    existing_alert = Alert(
        id=uuid.uuid4(),
        rule_id=rule.id,
        service_id=sample_service.id,
        severity=Severity.critical,
        message="Previous alert",
        created_at=now - timedelta(minutes=5),  # within 15 min window
    )
    session.add(existing_alert)

    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=now - timedelta(minutes=2),
    )
    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=now,
    )
    session.add_all([prev_check, current_check])
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 0  # suppressed by dedup


# --- Global rules tests ---


@pytest.mark.asyncio
async def test_global_rule_applies_to_any_service(session, sample_service, evaluator):
    """A rule with service_id=None applies to all services."""
    now = datetime.now(timezone.utc)

    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=now - timedelta(minutes=5),
    )
    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=now,
    )
    session.add_all([prev_check, current_check])

    # Global rule (no service_id)
    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=None,
        name="Global status change",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=True,
        created_at=now,
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 1


# --- Inactive rule tests ---


@pytest.mark.asyncio
async def test_inactive_rule_is_skipped(session, sample_service, evaluator):
    """Inactive rules are not evaluated."""
    now = datetime.now(timezone.utc)

    prev_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.healthy,
        response_time_ms=100,
        checked_at=now - timedelta(minutes=5),
    )
    current_check = HealthCheck(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        status=HealthStatus.down,
        response_time_ms=None,
        checked_at=now,
    )
    session.add_all([prev_check, current_check])

    rule = AlertRule(
        id=uuid.uuid4(),
        service_id=sample_service.id,
        name="Inactive rule",
        condition_type=ConditionType.status_change,
        threshold_value=1,
        is_active=False,
        created_at=now,
    )
    session.add(rule)
    await session.commit()

    alerts = await evaluator.evaluate(session, sample_service.id, current_check)
    assert len(alerts) == 0
