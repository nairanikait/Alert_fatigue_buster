import datetime
import logging
from typing import Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.notification import Notification

logger = logging.getLogger("alert_buster.cooldown")

def check_cooldown(
    db: Session,
    incident_id: str,
    severity: str,
    is_flaky: bool,
    cooldown_rules: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Determines if an alert/incident is currently within an adaptive cooldown window.
    Returns: (is_in_cooldown, reason_string)
    """
    # 1. Determine cooldown window
    if is_flaky:
        window_seconds = cooldown_rules.get("flaky_seconds", 1800)
    else:
        sev_key = f"{severity.lower()}_seconds"
        window_seconds = cooldown_rules.get(sev_key, 300)

    # 2. Check last notification sent for this incident
    last_notification = (
        db.query(Notification)
        .filter(Notification.incident_id == incident_id)
        .order_by(Notification.sent_at.desc())
        .first()
    )

    if not last_notification:
        # First notification for this incident is never cooled down
        return False, "Initial notification for incident permitted immediately."

    now = datetime.datetime.utcnow()
    elapsed = (now - last_notification.sent_at).total_seconds()

    if elapsed < window_seconds:
        remaining = int(window_seconds - elapsed)
        reason = (
            f"Suppressed: active cooldown of {window_seconds}s for {severity.upper()} "
            f"severity ({remaining}s remaining before re-notification)."
        )
        logger.info(f"Cooldown active for incident {incident_id}: {reason}")
        return True, reason

    return False, f"Cooldown expired ({int(elapsed)}s elapsed since last notification)."
