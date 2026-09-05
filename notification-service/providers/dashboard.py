import os
import sys
import logging
import datetime
from typing import Dict, Any, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

# Ensure backend directory is accessible for database & models
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.core.database import SessionLocal
    from app.models.alert import Alert as DbAlert
except Exception:
    SessionLocal = None
    DbAlert = None

logger = logging.getLogger("notification_service.providers.dashboard")

class DatabasePersistenceError(Exception):
    """Raised when alert storage to the persistent database fails."""
    pass

class DashboardProvider:
    def __init__(self, session_factory=None):
        self.name = "dashboard"
        self._session_factory = session_factory or SessionLocal

    def store(self, alert, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Persists a standardized Alert into Supabase PostgreSQL (or SQLite during testing).
        Applies deduplication safety using dedup_key / id.
        """
        own_session = False
        if db is None or not hasattr(db, "query"):
            if not self._session_factory:
                raise DatabasePersistenceError("Database session factory is not configured.")
            db = self._session_factory()
            own_session = True

        try:
            effective_key = alert.dedup_key or alert.id
            now = datetime.datetime.utcnow()

            # Deduplication safety check: find existing alert matching dedup_key or fingerprint
            existing = db.query(DbAlert).filter(
                or_(
                    DbAlert.dedup_key == effective_key,
                    DbAlert.fingerprint == effective_key
                )
            ).first()

            if existing:
                existing.occurrence_count = (existing.occurrence_count or 1) + 1
                existing.last_seen = now
                if alert.title:
                    existing.title = alert.title
                    existing.alert_name = alert.title
                if alert.description:
                    existing.description = alert.description
                    existing.message = alert.description
                if alert.root_cause:
                    existing.root_cause = alert.root_cause
                if alert.severity:
                    existing.severity = alert.severity.upper()

                db.commit()
                db.refresh(existing)

                logger.info(
                    f"[DASHBOARD] Deduplicated alert '{alert.id}' (dedup_key='{effective_key}') "
                    f"-> occurrence_count={existing.occurrence_count} (DB ID: {existing.id})"
                )
                return {
                    "success": True,
                    "action": "deduplicated",
                    "id": str(existing.id),
                    "alert_id": alert.id,
                    "occurrence_count": existing.occurrence_count
                }

            # New alert insertion
            sev_upper = alert.severity.upper()
            sev_score_map = {"CRITICAL": 90.0, "HIGH": 70.0, "MEDIUM": 50.0, "LOW": 20.0}

            new_record = DbAlert(
                fingerprint=effective_key[:64],
                dedup_key=effective_key[:128],
                alert_name=alert.title[:128],
                title=alert.title[:255],
                message=alert.description,
                description=alert.description,
                service=alert.service[:128],
                severity=sev_upper,
                severity_score=sev_score_map.get(sev_upper, 50.0),
                status="OPEN",
                root_cause=alert.root_cause[:255] if alert.root_cause else None,
                source="notification-service",
                timestamp=now,
                first_seen=now,
                last_seen=now,
                occurrence_count=1,
                raw_payload=alert.model_dump() if hasattr(alert, "model_dump") else dict(alert),
                notification_status="SENT"
            )

            db.add(new_record)
            db.commit()
            db.refresh(new_record)

            logger.info(
                f"[DASHBOARD] Stored new alert '{alert.id}' in Supabase (DB ID: {new_record.id}, "
                f"service: {alert.service}, severity: {alert.severity})"
            )

            # Optional: Non-blocking WebSocket broadcast if available
            try:
                from app.core.events import ws_manager
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(ws_manager.broadcast("ALERT_UPDATE", {"alert": new_record.to_dict()}))
                except RuntimeError:
                    pass
            except Exception:
                pass

            return {
                "success": True,
                "action": "stored",
                "id": str(new_record.id),
                "alert_id": alert.id,
                "status": new_record.status
            }

        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error(f"[DASHBOARD] Database persistence error for alert '{alert.id}': {e}", exc_info=True)
            raise DatabasePersistenceError(f"Database persistence failed: {str(e)}") from e
        finally:
            if own_session and db:
                db.close()

    def send(self, alert_id: str, title: str, severity: str, alert=None, db=None) -> bool:
        """
        Adapter method for routing engine dispatch.
        If full alert object is supplied, delegates to self.store().
        """
        if alert is not None:
            res = self.store(alert, db=db)
            return res.get("success", False)
        logger.info(f"[DASHBOARD] Notification recorded for alert '{alert_id}' ({severity})")
        return True
