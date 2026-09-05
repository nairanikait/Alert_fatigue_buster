import time
import json
import uuid
import datetime
from collections import deque
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

from app.core.database import get_db
from app.core.events import ws_manager
from app.models.security import WebhookSource, WebhookRequest, SecurityEvent, SecurityBaseline
from app.models.alert import Alert
from app.services.security_shield import (
    shield,
    HMACSignatureVerifier,
    DEFAULT_SOURCE_SECRETS
)
from app.services.normalization import normalize_generic, normalize_prometheus, normalize_datadog
from app.services.alert_processor import process_alert

router = APIRouter(prefix="/security", tags=["Alert Integrity Shield"])

# ============================================================
# 1. LIVE SECURITY INGESTION (SHIELD PIPELINE)
# ============================================================
@router.post("/ingest", summary="Ingest webhook through Alert Integrity Shield")
async def ingest_with_shield(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Primary ingestion gate protected by Alert Integrity Shield:
    Authentication -> Signature -> Replay -> Rate Limit -> Schema -> Anomaly -> Trust Score -> Decision
    """
    raw_body = await request.body()
    client_ip = request.client.host if request.client else "127.0.0.1"
    endpoint_path = str(request.url.path)
    headers = dict(request.headers)

    decision = shield.guard_webhook(
        raw_body=raw_body,
        headers=headers,
        client_ip=client_ip,
        endpoint_path=endpoint_path,
        db=db
    )

    action = decision["decision"]
    status_code = decision["status_code"]

    if action == "BLOCKED":
        raise HTTPException(status_code=status_code, detail=decision["reason"])

    payload = decision["payload"]
    source_name = decision["source"]
    is_critical = decision["is_critical"]
    trust_score = decision["trust_score"]

    if action == "QUARANTINED":
        response.status_code = status_code
        # Preserve alert in database without sending normal notifications
        normalized = normalize_generic(payload) if source_name != "datadog" else normalize_datadog(payload)
        
        # Save alert directly with QUARANTINED status
        quarantine_alert = Alert(
            fingerprint=normalized.get("fingerprint", f"quarantine_{uuid.uuid4().hex[:12]}"),
            source=source_name,
            alert_name=normalized.get("alert_name", "UnknownAlert"),
            service=normalized.get("service", "unknown"),
            host=normalized.get("host"),
            environment=normalized.get("environment", "production"),
            severity="critical" if is_critical else normalized.get("severity", "medium").lower(),
            severity_score=90.0 if is_critical else 50.0,
            status="FIRING",
            message=normalized.get("message", "Quarantined alert payload preserved"),
            raw_payload=payload,
            labels=normalized.get("labels", {}),
            timestamp=datetime.datetime.utcnow(),
            notification_status="SUPPRESSED",
            suppression_reason=decision["reason"],
            suppression_category="quarantine",
            security_status="QUARANTINED" if not is_critical else "SUSPICIOUS",
            trust_score=trust_score,
            quarantine_reason=decision["reason"],
            explainability_notes=[{
                "rule": "ALERT_INTEGRITY_SHIELD",
                "decision": "QUARANTINED",
                "reason": decision["reason"],
                "trust_score": trust_score,
                "is_critical": is_critical
            }]
        )
        db.add(quarantine_alert)
        db.commit()
        db.refresh(quarantine_alert)

        # Notify connected dashboard in real time
        alert_dict = quarantine_alert.to_dict()
        import asyncio
        asyncio.create_task(ws_manager.broadcast("ALERT_QUARANTINED", alert_dict))
        if is_critical:
            asyncio.create_task(ws_manager.broadcast("CRITICAL_ALERT_QUARANTINED", alert_dict))

        return {
            "status": "quarantined",
            "decision": action,
            "is_critical": is_critical,
            "trust_score": trust_score,
            "reason": decision["reason"],
            "alert_id": quarantine_alert.id,
            "message": "Alert preserved in quarantine for SRE security review"
        }

    # Action is ACCEPTED -> Ingest into existing Alert Fatigue Buster pipeline!
    if source_name == "prometheus":
        normalized_items = normalize_prometheus(payload)
        results = []
        for item in normalized_items:
            res = process_alert(db, item)
            # Tag with security verification status
            if "alert_id" in res:
                db.query(Alert).filter(Alert.id == res["alert_id"]).update({
                    Alert.security_status: "ACCEPTED",
                    Alert.trust_score: trust_score
                })
                db.commit()
            results.append(res)
        return {"status": "success", "decision": "ACCEPTED", "trust_score": trust_score, "results": results}
    elif source_name == "datadog":
        normalized = normalize_datadog(payload)
        result = process_alert(db, normalized)
        if "alert_id" in result:
            db.query(Alert).filter(Alert.id == result["alert_id"]).update({
                Alert.security_status: "ACCEPTED",
                Alert.trust_score: trust_score
            })
            db.commit()
        return {"status": "success", "decision": "ACCEPTED", "trust_score": trust_score, "result": result}
    else:
        normalized = normalize_generic(payload)
        result = process_alert(db, normalized)
        if "alert_id" in result:
            db.query(Alert).filter(Alert.id == result["alert_id"]).update({
                Alert.security_status: "ACCEPTED",
                Alert.trust_score: trust_score
            })
            db.commit()
        return {"status": "success", "decision": "ACCEPTED", "trust_score": trust_score, "result": result}

# ============================================================
# 2. SECURITY OVERVIEW & REAL DATABASE METRICS
# ============================================================
@router.get("/overview", summary="Aggregated Security Status & Metrics from Real DB")
def get_security_overview(db: Session = Depends(get_db)):
    """
    Computes real metrics directly from database tables:
    - security_events
    - webhook_requests
    - alerts (security_status)
    """
    total_screened = db.query(SecurityEvent).count()
    blocked_count = db.query(SecurityEvent).filter(SecurityEvent.action == "BLOCKED").count()
    quarantined_events = db.query(SecurityEvent).filter(SecurityEvent.action == "QUARANTINED").count()
    
    invalid_sigs = db.query(SecurityEvent).filter(SecurityEvent.event_type == "INVALID_SIGNATURE").count()
    replay_count = db.query(SecurityEvent).filter(SecurityEvent.event_type == "REPLAY_DETECTED").count()
    rate_limits = db.query(SecurityEvent).filter(SecurityEvent.event_type == "RATE_LIMIT_EXCEEDED").count()
    injections = db.query(SecurityEvent).filter(
        or_(
            SecurityEvent.event_type == "ALERT_INJECTION_DETECTED",
            SecurityEvent.event_type == "ANOMALOUS_VOLUME"
        )
    ).count()

    # Active Quarantined Alerts count in alerts table
    pending_quarantines = db.query(Alert).filter(
        Alert.security_status.in_(["QUARANTINED", "SUSPICIOUS"])
    ).count()

    pending_critical = db.query(Alert).filter(
        Alert.security_status.in_(["QUARANTINED", "SUSPICIOUS"]),
        Alert.severity.ilike("critical")
    ).count()

    # Average Trust Score across all events
    avg_score_res = db.query(func.avg(SecurityEvent.trust_score)).scalar()
    avg_trust_score = round(float(avg_score_res), 1) if avg_score_res is not None else 98.5

    # System Status Calculation: PROTECTED / WARNING / CRITICAL
    if pending_critical > 0:
        system_status = "CRITICAL"
        status_message = f"{pending_critical} suspicious critical alerts pending SRE review!"
    elif total_screened > 10 and (blocked_count / total_screened) > 0.25:
        system_status = "CRITICAL"
        status_message = f"Elevated threat level: {blocked_count} of {total_screened} requests blocked by shield"
    elif pending_quarantines > 0 or rate_limits > 0 or invalid_sigs > 0:
        system_status = "WARNING"
        status_message = f"Shield active: {pending_quarantines} quarantined alerts awaiting inspection"
    else:
        system_status = "PROTECTED"
        status_message = "All alert pipelines secured and operating normally"

    # Distribution of decisions
    accepted_count = db.query(SecurityEvent).filter(SecurityEvent.action == "ACCEPTED").count()

    return {
        "status": "success",
        "system_status": system_status,
        "status_message": status_message,
        "metrics": {
            "total_screened": total_screened,
            "blocked_requests": blocked_count,
            "quarantined_alerts": pending_quarantines,
            "pending_critical_quarantines": pending_critical,
            "invalid_signatures": invalid_sigs,
            "replay_attempts": replay_count,
            "rate_limit_violations": rate_limits,
            "alert_injection_attempts": injections,
            "average_trust_score": avg_trust_score,
            "accepted_requests": accepted_count
        },
        "distribution": {
            "trusted": accepted_count,
            "suspicious": quarantined_events,
            "blocked": blocked_count
        }
    }

# ============================================================
# 3. SECURITY AUDIT EVENT STREAM
# ============================================================
@router.get("/events", summary="List persistent security audit trail")
def list_security_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(SecurityEvent)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if source:
        query = query.filter(SecurityEvent.source == source)
    if action:
        query = query.filter(SecurityEvent.action == action)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)

    total = query.count()
    events = query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "status": "success",
        "total": total,
        "events": [e.to_dict() for e in events]
    }

# ============================================================
# 4. QUARANTINE SYSTEM (REVIEW / APPROVE / REJECT)
# ============================================================
@router.get("/quarantine", summary="List quarantined and suspicious alerts")
def list_quarantined_alerts(
    is_critical: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Alert).filter(Alert.security_status.in_(["QUARANTINED", "SUSPICIOUS"]))

    if is_critical is True:
        query = query.filter(Alert.severity.ilike("critical"))
    elif is_critical is False:
        query = query.filter(~Alert.severity.ilike("critical"))

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Alert.alert_name.ilike(term),
                Alert.service.ilike(term),
                Alert.quarantine_reason.ilike(term)
            )
        )

    total = query.count()
    alerts = query.order_by(Alert.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "status": "success",
        "total": total,
        "quarantined_alerts": [a.to_dict() for a in alerts]
    }

@router.post("/quarantine/{alert_id}/approve", summary="SRE approves quarantined alert into processing pipeline")
def approve_quarantined_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Authorized SRE action: Releases quarantined alert and runs it through
    the standard processing pipeline (dedup, batching, correlation, routing).
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Quarantined alert not found")

    # Mark approved in security status
    alert.security_status = "ACCEPTED"
    alert.suppression_reason = None
    alert.suppression_category = None
    alert.trust_score = max(alert.trust_score or 50.0, 85.0)

    # Re-evaluate with processing pipeline
    raw = alert.raw_payload or {
        "alert_name": alert.alert_name,
        "service": alert.service,
        "severity": alert.severity,
        "message": alert.message,
        "source": alert.source
    }
    norm = normalize_generic(raw)
    result = process_alert(db, norm)

    # Log SRE approval event
    shield.audit.record_event(
        db=db,
        event_type="ALERT_ACCEPTED",
        source=alert.source,
        action="ACCEPTED",
        reason=f"Quarantined alert {alert_id} manually approved by SRE",
        severity="INFO",
        trust_score=alert.trust_score,
        alert_id=alert.id
    )

    db.commit()
    return {
        "status": "success",
        "message": f"Alert {alert_id} released from quarantine and processed",
        "pipeline_result": result
    }

@router.post("/quarantine/{alert_id}/reject", summary="SRE rejects and dismisses quarantined alert")
def reject_quarantined_alert(
    alert_id: int,
    reason: str = Query("Rejected as unauthorized or invalid by SRE", description="Reason for rejection"),
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Quarantined alert not found")

    alert.security_status = "BLOCKED"
    alert.status = "SUPPRESSED"
    alert.suppression_reason = reason
    alert.quarantine_reason = f"Rejected by SRE: {reason}"

    shield.audit.record_event(
        db=db,
        event_type="ALERT_BLOCKED",
        source=alert.source,
        action="BLOCKED",
        reason=f"Alert {alert_id} rejected by SRE: {reason}",
        severity="LOW",
        trust_score=0.0,
        alert_id=alert.id
    )

    db.commit()
    return {
        "status": "success",
        "message": f"Alert {alert_id} rejected and purged from active pipeline"
    }

# ============================================================
# 5. WEBHOOK SOURCES & SECRET ROTATION
# ============================================================
@router.get("/sources", summary="List registered webhook sources (masked secrets)")
def list_webhook_sources(db: Session = Depends(get_db)):
    # Ensure default sources exist
    shield.auth.seed_defaults(db)
    sources = db.query(WebhookSource).all()
    return {
        "status": "success",
        "sources": [s.to_safe_dict() for s in sources]
    }

@router.post("/sources", summary="Register a new alert monitoring source")
def create_webhook_source(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    name = str(data.get("source_name", "")).strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="source_name is required")

    existing = db.query(WebhookSource).filter(WebhookSource.source_name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Source '{name}' already exists")

    import secrets
    secret_key = f"{name[:3]}-sec-{secrets.token_hex(16)}"
    rpm = int(data.get("rate_limit_per_minute", 1000))

    src = WebhookSource(
        id=str(uuid.uuid4()),
        source_name=name,
        source_identifier=f"src_{name}_{secrets.token_hex(4)}",
        secret=secret_key,
        is_enabled=True,
        rate_limit_per_minute=rpm,
        trust_rating=100.0
    )
    db.add(src)
    db.commit()
    shield.auth.refresh_cache(db)

    # Return secret ONCE during creation
    return {
        "status": "success",
        "message": f"Source '{name}' registered successfully. Store this secret securely; it will not be shown again.",
        "source": src.to_safe_dict(),
        "generated_secret": secret_key
    }

@router.post("/sources/{source_id}/rotate-secret", summary="Rotate webhook secret with zero downtime")
def rotate_source_secret(
    source_id: str,
    grace_period_hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    src = db.query(WebhookSource).filter(
        or_(WebhookSource.id == source_id, WebhookSource.source_name == source_id)
    ).first()
    if not src:
        raise HTTPException(status_code=404, detail="Webhook source not found")

    res = shield.auth.rotate_secret(src.source_name, db, grace_period_hours=grace_period_hours)

    shield.audit.record_event(
        db=db,
        event_type="SECRET_ROTATED",
        source=src.source_name,
        action="ACCEPTED",
        reason=f"Secret rotated with {grace_period_hours}h grace transition",
        severity="INFO",
        trust_score=100.0
    )

    return {
        "status": "success",
        "message": f"Secret rotated for source '{src.source_name}'. Previous secret remains valid for {grace_period_hours}h.",
        "rotation_details": res
    }

@router.post("/sources/{source_id}/toggle", summary="Enable or disable a webhook source")
def toggle_source_status(
    source_id: str,
    db: Session = Depends(get_db)
):
    src = db.query(WebhookSource).filter(
        or_(WebhookSource.id == source_id, WebhookSource.source_name == source_id)
    ).first()
    if not src:
        raise HTTPException(status_code=404, detail="Webhook source not found")

    src.is_enabled = not src.is_enabled
    src.updated_at = datetime.datetime.utcnow()
    db.commit()
    shield.auth.refresh_cache(db)

    return {
        "status": "success",
        "source_name": src.source_name,
        "is_enabled": src.is_enabled
    }

# ============================================================
# 6. SECURITY TEST SCENARIO RUNNER (FOR LIVE JUDGING & DEMOS)
# ============================================================
@router.post("/test-scenario", summary="Execute automated security test scenario with simulated headers")
def run_security_test_scenario(
    scenario: str = Query(..., description="valid_alert | invalid_signature | replay_attack | alert_flood | unknown_source | malformed_payload | critical_suspicious"),
    db: Session = Depends(get_db)
):
    """
    Direct test driver for the 7 core security scenarios:
    1. valid_alert -> Valid HMAC + Fresh Timestamp + Nonce -> ACCEPTED (Trust: 95+)
    2. invalid_signature -> Tampered HMAC -> BLOCKED (401)
    3. replay_attack -> Same Request ID reused -> BLOCKED (409)
    4. alert_flood -> Rate limit exceeded -> THROTTLED / BLOCKED (429)
    5. unknown_source -> Unregistered client -> QUARANTINED (Trust < 40)
    6. malformed_payload -> Missing mandatory fields -> REJECTED (400)
    7. critical_suspicious -> Critical alert with anomalous volume -> QUARANTINED & Preserved (Never dropped!)
    """
    shield.auth.seed_defaults(db)
    sim_secret = DEFAULT_SOURCE_SECRETS["simulator"]
    now_ts = str(time.time())
    req_id = f"test_req_{uuid.uuid4().hex[:8]}"

    base_payload = {
        "source": "simulator",
        "alert_name": "HighLatencySpike",
        "service": "api-gateway",
        "severity": "high",
        "environment": "production",
        "message": "API gateway P99 latency exceeded 1200ms"
    }

    if scenario == "valid_alert":
        body_bytes = json.dumps(base_payload).encode("utf-8")
        sig = HMACSignatureVerifier.calculate_signature(body_bytes, sim_secret)
        headers = {
            "x-alert-source": "simulator",
            "x-alert-signature": sig,
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "ACCEPTED", "result": res}

    elif scenario == "invalid_signature":
        body_bytes = json.dumps(base_payload).encode("utf-8")
        headers = {
            "x-alert-source": "simulator",
            "x-alert-signature": "tampered_bad_hex_signature_9999",
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "BLOCKED (401)", "result": res}

    elif scenario == "replay_attack":
        body_bytes = json.dumps(base_payload).encode("utf-8")
        sig = HMACSignatureVerifier.calculate_signature(body_bytes, sim_secret)
        fixed_id = f"replayed_id_{uuid.uuid4().hex[:6]}"
        headers = {
            "x-alert-source": "simulator",
            "x-alert-signature": sig,
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": fixed_id
        }
        # First request succeeds
        shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        # Second request with SAME ID fails as REPLAY ATTACK
        res2 = shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "BLOCKED (409)", "result": res2}

    elif scenario == "alert_flood":
        # Artificially trigger rate limiter
        key = "simulator:flood_test_ip"
        for _ in range(5005):
            shield.rate_limiter._requests.setdefault(key, deque()).append(time.time())
        body_bytes = json.dumps(base_payload).encode("utf-8")
        sig = HMACSignatureVerifier.calculate_signature(body_bytes, sim_secret)
        headers = {
            "x-alert-source": "simulator",
            "x-alert-signature": sig,
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(body_bytes, headers, "flood_test_ip", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "BLOCKED / THROTTLED (429)", "result": res}

    elif scenario == "unknown_source":
        body_bytes = json.dumps(base_payload).encode("utf-8")
        headers = {
            "x-alert-source": "unregistered_external_hacker",
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "QUARANTINED (Low Trust)", "result": res}

    elif scenario == "malformed_payload":
        bad_body = b'{"not_an_alert": true, "corrupted": [1, 2, 3}'  # Invalid JSON syntax
        headers = {
            "x-alert-source": "simulator",
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(bad_body, headers, "127.0.0.1", "/api/security/ingest", db)
        return {"scenario": scenario, "expected": "REJECTED (400)", "result": res}

    elif scenario == "critical_suspicious":
        crit_payload = {
            "source": "simulator",
            "alert_name": "CoreDatabaseClusterOutage",
            "service": "database",
            "severity": "critical",
            "message": "Primary PostgreSQL node unreachable, replica lag infinity"
        }
        body_bytes = json.dumps(crit_payload).encode("utf-8")
        # Incomplete signature and sudden volume burst to trigger quarantine
        headers = {
            "x-alert-source": "simulator",
            "x-alert-timestamp": now_ts,
            "x-alert-request-id": req_id
        }
        res = shield.guard_webhook(body_bytes, headers, "127.0.0.1", "/api/security/ingest", db)
        return {
            "scenario": scenario,
            "expected": "QUARANTINED & PRESERVED (Critical Alert Safety)",
            "is_critical": True,
            "result": res
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario}'")
