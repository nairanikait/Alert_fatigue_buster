import datetime
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.adapters.pagerduty import PagerDutyAdapter
from app.adapters.slack import SlackAdapter
from app.adapters.email import EmailAdapter
from app.adapters.mock import MockNotificationAdapter

logger = logging.getLogger("alert_buster.routing")

class NotificationRouter:
    def __init__(self):
        self.pagerduty = PagerDutyAdapter()
        self.slack = SlackAdapter()
        self.email = EmailAdapter()
        self.mock = MockNotificationAdapter()

    def route_and_dispatch(
        self,
        db: Session,
        channel: str,
        title: str,
        message: str,
        incident_id: Optional[str] = None,
        alert_id: Optional[int] = None,
        reason: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Notification:
        channel_lower = (channel or "mock").lower()
        
        # Select appropriate adapter
        if channel_lower == "pagerduty":
            adapter = self.pagerduty
        elif channel_lower == "slack":
            adapter = self.slack
        elif channel_lower == "email":
            adapter = self.email
        else:
            adapter = self.mock

        data = {
            "title": title,
            "message": message,
            "incident_id": incident_id,
            "alert_id": alert_id,
            "channel": channel_lower,
            "payload": payload or {}
        }

        # Dispatch via adapter
        try:
            result = adapter.send(data)
            status = result.get("status", "SENT")
        except Exception as e:
            logger.error(f"Error in adapter {channel_lower}: {e}")
            status = "FAILED"

        # Record notification in database
        notification = Notification(
            incident_id=incident_id,
            alert_id=alert_id,
            channel=channel_lower,
            status=status,
            title=title,
            message=message,
            payload=payload or {},
            reason=reason,
            sent_at=datetime.datetime.utcnow()
        )
        db.add(notification)
        db.flush()

        logger.info(
            f"[ROUTER DISPATCH] Notification #{notification.id} dispatched to {channel_lower.upper()} "
            f"for incident {incident_id}. Status: {status}"
        )
        return notification

router = NotificationRouter()
