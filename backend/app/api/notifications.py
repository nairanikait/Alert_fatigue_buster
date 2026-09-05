from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse], summary="List sent and simulated notifications")
def list_notifications(
    channel: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(Notification)
    if channel:
        query = query.filter(Notification.channel == channel.lower())
    notifs = query.order_by(Notification.sent_at.desc()).limit(limit).all()
    return [NotificationResponse.model_validate(n.to_dict()) for n in notifs]

@router.post("/test-email", summary="Send a test email using configured provider (Resend or SMTP)")
def test_email(
    recipient: Optional[str] = None,
    subject: str = "Test Alert Notification",
    message: str = "This is a test notification from Alert Fatigue Buster to verify your Resend email setup."
):
    from app.adapters.email import EmailAdapter
    adapter = EmailAdapter()
    result = adapter.send({
        "recipient": recipient,
        "title": subject,
        "message": message
    })
    return result

@router.post("/test-pagerduty", summary="Send a test alert to PagerDuty Events API v2")
def test_pagerduty(
    title: str = "Test PagerDuty Alert - Alert Fatigue Buster",
    severity: str = "critical",
    service: str = "database-cluster"
):
    from app.adapters.pagerduty import PagerDutyAdapter
    adapter = PagerDutyAdapter()
    result = adapter.send({
        "title": title,
        "severity": severity,
        "service": service,
        "payload": {
            "source": service,
            "test": True,
            "environment": "production"
        }
    })
    return result
