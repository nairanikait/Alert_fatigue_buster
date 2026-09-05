import datetime
import pytest
from sqlalchemy import inspect
from app.core.database import Base, engine, SessionLocal
from app.models.simulation import Simulation
from app.models.alert import Alert
from app.models.alert_event import AlertEvent
from app.models.incident import Incident
from app.models.notification import Notification
from app.services.alert_processor import process_alert
from app.services.normalization import normalize_generic

@pytest.fixture
def setup_clean_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(AlertEvent).delete()
    db.query(Alert).delete()
    db.query(Incident).delete()
    db.query(Notification).delete()
    db.query(Simulation).delete()
    db.commit()
    yield db
    db.close()

def test_1_database_tables_and_indexes_exist(setup_clean_db):
    """Verify all 5 required entities and indexes are properly created in the database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "simulations" in tables
    assert "alerts" in tables
    assert "alert_events" in tables
    assert "incidents" in tables
    assert "notifications" in tables

    # Verify Alert table columns and indexes
    alert_cols = {c["name"] for c in inspector.get_columns("alerts")}
    assert "simulation_id" in alert_cols
    assert "incident_id" in alert_cols
    assert "raw_payload" in alert_cols
    assert "fingerprint" in alert_cols
    assert "occurrence_count" in alert_cols

    # Verify AlertEvent table columns
    event_cols = {c["name"] for c in inspector.get_columns("alert_events")}
    assert "alert_id" in event_cols
    assert "simulation_id" in event_cols
    assert "incident_id" in event_cols
    assert "event_type" in event_cols
    assert "action" in event_cols
    assert "reason" in event_cols
    assert "details" in event_cols

    # Verify Simulation table columns
    sim_cols = {c["name"] for c in inspector.get_columns("simulations")}
    assert "scenario" in sim_cols
    assert "status" in sim_cols
    assert "total_alerts" in sim_cols
    assert "processed_alerts" in sim_cols
    assert "suppressed_alerts" in sim_cols
    assert "notifications" in sim_cols
    assert "start_time" in sim_cols
    assert "completion_time" in sim_cols

    # Verify Notification failure_reason column
    notif_cols = {c["name"] for c in inspector.get_columns("notifications")}
    assert "failure_reason" in notif_cols

def test_2_single_alert_persistence_and_lifecycle_events(setup_clean_db):
    """Verify a single alert generates persistent Alert, Incident, Notification, and AlertEvent records."""
    db = setup_clean_db
    raw = {
        "source": "prometheus",
        "alert_name": "DatabaseConnectionTimeout",
        "service": "database",
        "host": "db-01",
        "environment": "production",
        "severity": "critical",
        "status": "firing",
        "message": "Database pool exhausted on port 5432",
        "labels": {"cluster": "us-east-1"},
        "simulation_id": "sim_test_001"
    }

    norm = normalize_generic(raw)
    result = process_alert(db, norm)

    assert result["action"] == "NOTIFIED"
    
    # Check Alert in DB
    alerts = db.query(Alert).all()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.alert_name == "DatabaseConnectionTimeout"
    assert alert.service == "database"
    assert alert.simulation_id == "sim_test_001"
    assert alert.occurrence_count == 1
    assert alert.raw_payload["source"] == "prometheus"

    # Check Incident in DB
    incidents = db.query(Incident).all()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.root_cause_service == "database"
    assert alert.correlation_group_id == inc.id

    # Check Notification in DB
    notifs = db.query(Notification).all()
    assert len(notifs) == 1
    assert notifs[0].incident_id == inc.id

    # Check AlertEvents in DB
    events = db.query(AlertEvent).order_by(AlertEvent.id.asc()).all()
    event_types = [e.event_type for e in events]
    assert "RECEIVED" in event_types
    assert "NORMALIZED" in event_types
    assert "CORRELATED" in event_types
    assert "ROUTED" in event_types

def test_3_100_duplicate_alerts_increment_occurrence_count_without_duplicate_notifications(setup_clean_db):
    """Verify that 100 duplicate alerts increment occurrence count on 1 record and log DEDUPLICATED events."""
    db = setup_clean_db
    base_time = datetime.datetime.utcnow()

    for i in range(100):
        raw = {
            "source": "datadog",
            "alert_name": "MemorySpike",
            "service": "payment-service",
            "host": "pay-pod-1",
            "environment": "production",
            "severity": "medium",
            "status": "firing",
            "message": "Heap memory usage at 91%",
            "timestamp": base_time + datetime.timedelta(seconds=i * 0.1),
            "simulation_id": "sim_dedup_100"
        }
        norm = normalize_generic(raw)
        process_alert(db, norm)

    # Must only have 1 unique alert row in alerts table with occurrence_count = 100
    alerts = db.query(Alert).filter(Alert.alert_name == "MemorySpike").all()
    assert len(alerts) == 1
    assert alerts[0].occurrence_count == 100
    assert alerts[0].suppression_category == "duplicate"

    # Must have logged DEDUPLICATED events
    dedup_events = db.query(AlertEvent).filter(AlertEvent.event_type == "DEDUPLICATED").all()
    assert len(dedup_events) == 99  # 1st was new, 99 were duplicates

    # Total notifications must not be 100 (deduplication suppressed the burst)
    notifs = db.query(Notification).all()
    assert len(notifs) <= 1

def test_4_simulation_entity_persistence_and_metrics(setup_clean_db):
    """Verify Simulation entity lifecycle and metrics calculation from real DB data."""
    db = setup_clean_db
    sim_id = "sim_full_lifecycle_001"
    start_time = datetime.datetime.utcnow()

    sim = Simulation(
        id=sim_id,
        scenario="database_outage",
        status="RUNNING",
        total_alerts=50,
        start_time=start_time
    )
    db.add(sim)
    db.commit()

    # Ingest 50 alerts tagged with this simulation
    for i in range(50):
        raw = {
            "source": "prometheus",
            "alert_name": "DBFailure" if i == 0 else "PaymentCascadeFailure",
            "service": "database" if i == 0 else "payment-service",
            "host": "pod-1",
            "environment": "production",
            "severity": "critical" if i == 0 else "high",
            "status": "firing",
            "message": f"Failure event {i}",
            "simulation_id": sim_id
        }
        norm = normalize_generic(raw)
        process_alert(db, norm)

    # Update simulation
    sim.status = "COMPLETED"
    sim.completion_time = datetime.datetime.utcnow()
    sim.processed_alerts = 50
    total_alerts_in_db = db.query(Alert).filter(Alert.simulation_id == sim_id).count()
    assert total_alerts_in_db > 0

    events = db.query(AlertEvent).filter(AlertEvent.simulation_id == sim_id).all()
    assert len(events) >= 50

    db.commit()
    persisted_sim = db.query(Simulation).filter(Simulation.id == sim_id).first()
    assert persisted_sim.status == "COMPLETED"
    assert persisted_sim.total_alerts == 50
