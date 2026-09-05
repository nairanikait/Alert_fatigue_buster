import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure notification-service is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
notif_dir = os.path.join(os.path.dirname(backend_dir), "notification-service")
if notif_dir not in sys.path:
    sys.path.insert(0, notif_dir)

from app.main import app as main_app
from main import app as standalone_app
from router import get_channels, ROUTES
from models import Alert

# ============================================================
# 1. TEST STANDALONE NOTIFICATION SERVICE
# ============================================================

@pytest.fixture
def standalone_client():
    return TestClient(standalone_app)

@pytest.fixture
def backend_client():
    return TestClient(main_app)

def test_centralized_routes():
    assert ROUTES["low"] == ["dashboard"]
    assert ROUTES["medium"] == ["dashboard", "email"]
    assert ROUTES["high"] == ["dashboard", "email", "slack"]
    assert ROUTES["critical"] == ["dashboard", "slack", "pagerduty"]

def test_routing_low(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "alert-low-01",
        "title": "Low warning",
        "description": "Minor issue",
        "service": "api-gateway",
        "severity": "low"
    })
    assert res.status_code == 200
    assert res.json()["channels"] == ["dashboard"]

def test_routing_medium(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "alert-med-01",
        "title": "Medium warning",
        "description": "Moderate issue",
        "service": "auth-service",
        "severity": "medium"
    })
    assert res.status_code == 200
    assert res.json()["channels"] == ["dashboard", "email"]

def test_routing_high(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "alert-high-01",
        "title": "High error rate",
        "description": "Significant degradation",
        "service": "payment-service",
        "severity": "high"
    })
    assert res.status_code == 200
    assert res.json()["channels"] == ["dashboard", "email", "slack"]

def test_routing_critical(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "alert-crit-01",
        "title": "Database Outage",
        "description": "Postgres connection pool down",
        "service": "database",
        "severity": "critical"
    })
    assert res.status_code == 200
    assert res.json()["channels"] == ["dashboard", "slack", "pagerduty"]

def test_invalid_severity(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "alert-bad",
        "title": "Bad severity",
        "description": "Testing invalid severity rejection",
        "service": "billing",
        "severity": "catastrophic"
    })
    assert res.status_code == 422

def test_empty_id(standalone_client):
    res = standalone_client.post("/alert", json={
        "id": "",
        "title": "Empty ID",
        "description": "Testing empty id rejection",
        "service": "billing",
        "severity": "low"
    })
    assert res.status_code == 422

# ============================================================
# 2. TEST MOUNTED ROUTE ON MAIN BACKEND APP (INTEGRATION)
# ============================================================

def test_main_backend_mounted_alert_route(backend_client):
    res = backend_client.post("/alert", json={
        "id": "main-crit-01",
        "title": "Critical Alert via Main App",
        "description": "Testing mounted routing endpoint",
        "service": "order-service",
        "severity": "critical"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["alert_id"] == "main-crit-01"
    assert data["severity"] == "critical"
    assert data["channels"] == ["dashboard", "slack", "pagerduty"]
