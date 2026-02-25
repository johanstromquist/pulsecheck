import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from pulsecheck.alerting.dispatcher import NotificationDispatcher
from pulsecheck.models.alert import (
    Alert,
    AlertRule,
    ConditionType,
    ChannelType,
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    Severity,
)


@pytest.fixture
def dispatcher():
    return NotificationDispatcher()


@pytest.fixture
def sample_alert():
    return Alert(
        id=uuid.uuid4(),
        rule_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        severity=Severity.critical,
        message="Service is down",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def webhook_channel():
    return NotificationChannel(
        id=uuid.uuid4(),
        name="test-webhook",
        channel_type=ChannelType.webhook,
        config={"url": "https://hooks.example.com/test"},
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def slack_channel():
    return NotificationChannel(
        id=uuid.uuid4(),
        name="test-slack",
        channel_type=ChannelType.slack,
        config={"webhook_url": "https://hooks.slack.com/test"},
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def email_channel():
    return NotificationChannel(
        id=uuid.uuid4(),
        name="test-email",
        channel_type=ChannelType.email,
        config={"email": "admin@example.com"},
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_webhook_dispatch_sends_correct_payload(
    session, dispatcher, sample_alert, webhook_channel
):
    """Webhook notifications are dispatched with correct payload."""
    with patch("pulsecheck.alerting.dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        logs = await dispatcher.dispatch(session, sample_alert, [webhook_channel])

        assert len(logs) == 1
        assert logs[0].status == NotificationStatus.sent

        # Verify the POST call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.example.com/test"
        payload = call_args[1]["json"]
        assert payload["alert_id"] == str(sample_alert.id)
        assert payload["severity"] == "critical"
        assert payload["message"] == "Service is down"
        assert payload["service_id"] == str(sample_alert.service_id)


@pytest.mark.asyncio
async def test_slack_dispatch(session, dispatcher, sample_alert, slack_channel):
    """Slack notifications are dispatched."""
    with patch("pulsecheck.alerting.dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        logs = await dispatcher.dispatch(session, sample_alert, [slack_channel])

        assert len(logs) == 1
        assert logs[0].status == NotificationStatus.sent
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_email_dispatch_stub(session, dispatcher, sample_alert, email_channel):
    """Email dispatch is a stub that succeeds (logs instead of sending)."""
    logs = await dispatcher.dispatch(session, sample_alert, [email_channel])
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.sent


@pytest.mark.asyncio
async def test_dispatch_records_failure(session, dispatcher, sample_alert, webhook_channel):
    """Failed dispatch records error in notification log."""
    with patch("pulsecheck.alerting.dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        logs = await dispatcher.dispatch(session, sample_alert, [webhook_channel])

        assert len(logs) == 1
        assert logs[0].status == NotificationStatus.failed
        assert "Connection refused" in logs[0].error_message


@pytest.mark.asyncio
async def test_inactive_channel_skipped(session, dispatcher, sample_alert, webhook_channel):
    """Inactive channels are not dispatched to."""
    webhook_channel.is_active = False
    logs = await dispatcher.dispatch(session, sample_alert, [webhook_channel])
    assert len(logs) == 0
