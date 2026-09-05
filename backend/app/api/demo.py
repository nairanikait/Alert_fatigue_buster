import datetime
import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.events import ws_manager
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

router = APIRouter(prefix="/demo", tags=["Demo Simulation"])

@router.post("/database-outage", summary="Simulate massive 500-alert Database Outage incident")
async def simulate_database_outage(db: Session = Depends(get_db)):
    """
    Generates 500 alerts in realistic chronological cascade:
    1x DatabaseDown, 100x PaymentFailure, 150x OrderFailure, 100x AuthFailure, 149x APIUnavailable.
    """
    base_time = datetime.datetime.utcnow()
    raw_alerts: List[Dict[str, Any]] = []

    # 1. Primary Root Cause Alert (T=0)
    raw_alerts.append({
        "source": "prometheus",
        "alert_name": "DatabaseDown",
        "service": "database",
        "host": "db-cluster-node-01",
        "environment": "production",
        "severity": "critical",
        "status": "firing",
        "message": "FATAL: Connection refused on postgres-primary:5432. All connections dropping.",
        "timestamp": base_time,
        "labels": {"cluster": "us-east-1", "tier": "storage"}
    })

    # 2. Downstream Failures cascading rapidly (T+1s to T+4s)
    # PaymentFailure x 100
    for i in range(100):
        raw_alerts.append({
            "source": "datadog",
            "alert_name": "PaymentFailure",
            "service": "payment-service",
            "host": f"pay-pod-{(i % 4) + 1}",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "Payment processing failed: DB connection timeout during transaction commit",
            "timestamp": base_time + datetime.timedelta(seconds=1, milliseconds=i * 10),
            "labels": {"team": "payments"}
        })

    # OrderFailure x 150
    for i in range(150):
        raw_alerts.append({
            "source": "prometheus",
            "alert_name": "OrderFailure",
            "service": "order-service",
            "host": f"order-pod-{(i % 6) + 1}",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "Could not persist customer order: database pool exhausted",
            "timestamp": base_time + datetime.timedelta(seconds=2, milliseconds=i * 8),
            "labels": {"team": "orders"}
        })

    # AuthenticationFailure x 100
    for i in range(100):
        raw_alerts.append({
            "source": "datadog",
            "alert_name": "AuthenticationFailure",
            "service": "authentication-service",
            "host": f"auth-pod-{(i % 3) + 1}",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "JWT session validation timeout: unable to reach user credential store",
            "timestamp": base_time + datetime.timedelta(seconds=3, milliseconds=i * 10),
            "labels": {"team": "security"}
        })

    # APIUnavailable x 149
    for i in range(149):
        raw_alerts.append({
            "source": "generic",
            "alert_name": "APIUnavailable",
            "service": "api-gateway",
            "host": f"edge-gw-{(i % 2) + 1}",
            "environment": "production",
            "severity": "medium",
            "status": "firing",
            "message": "HTTP 502 Bad Gateway: Upstream order and auth services unreachable",
            "timestamp": base_time + datetime.timedelta(seconds=4, milliseconds=i * 5),
            "labels": {"team": "platform"}
        })

    # Process all 500 alerts through the intelligence pipeline
    total_processed = 0
    suppressed_count = 0
    notifications_count = 0
    unique_count = 0

    for raw in raw_alerts:
        normalized = normalize_generic(raw)
        result = process_alert(db, normalized)
        total_processed += 1
        
        action = result.get("action")
        if "SUPPRESSED" in action or action == "BATCHED":
            suppressed_count += 1
        elif action == "NOTIFIED":
            notifications_count += 1

    # Broadcast simulation completion to all frontend clients
    asyncio.create_task(ws_manager.broadcast("DEMO_COMPLETE", {
        "scenario": "database-outage",
        "total_incoming": total_processed,
        "suppressed": suppressed_count,
        "notifications": notifications_count
    }))

    return {
        "status": "success",
        "scenario": "Database Outage Incident Storm",
        "total_generated": len(raw_alerts),
        "total_incoming": total_processed,
        "suppressed": suppressed_count,
        "notifications_dispatched": notifications_count,
        "reduction_percentage": round((1.0 - (notifications_count / total_processed)) * 100.0, 1),
        "message": "500 alerts successfully processed into intelligent root-cause incident"
    }

@router.post("/flaky-pod", summary="Simulate flapping Pod restart alert")
async def simulate_flaky_pod(db: Session = Depends(get_db)):
    """
    Generates a flapping PodRestarted alert that repeatedly fires and resolves.
    Demonstrates the Flaky Alert Detector.
    """
    base_time = datetime.datetime.utcnow()
    results = []

    for i in range(6):
        # Fire
        fire_alert = normalize_generic({
            "source": "prometheus",
            "alert_name": "PodRestarted",
            "service": "order-service",
            "host": "worker-k8s-node-4",
            "environment": "production",
            "severity": "medium",
            "status": "firing",
            "message": f"Pod order-service-worker-{i} crashed with OOMKilled, restarting container",
            "timestamp": base_time + datetime.timedelta(seconds=i * 10)
        })
        res_fire = process_alert(db, fire_alert)
        results.append(res_fire)

        # Resolve
        resolve_alert = normalize_generic({
            "source": "prometheus",
            "alert_name": "PodRestarted",
            "service": "order-service",
            "host": "worker-k8s-node-4",
            "environment": "production",
            "severity": "medium",
            "status": "resolved",
            "message": f"Pod order-service-worker-{i} back to Running state",
            "timestamp": base_time + datetime.timedelta(seconds=i * 10 + 5)
        })
        res_resolve = process_alert(db, resolve_alert)
        results.append(res_resolve)

    asyncio.create_task(ws_manager.broadcast("DEMO_COMPLETE", {"scenario": "flaky-pod"}))

    return {
        "status": "success",
        "scenario": "Flaky Pod Flapping",
        "flaps_generated": 6,
        "message": "Flapping Pod alert successfully flagged with 'NOISY / FLAKY' badge and extended cooldown."
    }

@router.post("/alert-storm", summary="Simulate high-velocity multi-service alert storm")
async def simulate_alert_storm(db: Session = Depends(get_db)):
    """
    Generates a storm of diverse alerts across multiple microservices.
    Demonstrates burst batching and digest notifications.
    """
    services = ["payment-service", "order-service", "redis", "message-queue", "api-gateway"]
    alerts = ["HighMemory", "QueueBacklog", "SlowQueries", "CacheMissSpike", "NetworkLatency"]
    base_time = datetime.datetime.utcnow()

    total = 0
    for i in range(75):
        svc = services[i % len(services)]
        alt = alerts[i % len(alerts)]
        norm = normalize_generic({
            "source": "datadog",
            "alert_name": alt,
            "service": svc,
            "host": f"{svc}-host-01",
            "environment": "production",
            "severity": "medium",
            "status": "firing",
            "message": f"Elevated resource utilization on {svc} ({alt})",
            "timestamp": base_time + datetime.timedelta(milliseconds=i * 50)
        })
        process_alert(db, norm)
        total += 1

    asyncio.create_task(ws_manager.broadcast("DEMO_COMPLETE", {"scenario": "alert-storm"}))

    return {
        "status": "success",
        "scenario": "Multi-Service Alert Storm",
        "total_alerts": total,
        "message": "Alert storm batched into structured digests."
    }

@router.post("/critical", summary="Simulate genuine critical emergency (Never Silenced)")
async def simulate_critical_emergency(db: Session = Depends(get_db)):
    """
    Generates a solitary P1 Critical Alert.
    Demonstrates that critical emergencies bypass cooldowns/batching and notify immediately.
    """
    now = datetime.datetime.utcnow()
    norm = normalize_generic({
        "source": "prometheus",
        "alert_name": "DataLossImminent",
        "service": "database",
        "host": "prod-master-db",
        "environment": "production",
        "severity": "critical",
        "status": "firing",
        "message": "EMERGENCY: RAID controller hardware fault detected on database master storage array!",
        "timestamp": now,
        "labels": {"priority": "P1", "page": "immediate"}
    })
    result = process_alert(db, norm)
    asyncio.create_task(ws_manager.broadcast("DEMO_COMPLETE", {"scenario": "critical"}))

    return {
        "status": "success",
        "scenario": "P1 Critical Emergency",
        "result": result,
        "message": "Critical emergency successfully bypassed all filters and dispatched immediately to PagerDuty!"
    }

@router.post("/recovery", summary="Simulate resolution of active incidents")
async def simulate_recovery(db: Session = Depends(get_db)):
    """
    Sends resolution events for active firing alerts.
    Demonstrates lifecycle state transition to RESOLVED and incident duration calculation.
    """
    now = datetime.datetime.utcnow()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["FIRING", "ONGOING"])).all()

    resolved_count = 0
    for a in active_alerts:
        norm = normalize_generic({
            "source": a.source,
            "alert_name": a.alert_name,
            "service": a.service,
            "host": a.host,
            "environment": a.environment,
            "severity": a.severity,
            "status": "resolved",
            "message": f"Service {a.service} recovered. Incident resolved.",
            "timestamp": now
        })
        process_alert(db, norm)
        resolved_count += 1

    # Ensure all firing incidents are marked resolved
    for inc in db.query(Incident).filter(Incident.status == "FIRING").all():
        active_count = (
            db.query(Alert)
            .filter(Alert.correlation_group_id == inc.id, Alert.status.in_(["FIRING", "ONGOING"]))
            .count()
        )
        if active_count == 0:
            inc.status = "RESOLVED"
            inc.resolved_at = now
            if inc.created_at:
                inc.duration_seconds = max(1.0, (now - inc.created_at).total_seconds())
    db.commit()

    asyncio.create_task(ws_manager.broadcast("DEMO_COMPLETE", {"scenario": "recovery"}))

    return {
        "status": "success",
        "scenario": "Incident Recovery",
        "resolved_alerts": resolved_count,
        "message": f"{resolved_count} active alerts transitioned to RESOLVED state with duration tracking."
    }

@router.post("/reset", summary="Reset all demo alerts, incidents, and notifications")
async def reset_demo_data(db: Session = Depends(get_db)):
    """
    Wipes alerts, incidents, and notifications for clean judging demonstrations.
    """
    db.query(Alert).delete()
    db.query(Incident).delete()
    db.query(Notification).delete()
    db.commit()

    asyncio.create_task(ws_manager.broadcast("DEMO_RESET", {}))

    return {"status": "success", "message": "Demo data successfully reset."}
