import uuid
import datetime
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.incident import Incident
from app.services.root_cause import identify_root_cause
from app.services.topology import (
    build_topology_graph,
    get_downstream_services,
    get_upstream_services,
    are_services_topologically_related
)

logger = logging.getLogger("alert_buster.correlation")

def find_or_create_incident(
    db: Session,
    alert: Alert,
    window_seconds: int = 15,
    max_dependency_depth: int = 5
) -> Tuple[Incident, bool, Optional[str]]:
    """
    Correlates an incoming alert into an active incident using multi-hop service topology and temporal proximity.
    Returns:
      (incident, is_new_incident, suppression_reason_if_downstream)
    """
    now = alert.timestamp or datetime.datetime.utcnow()
    window_start = now - datetime.timedelta(seconds=window_seconds)

    # 1. Fetch all active incidents within the temporal window
    active_incidents = (
        db.query(Incident)
        .filter(
            Incident.status.in_(["FIRING", "ONGOING"]),
            Incident.updated_at >= window_start
        )
        .all()
    )

    # Fetch topology adjacency graphs once efficiently
    downstream_adj, upstream_adj = build_topology_graph(db)

    # 2. Check for multi-hop topological or direct relationship
    for inc in active_incidents:
        is_related = False

        # Condition 1: Direct service match with root cause
        if inc.root_cause_service == alert.service:
            is_related = True
        # Condition 2: Alert service is already in affected services
        elif alert.service in (inc.affected_services or []):
            is_related = True
        else:
            # Condition 3 & 4: Alert service is reachable downstream or upstream from root cause
            if inc.root_cause_service:
                downstream_of_root = get_downstream_services(
                    db=db,
                    service_id=inc.root_cause_service,
                    max_depth=max_dependency_depth,
                    downstream_adj=downstream_adj
                )
                if alert.service in downstream_of_root:
                    is_related = True
                else:
                    upstream_of_root = get_upstream_services(
                        db=db,
                        service_id=inc.root_cause_service,
                        max_depth=max_dependency_depth,
                        upstream_adj=upstream_adj
                    )
                    if alert.service in upstream_of_root:
                        is_related = True

            # Condition 5: Alert service is reachable from any already affected service
            if not is_related and inc.affected_services:
                for aff in inc.affected_services:
                    if are_services_topologically_related(db, aff, alert.service, max_depth=max_dependency_depth):
                        is_related = True
                        break

        if is_related:
            # Correlate alert with this existing incident
            alert.correlation_group_id = inc.id
            inc.alert_count += 1
            inc.updated_at = now
            
            affected = set(inc.affected_services or [])
            affected.add(alert.service)
            inc.affected_services = list(affected)

            # Re-evaluate root cause among all alerts in the incident
            cluster_alerts = db.query(Alert).filter(Alert.correlation_group_id == inc.id).all()
            if alert not in cluster_alerts:
                cluster_alerts.append(alert)

            root_alert, confidence, reason = identify_root_cause(
                db=db,
                alerts=cluster_alerts,
                max_dependency_depth=max_dependency_depth
            )
            inc.root_cause_alert_id = root_alert.id
            inc.root_cause_service = root_alert.service
            inc.root_cause_alert_name = root_alert.alert_name
            inc.root_cause_reason = reason
            inc.confidence_score = confidence
            inc.severity_score = max(inc.severity_score, alert.severity_score)
            
            # If the current alert is NOT the root cause, suppress it as a downstream symptom
            suppression_reason = None
            if alert.service != root_alert.service:
                suppression_reason = (
                    f"Suppressed: downstream alert correlated to active incident {inc.id} "
                    f"(Probable Root Cause: {root_alert.alert_name} on {root_alert.service})"
                )

            logger.info(
                f"Alert {alert.alert_name} correlated into existing incident {inc.id}. "
                f"Root cause: {inc.root_cause_service}"
            )
            return inc, False, suppression_reason

    # 3. No match found -> create a new Incident
    inc_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    new_incident = Incident(
        id=inc_id,
        title=f"Incident: {alert.alert_name} on {alert.service}",
        root_cause_alert_id=alert.id,
        root_cause_service=alert.service,
        root_cause_alert_name=alert.alert_name,
        root_cause_reason=f"Primary anomaly detected in service {alert.service}.",
        confidence_score=92.0,
        severity=alert.severity,
        severity_score=alert.severity_score,
        status="FIRING",
        affected_services=[alert.service],
        alert_count=1,
        suppressed_count=0,
        notifications_count=0,
        created_at=now,
        updated_at=now
    )
    db.add(new_incident)
    db.flush()

    alert.correlation_group_id = inc_id
    logger.info(f"Created new incident {inc_id} for root cause {alert.service}")
    return new_incident, True, None
