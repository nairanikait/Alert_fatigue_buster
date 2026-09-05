import os
import sys
import re
import logging
import datetime
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Canonical environment configuration: load backend/.env as single source of truth
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
canonical_env = os.path.join(backend_dir, ".env")
if os.path.exists(canonical_env):
    load_dotenv(canonical_env, override=False)

try:
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.core.config import settings
except Exception:
    settings = None

logger = logging.getLogger("notification_service.providers.pagerduty")

PAGERDUTY_EVENTS_V2_URL = "https://events.pagerduty.com/v2/enqueue"

class PagerDutyDeliveryError(Exception):
    """Raised when PagerDuty event submission fails."""
    pass

class PagerDutyProvider:
    """
    Real PagerDuty Events API v2 integration.
    Dispatches critical alert events to PagerDuty with intelligent deduplication,
    service attribution, and root cause diagnosis.
    """
    def __init__(self, api_key: Optional[str] = None, endpoint: str = PAGERDUTY_EVENTS_V2_URL):
        self.name = "pagerduty"
        self._api_key = api_key
        self.endpoint = endpoint

    @property
    def api_key(self) -> Optional[str]:
        return (
            self._api_key
            or os.getenv("PAGERDUTY_API_KEY")
            or (getattr(settings, "PAGERDUTY_API_KEY", None) if settings else None)
        )

    def _mask(self, text: Optional[str]) -> str:
        """Safely masks the PagerDuty integration key from any log or error string."""
        if not text:
            return ""
        key = self.api_key
        cleaned = str(text)
        if key and key in cleaned:
            cleaned = cleaned.replace(key, "***")
        return cleaned

    def _map_severity(self, severity: Optional[str]) -> str:
        sev = (severity or "critical").lower()
        if sev in ("critical", "sev1", "p1"):
            return "critical"
        elif sev in ("high", "sev2", "p2", "error"):
            return "error"
        elif sev in ("medium", "sev3", "p3", "warning"):
            return "warning"
        return "info"

    def _build_payload(self, alert: Any) -> Dict[str, Any]:
        alert_id = str(getattr(alert, "id", "unknown-alert"))
        title = getattr(alert, "title", "Critical Alert") or "Critical Alert"
        service = getattr(alert, "service", "system") or "system"
        description = getattr(alert, "description", "") or "No description provided."
        raw_sev = getattr(alert, "severity", "critical")
        pd_sev = self._map_severity(raw_sev)
        root_cause = getattr(alert, "root_cause", None)
        dedup_key = getattr(alert, "dedup_key", None) or alert_id

        now = datetime.datetime.utcnow().isoformat() + "Z"
        dashboard_url = "http://localhost:5173"

        custom_details: Dict[str, Any] = {
            "alert_id": alert_id,
            "service": service,
            "original_severity": raw_sev,
            "description": description,
            "dashboard_url": dashboard_url
        }
        if root_cause and str(root_cause).strip():
            custom_details["root_cause"] = str(root_cause).strip()

        payload = {
            "routing_key": self.api_key,
            "event_action": "trigger",
            "dedup_key": str(dedup_key),
            "payload": {
                "summary": f"[{raw_sev.upper()}] {title} — {service}",
                "source": service,
                "severity": pd_sev,
                "timestamp": now,
                "component": service,
                "custom_details": custom_details
            },
            "client": "Alert Fatigue Buster",
            "client_url": dashboard_url
        }
        return payload

    def send(
        self,
        alert_or_id: Any,
        title: Optional[str] = None,
        severity: Optional[str] = None,
        alert: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Sends an alert event to PagerDuty via Events API v2.
        Supports both direct Alert objects and adapter signature (alert_id, title, severity).
        """
        target_alert = alert
        if target_alert is None:
            if hasattr(alert_or_id, "title") or hasattr(alert_or_id, "id"):
                target_alert = alert_or_id
            else:
                class SimpleAlert:
                    pass
                target_alert = SimpleAlert()
                target_alert.id = str(alert_or_id)
                target_alert.title = title or "Critical Alert"
                target_alert.severity = severity or "critical"
                target_alert.service = "service"
                target_alert.description = title or "PagerDuty notification"
                target_alert.root_cause = None
                target_alert.dedup_key = str(alert_or_id)

        alert_id = getattr(target_alert, "id", str(alert_or_id))
        key = self.api_key

        if not key:
            logger.warning(
                f"[PAGERDUTY] PAGERDUTY_API_KEY is not configured. "
                f"Skipping live PagerDuty notification for alert '{alert_id}'."
            )
            return {
                "channel": "pagerduty",
                "provider": "pagerduty",
                "status": "failed",
                "error": "PAGERDUTY_API_KEY is not configured",
                "alert_id": alert_id
            }

        payload = self._build_payload(target_alert)

        try:
            logger.info(
                f"[PAGERDUTY] Dispatching PagerDuty Events API v2 for alert '{alert_id}' "
                f"(dedup_key='{payload.get('dedup_key')}')"
            )

            resp = requests.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if resp.status_code in (200, 201, 202):
                logger.info(f"[PAGERDUTY] Successfully dispatched alert '{alert_id}' to PagerDuty (status {resp.status_code}).")
                resp_json = {}
                try:
                    resp_json = resp.json()
                except Exception:
                    pass
                return {
                    "channel": "pagerduty",
                    "provider": "pagerduty",
                    "status": "sent",
                    "alert_id": alert_id,
                    "dedup_key": payload.get("dedup_key"),
                    "pagerduty_status": resp_json.get("status", "success")
                }
            else:
                err_msg = f"PagerDuty API returned HTTP {resp.status_code}: {resp.text}"
                masked_err = self._mask(err_msg)
                logger.error(f"[PAGERDUTY] Failed to deliver alert '{alert_id}': {masked_err}")
                return {
                    "channel": "pagerduty",
                    "provider": "pagerduty",
                    "status": "failed",
                    "error": masked_err,
                    "alert_id": alert_id
                }

        except Exception as e:
            masked_err = self._mask(str(e))
            logger.error(f"[PAGERDUTY] Exception dispatching alert '{alert_id}' to PagerDuty: {masked_err}")
            return {
                "channel": "pagerduty",
                "provider": "pagerduty",
                "status": "failed",
                "error": masked_err,
                "alert_id": alert_id
            }
