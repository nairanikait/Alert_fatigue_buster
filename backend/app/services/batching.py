import datetime
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("alert_buster.batching")

class AlertBatchBuffer:
    """
    Sliding window buffer that aggregates rapid bursts of non-critical alerts into digest batches.
    """
    def __init__(self):
        self.buffer: List[Dict[str, Any]] = []
        self.last_flush = datetime.datetime.utcnow()

    def should_batch(self, severity: str, batch_enabled: bool = True) -> bool:
        """
        Critical alerts bypass batching for immediate dispatch.
        Medium and Low alerts can be batched.
        """
        if not batch_enabled:
            return False
        return severity.lower() in ("medium", "low", "info")

    def add_to_batch(self, alert_data: Dict[str, Any]):
        self.buffer.append(alert_data)

    def peek(self) -> List[Dict[str, Any]]:
        return list(self.buffer)

    def count(self) -> int:
        return len(self.buffer)

    def clear(self):
        self.buffer.clear()
        self.last_flush = datetime.datetime.utcnow()

    def generate_digest(
        self,
        incident_title: Optional[str] = None,
        root_cause: Optional[str] = None,
        clear_buffer: bool = True
    ) -> Dict[str, Any]:
        """
        Builds a structured digest summary from buffered alerts.
        """
        total = len(self.buffer)
        if total == 0:
            return {}

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        services = set()
        alert_types = set()

        for a in self.buffer:
            sev = a.get("severity", "medium").lower()
            counts[sev] = counts.get(sev, 0) + 1
            services.add(a.get("service", "unknown"))
            alert_types.add(a.get("alert_name", "unknown"))

        services_list = sorted(list(services))
        digest_message = (
            f"🚨 ALERT DIGEST\n\n"
            f"{total} alerts detected in active batch window.\n\n"
            f"• Critical: {counts['critical']}\n"
            f"• High: {counts['high']}\n"
            f"• Medium: {counts['medium']}\n"
            f"• Low: {counts['low']}\n\n"
            f"Affected Services ({len(services_list)}):\n"
            + "\n".join([f"  - {s}" for s in services_list[:6]]) + "\n\n"
            f"Likely Root Cause:\n{root_cause or 'Cross-service disturbance'}"
        )

        digest_payload = {
            "title": f"Alert Digest: {total} alerts across {len(services_list)} services",
            "message": digest_message,
            "total_alerts": total,
            "counts": counts,
            "services": services_list,
            "root_cause": root_cause,
            "alerts": list(self.buffer)
        }

        if clear_buffer:
            self.clear()

        return digest_payload

batch_buffer = AlertBatchBuffer()
