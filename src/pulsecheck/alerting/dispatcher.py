import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pulsecheck.models.alert import (
    Alert,
    ChannelType,
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


class NotificationDispatcher:
    """Dispatches alert notifications to configured channels."""

    async def dispatch(
        self,
        session: AsyncSession,
        alert: Alert,
        channels: list[NotificationChannel],
    ) -> list[NotificationLog]:
        """Send notifications for an alert to all provided channels.

        Returns list of NotificationLog entries recording delivery status.
        """
        logs: list[NotificationLog] = []
        for channel in channels:
            if not channel.is_active:
                continue
            log = await self._send_to_channel(session, alert, channel)
            logs.append(log)

        if logs:
            await session.flush()

        return logs

    async def _send_to_channel(
        self,
        session: AsyncSession,
        alert: Alert,
        channel: NotificationChannel,
    ) -> NotificationLog:
        status = NotificationStatus.sent
        error_message = None

        try:
            if channel.channel_type == ChannelType.webhook:
                await self._send_webhook(alert, channel)
            elif channel.channel_type == ChannelType.slack:
                await self._send_slack(alert, channel)
            elif channel.channel_type == ChannelType.email:
                self._send_email(alert, channel)
        except Exception as exc:
            status = NotificationStatus.failed
            error_message = str(exc)
            logger.error(
                "Failed to send notification via %s channel %s: %s",
                channel.channel_type.value,
                channel.name,
                exc,
            )

        log = NotificationLog(
            id=uuid.uuid4(),
            alert_id=alert.id,
            channel_id=channel.id,
            status=status,
            error_message=error_message,
            sent_at=datetime.now(timezone.utc),
        )
        session.add(log)
        return log

    async def _send_webhook(self, alert: Alert, channel: NotificationChannel) -> None:
        url = channel.config.get("url")
        if not url:
            raise ValueError("Webhook channel missing 'url' in config")

        payload = {
            "alert_id": str(alert.id),
            "rule_id": str(alert.rule_id),
            "service_id": str(alert.service_id),
            "severity": alert.severity.value,
            "message": alert.message,
            "created_at": alert.created_at.isoformat(),
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        logger.info("Webhook notification sent to %s", url)

    async def _send_slack(self, alert: Alert, channel: NotificationChannel) -> None:
        url = channel.config.get("webhook_url")
        if not url:
            raise ValueError("Slack channel missing 'webhook_url' in config")

        emoji = ":red_circle:" if alert.severity.value == "critical" else ":warning:"
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *PulseCheck Alert*\n"
                        f"*Severity:* {alert.severity.value}\n"
                        f"*Service:* {alert.service_id}\n"
                        f"*Message:* {alert.message}",
                    },
                }
            ]
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        logger.info("Slack notification sent to channel %s", channel.name)

    def _send_email(self, alert: Alert, channel: NotificationChannel) -> None:
        """Stub: logs the email instead of actually sending it."""
        recipient = channel.config.get("email", "unknown")
        logger.info(
            "EMAIL STUB: Would send alert %s to %s — severity=%s message=%s",
            alert.id,
            recipient,
            alert.severity.value,
            alert.message,
        )
