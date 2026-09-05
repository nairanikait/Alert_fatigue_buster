import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
import httpx
from app.adapters.base import BaseNotificationAdapter
from app.adapters.mock import MockNotificationAdapter
from app.core.config import settings

logger = logging.getLogger("alert_buster.adapters.email")

class EmailAdapter(BaseNotificationAdapter):
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.sender = settings.EMAIL_FROM
        self.resend_api_key = settings.RESEND_API_KEY
        self.resend_from = settings.RESEND_FROM_EMAIL or "onboarding@resend.dev"
        self.notification_email = settings.NOTIFICATION_EMAIL
        self.mock = MockNotificationAdapter(channel_name="email")

    def send(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        # Priority 1: Resend HTTP API
        if self.resend_api_key:
            return self._send_resend(notification_data)

        # Priority 2: Standard SMTP
        if self.host and self.user:
            return self._send_smtp(notification_data)

        logger.info("Neither Resend nor SMTP configured. Using MockNotificationAdapter for Email.")
        return self.mock.send(notification_data)

    def _send_resend(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        recipient = notification_data.get("recipient") or self.notification_email or self.sender
        title = notification_data.get("title", "Alert Notification")
        message = notification_data.get("message", "")

        html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; margin: 0;">
    <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 8px; border: 1px solid #334155; overflow: hidden;">
        <div style="background: #0284c7; padding: 16px 20px;">
            <h2 style="margin: 0; color: #ffffff; font-size: 18px;">[Alert Buster] {title}</h2>
        </div>
        <div style="padding: 20px; white-space: pre-wrap; line-height: 1.6; color: #e2e8f0; font-size: 14px;">
{message}
        </div>
        <div style="padding: 12px 20px; background: #0f172a; border-top: 1px solid #334155; font-size: 12px; color: #64748b; text-align: center;">
            Alert Fatigue Buster &bull; Intelligent Alert Orchestration
        </div>
    </div>
</body>
</html>"""

        try:
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "from": self.resend_from,
                "to": [recipient],
                "subject": f"[Alert Buster] {title}",
                "html": html_body,
                "text": message
            }

            with httpx.Client(timeout=10.0) as client:
                res = client.post("https://api.resend.com/emails", json=body, headers=headers)

            if res.status_code in (200, 201):
                data = res.json()
                email_id = data.get("id")
                logger.info(f"[RESEND] Successfully dispatched email to {recipient} (Resend ID: {email_id})")
                return {"status": "SENT", "channel": "email", "provider": "resend", "id": email_id}
            else:
                logger.error(f"[RESEND] API rejected delivery (HTTP {res.status_code}): {res.text}")
                return {"status": "FAILED", "channel": "email", "provider": "resend", "error": res.text}
        except Exception as e:
            logger.error(f"[RESEND] Exception during dispatch: {e}")
            return {"status": "FAILED", "channel": "email", "provider": "resend", "error": str(e)}

    def _send_smtp(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            recipient = notification_data.get("recipient", self.sender)
            title = notification_data.get("title", "Alert Notification")
            message = notification_data.get("message", "")

            msg = MIMEMultipart()
            msg["From"] = self.sender
            msg["To"] = recipient
            msg["Subject"] = f"[Alert Buster] {title}"
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(self.host, self.port, timeout=5) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)

            return {"status": "SENT", "channel": "email"}
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}. Falling back to simulation.")
            return self.mock.send(notification_data)
