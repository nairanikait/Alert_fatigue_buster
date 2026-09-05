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

logger = logging.getLogger("notification_service.providers.slack")

class SlackDeliveryError(Exception):
    """Raised when Slack webhook dispatch fails."""
    pass

class SlackProvider:
    def __init__(self, webhook_url: Optional[str] = None):
        self.name = "slack"
        self._webhook_url = webhook_url

    @property
    def webhook_url(self) -> Optional[str]:
        return (
            self._webhook_url
            or os.getenv("SLACK_WEBHOOK_URL")
            or (getattr(settings, "SLACK_WEBHOOK_URL", None) if settings else None)
        )

    def _mask(self, text: Optional[str]) -> str:
        """Safely masks webhook URL from any log or error string."""
        if not text:
            return ""
        url = self.webhook_url
        cleaned = str(text)
        if url and url in cleaned:
            cleaned = cleaned.replace(url, "https://hooks.slack.com/services/***")
        return re.sub(r"https://hooks\.slack\.com/services/\S+", "https://hooks.slack.com/services/***", cleaned)

    def _build_payload(self, alert: Any) -> Dict[str, Any]:
        sev = (getattr(alert, "severity", "high") or "high").upper()
        title = getattr(alert, "title", "Alert") or "Alert"
        service = getattr(alert, "service", "unknown-service") or "unknown-service"
        description = getattr(alert, "description", "No description provided.") or "No description provided."
        alert_id = str(getattr(alert, "id", "N/A"))
        root_cause = getattr(alert, "root_cause", None)
        status = (getattr(alert, "status", "OPEN") or "OPEN").upper()

        now = datetime.datetime.utcnow()
        time_str = now.strftime("%Y-%m-%d %H:%M UTC")

        # Color-code based on severity
        color_map = {
            "CRITICAL": "#ef4444",  # Red
            "HIGH": "#f97316",      # Orange
            "MEDIUM": "#eab308",    # Yellow
            "LOW": "#3b82f6"        # Blue
        }
        color = color_map.get(sev, "#f97316")

        emoji_map = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "⚡",
            "LOW": "ℹ️"
        }
        emoji = emoji_map.get(sev, "⚠️")

        fields = [
            {"title": "Service", "value": f"`{service}`", "short": True},
            {"title": "Severity", "value": f"*{sev}*", "short": True},
            {"title": "Status", "value": status, "short": True},
            {"title": "Alert ID", "value": f"`{alert_id}`", "short": True},
            {"title": "Detected At", "value": time_str, "short": True},
        ]

        if root_cause and str(root_cause).strip():
            fields.append({
                "title": "Root Cause Diagnosis",
                "value": f"🔍 {root_cause}",
                "short": False
            })

        dashboard_url = "http://localhost:5173"

        payload = {
            "text": f"{emoji} *[{sev}]* {title} — `{service}`",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} [{sev}] {title}",
                    "title_link": dashboard_url,
                    "text": description,
                    "fields": fields,
                    "footer": f"Alert Fatigue Buster • <{dashboard_url}|View Dashboard>",
                    "footer_icon": "https://api.iconify.design/heroicons:shield-check-solid.svg",
                    "ts": int(now.timestamp())
                }
            ]
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
        Sends an alert message to Slack via Incoming Webhook.
        Supports both direct Alert objects and adapter signature (alert_id, title, severity).
        """
        # Determine target alert
        target_alert = alert
        if target_alert is None:
            if hasattr(alert_or_id, "title") or hasattr(alert_or_id, "id"):
                target_alert = alert_or_id
            else:
                class SimpleAlert:
                    pass
                target_alert = SimpleAlert()
                target_alert.id = str(alert_or_id)
                target_alert.title = title or "Alert"
                target_alert.severity = severity or "high"
                target_alert.service = "service"
                target_alert.description = title or "Alert notification"
                target_alert.root_cause = None
                target_alert.status = "OPEN"

        alert_id = getattr(target_alert, "id", str(alert_or_id))
        url = self.webhook_url

        if not url:
            logger.warning(
                f"[SLACK] SLACK_WEBHOOK_URL is not configured. "
                f"Skipping live Slack notification for alert '{alert_id}'."
            )
            return {
                "channel": "slack",
                "provider": "slack",
                "status": "failed",
                "error": "SLACK_WEBHOOK_URL is not configured",
                "alert_id": alert_id
            }

        payload = self._build_payload(target_alert)

        try:
            logger.info(
                f"[SLACK] Dispatching Slack webhook for alert '{alert_id}' "
                f"([{getattr(target_alert, 'severity', 'high').upper()}])"
            )

            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if resp.status_code == 200:
                logger.info(f"[SLACK] Successfully dispatched alert '{alert_id}' to Slack.")
                return {
                    "channel": "slack",
                    "provider": "slack",
                    "status": "sent",
                    "alert_id": alert_id
                }
            else:
                err_msg = f"Slack webhook returned HTTP {resp.status_code}: {resp.text}"
                masked_err = self._mask(err_msg)
                logger.error(f"[SLACK] Failed to deliver alert '{alert_id}': {masked_err}")
                return {
                    "channel": "slack",
                    "provider": "slack",
                    "status": "failed",
                    "error": masked_err,
                    "alert_id": alert_id
                }

        except Exception as e:
            masked_err = self._mask(str(e))
            logger.error(f"[SLACK] Exception dispatching alert '{alert_id}' to Slack: {masked_err}")
            return {
                "channel": "slack",
                "provider": "slack",
                "status": "failed",
                "error": masked_err,
                "alert_id": alert_id
            }
