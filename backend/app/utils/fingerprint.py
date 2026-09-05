import hashlib
import json
from typing import Dict, Any, Optional

def generate_fingerprint(
    alert_name: str,
    service: str,
    host: Optional[str] = None,
    environment: str = "production",
    labels: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a deterministic SHA256 fingerprint for alert deduplication.
    Uses normalized alert name, service, host, environment, and sorted label keys.
    """
    normalized_alert = (alert_name or "").strip().lower()
    normalized_service = (service or "").strip().lower()
    normalized_host = (host or "none").strip().lower()
    normalized_env = (environment or "production").strip().lower()

    # Filter out dynamic timestamps or run IDs from labels for stable deduplication
    label_str = ""
    if labels:
        stable_labels = {
            k.lower(): str(v).lower()
            for k, v in labels.items()
            if k.lower() not in ("timestamp", "time", "id", "run_id", "epoch")
        }
        sorted_items = sorted(stable_labels.items())
        label_str = json.dumps(sorted_items, separators=(",", ":"))

    raw_key = f"{normalized_alert}|{normalized_service}|{normalized_host}|{normalized_env}|{label_str}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]
