from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.utils.fingerprint import generate_fingerprint

def test_autosolve_suppressed_endpoint_integration():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    try:
        fp = generate_fingerprint("TestSuppressedMemoryAlert", "order-service", host="worker-1")
        # Seed a test suppressed alert
        test_alert = Alert(
            alert_name="TestSuppressedMemoryAlert",
            service="order-service",
            host="worker-1",
            fingerprint=fp,
            environment="production",
            status="FIRING",
            notification_status="SUPPRESSED",
            suppression_category="duplicate",
            message="Test suppressed alert for autosolve verification",
            occurrence_count=5
        )
        db.add(test_alert)
        db.commit()
        db.refresh(test_alert)

        alert_id = test_alert.id

        # Import endpoint function and invoke it
        from app.api.alerts import autosolve_suppressed_alerts
        import asyncio

        res = asyncio.run(autosolve_suppressed_alerts(db=db))
        assert res["status"] == "success"
        assert res["solved_count"] >= 1
        assert "pipeline_stages" in res
        assert len(res["pipeline_stages"]) == 5

        # Verify DB state of the alert
        updated = db.query(Alert).filter(Alert.id == alert_id).first()
        assert updated.status == "RESOLVED"
        assert updated.notification_status == "SENT"
        assert updated.resolved_at is not None

        # Verify lifecycle event was created
        evt = db.query(AlertEvent).filter(
            AlertEvent.alert_id == alert_id,
            AlertEvent.action == "AUTOSOLVED"
        ).first()
        assert evt is not None
        assert evt.event_type == "RESOLVED"

    finally:
        db.close()
