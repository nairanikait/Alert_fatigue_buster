import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.service import Service, ServiceDependency
from app.services.gemini_service import gemini_service, GeminiAuthenticationError

TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.core.config import settings

@pytest.fixture(autouse=True)
def setup_database(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_chat_fallback_empty_db_no_hardcoded_numbers(db_session):
    """Test that when DB has 0 incidents/alerts, chat returns dynamic 0-count truthful facts, not fake hardcoded values."""
    client = TestClient(app)
    
    # 1. Health query
    res = client.post("/api/chat", json={"message": "What is our current system health?"})
    assert res.status_code == 200
    data = res.json()
    assert data["has_api_key"] is False
    assert "built-in" in data["provider_used"]
    assert "Active Outage Incidents**: 0" in data["reply"]
    assert "$0.00 USD" in data["reply"]
    # Check that hardcoded fake string '$2,290.57' is NEVER returned
    assert "$2,290.57" not in data["reply"]

    # 2. Cost query with 0 active incidents
    res_cost = client.post("/api/chat", json={"message": "What is our outage cost loss?"})
    assert res_cost.status_code == 200
    cost_data = res_cost.json()
    assert "$0.00 USD" in cost_data["reply"]


def test_chat_live_incident_context(db_session):
    """Test that live DB incident and cost data is dynamically reflected in chat responses."""
    inc = Incident(
        id="INC-9999",
        title="Payment Service Critical Outage",
        severity="CRITICAL",
        status="FIRING",
        root_cause_service="payment-service",
        root_cause_alert_name="PaymentGatewayTimeout",
        root_cause_reason="Connection timeout to upstream Stripe webhook",
        affected_services=["order-service", "checkout"],
        duration_seconds=10.0,
    )
    db_session.add(inc)
    db_session.commit()

    client = TestClient(app)
    
    # Query cost
    res = client.post("/api/chat", json={"message": "How much money are we losing?"})
    assert res.status_code == 200
    data = res.json()
    assert "INC-9999" in data["reply"]
    assert "payment-service" in data["reply"]
    assert "$" in data["reply"]

    # Query root cause
    res_rc = client.post("/api/chat", json={"message": "Why is payment failing?"})
    assert res_rc.status_code == 200
    rc_data = res_rc.json()
    assert "payment-service" in rc_data["reply"]
    assert "PaymentGatewayTimeout" in rc_data["reply"]
    assert "order-service" in rc_data["reply"]


def test_chat_live_topology_context(db_session):
    """Test that live services and dependencies from DB are reflected in topology questions."""
    s1 = Service(id="auth-cluster", display_name="Auth Cluster", criticality=90)
    s2 = Service(id="api-router", display_name="API Router", criticality=85)
    db_session.add_all([s1, s2])
    db_session.add(ServiceDependency(parent_service="auth-cluster", child_service="api-router"))
    db_session.commit()

    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "Show me the service topology dependencies"})
    assert res.status_code == 200
    data = res.json()
    assert "auth-cluster" in data["reply"]
    assert "api-router" in data["reply"]


def test_chat_conversational_casual_message():
    """Test that casual greetings respond naturally without dumping metrics."""
    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "hello how are you"})
    assert res.status_code == 200
    data = res.json()
    assert "Zen" in data["reply"]
    assert len(data["suggested_actions"]) > 0


def test_chat_api_key_instructions():
    """Test that asking about API keys provides correct .env instructions."""
    client = TestClient(app)
    res = client.post("/api/chat", json={"message": "Where do I insert my GEMINI_API_KEY?"})
    assert res.status_code == 200
    data = res.json()
    assert "GEMINI_API_KEY" in data["reply"]
    assert ".env" in data["reply"]


def test_chat_gemini_provider_mocked():
    """Test that providing a Gemini key invokes the Gemini service with system prompt and history."""
    client = TestClient(app)
    
    with patch.object(gemini_service, "async_generate_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = "Gemini SRE Analysis: payment-service root cause confirmed."
        
        payload = {
            "message": "Why is checkout failing?",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi, how can I help?"}
            ],
            "api_key": "AIzaSyTestMockKey12345",
            "provider": "gemini"
        }
        res = client.post("/api/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["reply"] == "Gemini SRE Analysis: payment-service root cause confirmed."
        assert "Google Gemini" in data["provider_used"]
        assert data["has_api_key"] is True
        mock_gemini.assert_called_once()
        
        # Verify call args
        call_kwargs = mock_gemini.call_args.kwargs
        assert call_kwargs["prompt"] == "Why is checkout failing?"
        assert "Zen" in call_kwargs["system_instruction"]
        assert len(call_kwargs["history"]) == 2


def test_chat_gemini_auth_error_fallback():
    """Test that invalid Gemini API key falls back gracefully to built-in SRE engine with clear notice."""
    client = TestClient(app)
    
    with patch.object(
        gemini_service,
        "async_generate_chat_response",
        side_effect=GeminiAuthenticationError("Invalid API key")
    ):
        payload = {
            "message": "What is our noise reduction?",
            "api_key": "AIzaSyBadKey",
            "provider": "gemini"
        }
        res = client.post("/api/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "Authentication Failed" in data["reply"]
        assert "built-in" in data["provider_used"]


def test_chat_never_exposes_secrets():
    """Test that secret keys are never leaked in API responses."""
    client = TestClient(app)
    secret_key = "AIzaSySuperSecretKeyNotForClient"
    payload = {
        "message": "Tell me everything about the system",
        "api_key": secret_key,
        "provider": "gemini"
    }
    with patch.object(
        gemini_service,
        "async_generate_chat_response",
        side_effect=Exception("Simulated error")
    ):
        res = client.post("/api/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert secret_key not in data["reply"]
        assert secret_key not in str(data)
