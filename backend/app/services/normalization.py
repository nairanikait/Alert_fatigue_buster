import datetime
from typing import Dict, Any, List, Optional
from app.utils.fingerprint import generate_fingerprint

def parse_iso_datetime(dt_str: Optional[str]) -> datetime.datetime:
    if not dt_str:
        return datetime.datetime.utcnow()
    try:
        # Standard ISO format parsing
        return datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.datetime.utcnow()

def normalize_generic(data: Dict[str, Any]) -> Dict[str, Any]:
    alert_name = data.get("alert_name", "UnknownAlert")
    service = data.get("service", "unknown-service")
    host = data.get("host")
    environment = data.get("environment", "production")
    severity = (data.get("severity") or "medium").lower()
    status = (data.get("status") or "firing").upper()
    message = data.get("message") or f"Alert {alert_name} for service {service}"
    labels = data.get("labels") or {}
    simulation_id = data.get("simulation_id")
    
    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        ts = parse_iso_datetime(timestamp)
    elif isinstance(timestamp, datetime.datetime):
        ts = timestamp
    else:
        ts = datetime.datetime.utcnow()

    fingerprint = generate_fingerprint(
        alert_name=alert_name,
        service=service,
        host=host,
        environment=environment,
        labels=labels
    )

    return {
        "source": data.get("source", "generic"),
        "alert_name": alert_name,
        "service": service,
        "host": host,
        "environment": environment,
        "severity": severity,
        "status": status,
        "message": message,
        "labels": labels,
        "timestamp": ts,
        "fingerprint": fingerprint,
        "simulation_id": simulation_id
    }

def normalize_prometheus(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalizes Prometheus Alertmanager webhook payload.
    Extracts individual alerts from the 'alerts' list.
    """
    alerts = data.get("alerts", [])
    if not alerts:
        # Check if single alert dict was passed
        if "labels" in data:
            alerts = [data]

    simulation_id = data.get("simulation_id")
    normalized_list = []
    for item in alerts:
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        alert_name = labels.get("alertname") or annotations.get("alertname") or "PrometheusAlert"
        service = labels.get("service") or labels.get("job") or annotations.get("service") or "infrastructure"
        host = labels.get("instance") or labels.get("host")
        environment = labels.get("environment") or labels.get("env") or "production"
        severity = (labels.get("severity") or annotations.get("severity") or "high").lower()
        status = (item.get("status") or "firing").upper()
        
        message = (
            annotations.get("description")
            or annotations.get("summary")
            or annotations.get("message")
            or f"{alert_name} on {service}"
        )
        ts = parse_iso_datetime(item.get("startsAt"))
        
        fingerprint = item.get("fingerprint") or generate_fingerprint(
            alert_name=alert_name,
            service=service,
            host=host,
            environment=environment,
            labels=labels
        )

        normalized_list.append({
            "source": "prometheus",
            "alert_name": alert_name,
            "service": service,
            "host": host,
            "environment": environment,
            "severity": severity,
            "status": status,
            "message": message,
            "labels": labels,
            "timestamp": ts,
            "fingerprint": fingerprint,
            "simulation_id": item.get("simulation_id") or simulation_id
        })

    return normalized_list

def normalize_datadog(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes Datadog webhook payload.
    Extracts tags, alert title, event type, and severity.
    """
    tags = data.get("tags", [])
    parsed_tags = {}
    service = "infrastructure"
    env = "production"
    
    if isinstance(tags, list):
        for tag in tags:
            if ":" in tag:
                k, v = tag.split(":", 1)
                parsed_tags[k] = v
                if k == "service":
                    service = v
                elif k in ("env", "environment"):
                    env = v
    elif isinstance(tags, dict):
        parsed_tags = tags
        service = tags.get("service", service)
        env = tags.get("env", tags.get("environment", env))

    title = data.get("title") or data.get("event_type") or "DatadogAlert"
    alert_name = title.split("[")[0].strip() if "[" in title else title
    host = data.get("hostname")
    simulation_id = data.get("simulation_id")
    
    alert_type = (data.get("alert_type") or "error").lower()
    severity_map = {
        "error": "critical",
        "warning": "high",
        "info": "low",
        "success": "low"
    }
    severity = severity_map.get(alert_type, "high")
    status = "RESOLVED" if alert_type == "success" else "FIRING"
    message = data.get("text_only_msg") or data.get("body") or f"{title} on {service}"
    
    ts = datetime.datetime.utcnow()
    date_val = data.get("date")
    if date_val:
        try:
            ts = datetime.datetime.utcfromtimestamp(date_val)
        except Exception:
            pass

    fingerprint = generate_fingerprint(
        alert_name=alert_name,
        service=service,
        host=host,
        environment=env,
        labels=parsed_tags
    )

    return {
        "source": "datadog",
        "alert_name": alert_name,
        "service": service,
        "host": host,
        "environment": env,
        "severity": severity,
        "status": status,
        "message": message,
        "labels": parsed_tags,
        "timestamp": ts,
        "fingerprint": fingerprint,
        "simulation_id": simulation_id
    }
