import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from app.core.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(String(64), index=True, nullable=True)
    alert_id = Column(Integer, index=True, nullable=True)
    channel = Column(String(64), index=True, nullable=False) # pagerduty, slack, email, mock
    status = Column(String(32), index=True, default="SENT") # SENT, SIMULATED, FAILED
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON, default=dict)
    reason = Column(Text, nullable=True) # e.g. "Triggered by Critical Database Outage"
    failure_reason = Column(Text, nullable=True)
    
    sent_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_notification_incident_sent", "incident_id", "sent_at"),
        Index("idx_notification_channel_status", "channel", "status"),
    )

    def to_dict(self):
        sent_at_iso = None
        if self.sent_at:
            s = self.sent_at.isoformat()
            sent_at_iso = s if (s.endswith("Z") or "+" in s) else s + "Z"

        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "alert_id": self.alert_id,
            "channel": self.channel,
            "status": self.status,
            "title": self.title,
            "message": self.message,
            "payload": self.payload or {},
            "reason": self.reason,
            "failure_reason": self.failure_reason,
            "sent_at": sent_at_iso
        }
