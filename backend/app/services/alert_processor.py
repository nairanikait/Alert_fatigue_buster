import datetime
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import load_rules
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.incident import Incident
from app.models.notification import Notification
from app.services.deduplication import check_deduplication
from app.services.flaky import evaluate_flaky_behavior
from app.services.lifecycle import handle_lifecycle_event
from app.services.severity import calculate_severity_score
from app.services.correlation import find_or_create_incident
from app.services.cooldown import check_cooldown
from app.services.batching import batch_buffer
from app.services.routing import router

logger = logging.getLogger("alert_buster.pipeline")

def _make_json_safe(obj: Any) -> Any:
    """Recursively converts non-JSON types (like datetime) to strings."""
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return obj

def _log_event(
    db: Session,
    event_type: str,
    alert_id: Optional[int] = None,
    simulation_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    action: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime.datetime] = None
) -> AlertEvent:
    """Helper to persist lifecycle events and decisions into alert_events table."""
    event = AlertEvent(
        alert_id=alert_id,
        simulation_id=simulation_id,
        incident_id=incident_id,
        event_type=event_type,
        action=action,
        reason=reason,
        details=_make_json_safe(details or {}),
        timestamp=timestamp or datetime.datetime.utcnow()
    )
    db.add(event)
    return event

def _finish_transaction(db: Session, auto_commit: bool):
    if auto_commit:
        db.commit()
    else:
        db.flush()

def process_alert(db: Session, raw_alert: Dict[str, Any], auto_commit: bool = True) -> Dict[str, Any]:
    """
    Main Alert Fatigue Buster Intelligence Pipeline with full PostgreSQL persistence:
      1. RECEIVED event logging
      2. NORMALIZED event logging
      3. Lifecycle verification (Resolve handling -> RESOLVED event)
      4. Deduplication Check (DEDUPLICATED event & occurrence count increment)
      5. Flaky / Flapping Detection
      6. Alert entity creation & persistence
      7. Correlation & Service Topology Linking (CORRELATED event)
      8. Severity 0-100 Calculation & Blast Radius
      9. Downstream suppression (SUPPRESSED event)
      10. Adaptive Cooldown Assessment (SUPPRESSED event)
      11. Batching vs Immediate Dispatch (BATCHED event)
      12. Smart Routing to Destination Channel (ROUTED event)
    """
    rules = load_rules()
    dedup_rules = rules.get("deduplication", {})
    cooldown_rules = rules.get("cooldown", {})
    batch_rules = rules.get("batching", {})
    routing_rules = rules.get("routing", {})
    flaky_rules = rules.get("flaky_detection", {})

    alert_name = raw_alert["alert_name"]
    service = raw_alert["service"]
    host = raw_alert.get("host")
    environment = raw_alert.get("environment", "production")
    raw_severity = raw_alert.get("severity", "medium").lower()
    raw_status = raw_alert.get("status", "FIRING").upper()
    message = raw_alert.get("message", "")
    labels = raw_alert.get("labels", {})
    timestamp = raw_alert.get("timestamp") or datetime.datetime.utcnow()
    fingerprint = raw_alert["fingerprint"]
    simulation_id = raw_alert.get("simulation_id")
    source = raw_alert.get("source", "generic")

    logger.info(f"[PIPELINE INGEST] {alert_name} on {service} ({environment}) | status={raw_status} | sim={simulation_id}")

    # Event 1: Record RECEIVED lifecycle event
    _log_event(
        db=db,
        event_type="RECEIVED",
        simulation_id=simulation_id,
        action="INGEST",
        reason=f"Alert received from source {source}",
        details={
            "source": source,
            "alert_name": alert_name,
            "service": service,
            "status": raw_status,
            "environment": environment
        },
        timestamp=timestamp
    )

    # Event 2: Record NORMALIZED lifecycle event
    _log_event(
        db=db,
        event_type="NORMALIZED",
        simulation_id=simulation_id,
        action="NORMALIZE",
        reason="Alert payload normalized into standard schema",
        details={
            "fingerprint": fingerprint,
            "service": service,
            "severity": raw_severity,
            "host": host
        },
        timestamp=timestamp
    )

    # Step 1: Lifecycle check (Handle RESOLVED events)
    if raw_status == "RESOLVED":
        resolved_alert = handle_lifecycle_event(
            db=db,
            alert_name=alert_name,
            service=service,
            host=host,
            status=raw_status,
            timestamp=timestamp
        )
        if resolved_alert:
            _log_event(
                db=db,
                event_type="RESOLVED",
                alert_id=resolved_alert.id,
                simulation_id=simulation_id or resolved_alert.simulation_id,
                incident_id=resolved_alert.correlation_group_id or resolved_alert.incident_id,
                action="RESOLVED",
                reason="Alert received RESOLVED status; transitioned active alert to RESOLVED.",
                details={"duration_seconds": resolved_alert.duration_seconds},
                timestamp=timestamp
            )
            _finish_transaction(db, auto_commit)
            return {
                "action": "RESOLVED",
                "alert": resolved_alert.to_dict(),
                "duration_seconds": resolved_alert.duration_seconds
            }
        
        # If no active firing alert found, record the standalone resolved event
        alert_obj = Alert(
            simulation_id=simulation_id,
            fingerprint=fingerprint,
            source=source,
            alert_name=alert_name,
            service=service,
            host=host,
            environment=environment,
            severity=raw_severity,
            severity_score=10.0,
            status="RESOLVED",
            message=message,
            raw_payload=_make_json_safe(raw_alert),
            labels=labels,
            timestamp=timestamp,
            first_seen=timestamp,
            last_seen=timestamp,
            resolved_at=timestamp,
            notification_status="SUPPRESSED",
            suppression_reason="Alert arrived with RESOLVED status (no prior firing incident)."
        )
        db.add(alert_obj)
        db.flush()
        _log_event(
            db=db,
            event_type="RESOLVED",
            alert_id=alert_obj.id,
            simulation_id=simulation_id,
            action="RESOLVED_STANDALONE",
            reason="Standalone resolved alert recorded.",
            details={"fingerprint": fingerprint},
            timestamp=timestamp
        )
        _finish_transaction(db, auto_commit)
        return {"action": "RESOLVED_STANDALONE", "alert": alert_obj.to_dict()}

    # Step 2: Deduplication Engine Check
    if dedup_rules.get("enabled", True):
        is_dup, existing_alert, dup_reason = check_deduplication(
            db=db,
            fingerprint=fingerprint,
            timestamp=timestamp,
            window_seconds=dedup_rules.get("window_seconds", 30)
        )
        if is_dup and existing_alert:
            # Update suppression reason and category
            existing_alert.notification_status = "SUPPRESSED"
            existing_alert.suppression_reason = dup_reason
            existing_alert.suppression_category = "duplicate"
            existing_alert.fire_count += 1
            if simulation_id and not existing_alert.simulation_id:
                existing_alert.simulation_id = simulation_id
            
            # Check flaky on duplicate burst
            if existing_alert.fire_count >= flaky_rules.get("threshold", 10):
                existing_alert.is_flaky = True

            # Update incident count if attached
            inc_id = existing_alert.correlation_group_id or existing_alert.incident_id
            if inc_id:
                inc = db.query(Incident).filter(Incident.id == inc_id).first()
                if inc:
                    inc.alert_count += 1
                    inc.suppressed_count += 1
                    inc.updated_at = timestamp

            # Event 3: Record DEDUPLICATED lifecycle event
            _log_event(
                db=db,
                event_type="DEDUPLICATED",
                alert_id=existing_alert.id,
                simulation_id=simulation_id or existing_alert.simulation_id,
                incident_id=inc_id,
                action="SUPPRESSED_DUPLICATE",
                reason=dup_reason,
                details={
                    "occurrence_count": existing_alert.occurrence_count,
                    "fingerprint": fingerprint,
                    "fire_count": existing_alert.fire_count
                },
                timestamp=timestamp
            )

            _finish_transaction(db, auto_commit)
            return {
                "action": "SUPPRESSED_DUPLICATE",
                "alert": existing_alert.to_dict(),
                "reason": dup_reason
            }

    # Step 3: Check Flaky / Flapping behavior for new occurrence
    is_flaky = False
    if flaky_rules.get("enabled", True):
        is_flaky = evaluate_flaky_behavior(
            db=db,
            fingerprint=fingerprint,
            status=raw_status,
            threshold=flaky_rules.get("threshold", 4),
            window_seconds=flaky_rules.get("window_seconds", 120)
        )

    # Step 4: Create new Alert database object
    new_alert = Alert(
        simulation_id=simulation_id,
        fingerprint=fingerprint,
        source=source,
        alert_name=alert_name,
        service=service,
        host=host,
        environment=environment,
        severity=raw_severity,
        status="FIRING",
        message=message,
        raw_payload=_make_json_safe(raw_alert),
        labels=labels,
        timestamp=timestamp,
        first_seen=timestamp,
        last_seen=timestamp,
        occurrence_count=1,
        is_flaky=is_flaky,
        fire_count=1,
        resolve_count=0
    )
    db.add(new_alert)
    db.flush() # Populate new_alert.id

    # Step 5: Correlation Engine & Topological Incident Grouping
    correlation_rules = rules.get("correlation", {})
    incident, is_new_incident, downstream_suppression = find_or_create_incident(
        db=db,
        alert=new_alert,
        window_seconds=correlation_rules.get("window_seconds", 15),
        max_dependency_depth=correlation_rules.get("max_dependency_depth", 5)
    )

    if incident:
        new_alert.incident_id = incident.id
        new_alert.correlation_group_id = incident.id
        # Record CORRELATED lifecycle event
        _log_event(
            db=db,
            event_type="CORRELATED",
            alert_id=new_alert.id,
            simulation_id=simulation_id,
            incident_id=incident.id,
            action="CORRELATED",
            reason=f"Alert linked to incident {incident.id} (root cause: {incident.root_cause_service})",
            details={
                "incident_id": incident.id,
                "root_cause_service": incident.root_cause_service,
                "root_cause_alert_name": incident.root_cause_alert_name,
                "is_new_incident": is_new_incident
            },
            timestamp=timestamp
        )

    # Step 6: Severity Scoring with Blast Radius
    downstream_count = len(incident.affected_services or []) - 1 if incident else 0
    sev_score, final_sev, sev_notes = calculate_severity_score(
        db=db,
        alert_name=alert_name,
        service_name=service,
        raw_severity=raw_severity,
        environment=environment,
        is_flaky=is_flaky,
        affected_downstream_count=max(0, downstream_count)
    )
    new_alert.severity = final_sev
    new_alert.severity_score = sev_score
    new_alert.explainability_notes = sev_notes

    # Update incident severity if needed
    if incident:
        incident.severity_score = max(incident.severity_score, sev_score)
        if final_sev == "CRITICAL":
            incident.severity = "CRITICAL"

    # Step 7: Downstream suppression check
    if downstream_suppression:
        new_alert.notification_status = "SUPPRESSED"
        new_alert.suppression_reason = downstream_suppression
        new_alert.suppression_category = "downstream"
        if incident:
            incident.suppressed_count += 1
        
        _log_event(
            db=db,
            event_type="SUPPRESSED",
            alert_id=new_alert.id,
            simulation_id=simulation_id,
            incident_id=incident.id if incident else None,
            action="SUPPRESSED_DOWNSTREAM",
            reason=downstream_suppression,
            details={"suppression_category": "downstream"},
            timestamp=timestamp
        )

        _finish_transaction(db, auto_commit)
        return {
            "action": "SUPPRESSED_DOWNSTREAM",
            "alert": new_alert.to_dict(),
            "incident": incident.to_dict() if incident else None,
            "reason": downstream_suppression
        }

    # Step 8: Batching Evaluation (group burst non-critical alerts into digests)
    if batch_rules.get("enabled", True) and batch_buffer.should_batch(final_sev, True) and not is_new_incident:
        batch_buffer.add_to_batch({
            "alert_id": new_alert.id,
            "alert_name": alert_name,
            "service": service,
            "severity": final_sev
        })
        new_alert.status = "BATCHED"
        new_alert.notification_status = "BATCHED"
        new_alert.suppression_reason = "Batched into active alert digest window."
        new_alert.suppression_category = "batch"
        if incident:
            incident.suppressed_count += 1

        _log_event(
            db=db,
            event_type="BATCHED",
            alert_id=new_alert.id,
            simulation_id=simulation_id,
            incident_id=incident.id if incident else None,
            action="BATCHED",
            reason="Alert queued in digest batch.",
            details={"suppression_category": "batch"},
            timestamp=timestamp
        )

        _finish_transaction(db, auto_commit)
        return {
            "action": "BATCHED",
            "alert": new_alert.to_dict(),
            "incident": incident.to_dict() if incident else None,
            "reason": "Alert queued in digest batch."
        }

    # Step 9: Adaptive Cooldown Evaluation
    in_cooldown, cooldown_reason = check_cooldown(
        db=db,
        incident_id=incident.id if incident else "GLOBAL",
        severity=final_sev,
        is_flaky=is_flaky,
        cooldown_rules=cooldown_rules
    )

    if in_cooldown:
        new_alert.notification_status = "SUPPRESSED"
        new_alert.suppression_reason = cooldown_reason
        new_alert.suppression_category = "cooldown"
        if incident:
            incident.suppressed_count += 1

        _log_event(
            db=db,
            event_type="SUPPRESSED",
            alert_id=new_alert.id,
            simulation_id=simulation_id,
            incident_id=incident.id if incident else None,
            action="SUPPRESSED_COOLDOWN",
            reason=cooldown_reason,
            details={"suppression_category": "cooldown"},
            timestamp=timestamp
        )

        _finish_transaction(db, auto_commit)
        return {
            "action": "SUPPRESSED_COOLDOWN",
            "alert": new_alert.to_dict(),
            "incident": incident.to_dict() if incident else None,
            "reason": cooldown_reason
        }

    # Step 10: Dispatch Notification via Smart Router
    target_raw = routing_rules.get(final_sev.lower(), "slack")
    if isinstance(target_raw, str):
        target_channels = [c.strip() for c in target_raw.split(",") if c.strip()]
    elif isinstance(target_raw, list):
        target_channels = target_raw
    else:
        target_channels = [str(target_raw)]
    
    # Construct professional notification message
    notif_title = f"🚨 {final_sev} INCIDENT: {alert_name} on {service}"
    inc_service = incident.root_cause_service if incident else service
    inc_alert = incident.root_cause_alert_name if incident else alert_name
    inc_reason = incident.root_cause_reason if incident else "Alert threshold breached"
    inc_count = incident.alert_count if incident else 1
    inc_svcs = ', '.join(incident.affected_services or [service]) if incident else service

    notif_body = (
        f"🚨 {final_sev} INCIDENT\n\n"
        f"• Service: {service}\n"
        f"• Environment: {environment.upper()}\n"
        f"• Alert: {alert_name}\n"
        f"• Severity Score: {sev_score}/100\n"
        f"• Probable Root Cause: {inc_service} ({inc_alert})\n"
        f"• Root Cause Reason: {inc_reason}\n"
        f"• Total Linked Alerts: {inc_count}\n"
        f"• Affected Downstream Services: {inc_svcs}\n\n"
        f"Recommended Action:\nInvestigate {service} infrastructure and connectivity immediately."
    )

    last_notif = None
    for target_channel in target_channels:
        notif = router.route_and_dispatch(
            db=db,
            channel=target_channel,
            title=notif_title,
            message=notif_body,
            incident_id=incident.id if incident else None,
            alert_id=new_alert.id,
            reason=f"Primary alert notification for {final_sev} incident {incident.id if incident else 'SINGLE'}",
            payload={
                "service": service,
                "severity": final_sev,
                "severity_score": sev_score,
                "root_cause": inc_service
            }
        )
        last_notif = notif

    new_alert.notification_status = "SENT"
    if incident:
        incident.notifications_count += 1

    # Event: Record ROUTED lifecycle event
    _log_event(
        db=db,
        event_type="ROUTED",
        alert_id=new_alert.id,
        simulation_id=simulation_id,
        incident_id=incident.id if incident else None,
        action="NOTIFIED",
        reason=f"Dispatched notification to channel {target_channel}",
        details={
            "channel": target_channel,
            "notification_id": notif.id,
            "severity": final_sev,
            "severity_score": sev_score
        },
        timestamp=timestamp
    )

    _finish_transaction(db, auto_commit)

    return {
        "action": "NOTIFIED",
        "alert": new_alert.to_dict(),
        "incident": incident.to_dict() if incident else None,
        "notification": notif.to_dict()
    }
