from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class GenericAlertInput(BaseModel):
    source: Optional[str] = "generic"
    alert_name: str = Field(..., description="e.g. HighCPU, DatabaseDown")
    service: str = Field(..., description="e.g. payment-service")
    host: Optional[str] = None
    environment: Optional[str] = "production"
    severity: Optional[str] = "medium"
    status: Optional[str] = "firing"
    message: str = Field(..., description="Description of the alert")
    timestamp: Optional[datetime] = None
    labels: Optional[Dict[str, Any]] = Field(default_factory=dict)

# Prometheus Alertmanager standard payload model
class PrometheusAlertItem(BaseModel):
    status: Optional[str] = "firing"
    labels: Dict[str, Any] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None

class PrometheusWebhookInput(BaseModel):
    version: Optional[str] = "4"
    groupKey: Optional[str] = None
    status: Optional[str] = "firing"
    receiver: Optional[str] = None
    groupLabels: Optional[Dict[str, Any]] = Field(default_factory=dict)
    commonLabels: Optional[Dict[str, Any]] = Field(default_factory=dict)
    commonAnnotations: Optional[Dict[str, Any]] = Field(default_factory=dict)
    alerts: List[PrometheusAlertItem] = Field(default_factory=list)

# Datadog standard webhook payload model
class DatadogWebhookInput(BaseModel):
    id: Optional[str] = None
    event_type: Optional[str] = "error"
    title: Optional[str] = None
    text_only_msg: Optional[str] = None
    body: Optional[str] = None
    alert_type: Optional[str] = "error" # error, warning, info, success
    tags: Optional[List[str]] = Field(default_factory=list)
    date: Optional[int] = None
    priority: Optional[str] = "normal"
    hostname: Optional[str] = None

class AlertResponse(BaseModel):
    id: int
    fingerprint: str
    source: str
    alert_name: str
    service: str
    host: Optional[str] = None
    environment: str
    severity: str
    severity_score: float
    status: str
    message: str
    labels: Dict[str, Any]
    timestamp: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    resolved_at: Optional[str] = None
    duration_seconds: float
    occurrence_count: int
    root_cause_id: Optional[int] = None
    correlation_group_id: Optional[str] = None
    notification_status: str
    suppression_reason: Optional[str] = None
    suppression_category: Optional[str] = None
    is_flaky: bool
    fire_count: int
    resolve_count: int
    explainability_notes: List[Any] = Field(default_factory=list)
    security_status: Optional[str] = "ACCEPTED"
    trust_score: Optional[float] = 100.0
    quarantine_reason: Optional[str] = None

    class Config:
        from_attributes = True

