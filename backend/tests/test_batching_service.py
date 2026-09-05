import pytest
import datetime
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.notification import Notification
from app.models.service import Service, ServiceDependency
from app.services.batching import batch_buffer
from app.services.batch_flusher import BatchFlushWorker, batch_flusher
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def db():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    
    # Seed topology
    session.add(Service(id="order-service", display_name="Order Service", criticality=80))
    session.add(Service(id="database", display_name="Database", criticality=100))
    session.commit()

    batch_buffer.clear()
    yield session
    batch_buffer.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_1_multiple_alerts_enter_same_batch():
    """1. Multiple alerts enter the same batch."""
    batch_buffer.clear()
    for i in range(5):
        batch_buffer.add_to_batch({
            "alert_id": i + 1,
            "alert_name": f"DiskWarning-{i}",
            "service": "order-service",
            "severity": "low"
        })
    assert batch_buffer.count() == 5
    assert len(batch_buffer.peek()) == 5

def test_2_batch_does_not_send_when_not_ready():
    """2. Batch does not send when it should wait (under count and window)."""
    batch_buffer.clear()
    batch_buffer.add_to_batch({
        "alert_id": 1,
        "alert_name": "LowMem",
        "service": "order-service",
        "severity": "low"
    })
    batch_buffer.last_flush = datetime.datetime.utcnow()

    worker = BatchFlushWorker()
    rules = {
        "batching": {
            "enabled": True,
            "max_alerts": 50,
            "flush_interval_seconds": 60
        }
    }
    assert worker.is_batch_ready(rules) is False

def test_3_and_4_periodic_flush_sends_digest_and_clears_buffer(db):
    """3 & 4. Flush sends digest once ready and removes flushed batch."""
    batch_buffer.clear()
    for i in range(3):
        batch_buffer.add_to_batch({
            "alert_id": i + 1,
            "alert_name": f"Warning-{i}",
            "service": "order-service",
            "severity": "medium",
            "incident_id": "INC-TEST-1"
        })

    # Artificially expire the window
    batch_buffer.last_flush = datetime.datetime.utcnow() - datetime.timedelta(seconds=45)

    worker = BatchFlushWorker()
    rules = {
        "batching": {
            "enabled": True,
            "max_alerts": 50,
            "flush_interval_seconds": 30
        },
        "routing": {
            "digest": "email"
        }
    }

    assert worker.is_batch_ready(rules) is True
    res = worker.flush_batch(db, rules)

    assert res is not None
    assert res["channel"] == "email"
    assert "Alert Digest" in res["title"]

    # Verify buffer cleared
    assert batch_buffer.count() == 0

    # Verify persisted in database
    notif = db.query(Notification).filter(Notification.id == res["id"]).first()
    assert notif is not None
    assert notif.channel == "email"

def test_5_failed_delivery_does_not_lose_buffered_alerts(db):
    """5. Failed delivery restores buffered alerts and does not lose data."""
    batch_buffer.clear()
    batch_buffer.add_to_batch({
        "alert_id": 101,
        "alert_name": "CriticalWarning",
        "service": "order-service",
        "severity": "low"
    })

    worker = BatchFlushWorker()
    rules = {
        "batching": {"enabled": True, "max_alerts": 1, "flush_interval_seconds": 1},
        "routing": {"digest": "email"}
    }

    with patch("app.services.routing.router.route_and_dispatch", side_effect=RuntimeError("SMTP Outage")):
        with pytest.raises(RuntimeError):
            worker.flush_batch(db, rules)

    # Buffer must retain the alert for retry
    assert batch_buffer.count() == 1
    assert batch_buffer.peek()[0]["alert_id"] == 101

def test_6_multiple_flush_cycles_do_not_duplicate(db):
    """6. Multiple flush cycles on empty buffer return None without duplicate notifications."""
    batch_buffer.clear()
    worker = BatchFlushWorker()
    rules = {"batching": {"enabled": True, "flush_interval_seconds": 1}}

    # Empty flush
    res = worker.flush_batch(db, rules)
    assert res is None
    assert db.query(Notification).count() == 0

@pytest.mark.asyncio
async def test_7_worker_lifecycle_clean_start_stop():
    """7. Application/test shutdown cleanly stops the background worker."""
    worker = BatchFlushWorker()
    worker.start()
    assert worker.is_running is True
    assert worker._task is not None

    await asyncio.sleep(0.05)
    await worker.stop()
    assert worker.is_running is False
    assert worker._task is None

def test_8_critical_alert_bypasses_batching(db):
    """8. Critical alerts immediately dispatch and bypass the batch buffer."""
    batch_buffer.clear()
    now = datetime.datetime.utcnow()
    alert = normalize_generic({
        "alert_name": "DatabaseOutage",
        "service": "database",
        "severity": "critical",
        "status": "firing",
        "timestamp": now
    })

    res = process_alert(db, alert)
    assert res["action"] == "NOTIFIED"
    # Not added to batch buffer
    assert batch_buffer.count() == 0
