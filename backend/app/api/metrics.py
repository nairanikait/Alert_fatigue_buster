from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.config import load_rules
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.service import Service
from app.models.system_rule import SystemRule
from app.schemas.metrics import (
    MetricsResponse, SuppressionBreakdown, ChannelBreakdown,
    SeverityBreakdown, ServiceImpact, CostSavingsBreakdown, EngineeringTimeSaved
)

router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("", response_model=MetricsResponse, summary="Get alert reduction metrics and defensible ROI/Time calculations")
def get_metrics(db: Session = Depends(get_db)):
    # Calculate Total Incoming Alerts (Sum of occurrence_count for all records)
    total_incoming = db.query(func.coalesce(func.sum(Alert.occurrence_count), 0)).scalar() or 0
    unique_alerts = db.query(func.count(Alert.id)).scalar() or 0
    notifications_sent = db.query(func.count(Notification.id)).scalar() or 0
    active_incidents = db.query(func.count(Incident.id)).filter(Incident.status == "FIRING").scalar() or 0

    suppressed_alerts = max(0, total_incoming - notifications_sent)

    if total_incoming > 0:
        reduction_percentage = round((1.0 - (notifications_sent / total_incoming)) * 100.0, 1)
    else:
        reduction_percentage = 0.0

    # Suppression categories breakdown
    duplicate_suppressed = max(0, total_incoming - unique_alerts)
    batched_count = db.query(func.count(Alert.id)).filter(Alert.suppression_category == "batch").scalar() or 0
    downstream_count = db.query(func.count(Alert.id)).filter(Alert.suppression_category == "downstream").scalar() or 0
    cooldown_count = db.query(func.count(Alert.id)).filter(Alert.suppression_category == "cooldown").scalar() or 0
    flaky_count = db.query(func.count(Alert.id)).filter(Alert.is_flaky == True).scalar() or 0

    # Channel breakdown
    channels = db.query(Notification.channel, func.count(Notification.id)).group_by(Notification.channel).all()
    channel_map = {c.lower(): count for c, count in channels}

    # Severity breakdown
    severities = db.query(Alert.severity, func.count(Alert.id)).group_by(Alert.severity).all()
    sev_map = {s.lower(): count for s, count in severities}

    # Top affected services
    service_counts = (
        db.query(Alert.service, func.sum(Alert.occurrence_count).label("total"))
        .group_by(Alert.service)
        .order_by(func.sum(Alert.occurrence_count).desc())
        .limit(6)
        .all()
    )
    all_svcs = {s.id: s.criticality for s in db.query(Service).all()}
    top_services = [
        ServiceImpact(
            service=svc_name,
            count=int(cnt or 0),
            criticality=all_svcs.get(svc_name, 50)
        )
        for svc_name, cnt in service_counts
    ]

    # Load configurable ROI assumptions from rules config / DB
    rule_entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
    rules = (rule_entry.value if rule_entry and rule_entry.value else load_rules()) or {}
    cost_cfg = rules.get("cost_savings", {})

    engineer_hourly_rate = float(cost_cfg.get("engineer_hourly_rate", 80.0))
    interruption_recovery_minutes = float(cost_cfg.get("interruption_recovery_minutes", 3.0))
    avoided_interruption_cost = float(cost_cfg.get("avoided_interruption_cost", 4.0))
    avoided_downstream_triage_cost = float(cost_cfg.get("avoided_downstream_triage_cost", 15.0))

    # Core Defensible ROI Calculations (Idea 8 exact specification)
    # 1. Dedup & Batching Savings:
    cost_saved_dedup_batching = round(max(total_incoming - notifications_sent, 0) * avoided_interruption_cost, 2)

    # 2. Smart Routing / Triage Savings:
    cost_saved_routing_triage = round(downstream_count * avoided_downstream_triage_cost, 2)

    # 3. Total Cost Saved:
    total_cost_saved = round(cost_saved_dedup_batching + cost_saved_routing_triage, 2)

    # 4. Engineering Focus Time Saved:
    engineering_minutes_saved = round(suppressed_alerts * interruption_recovery_minutes, 1)
    engineering_hours_saved = round(engineering_minutes_saved / 60.0, 2)
    interruption_minutes_saved = engineering_minutes_saved

    # Human-readable format (e.g. "2h 15m" or "74h 42m")
    total_mins_int = int(round(engineering_minutes_saved))
    hrs = total_mins_int // 60
    mins = total_mins_int % 60
    if hrs > 0:
        human_readable_time = f"{hrs}h {mins}m" if mins > 0 else f"{hrs}h"
    else:
        human_readable_time = f"{mins}m"

    return MetricsResponse(
        incoming_alerts=int(total_incoming),
        unique_alerts=int(unique_alerts),
        suppressed_alerts=int(suppressed_alerts),
        batched_alerts=int(batched_count),
        notifications_sent=int(notifications_sent),
        reduction_percentage=reduction_percentage,
        active_incidents=int(active_incidents),
        suppression_breakdown=SuppressionBreakdown(
            duplicates=int(duplicate_suppressed),
            batched=int(batched_count),
            downstream=int(downstream_count),
            cooldown=int(cooldown_count),
            flaky=int(flaky_count)
        ),
        channel_breakdown=ChannelBreakdown(
            pagerduty=channel_map.get("pagerduty", 0),
            slack=channel_map.get("slack", 0),
            email=channel_map.get("email", 0),
            mock=channel_map.get("mock", 0)
        ),
        severity_breakdown=SeverityBreakdown(
            critical=sev_map.get("critical", 0),
            high=sev_map.get("high", 0),
            medium=sev_map.get("medium", 0),
            low=sev_map.get("low", 0)
        ),
        top_affected_services=top_services,
        cost_savings=CostSavingsBreakdown(
            cost_saved_dedup_batching=cost_saved_dedup_batching,
            cost_saved_routing_triage=cost_saved_routing_triage,
            total_cost_saved=total_cost_saved,
            engineering_hours_saved=engineering_hours_saved,
            interruption_minutes_saved=interruption_minutes_saved,
            incoming_alerts=int(total_incoming),
            notifications_sent=int(notifications_sent),
            suppressed_alerts=int(suppressed_alerts),
            downstream_suppressed=int(downstream_count),
            engineer_hourly_rate=engineer_hourly_rate,
            interruption_recovery_minutes=interruption_recovery_minutes,
            avoided_interruption_cost=avoided_interruption_cost,
            avoided_downstream_triage_cost=avoided_downstream_triage_cost,
            cost_per_interruption=avoided_interruption_cost,
            avg_context_switch_min=interruption_recovery_minutes,
            dedup_batching_saved=cost_saved_dedup_batching,
            routing_triage_saved=cost_saved_routing_triage,
            total_dollars_saved=total_cost_saved
        ),
        time_saved=EngineeringTimeSaved(
            total_minutes_saved=engineering_minutes_saved,
            total_hours_saved=round(engineering_hours_saved, 1),
            human_readable=human_readable_time
        )
    )
