import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.service import Service, ServiceDependency
from app.services.simulation_runner import simulation_manager

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
simulation_manager.session_factory = TestingSessionLocal

@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    simulation_manager.session_factory = TestingSessionLocal
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add_all([
        Service(id="database", display_name="Database Cluster", criticality=100),
        Service(id="payment-service", display_name="Payment Service", criticality=90),
        Service(id="order-service", display_name="Order Service", criticality=80),
        Service(id="authentication-service", display_name="Auth Service", criticality=90),
        Service(id="api-gateway", display_name="API Gateway", criticality=80),
    ])
    db.commit()
    db.close()
    yield

def test_start_and_get_simulation():
    client = TestClient(app)
    
    # 1. Start simulation
    res = client.post("/api/simulations", json={
        "scenario": "critical_emergency",
        "speed": "slow",
        "force_stop_active": True
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert "simulation_id" in data
    assert data["scenario"] == "critical_emergency"
    assert data["target_count"] == 1
    sim_id = data["simulation_id"]

    # 2. Status by ID
    status_res = client.get(f"/api/simulations/{sim_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["simulation_id"] == sim_id
    assert status_data["status"] in ["RUNNING", "COMPLETED"]

    # 3. Active check
    active_res = client.get("/api/simulations/active")
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert "active" in active_data

    # Give simulation a moment to process event
    time.sleep(0.1)

    # 4. Get events
    events_res = client.get(f"/api/simulations/{sim_id}/events")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert "events" in events_data
    assert len(events_data["events"]) >= 1

def test_stop_simulation():
    client = TestClient(app)
    # Start slow high volume
    res = client.post("/api/simulations", json={
        "scenario": "alert_storm",
        "count": 500,
        "speed": "slow",
        "force_stop_active": True
    })
    assert res.status_code == 200
    sim_id = res.json()["simulation_id"]

    # Stop simulation
    stop_res = client.post(f"/api/simulations/{sim_id}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"
