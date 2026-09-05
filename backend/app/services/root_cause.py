import datetime
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.service import Service
from app.services.topology import build_topology_graph, get_downstream_services

def identify_root_cause(
    db: Session,
    alerts: List[Alert],
    max_dependency_depth: int = 5
) -> Tuple[Alert, float, str]:
    """
    Evaluates a correlated cluster of alerts to determine the probable root cause using multi-hop topology.
    Returns:
      (root_cause_alert, confidence_percentage, explainable_reason)
    """
    if not alerts:
        raise ValueError("Cannot determine root cause from empty alert list")

    if len(alerts) == 1:
        return (
            alerts[0],
            95.0,
            f"Isolated incident directly rooted at service '{alerts[0].service}'."
        )

    # Sort alerts chronologically
    sorted_alerts = sorted(alerts, key=lambda a: a.first_seen or a.timestamp)
    earliest_alert = sorted_alerts[0]

    # Fetch dependency graph once
    downstream_adj, _ = build_topology_graph(db)

    # Fetch services criticality
    services = {s.id: s.criticality for s in db.query(Service).all()}

    # Score each candidate
    best_candidate = earliest_alert
    best_score = -1.0
    best_reasons = []

    for alert in alerts:
        candidate_score = 0.0
        reasons = []

        # Factor 1: Temporal priority (earlier is more probable)
        time_diff = (alert.first_seen - earliest_alert.first_seen).total_seconds()
        if time_diff <= 0.5:
            candidate_score += 40.0
            reasons.append("Fired first in the incident timeline")
        else:
            time_penalty = min(25.0, time_diff * 4.0)
            candidate_score += max(0.0, 40.0 - time_penalty)
            reasons.append(f"Fired {time_diff:.1f}s after initial event")

        # Factor 2: Dependency topology (upstream parent/ancestor vs downstream)
        downstream_map = get_downstream_services(
            db=db,
            service_id=alert.service,
            max_depth=max_dependency_depth,
            downstream_adj=downstream_adj
        )
        downstream_affected = []
        for other in alerts:
            if other.id != alert.id and other.service in downstream_map:
                downstream_affected.append(other.service)

        if downstream_affected:
            unique_downstream_affected = list(dict.fromkeys(downstream_affected))
            dep_score = min(35.0, len(unique_downstream_affected) * 12.0)
            candidate_score += dep_score
            reasons.append(
                f"Upstream ancestor to {len(unique_downstream_affected)} failing downstream services ({', '.join(unique_downstream_affected)})"
            )

        # Factor 3: Service criticality
        crit = services.get(alert.service, 50)
        crit_score = (crit / 100.0) * 15.0
        candidate_score += crit_score

        # Factor 4: Severity score contribution
        candidate_score += (alert.severity_score / 100.0) * 10.0

        if candidate_score > best_score:
            best_score = candidate_score
            best_candidate = alert
            best_reasons = reasons

    # Compute confidence percentage (bounded between 75% and 98%)
    confidence = round(min(98.0, max(75.0, best_score * 0.95)), 1)
    
    # Construct transparent explanation
    downstream_svcs = [
        a.service for a in sorted_alerts
        if a.service != best_candidate.service
    ]
    unique_downstream = list(dict.fromkeys(downstream_svcs))

    if unique_downstream:
        time_lead = max(0.5, (sorted_alerts[1].first_seen - best_candidate.first_seen).total_seconds())
        explanation = (
            f"'{best_candidate.alert_name}' on '{best_candidate.service}' is the probable root cause "
            f"because it occurred {time_lead:.1f}s before failures cascading into {len(unique_downstream)} "
            f"dependent services ({', '.join(unique_downstream[:4])})."
        )
    else:
        explanation = (
            f"'{best_candidate.alert_name}' on '{best_candidate.service}' is the probable root cause "
            f"based on chronological origin and infrastructure criticality ({services.get(best_candidate.service, 50)}/100)."
        )

    return best_candidate, confidence, explanation
