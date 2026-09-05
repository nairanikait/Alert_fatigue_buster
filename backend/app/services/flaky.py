import datetime
import logging
from sqlalchemy.orm import Session
from app.models.alert import Alert

logger = logging.getLogger("alert_buster.flaky")

def evaluate_flaky_behavior(
    db: Session,
    fingerprint: str,
    status: str,
    threshold: int = 4,
    window_seconds: int = 120
) -> bool:
    """
    Evaluates whether an alert exhibits noisy/flapping behavior.
    Checks state transitions between FIRING and RESOLVED within window_seconds.
    """
    now = datetime.datetime.utcnow()
    window_start = now - datetime.timedelta(seconds=window_seconds)

    # Query recent alerts for this fingerprint
    recent_alerts = (
        db.query(Alert)
        .filter(
            Alert.fingerprint == fingerprint,
            Alert.timestamp >= window_start
        )
        .all()
    )

    total_fires = sum(a.fire_count for a in recent_alerts)
    total_resolves = sum(a.resolve_count for a in recent_alerts)

    # If the alert has repeatedly fired and resolved, or fired excessively
    state_switches = min(total_fires, total_resolves)
    if state_switches >= 2 or (total_fires >= threshold and total_resolves >= 1):
        logger.warning(
            f"Flaky flapping detected for fingerprint {fingerprint[:8]}... "
            f"(fires: {total_fires}, resolves: {total_resolves})"
        )
        return True

    return False
