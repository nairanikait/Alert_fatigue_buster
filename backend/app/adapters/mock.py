import logging
from typing import Dict, Any
from app.adapters.base import BaseNotificationAdapter

logger = logging.getLogger("alert_buster.adapters.mock")

class MockNotificationAdapter(BaseNotificationAdapter):
    def __init__(self, channel_name: str = "mock"):
        self.channel_name = channel_name

    def send(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        title = notification_data.get("title", "Alert Notification")
        message = notification_data.get("message", "")
        logger.info(
            f"[MOCK NOTIFICATION DISPATCHED] Channel: {self.channel_name} | "
            f"Title: {title} | Message: {message[:120]}..."
        )
        return {
            "status": "SIMULATED",
            "channel": self.channel_name,
            "message_id": f"mock-{id(notification_data)}",
            "delivered": True,
            "note": f"Delivered to simulated {self.channel_name} receiver"
        }
