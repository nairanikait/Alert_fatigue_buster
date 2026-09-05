import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.incident import Incident

logger = logging.getLogger("alert_buster.lifecycle")

def handle_lifecycle_event(
    db: Session,
    alert_name: str,
    service: str,
    host: Optional[str],
    status: str,
    timestamp: Optional[datetime.datetime] = None
) -> Optional[Alert]:
    """
    Handles transition of alert lifecycle.
    If status is 'RESOLVED', finds active firing alert for this service and marks resolved,
    calculating incident duration.
    """
    if not status:
        return None

    # Support all standard resolution statuses across Prometheus, Datadog, and generic webhooks
    resolved_statuses = {"RESOLVED", "RESOLVE", "OK", "CLEAR", "SUCCESS", "NORMAL"}
    if status.strip().upper() not in resolved_statuses:
        return None

    # Sanitize timestamp: ensure timezone-naive UTC to avoid Python timezone mismatch TypeErrors
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()
    elif isinstance(timestamp, str):
        try:
            timestamp = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception:
            timestamp = datetime.datetime.utcnow()
    
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)

    # Search for active firing, ongoing, or batched alert
    query = (
        db.query(Alert)
        .filter(
            Alert.alert_name == alert_name,
            Alert.service == service,
            Alert.status.in_(["FIRING", "ONGOING", "BATCHED"])
        )
    )

    # Prefer matching host if provided
    active_alert = None
    if host:
        active_alert = query.filter(Alert.host == host).order_by(Alert.last_seen.desc()).first()
    
    if not active_alert:
        active_alert = query.order_by(Alert.last_seen.desc()).first()

    if active_alert:
        active_alert.status = "RESOLVED"
        active_alert.resolved_at = timestamp
        active_alert.resolve_count += 1
        
        if active_alert.first_seen:
            first_seen = active_alert.first_seen
            if first_seen.tzinfo is not None:
                first_seen = first_seen.replace(tzinfo=None)
            duration = (timestamp - first_seen).total_seconds()
            active_alert.duration_seconds = max(1.0, duration)
        
        db.flush()

        logger.info(
            f"Alert {alert_name} on {service} marked RESOLVED. "
            f"Duration: {active_alert.duration_seconds:.1f}s"
        )

        # Check if all alerts in correlation group are resolved
        if active_alert.correlation_group_id:
            incident = db.query(Incident).filter(Incident.id == active_alert.correlation_group_id).first()
            if incident:
                ongoing_in_group = (
                    db.query(Alert)
                    .filter(
                        Alert.correlation_group_id == incident.id,
                        Alert.status.in_(["FIRING", "ONGOING", "BATCHED"])
                    )
                    .count()
                )
                if ongoing_in_group == 0:
                    incident.status = "RESOLVED"
                    incident.resolved_at = timestamp
                    if incident.created_at:
                        created_at = incident.created_at
                        if created_at.tzinfo is not None:
                            created_at = created_at.replace(tzinfo=None)
                        incident.duration_seconds = max(1.0, (timestamp - created_at).total_seconds())
                    logger.info(f"Incident {incident.id} marked RESOLVED. Duration: {incident.duration_seconds:.1f}s")
                    db.flush()

        return active_alert

    return None
