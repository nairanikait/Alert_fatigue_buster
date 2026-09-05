import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.service import Service, ServiceDependency
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    
    # Seed base services
    db.add_all([
        Service(id="database", display_name="Database Cluster", criticality=100),
        Service(id="payment-service", display_name="Payment Service", criticality=90),
        Service(id="order-service", display_name="Order Service", criticality=80),
        Service(id="authentication-service", display_name="Auth Service", criticality=90),
        Service(id="api-gateway", display_name="API Gateway", criticality=80),
    ])
    db.add_all([
        ServiceDependency(parent_service="database", child_service="payment-service"),
        ServiceDependency(parent_service="database", child_service="order-service"),
        ServiceDependency(parent_service="database", child_service="authentication-service"),
        ServiceDependency(parent_service="order-service", child_service="api-gateway"),
    ])
    db.commit()

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_1_deduplication_100_identical_alerts(db_session):
    """
    TEST 1: 100 identical alerts within window should result in 1 logical alert
    and 99 duplicates suppressed.
    """
    now = datetime.datetime.utcnow()
    results = []
    
    for i in range(100):
        raw = {
            "source": "prometheus",
            "alert_name": "HighCPU",
            "service": "payment-service",
            "host": "pay-node-1",
            "environment": "production",
            "severity": "high",
            "status": "firing",
            "message": "CPU usage exceeded 90%",
            "timestamp": now + datetime.timedelta(milliseconds=i * 50)
        }
        norm = normalize_generic(raw)
        res = process_alert(db_session, norm)
        results.append(res)

    # Verify in DB
    alerts = db_session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].occurrence_count == 100
    
    suppressed = [r for r in results if r.get("action") == "SUPPRESSED_DUPLICATE"]
    assert len(suppressed) == 99

def test_2_burst_batching(db_session):
    """
    TEST 2: 50 low/medium alerts arriving in a burst should be batched
    instead of producing 50 notifications.
    """
    now = datetime.datetime.utcnow()
    # First alert creates incident
    first = normalize_generic({
        "alert_name": "CacheMissHigh",
        "service": "order-service",
        "severity": "medium",
        "status": "firing",
        "message": "High cache misses on order-service",
        "timestamp": now
    })
    process_alert(db_session, first)

    # 49 subsequent alerts
    batched_count = 0
    for i in range(1, 50):
        raw = normalize_generic({
            "alert_name": f"MinorWarning-{i}",
            "service": "order-service",
            "severity": "low",
            "status": "firing",
            "message": f"Minor warning {i}",
            "timestamp": now + datetime.timedelta(milliseconds=i * 20)
        })
        res = process_alert(db_session, raw)
        if res.get("action") == "BATCHED":
            batched_count += 1

    # Most should be batched
    assert batched_count > 30

def test_3_database_down_correlated_root_cause(db_session):
    """
    TEST 3: DatabaseDown followed by downstream failures should identify
    DatabaseDown as the probable root cause.
    """
    base = datetime.datetime.utcnow()
    
    # 1. DatabaseDown fires at T=0
    db_alert = normalize_generic({
        "alert_name": "DatabaseDown",
        "service": "database",
        "severity": "critical",
        "status": "firing",
        "message": "Postgres connection pool exhausted",
        "timestamp": base
    })
    process_alert(db_session, db_alert)

    # 2. Dependent services fail shortly after (T+1s to T+3s)
    for svc in ["payment-service", "order-service", "authentication-service"]:
        child_alert = normalize_generic({
            "alert_name": f"{svc.title()}ConnectionError",
            "service": svc,
            "severity": "high",
            "status": "firing",
            "message": f"Connection to upstream database timed out",
            "timestamp": base + datetime.timedelta(seconds=1)
        })
        process_alert(db_session, child_alert)

    # Check incident
    incidents = db_session.query(Incident).all()
    assert len(incidents) == 1
    inc = incidents[0]
    
    assert inc.root_cause_service == "database"
    assert inc.root_cause_alert_name == "DatabaseDown"
    assert "database" in inc.root_cause_reason.lower()
    assert inc.confidence_score >= 80.0

def test_4_critical_alert_immediate_dispatch(db_session):
    """
    TEST 4: Critical alert should trigger immediate notification without suppression.
    """
    alert = normalize_generic({
        "alert_name": "DataLossImminent",
        "service": "database",
        "severity": "critical",
        "status": "firing",
        "message": "Immediate attention required",
        "timestamp": datetime.datetime.utcnow()
    })
    res = process_alert(db_session, alert)
    assert res.get("action") == "NOTIFIED"
    assert "notification" in res
    assert res["notification"]["channel"] == "pagerduty"

def test_5_low_severity_routing_email(db_session):
    """
    TEST 5: Low severity alert should route to email/mock channel.
    """
    alert = normalize_generic({
        "alert_name": "DiskUsage70Percent",
        "service": "api-gateway",
        "severity": "low",
        "status": "firing",
        "message": "Disk usage is 70%",
        "timestamp": datetime.datetime.utcnow()
    })
    res = process_alert(db_session, alert)
    assert res.get("action") == "NOTIFIED"
    assert res["notification"]["channel"] == "email"

def test_6_flaky_alert_detection(db_session):
    """
    TEST 6: Alert that repeatedly fires and resolves should be marked as noisy/flaky.
    """
    base = datetime.datetime.utcnow()
    
    for i in range(4):
        # Fire
        f = normalize_generic({
            "alert_name": "FlappingPod",
            "service": "payment-service",
            "severity": "medium",
            "status": "firing",
            "message": "Pod restarted",
            "timestamp": base + datetime.timedelta(seconds=i * 10)
        })
        process_alert(db_session, f)

        # Resolve
        r = normalize_generic({
            "alert_name": "FlappingPod",
            "service": "payment-service",
            "severity": "medium",
            "status": "resolved",
            "message": "Pod healthy",
            "timestamp": base + datetime.timedelta(seconds=i * 10 + 2)
        })
        process_alert(db_session, r)

    # Next occurrence should be detected as flaky
    last_f = normalize_generic({
        "alert_name": "FlappingPod",
        "service": "payment-service",
        "severity": "medium",
        "status": "firing",
        "message": "Pod restarted again",
        "timestamp": base + datetime.timedelta(seconds=50)
    })
    res = process_alert(db_session, last_f)
    alert_record = db_session.query(Alert).filter(Alert.alert_name == "FlappingPod").order_by(Alert.id.desc()).first()
    assert alert_record.is_flaky is True

def test_7_firing_to_resolve_lifecycle(db_session):
    """
    TEST 7: Firing -> resolve lifecycle transition calculates duration.
    """
    t0 = datetime.datetime.utcnow() - datetime.timedelta(seconds=45)
    t1 = datetime.datetime.utcnow()

    # Fire
    fire = normalize_generic({
        "alert_name": "SlowAPI",
        "service": "api-gateway",
        "severity": "high",
        "status": "firing",
        "message": "Response time > 2s",
        "timestamp": t0
    })
    process_alert(db_session, fire)

    alert_in_db = db_session.query(Alert).filter(Alert.alert_name == "SlowAPI").first()
    assert alert_in_db.status in ("FIRING", "ONGOING")

    # Resolve
    resolve = normalize_generic({
        "alert_name": "SlowAPI",
        "service": "api-gateway",
        "severity": "high",
        "status": "resolved",
        "message": "API response time normalized",
        "timestamp": t1
    })
    res = process_alert(db_session, resolve)
    assert res.get("action") == "RESOLVED"

    updated = db_session.query(Alert).filter(Alert.alert_name == "SlowAPI").first()
    assert updated.status == "RESOLVED"
    assert updated.duration_seconds >= 40.0
