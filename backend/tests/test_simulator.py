import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.system_rule import SystemRule
from app.models.service import Service, ServiceDependency

from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed topology
    db.add_all([
        Service(id="database", display_name="Database Cluster", criticality=100),
        Service(id="payment-service", display_name="Payment Service", criticality=90),
        Service(id="order-service", display_name="Order Service", criticality=80),
        Service(id="authentication-service", display_name="Auth Service", criticality=90),
        Service(id="api-gateway", display_name="API Gateway", criticality=80),
        Service(id="checkout", display_name="Checkout Web", criticality=75),
        Service(id="redis", display_name="Redis Cache", criticality=70),
        Service(id="message-queue", display_name="Kafka Queue", criticality=75),
    ])
    db.add_all([
        ServiceDependency(parent_service="database", child_service="payment-service"),
        ServiceDependency(parent_service="database", child_service="order-service"),
        ServiceDependency(parent_service="database", child_service="authentication-service"),
        ServiceDependency(parent_service="order-service", child_service="checkout"),
        ServiceDependency(parent_service="checkout", child_service="api-gateway"),
    ])
    db.commit()
    db.close()
    yield

client = TestClient(app)

def test_database_outage_simulation():
    res = client.post("/api/simulator/database-outage")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_generated"] == 500
    assert data["total_incoming"] == 500
    assert data["suppressed_count"] > 400
    assert data["reduction_percentage"] > 90.0

def test_flaky_pod_simulation():
    res = client.post("/api/simulator/flaky-pod")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_generated"] > 10

def test_alert_storm_simulation():
    res = client.post("/api/simulator/alert-storm?alert_count=100&severity=mixed")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_generated"] == 100

def test_critical_emergency_simulation():
    res = client.post("/api/simulator/critical-emergency")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_generated"] == 1
    # Critical should dispatch to notification channel
    assert data["notifications_dispatched"] >= 1

def test_service_cascade_simulation():
    res = client.post("/api/simulator/service-cascade")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_generated"] > 100

def test_recovery_simulation():
    # First create an incident
    client.post("/api/simulator/critical-emergency")
    # Then recover
    res = client.post("/api/simulator/recovery")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["active_incidents"] == 0

def test_generic_run_dispatcher():
    res = client.post("/api/simulator/run", json={"scenario": "critical_emergency"})
    assert res.status_code == 200
    assert res.json()["status"] == "success"

def test_analytics_alias_endpoint():
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "incoming_alerts" in data
    assert "reduction_percentage" in data
