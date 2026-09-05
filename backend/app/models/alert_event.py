import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from app.core.database import Base

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id = Column(Integer, index=True, nullable=True)
    simulation_id = Column(String(64), index=True, nullable=True)
    incident_id = Column(String(64), index=True, nullable=True)
    
    # Complete lifecycle event type:
    # RECEIVED, NORMALIZED, DEDUPLICATED, CORRELATED, BATCHED, SUPPRESSED, ROUTED, RESOLVED
    event_type = Column(String(64), index=True, nullable=False)
    
    action = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_alert_events_alert_time", "alert_id", "timestamp"),
        Index("idx_alert_events_sim_time", "simulation_id", "timestamp"),
        Index("idx_alert_events_type_time", "event_type", "timestamp"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "simulation_id": self.simulation_id,
            "incident_id": self.incident_id,
            "event_type": self.event_type,
            "action": self.action,
            "reason": self.reason,
            "details": self.details or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
