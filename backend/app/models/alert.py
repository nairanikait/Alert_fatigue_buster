import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Index
from app.core.database import Base

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    simulation_id = Column(String(64), index=True, nullable=True)
    incident_id = Column(String(64), index=True, nullable=True)
    
    fingerprint = Column(String(64), index=True, nullable=False)
    source = Column(String(64), default="generic")
    alert_name = Column(String(128), nullable=False)
    service = Column(String(128), index=True, nullable=False)
    host = Column(String(128), nullable=True)
    environment = Column(String(64), default="production")
    
    severity = Column(String(32), index=True, default="medium")
    severity_score = Column(Float, default=50.0)
    
    # Lifecycle status: FIRING, ONGOING, RESOLVED, SUPPRESSED, BATCHED
    status = Column(String(32), index=True, default="FIRING")
    
    message = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    root_cause = Column(String(255), nullable=True)
    dedup_key = Column(String(128), index=True, nullable=True)
    raw_payload = Column(JSON, default=dict)
    labels = Column(JSON, default=dict)
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    
    occurrence_count = Column(Integer, default=1)
    
    # Correlation & Root Cause
    root_cause_id = Column(Integer, nullable=True)
    correlation_group_id = Column(String(64), index=True, nullable=True)
    
    # Notification & Suppression Tracking
    notification_status = Column(String(32), default="PENDING") # SENT, SUPPRESSED, BATCHED, PENDING
    suppression_reason = Column(Text, nullable=True)
    suppression_category = Column(String(64), nullable=True) # duplicate, batch, cooldown, downstream, flaky
    
    # Flaky Alert Tracking
    is_flaky = Column(Boolean, default=False)
    fire_count = Column(Integer, default=1)
    resolve_count = Column(Integer, default=0)
    
    # Additional Context & Explainability
    explainability_notes = Column(JSON, default=list)

    # Security Layer: Alert Integrity Shield
    security_status = Column(String(32), index=True, default="ACCEPTED") # ACCEPTED, SUSPICIOUS, QUARANTINED, BLOCKED
    trust_score = Column(Float, default=100.0)
    quarantine_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_alert_fingerprint_status", "fingerprint", "status"),
        Index("idx_alert_service_time", "service", "timestamp"),
        Index("idx_alert_sim_id", "simulation_id"),
        Index("idx_alert_inc_id", "incident_id"),
        Index("idx_alert_status_time", "status", "timestamp"),
        Index("idx_alert_security_status", "security_status"),
    )

    def to_dict(self):
        def _to_utc_iso(dt):
            if not dt:
                return None
            s = dt.isoformat()
            return s if (s.endswith("Z") or "+" in s) else s + "Z"

        return {
            "id": self.id,
            "title": self.title or self.alert_name,
            "description": self.description or self.message,
            "root_cause": self.root_cause,
            "dedup_key": self.dedup_key or self.fingerprint,
            "created_at": _to_utc_iso(self.timestamp or self.first_seen),
            "simulation_id": self.simulation_id,
            "incident_id": self.incident_id or self.correlation_group_id,
            "fingerprint": self.fingerprint,
            "source": self.source,
            "alert_name": self.alert_name or self.title,
            "service": self.service,
            "host": self.host,
            "environment": self.environment,
            "severity": self.severity,
            "severity_score": self.severity_score,
            "status": self.status,
            "message": self.message or self.description,
            "raw_payload": self.raw_payload or {},
            "labels": self.labels or {},
            "timestamp": _to_utc_iso(self.timestamp),
            "first_seen": _to_utc_iso(self.first_seen),
            "last_seen": _to_utc_iso(self.last_seen),
            "resolved_at": _to_utc_iso(self.resolved_at),
            "duration_seconds": self.duration_seconds,
            "occurrence_count": self.occurrence_count,
            "root_cause_id": self.root_cause_id,
            "correlation_group_id": self.correlation_group_id or self.incident_id,
            "notification_status": self.notification_status,
            "suppression_reason": self.suppression_reason,
            "suppression_category": self.suppression_category,
            "is_flaky": self.is_flaky,
            "fire_count": self.fire_count,
            "resolve_count": self.resolve_count,
            "explainability_notes": self.explainability_notes or [],
            "security_status": self.security_status or "ACCEPTED",
            "trust_score": self.trust_score if self.trust_score is not None else 100.0,
            "quarantine_reason": self.quarantine_reason
        }
