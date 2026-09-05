import logging
import httpx
from typing import Dict, Any
from app.adapters.base import BaseNotificationAdapter
from app.adapters.mock import MockNotificationAdapter
from app.core.config import settings

logger = logging.getLogger("alert_buster.adapters.pagerduty")

class PagerDutyAdapter(BaseNotificationAdapter):
    def __init__(self):
        self.api_key = settings.PAGERDUTY_API_KEY
        self.mock = MockNotificationAdapter(channel_name="pagerduty")

    def send(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            logger.info("PagerDuty API key not set. Using MockNotificationAdapter for PagerDuty.")
            return self.mock.send(notification_data)

        # Real PagerDuty Events API v2 call
        try:
            custom_payload = notification_data.get("payload", {})
            raw_sev = notification_data.get("severity") or custom_payload.get("severity", "critical")
            
            # Map severity to PagerDuty valid values: critical, error, warning, info
            sev_map = {
                "critical": "critical",
                "high": "error",
                "medium": "warning",
                "low": "info"
            }
            pd_sev = sev_map.get(str(raw_sev).lower(), "critical")
            source_val = notification_data.get("service") or custom_payload.get("service", "alert-buster")

            payload = {
                "routing_key": self.api_key,
                "event_action": "trigger",
                "payload": {
                    "summary": notification_data.get("title", "Critical Alert"),
                    "severity": pd_sev,
                    "source": str(source_val),
                    "custom_details": custom_payload
                }
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post("https://events.pagerduty.com/v2/enqueue", json=payload)
                if res.status_code in (200, 202):
                    res_data = res.json()
                    logger.info(f"[PAGERDUTY] Successfully dispatched alert to PagerDuty (dedup_key: {res_data.get('dedup_key')})")
                    return {
                        "status": "SENT",
                        "channel": "pagerduty",
                        "provider": "pagerduty",
                        "response": res_data
                    }
                else:
                    logger.error(f"[PAGERDUTY] API error {res.status_code}: {res.text}")
                    return {
                        "status": "FAILED",
                        "channel": "pagerduty",
                        "provider": "pagerduty",
                        "error": res.text
                    }
        except Exception as e:
            logger.error(f"Failed to dispatch to PagerDuty: {e}. Falling back to simulation.")
            return self.mock.send(notification_data)
