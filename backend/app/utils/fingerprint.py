import hashlib
import json
from typing import Dict, Any, Optional

def generate_fingerprint(
    alert_name: str,
    service: str,
    host: Optional[str] = None,
    environment: str = "production",
    labels: Optional[Dict[str, Any]] = None,
    cluster: Optional[str] = None,
    namespace: Optional[str] = None,
    region: Optional[str] = None,
    source: Optional[str] = None,
    severity: Optional[str] = None,
    component: Optional[str] = None,
    resource_id: Optional[str] = None,
    custom_attributes: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates a deterministic SHA256 fingerprint for alert deduplication and correlation.

    Parameters:
        alert_name (str): The name/type of the firing alert (e.g., 'HighCpuUsage', 'PostgreSqlDown').
        service (str): Affected service or application (e.g., 'payment-service', 'auth-api').
        host (Optional[str]): Hostname, IP, or node identifier (e.g., 'worker-node-01'). Defaults to 'none'.
        environment (str): Deployment tier (e.g., 'production', 'staging'). Defaults to 'production'.
        labels (Optional[Dict[str, Any]]): Arbitrary monitoring labels or tags from Prometheus/Datadog.
        cluster (Optional[str]): Kubernetes or database cluster name (e.g., 'k8s-prod-us-east-1').
        namespace (Optional[str]): Kubernetes namespace or logical tenancy boundary (e.g., 'payments').
        region (Optional[str]): Cloud availability zone or region (e.g., 'us-east-1', 'eu-west-1').
        source (Optional[str]): Ingestion source tool (e.g., 'prometheus', 'datadog', 'cloudwatch', 'sentry').
        severity (Optional[str]): Alert severity level (e.g., 'critical', 'high', 'medium', 'low').
        component (Optional[str]): Specific subsystem or service component (e.g., 'connection-pool', 'cache').
        resource_id (Optional[str]): Target resource ARN, container ID, pod name, or disk partition.
        custom_attributes (Optional[Dict[str, Any]]): Extra dynamic or domain-specific dimensions to hash.

    Returns:
        str: 32-character hexadecimal deterministic hash for reliable alert deduplication.
    """
    normalized_alert = (alert_name or "").strip().lower()
    normalized_service = (service or "").strip().lower()
    normalized_host = (host or "none").strip().lower()
    normalized_env = (environment or "production").strip().lower()

    # Normalize topological and infrastructure dimensions
    normalized_cluster = (cluster or "").strip().lower()
    normalized_namespace = (namespace or "").strip().lower()
    normalized_region = (region or "").strip().lower()
    normalized_source = (source or "").strip().lower()
    normalized_severity = (severity or "").strip().lower()
    normalized_component = (component or "").strip().lower()
    normalized_resource = (resource_id or "").strip().lower()

    # Merge labels with custom attributes
    combined_labels = dict(labels or {})
    if custom_attributes:
        combined_labels.update(custom_attributes)

    # Filter out volatile/dynamic timestamps and ephemeral trace identifiers
    label_str = ""
    if combined_labels:
        volatile_keys = {
            "timestamp", "time", "id", "run_id", "epoch",
            "trace_id", "span_id", "correlation_id", "inserted_at"
        }
        stable_labels = {
            str(k).lower(): str(v).lower()
            for k, v in combined_labels.items()
            if str(k).lower() not in volatile_keys
        }
        sorted_items = sorted(stable_labels.items())
        label_str = json.dumps(sorted_items, separators=(",", ":"))

    # Core identity fields
    key_parts = [
        normalized_alert,
        normalized_service,
        normalized_host,
        normalized_env,
    ]

    # Optional topological & infrastructure dimensions
    if normalized_cluster:
        key_parts.append(f"cluster:{normalized_cluster}")
    if normalized_namespace:
        key_parts.append(f"ns:{normalized_namespace}")
    if normalized_region:
        key_parts.append(f"region:{normalized_region}")
    if normalized_source:
        key_parts.append(f"source:{normalized_source}")
    if normalized_severity:
        key_parts.append(f"severity:{normalized_severity}")
    if normalized_component:
        key_parts.append(f"component:{normalized_component}")
    if normalized_resource:
        key_parts.append(f"resource:{normalized_resource}")

    key_parts.append(label_str)
    raw_key = "|".join(key_parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]
