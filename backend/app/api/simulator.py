import datetime
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.events import ws_manager
from app.models.simulation import Simulation
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.incident import Incident
from app.models.notification import Notification
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

router = APIRouter(prefix="/simulator", tags=["Alert Simulator"])

class ScenarioRunRequest(BaseModel):
    scenario: str = Field(..., description="Scenario identifier (e.g. database_outage, flaky_pod, alert_storm, critical_emergency, service_cascade, recovery)")
    alert_count: Optional[int] = Field(None, description="Alert count override for high-volume storm simulations")
    speed: Optional[str] = Field("normal", description="Simulation velocity: slow, normal, fast")
    severity: Optional[str] = Field("mixed", description="Severity filter: mixed, critical, high, medium, low")

def _summarize_simulation_results(db: Session, scenario_name: str, total_generated: int) -> Dict[str, Any]:
    """
    Computes real simulation outcome telemetry directly from the database
    and the single-source-of-truth alert processing results.
    """
    total_incoming = db.query(func.coalesce(func.sum(Alert.occurrence_count), 0)).scalar() or 0
    unique_alerts = db.query(func.count(Alert.id)).scalar() or 0
    notifications_sent = db.query(func.count(Notification.id)).scalar() or 0
    active_incidents = db.query(func.count(Incident.id)).filter(Incident.status == "FIRING").scalar() or 0

    suppressed_count = max(0, total_incoming - notifications_sent)
    reduction_percentage = round((1.0 - (notifications_sent / total_incoming)) * 100.0, 1) if total_incoming > 0 else 0.0

    duplicate_merged = max(0, total_incoming - unique_alerts)
    batched_count = db.query(func.count(Alert.id)).filter(Alert.suppression_category == "batch").scalar() or 0
    correlated_count = db.query(func.count(Alert.id)).filter(Alert.root_cause_id.isnot(None)).scalar() or 0

    # Fetch latest active or recent incident for root cause analysis
    latest_incident = db.query(Incident).order_by(Incident.created_at.desc()).first()
    probable_root_cause = latest_incident.title if latest_incident else "Database Connection Failure"
    confidence_score = latest_incident.confidence_score if latest_incident else 94

    # Channel breakdown
    channels = db.query(Notification.channel, func.count(Notification.id)).group_by(Notification.channel).all()
    channel_breakdown = {c.lower(): count for c, count in channels}

    return {
        "status": "success",
        "scenario": scenario_name,
        "total_generated": total_generated,
        "total_accepted": total_generated,
        "total_incoming": int(total_incoming),
        "unique_alerts": int(unique_alerts),
        "duplicates_merged": int(duplicate_merged),
        "correlated_alerts": int(correlated_count),
        "batched_alerts": int(batched_count),
        "suppressed_count": int(suppressed_count),
        "notifications_dispatched": int(notifications_sent),
        "reduction_percentage": reduction_percentage,
        "active_incidents": int(active_incidents),
        "probable_root_cause": probable_root_cause,
        "confidence_score": confidence_score,
        "channel_breakdown": {
            "pagerduty": channel_breakdown.get("pagerduty", 0),
            "slack": channel_breakdown.get("slack", 0),
            "email": channel_breakdown.get("email", 0),
            "mock": channel_breakdown.get("mock", 0),
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

def _persist_scenario_execution(
    db: Session,
    scenario_name: str,
    raw_alerts: List[Dict[str, Any]],
    speed: str = "normal",
    severity: str = "mixed"
) -> Dict[str, Any]:
    """Helper to track simulation entity in database and process all alerts through the persistent pipeline."""
    now_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:4]
    sim_id = f"sim_{now_str}_{rand_suffix}"
    start_time = datetime.datetime.utcnow()

    # Create persistent Simulation entity
    db_sim = Simulation(
        id=sim_id,
        scenario=scenario_name,
        status="RUNNING",
        total_alerts=len(raw_alerts),
        processed_alerts=0,
        suppressed_alerts=0,
        notifications=0,
        reduction_percentage=0.0,
        speed=speed,
        severity=severity,
        start_time=start_time
    )
    db.add(db_sim)
    db.commit()

    # Process all alerts tagged with simulation_id with batched commits
    for idx, raw in enumerate(raw_alerts):
        raw["simulation_id"] = sim_id
        normalized = normalize_generic(raw)
        process_alert(db, normalized, auto_commit=False)
        if (idx + 1) % 25 == 0 or (idx + 1) == len(raw_alerts):
            db.commit()

    summary = _summarize_simulation_results(db, scenario_name, len(raw_alerts))
    completion_time = datetime.datetime.utcnow()

    # Update persistent Simulation record
    db_sim.status = "COMPLETED"
    db_sim.processed_alerts = len(raw_alerts)
    db_sim.suppressed_alerts = summary.get("suppressed_count", 0)
    db_sim.notifications = summary.get("notifications_dispatched", 0)
    db_sim.reduction_percentage = summary.get("reduction_percentage", 0.0)
    db_sim.completion_time = completion_time
    db_sim.metadata_json = summary
    db.commit()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.broadcast("SIMULATION_COMPLETE", summary))
    except RuntimeError:
        pass
    return summary

# ============================================================================
# SCENARIO 1: DATABASE OUTAGE (500 alerts)
# ============================================================================
@router.post("/database-outage", summary="Simulate 500-alert Database Outage incident")
async def simulate_database_outage(db: Session = Depends(get_db)):
    base_time = datetime.datetime.utcnow()
    raw_alerts: List[Dict[str, Any]] = []

    # 1. Root cause alert (T=0)
    raw_alerts.append({
        "source": "prometheus",
        "alert_name": "DatabaseDown",
        "service": "database",
        "host": "db-cluster-node-01",
        "environment": "production",
        "severity": "critical",
        "status": "firing",
        "message": "FATAL: Connection refused on postgres-primary:5432. Pool exhausted.",
        "timestamp": base_time,
        "labels": {"cluster": "us-east-1", "tier": "storage"}
    })

    # 2. Downstream cascading failures (T+1s to T+4s)
    # Payment failures (100)
    for i in range(100):
        raw_alerts.append({
            "source": "datadog",
            "alert_name": "PaymentFailure",
            "service": "payment-service",
            "host": f"pay-pod-{(i % 4) + 1}",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "Payment processing failed: DB connection timeout during commit",
            "timestamp": base_time + datetime.timedelta(seconds=1, milliseconds=i * 10),
            "labels": {"team": "payments"}
        })

    # Order failures (150)
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

    # Authentication failures (100)
    for i in range(100):
        raw_alerts.append({
            "source": "datadog",
            "alert_name": "AuthenticationFailure",
            "service": "authentication-service",
            "host": f"auth-pod-{(i % 3) + 1}",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "Session token verification timeout: unable to reach user store",
            "timestamp": base_time + datetime.timedelta(seconds=3, milliseconds=i * 10),
            "labels": {"team": "security"}
        })

    # API Gateway failures (149)
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

    return _persist_scenario_execution(db, "Database Outage", raw_alerts, speed="normal", severity="mixed")

# ============================================================================
# SCENARIO 2: FLAKY POD (50-100 events, flapping firing/resolved cycles)
# ============================================================================
@router.post("/flaky-pod", summary="Simulate flapping Pod restart alert")
async def simulate_flaky_pod(db: Session = Depends(get_db)):
    base_time = datetime.datetime.utcnow()
    raw_alerts: List[Dict[str, Any]] = []

    # Simulate 8 rapid cycles of Firing <-> Resolved (16 state events total, representing 64 raw alerts)
    for i in range(8):
        # Fire burst
        for b in range(4):
            raw_alerts.append({
                "source": "prometheus",
                "alert_name": "PodRestarted",
                "service": "order-service",
                "host": "worker-k8s-node-4",
                "environment": "production",
                "severity": "medium",
                "status": "firing",
                "message": f"Pod order-service-worker-{i} crashed with OOMKilled, restarting container",
                "timestamp": base_time + datetime.timedelta(seconds=i * 10, milliseconds=b * 200)
            })

        # Resolve
        raw_alerts.append({
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

    return _persist_scenario_execution(db, "Flaky Pod Flapping", raw_alerts, speed="normal", severity="medium")

# ============================================================================
# SCENARIO 3: ALERT STORM (Configurable count 100-5000 alerts)
# ============================================================================
@router.post("/alert-storm", summary="Simulate high-velocity multi-service alert storm")
async def simulate_alert_storm(
    alert_count: int = 500,
    speed: str = "normal",
    severity: str = "mixed",
    db: Session = Depends(get_db)
):
    count = min(max(alert_count, 50), 2000)
    services = ["payment-service", "order-service", "redis", "message-queue", "api-gateway", "database"]
    alert_names = ["HighCPU", "HighMemory", "QueueBacklog", "SlowQueries", "CacheMissSpike", "NetworkLatency"]
    severities = ["critical", "high", "medium", "low"] if severity == "mixed" else [severity]
    base_time = datetime.datetime.utcnow()
    raw_alerts: List[Dict[str, Any]] = []

    for i in range(count):
        svc = services[i % len(services)]
        alt = alert_names[i % len(alert_names)]
        sev = severities[i % len(severities)]
        
        raw_alerts.append({
            "source": "datadog" if i % 2 == 0 else "prometheus",
            "alert_name": alt,
            "service": svc,
            "host": f"{svc}-node-{(i % 5) + 1}",
            "environment": "production",
            "severity": sev,
            "status": "firing",
            "message": f"Resource threshold breached on {svc} ({alt}: {85 + (i % 15)}% utilization)",
            "timestamp": base_time + datetime.timedelta(milliseconds=i * 25)
        })

    return _persist_scenario_execution(db, f"Alert Storm ({count} Alerts)", raw_alerts, speed=speed, severity=severity)

# ============================================================================
# SCENARIO 4: CRITICAL EMERGENCY (Never silenced, direct to PagerDuty)
# ============================================================================
@router.post("/critical-emergency", summary="Simulate genuine critical emergency")
async def simulate_critical_emergency(db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    raw_alerts = [{
        "source": "prometheus",
        "alert_name": "ProductionDatabaseDown",
        "service": "database",
        "host": "prod-master-db-01",
        "environment": "production",
        "severity": "critical",
        "status": "firing",
        "message": "EMERGENCY: Primary production database cluster unreachable. Immediate engineering response required.",
        "timestamp": now,
        "labels": {"priority": "P1", "page": "immediate", "team": "sre"}
    }]

    return _persist_scenario_execution(db, "P1 Critical Emergency", raw_alerts, speed="normal", severity="critical")

# ============================================================================
# SCENARIO 5: SERVICE CASCADE (Topological failure order)
# ============================================================================
@router.post("/service-cascade", summary="Simulate strict topological failure cascade")
async def simulate_service_cascade(db: Session = Depends(get_db)):
    """
    Fires alerts in strict topological cascade:
    Database -> Payment -> Orders -> Checkout -> API Gateway
    """
    base_time = datetime.datetime.utcnow()
    cascade_steps = [
        {"service": "database", "alert": "DatabaseStorageExhausted", "severity": "critical", "msg": "Storage volume /data at 100% capacity on postgres-master"},
        {"service": "payment-service", "alert": "PaymentTxCommitFailed", "severity": "high", "msg": "Payment ledger unable to persist transaction due to upstream DB disk full"},
        {"service": "order-service", "alert": "OrderCheckoutTimeout", "severity": "high", "msg": "Order workflow timed out awaiting payment confirmation"},
        {"service": "checkout", "alert": "CheckoutCartDropoff", "severity": "medium", "msg": "User cart submissions failing downstream order placement"},
        {"service": "api-gateway", "alert": "Gateway504GatewayTimeout", "severity": "medium", "msg": "API gateway ingress dropping timed-out requests to checkout"}
    ]

    raw_alerts: List[Dict[str, Any]] = []
    for step_idx, step in enumerate(cascade_steps):
        burst_size = 40 if step_idx == 0 else 60
        for b in range(burst_size):
            raw_alerts.append({
                "source": "prometheus",
                "alert_name": step["alert"],
                "service": step["service"],
                "host": f"{step['service']}-pod-{(b % 3) + 1}",
                "environment": "production",
                "severity": step["severity"],
                "status": "firing",
                "message": step["msg"],
                "timestamp": base_time + datetime.timedelta(seconds=step_idx * 2, milliseconds=b * 20)
            })

    return _persist_scenario_execution(db, "Service Cascade", raw_alerts, speed="normal", severity="mixed")

# ============================================================================
# SCENARIO 6: RECOVERY (Resolves active incidents)
# ============================================================================
@router.post("/recovery", summary="Simulate incident recovery and resolution")
async def simulate_recovery(db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["FIRING", "ONGOING"])).all()

    resolved_count = 0
    raw_alerts = []
    for a in active_alerts:
        raw_alerts.append({
            "source": a.source,
            "alert_name": a.alert_name,
            "service": a.service,
            "host": a.host,
            "environment": a.environment,
            "severity": a.severity,
            "status": "resolved",
            "message": f"Service {a.service} health check passed. Incident resolved.",
            "timestamp": now
        })

    summary = _persist_scenario_execution(db, "Incident Recovery", raw_alerts, speed="normal", severity="low")

    # Update active incidents
    for inc in db.query(Incident).filter(Incident.status == "FIRING").all():
        active_count = db.query(Alert).filter(Alert.correlation_group_id == inc.id, Alert.status.in_(["FIRING", "ONGOING"])).count()
        if active_count == 0:
            inc.status = "RESOLVED"
            inc.resolved_at = now
            if inc.created_at:
                inc.duration_seconds = max(1.0, (now - inc.created_at).total_seconds())
    db.commit()

    summary["message"] = f"{len(raw_alerts)} active alert instances resolved."
    return summary

# ============================================================================
# RESET ENDPOINT
# ============================================================================
@router.post("/reset", summary="Reset all alerts, incidents, notifications, simulations, and events")
async def reset_simulator_data(db: Session = Depends(get_db)):
    db.query(AlertEvent).delete()
    db.query(Alert).delete()
    db.query(Incident).delete()
    db.query(Notification).delete()
    db.query(Simulation).delete()
    db.commit()

    summary = {
        "status": "success",
        "message": "Telemetry store reset. All alerts, incidents, notifications, events, and simulations purged.",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    asyncio.create_task(ws_manager.broadcast("DEMO_RESET", summary))
    return summary

# ============================================================================
# GENERIC RUN DISPATCHER
# ============================================================================
@router.post("/run", summary="Generic scenario execution endpoint")
async def run_scenario(req: ScenarioRunRequest, db: Session = Depends(get_db)):
    scen = req.scenario.lower().replace("-", "_")

    if scen == "database_outage":
        return await simulate_database_outage(db)
    elif scen == "flaky_pod":
        return await simulate_flaky_pod(db)
    elif scen == "alert_storm":
        count = req.alert_count or 500
        return await simulate_alert_storm(alert_count=count, speed=req.speed or "normal", severity=req.severity or "mixed", db=db)
    elif scen in ["critical", "critical_emergency"]:
        return await simulate_critical_emergency(db)
    elif scen in ["cascade", "service_cascade"]:
        return await simulate_service_cascade(db)
    elif scen in [
        "valid_alert", "invalid_signature", "replay_attack",
        "alert_flood", "unknown_source", "malformed_payload",
        "critical_suspicious"
    ]:
        from app.api.security import run_security_test_scenario
        return run_security_test_scenario(scen, db)
    elif scen == "recovery":
        return await simulate_recovery(db)
    elif scen == "reset":
        return await reset_simulator_data(db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown simulation scenario: '{req.scenario}'")

# ============================================================================
# DEDICATED SECURITY TEST SCENARIO ENDPOINT
# ============================================================================
@router.post("/security-test", summary="Run security test scenario from simulator")
def run_simulator_security_test(
    scenario: str = Body(..., embed=True, description="Scenario name"),
    db: Session = Depends(get_db)
):
    from app.api.security import run_security_test_scenario
    return run_security_test_scenario(scenario, db)

