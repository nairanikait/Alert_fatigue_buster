import logging
import httpx
from typing import Dict, Any
from app.adapters.base import BaseNotificationAdapter
from app.adapters.mock import MockNotificationAdapter
from app.core.config import settings

logger = logging.getLogger("alert_buster.adapters.slack")

class SlackAdapter(BaseNotificationAdapter):
    def __init__(self):
        self.webhook_url = settings.SLACK_WEBHOOK_URL
        self.mock = MockNotificationAdapter(channel_name="slack")

    def send(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.webhook_url:
            logger.info("Slack webhook URL not set. Using MockNotificationAdapter for Slack.")
            return self.mock.send(notification_data)

        try:
            title = notification_data.get("title", "Alert Notification")
            message = notification_data.get("message", "")
            
            # Format rich Slack Block Kit message
            payload = {
                "text": f"*{title}*\n{message}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": title[:150], "emoji": True}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": message}
                    }
                ]
            }
            with httpx.Client(timeout=5.0) as client:
                res = client.post(self.webhook_url, json=payload)
                if res.status_code == 200:
                    return {"status": "SENT", "channel": "slack"}
                else:
                    logger.error(f"Slack webhook failed with code {res.status_code}: {res.text}")
                    return self.mock.send(notification_data)
        except Exception as e:
            logger.error(f"Failed to post to Slack: {e}. Falling back to simulation.")
            return self.mock.send(notification_data)
