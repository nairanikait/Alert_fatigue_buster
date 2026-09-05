import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, Index
from app.core.database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(64), primary_key=True, index=True) # e.g. INC-20260904-ABCD
    title = Column(String(255), nullable=False)
    
    root_cause_alert_id = Column(Integer, nullable=True)
    root_cause_service = Column(String(128), index=True, nullable=False)
    root_cause_alert_name = Column(String(128), nullable=False)
    root_cause_reason = Column(Text, nullable=False)
    confidence_score = Column(Float, default=90.0) # e.g. 94.0%
    
    severity = Column(String(32), index=True, default="CRITICAL")
    severity_score = Column(Float, default=85.0)
    
    status = Column(String(32), index=True, default="FIRING") # FIRING, RESOLVED
    
    affected_services = Column(JSON, default=list)
    alert_count = Column(Integer, default=0)
    suppressed_count = Column(Integer, default=0)
    notifications_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    
    evidence = Column(JSON, default=list)

    __table_args__ = (
        Index("idx_incident_status_created", "status", "created_at"),
        Index("idx_incident_root_service_status", "root_cause_service", "status"),
    )

    @property
    def cost_burn_rate(self) -> float:
        sev = (self.severity or "HIGH").upper()
        if sev == "CRITICAL":
            rate_per_min = 3900.0
        elif sev == "HIGH":
            rate_per_min = 1920.0
        elif sev == "MEDIUM":
            rate_per_min = 840.0
        else:
            rate_per_min = 300.0

        svc_count = len(self.affected_services or [])
        blast_multiplier = 1.0 + (max(0, svc_count - 1) * 0.18)
        return round(rate_per_min * blast_multiplier, 2)

    @property
    def estimated_cost_loss(self) -> float:
        if self.duration_seconds and self.duration_seconds > 0:
            duration = self.duration_seconds
        elif self.created_at:
            duration = max(10.0, (datetime.datetime.utcnow() - self.created_at).total_seconds())
        else:
            duration = 30.0

        sev = (self.severity or "HIGH").upper()
        if sev == "CRITICAL":
            rate_per_sec = 65.0
            base_triage = 500.0
        elif sev == "HIGH":
            rate_per_sec = 32.0
            base_triage = 300.0
        elif sev == "MEDIUM":
            rate_per_sec = 14.0
            base_triage = 150.0
        else:
            rate_per_sec = 5.0
            base_triage = 50.0

        svc_count = len(self.affected_services or [])
        blast_multiplier = 1.0 + (max(0, svc_count - 1) * 0.18)
        total = base_triage + (duration * rate_per_sec * blast_multiplier)
        return round(total, 2)

    def to_dict(self):
        def _to_utc_iso(dt):
            if not dt:
                return None
            s = dt.isoformat()
            return s if (s.endswith("Z") or "+" in s) else s + "Z"

        return {
            "id": self.id,
            "title": self.title,
            "root_cause_alert_id": self.root_cause_alert_id,
            "root_cause_service": self.root_cause_service,
            "root_cause_alert_name": self.root_cause_alert_name,
            "root_cause_reason": self.root_cause_reason,
            "confidence_score": self.confidence_score,
            "severity": self.severity,
            "severity_score": self.severity_score,
            "status": self.status,
            "affected_services": self.affected_services or [],
            "alert_count": self.alert_count,
            "suppressed_count": self.suppressed_count,
            "notifications_count": self.notifications_count,
            "created_at": _to_utc_iso(self.created_at),
            "updated_at": _to_utc_iso(self.updated_at),
            "resolved_at": _to_utc_iso(self.resolved_at),
            "duration_seconds": self.duration_seconds,
            "evidence": self.evidence or [],
            "estimated_cost_loss": self.estimated_cost_loss,
            "cost_burn_rate_per_minute": self.cost_burn_rate
        }
