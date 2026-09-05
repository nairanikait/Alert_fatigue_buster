import asyncio
import datetime
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.config import load_rules
from app.core.database import SessionLocal
from app.core.events import ws_manager
from app.services.batching import batch_buffer
from app.services.routing import router

logger = logging.getLogger("alert_buster.batch_flusher")

class BatchFlushWorker:
    """
    Background worker that periodically flushes buffered alerts into structured digest notifications.
    """
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._flush_lock = asyncio.Lock()

    def is_batch_ready(self, rules: Optional[Dict[str, Any]] = None) -> bool:
        if rules is None:
            rules = load_rules()
        batch_cfg = rules.get("batching", {})
        if not batch_cfg.get("enabled", True):
            return False

        buffered_count = batch_buffer.count()
        if buffered_count == 0:
            return False

        max_alerts = batch_cfg.get("max_alerts", 50)
        if buffered_count >= max_alerts:
            return True

        interval = batch_cfg.get(
            "flush_interval_seconds",
            batch_cfg.get("window_seconds", 30)
        )
        elapsed = (datetime.datetime.utcnow() - batch_buffer.last_flush).total_seconds()
        return elapsed >= interval

    def flush_batch(self, db: Session, rules: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Synchronously flushes current buffered alerts into a digest notification.
        Preserves alerts if dispatch fails.
        """
        if rules is None:
            rules = load_rules()
        batch_cfg = rules.get("batching", {})
        routing_cfg = rules.get("routing", {})

        if batch_buffer.count() == 0:
            return None

        # Take snapshot
        snapshot = batch_buffer.peek()

        # Find primary incident ID if any
        incident_ids = [item.get("incident_id") for item in snapshot if item.get("incident_id")]
        primary_incident_id = incident_ids[0] if incident_ids else None

        # Generate digest without clearing yet
        digest = batch_buffer.generate_digest(
            incident_title=f"Incident {primary_incident_id}" if primary_incident_id else None,
            root_cause="Multi-service burst aggregation",
            clear_buffer=False
        )

        if not digest or digest.get("total_alerts", 0) == 0:
            return None

        channel = routing_cfg.get("digest", routing_cfg.get("low", "email"))

        try:
            notif = router.route_and_dispatch(
                db=db,
                channel=channel,
                title=digest["title"],
                message=digest["message"],
                incident_id=primary_incident_id,
                reason="Periodic scheduled batch digest flush",
                payload=digest
            )
            db.commit()

            # Now clear buffer since delivery succeeded
            batch_buffer.clear()
            logger.info(
                f"[BATCH FLUSH] Delivered digest of {len(snapshot)} alerts to {channel.upper()} (Notif ID #{notif.id})."
            )
            return notif.to_dict()
        except Exception as e:
            logger.error(f"[BATCH FLUSH ERROR] Delivery failed: {e}. Buffered alerts preserved.")
            db.rollback()
            raise e

    async def flush_now(self, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Thread-safe asynchronous trigger to flush pending batch.
        """
        async with self._flush_lock:
            rules = load_rules()
            if batch_buffer.count() == 0:
                return None
            if db is not None:
                return self.flush_batch(db, rules)
            else:
                session = self.session_factory()
                try:
                    res = self.flush_batch(session, rules)
                    if res:
                        asyncio.create_task(ws_manager.broadcast("NOTIFICATION_UPDATE", res))
                    return res
                finally:
                    session.close()

    async def run_loop(self):
        self.is_running = True
        logger.info("Batch flush background worker started.")
        try:
            while self.is_running:
                rules = load_rules()
                batch_cfg = rules.get("batching", {})
                interval = max(
                    1,
                    batch_cfg.get("flush_interval_seconds", batch_cfg.get("window_seconds", 10))
                )

                # Check in short intervals for responsive shutdown
                for _ in range(max(1, interval * 2)):
                    if not self.is_running:
                        break
                    await asyncio.sleep(0.5)

                if self.is_running and self.is_batch_ready(rules):
                    try:
                        await self.flush_now()
                    except Exception as e:
                        logger.warning(f"Error in batch flush cycle: {e}")
        except asyncio.CancelledError:
            logger.info("Batch flush background worker cancelled.")
        finally:
            self.is_running = False

    def start(self):
        if self._task is None or self._task.done():
            self.is_running = True
            self._task = asyncio.create_task(self.run_loop())

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

batch_flusher = BatchFlushWorker()
