import datetime
import logging
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models.alert import Alert

logger = logging.getLogger("alert_buster.deduplication")

def check_deduplication(
    db: Session,
    fingerprint: str,
    timestamp: datetime.datetime,
    window_seconds: int = 30
) -> Tuple[bool, Optional[Alert], Optional[str]]:
    """
    Checks if an alert with identical fingerprint already exists within the deduplication window.
    If yes, increments occurrence count, updates last_seen, and suppresses notification.
    """
    threshold_time = timestamp - datetime.timedelta(seconds=window_seconds)

    # Search for an ongoing or recently firing alert with matching fingerprint
    existing_alert = (
        db.query(Alert)
        .filter(
            Alert.fingerprint == fingerprint,
            Alert.status.in_(["FIRING", "ONGOING"]),
            Alert.last_seen >= threshold_time
        )
        .order_by(Alert.last_seen.desc())
        .first()
    )

    if existing_alert:
        existing_alert.occurrence_count += 1
        existing_alert.last_seen = timestamp
        existing_alert.status = "ONGOING"
        
        reason = (
            f"Suppressed: duplicate alert matching fingerprint {fingerprint[:8]}... "
            f"within {window_seconds}s window ({existing_alert.occurrence_count} occurrences merged)"
        )
        
        logger.info(
            f"Duplicate detected: {existing_alert.alert_name} on {existing_alert.service}. "
            f"Total occurrences: {existing_alert.occurrence_count}"
        )
        return True, existing_alert, reason

    return False, None, None
