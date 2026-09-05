import os
import sys
import logging
import datetime
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv
import resend

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

logger = logging.getLogger("notification_service.providers.email")

class EmailDeliveryError(Exception):
    """Raised when email delivery via Resend fails."""
    pass

class EmailProvider:
    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        default_recipient: Optional[str] = None
    ):
        self.name = "email"
        self._api_key = api_key
        self._from_email = from_email
        self._default_recipient = default_recipient

    @property
    def api_key(self) -> Optional[str]:
        return (
            self._api_key
            or os.getenv("RESEND_API_KEY")
            or (getattr(settings, "RESEND_API_KEY", None) if settings else None)
        )

    @property
    def from_email(self) -> str:
        return (
            self._from_email
            or os.getenv("RESEND_FROM_EMAIL")
            or (getattr(settings, "RESEND_FROM_EMAIL", None) if settings else None)
            or os.getenv("EMAIL_FROM")
            or "onboarding@resend.dev"
        )

    @property
    def default_recipient(self) -> str:
        return (
            self._default_recipient
            or os.getenv("NOTIFICATION_EMAIL")
            or (getattr(settings, "NOTIFICATION_EMAIL", None) if settings else None)
            or "alerts@alertbuster.local"
        )

    def _build_subject(self, alert: Any) -> str:
        sev = (getattr(alert, "severity", "medium") or "medium").upper()
        title = getattr(alert, "title", "Alert") or "Alert"
        service = getattr(alert, "service", "unknown-service") or "unknown-service"
        return f"[{sev}] {title} — {service}"

    def _build_html_body(self, alert: Any, detected_time_str: Optional[str] = None) -> str:
        sev = (getattr(alert, "severity", "medium") or "medium").upper()
        title = getattr(alert, "title", "Alert") or "Alert"
        service = getattr(alert, "service", "unknown-service") or "unknown-service"
        description = getattr(alert, "description", "No description provided.") or "No description provided."
        root_cause = getattr(alert, "root_cause", None)
        status = (getattr(alert, "status", "OPEN") or "OPEN").upper()

        if not detected_time_str:
            detected_time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        root_cause_section = ""
        if root_cause and str(root_cause).strip():
            root_cause_section = f"""
            <div style="margin-top: 12px; padding: 12px; background-color: #1e1e2d; border-radius: 6px; border-left: 3px solid #f59e0b;">
                <span style="font-size: 11px; text-transform: uppercase; color: #9ca3af; font-weight: 600; display: block;">Root Cause</span>
                <span style="color: #fef08a; font-size: 14px; font-weight: 500;">{root_cause}</span>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{sev} Severity Alert</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0;">
    <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #1e293b; border-radius: 10px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);">
        <!-- Header Banner -->
        <tr>
            <td style="padding: 24px; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #ffffff;">
                <span style="display: inline-block; padding: 4px 8px; background: rgba(0,0,0,0.25); border-radius: 4px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
                    {sev} SEVERITY ALERT
                </span>
                <h1 style="margin: 12px 0 0 0; font-size: 20px; font-weight: 700; line-height: 1.3;">
                    {title}
                </h1>
            </td>
        </tr>

        <!-- Alert Details -->
        <tr>
            <td style="padding: 24px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                    <tr>
                        <td width="50%" style="padding-bottom: 12px;">
                            <span style="font-size: 12px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Service</span>
                            <div style="font-size: 15px; font-weight: 600; color: #f8fafc; margin-top: 4px;">{service}</div>
                        </td>
                        <td width="50%" style="padding-bottom: 12px;">
                            <span style="font-size: 12px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Status</span>
                            <div style="font-size: 15px; font-weight: 600; color: #38bdf8; margin-top: 4px;">{status}</div>
                        </td>
                    </tr>
                    <tr>
                        <td width="50%">
                            <span style="font-size: 12px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Detected</span>
                            <div style="font-size: 14px; color: #cbd5e1; margin-top: 4px;">{detected_time_str}</div>
                        </td>
                        <td width="50%">
                            <span style="font-size: 12px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Alert ID</span>
                            <div style="font-size: 14px; font-family: monospace; color: #cbd5e1; margin-top: 4px;">{getattr(alert, 'id', 'N/A')}</div>
                        </td>
                    </tr>
                </table>

                <div style="margin-top: 8px; padding: 14px; background-color: #0f172a; border-radius: 6px; border: 1px solid #334155;">
                    <span style="font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: 600; display: block; margin-bottom: 6px;">Description</span>
                    <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #e2e8f0;">{description}</p>
                </div>

                {root_cause_section}

                <!-- CTA Button -->
                <div style="margin-top: 24px; text-align: center;">
                    <a href="http://localhost:5173" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: #3b82f6; color: #ffffff; text-decoration: none; font-weight: 600; border-radius: 6px; font-size: 14px; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.4);">
                        View Alert Dashboard &rarr;
                    </a>
                </div>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="padding: 16px 24px; background-color: #0f172a; border-top: 1px solid #334155; font-size: 12px; color: #64748b; text-align: center;">
                Alert Fatigue Buster &bull; Automated notification dispatch
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html

    def send(
        self,
        alert_or_id: Any,
        title: Optional[str] = None,
        severity: Optional[str] = None,
        recipient: Optional[str] = None,
        alert: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Sends an email via the Resend API for a standardized Alert.
        Supports both direct Alert objects and adapter signature (alert_id, title, severity).
        """
        # Determine effective alert object or construct minimal representation
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
                target_alert.severity = severity or "medium"
                target_alert.service = "service"
                target_alert.description = title or "Alert notification"
                target_alert.root_cause = None
                target_alert.status = "OPEN"

        alert_id = getattr(target_alert, "id", str(alert_or_id))
        target_recipient = recipient or self.default_recipient
        from_address = self.from_email
        api_key = self.api_key

        if not api_key:
            logger.warning(
                f"[EMAIL] RESEND_API_KEY is not configured in environment. "
                f"Skipping live email delivery for alert '{alert_id}'."
            )
            return {
                "channel": "email",
                "provider": "resend",
                "status": "failed",
                "error": "RESEND_API_KEY is not configured",
                "alert_id": alert_id,
                "recipient": target_recipient
            }

        # Build email content
        subject = self._build_subject(target_alert)
        html_content = self._build_html_body(target_alert)

        try:
            resend.api_key = api_key
            params: resend.Emails.SendParams = {
                "from": from_address,
                "to": [target_recipient],
                "subject": subject,
                "html": html_content
            }

            logger.info(
                f"[EMAIL] Dispatching email via Resend to {target_recipient} for alert '{alert_id}' "
                f"(subject='{subject}')"
            )

            resend_res = resend.Emails.send(params)
            email_id = None
            if isinstance(resend_res, dict):
                email_id = resend_res.get("id")
            elif hasattr(resend_res, "id"):
                email_id = resend_res.id

            logger.info(
                f"[EMAIL] Successfully sent email via Resend for alert '{alert_id}' (Resend ID: {email_id})"
            )

            return {
                "channel": "email",
                "provider": "resend",
                "status": "sent",
                "id": str(email_id or "sent"),
                "alert_id": alert_id,
                "recipient": target_recipient
            }

        except Exception as e:
            # Mask API key from error messages
            err_msg = str(e)
            if api_key and api_key in err_msg:
                err_msg = err_msg.replace(api_key, "***")

            logger.error(
                f"[EMAIL] Resend delivery failed for alert '{alert_id}': {err_msg}",
                exc_info=False
            )

            return {
                "channel": "email",
                "provider": "resend",
                "status": "failed",
                "error": err_msg,
                "alert_id": alert_id,
                "recipient": target_recipient
            }
