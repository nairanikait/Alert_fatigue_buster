import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from app.core.database import Base

class WebhookSource(Base):
    __tablename__ = "webhook_sources"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_name = Column(String(64), unique=True, nullable=False, index=True)
    source_identifier = Column(String(128), unique=True, nullable=False)
    secret = Column(String(255), nullable=False)  # Server-side only, masked on API exposure
    secondary_secret = Column(String(255), nullable=True)  # For zero-downtime rotation
    rotation_expires_at = Column(DateTime, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    rate_limit_per_minute = Column(Integer, default=1000, nullable=False)
    trust_rating = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    def to_safe_dict(self):
        """Export safe dictionary representation masking secrets."""
        masked = f"{self.secret[:4]}...{self.secret[-4:]}" if self.secret and len(self.secret) >= 8 else "****"
        has_secondary = bool(self.secondary_secret)
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_identifier": self.source_identifier,
            "masked_secret": masked,
            "has_secondary_secret": has_secondary,
            "rotation_expires_at": self.rotation_expires_at.isoformat() if self.rotation_expires_at else None,
            "is_enabled": self.is_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "trust_rating": self.trust_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

class WebhookRequest(Base):
    __tablename__ = "webhook_requests"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(64), nullable=False, index=True)
    request_id = Column(String(128), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    status = Column(String(32), default="PROCESSED", nullable=False)  # PROCESSED, REJECTED, REPLAY_DETECTED

    __table_args__ = (
        UniqueConstraint("source", "request_id", name="uq_webhook_source_request_id"),
        Index("ix_webhook_req_source_time", "source", "timestamp"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status,
        }

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(64), nullable=False, index=True)
    # Types: AUTHENTICATION_FAILED, INVALID_SIGNATURE, REPLAY_DETECTED, RATE_LIMIT_EXCEEDED,
    # SCHEMA_VALIDATION_FAILED, UNKNOWN_SOURCE, ANOMALOUS_VOLUME, ALERT_INJECTION_DETECTED,
    # ALERT_QUARANTINED, ALERT_BLOCKED, ALERT_ACCEPTED, SECRET_ROTATED
    source = Column(String(64), nullable=False, index=True)
    request_id = Column(String(128), nullable=True)
    alert_id = Column(Integer, nullable=True)
    severity = Column(String(32), default="INFO", nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    trust_score = Column(Float, default=100.0, nullable=False)
    action = Column(String(32), nullable=False)  # ACCEPTED, QUARANTINED, BLOCKED, THROTTLED
    reason = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source": self.source,
            "request_id": self.request_id,
            "alert_id": self.alert_id,
            "severity": self.severity,
            "trust_score": self.trust_score,
            "action": self.action,
            "reason": self.reason,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class SecurityBaseline(Base):
    __tablename__ = "security_baselines"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(64), nullable=False, index=True)
    service = Column(String(128), nullable=True, index=True)
    normal_rate_per_minute = Column(Float, default=50.0, nullable=False)
    last_window_count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "service": self.service,
            "normal_rate_per_minute": self.normal_rate_per_minute,
            "last_window_count": self.last_window_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
