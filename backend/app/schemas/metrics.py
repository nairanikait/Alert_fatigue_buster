from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class SuppressionBreakdown(BaseModel):
    duplicates: int = 0
    batched: int = 0
    downstream: int = 0
    cooldown: int = 0
    flaky: int = 0

class ChannelBreakdown(BaseModel):
    pagerduty: int = 0
    slack: int = 0
    email: int = 0
    mock: int = 0

class SeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

class ServiceImpact(BaseModel):
    service: str
    count: int
    criticality: int

class CostSavingsBreakdown(BaseModel):
    # Core Defensible ROI Metrics specified by Idea 8
    cost_saved_dedup_batching: float = 0.0
    cost_saved_routing_triage: float = 0.0
    total_cost_saved: float = 0.0
    engineering_hours_saved: float = 0.0
    interruption_minutes_saved: float = 0.0
    incoming_alerts: int = 0
    notifications_sent: int = 0
    suppressed_alerts: int = 0
    downstream_suppressed: int = 0

    # Configurable Assumption Parameters
    engineer_hourly_rate: float = 80.0
    interruption_recovery_minutes: float = 3.0
    avoided_interruption_cost: float = 4.0
    avoided_downstream_triage_cost: float = 15.0

    # Backward Compatibility Aliases
    cost_per_interruption: float = 4.0
    avg_context_switch_min: float = 3.0
    dedup_batching_saved: float = 0.0
    routing_triage_saved: float = 0.0
    total_dollars_saved: float = 0.0

class EngineeringTimeSaved(BaseModel):
    total_minutes_saved: float = 0.0
    total_hours_saved: float = 0.0
    human_readable: str = "0.0 hrs"

class MetricsResponse(BaseModel):
    incoming_alerts: int
    unique_alerts: int
    suppressed_alerts: int
    batched_alerts: int
    notifications_sent: int
    reduction_percentage: float
    active_incidents: int
    suppression_breakdown: SuppressionBreakdown
    channel_breakdown: ChannelBreakdown
    severity_breakdown: SeverityBreakdown
    top_affected_services: List[ServiceImpact]
    cost_savings: CostSavingsBreakdown
    time_saved: EngineeringTimeSaved
