from typing import List, Optional, Any
from pydantic import BaseModel

class IncidentResponse(BaseModel):
    id: str
    title: str
    root_cause_alert_id: Optional[int] = None
    root_cause_service: str
    root_cause_alert_name: str
    root_cause_reason: str
    confidence_score: float
    severity: str
    severity_score: float
    status: str
    affected_services: List[str]
    alert_count: int
    suppressed_count: int
    notifications_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None
    duration_seconds: float
    evidence: List[Any]
    estimated_cost_loss: Optional[float] = 0.0
    cost_burn_rate_per_minute: Optional[float] = 0.0

    class Config:
        from_attributes = True
