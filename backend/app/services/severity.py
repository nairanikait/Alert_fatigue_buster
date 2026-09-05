from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.service import Service, ServiceDependency

def calculate_severity_score(
    db: Session,
    alert_name: str,
    service_name: str,
    raw_severity: str,
    environment: str = "production",
    is_flaky: bool = False,
    affected_downstream_count: int = 0
) -> Tuple[float, str, List[str]]:
    """
    Computes an explainable 0-100 severity score with reasons.
    """
    reasons = []
    
    # 1. Base Score from raw severity
    base_map = {
        "critical": 80.0,
        "high": 60.0,
        "medium": 42.0,
        "low": 15.0,
        "info": 10.0
    }
    score = base_map.get(raw_severity.lower(), 42.0)
    reasons.append(f"Base severity '{raw_severity.upper()}' contributes {score:.0f} pts")

    # 2. Environment impact
    if environment.lower() == "production":
        score += 10.0
        reasons.append("Production environment impact: +10 pts")
    elif environment.lower() in ("staging", "qa"):
        score += 3.0
        reasons.append(f"Non-production environment ({environment}): +3 pts")

    # 3. Service Criticality
    svc = db.query(Service).filter(Service.id == service_name).first()
    crit_val = svc.criticality if svc else 50
    crit_contrib = (crit_val / 100.0) * 10.0
    score += crit_contrib
    reasons.append(f"Service criticality ({crit_val}/100) adds +{crit_contrib:.1f} pts")

    # 4. Blast Radius (downstream dependencies affected)
    if affected_downstream_count > 0:
        blast_contrib = min(20.0, affected_downstream_count * 5.0)
        score += blast_contrib
        reasons.append(f"Blast radius: {affected_downstream_count} downstream services affected (+{blast_contrib:.0f} pts)")

    # 5. Flaky Penalty / Demotion
    if is_flaky:
        score = max(15.0, score - 15.0)
        reasons.append("Flaky/flapping alert behavior detected (-15 pts penalty)")

    # Cap score between 0 and 100
    final_score = min(100.0, max(0.0, score))

    # Map to final severity classification: 80-100 Critical, 60-79 High, 40-59 Medium, 0-39 Low
    if final_score >= 80.0 or raw_severity.lower() == "critical":
        final_severity = "CRITICAL"
        final_score = max(80.0, final_score)
    elif final_score >= 60.0 or raw_severity.lower() == "high":
        final_severity = "HIGH"
    elif final_score >= 40.0:
        final_severity = "MEDIUM"
    else:
        final_severity = "LOW"

    return round(final_score, 1), final_severity, reasons
