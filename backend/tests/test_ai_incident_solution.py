import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.incident import Incident
from app.models.alert import Alert
from app.models.service import Service, ServiceDependency
from app.services.ai_incident_copilot import (
    build_incident_context,
    validate_and_normalize_ai_response,
    generate_deterministic_sre_analysis,
    analyze_incident_with_ai,
)
from app.api.incidents import get_or_generate_ai_incident_analysis, AIAnalysisRequest
from fastapi import HTTPException


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    try:
        # Seed test services and dependencies
        db.add(Service(id="database", display_name="PostgreSQL", criticality=90))
        db.add(Service(id="payment-service", display_name="Payment API", criticality=85))
        db.add(Service(id="order-service", display_name="Order Service", criticality=80))
        db.add(ServiceDependency(parent_service="database", child_service="payment-service"))
        db.add(ServiceDependency(parent_service="payment-service", child_service="order-service"))

        # Seed test incident
        inc = Incident(
            id="INC-TEST-001",
            title="Database Connection Pool Exhaustion Outage",
            root_cause_service="database",
            root_cause_alert_name="DatabaseConnectionExhausted",
            root_cause_reason="Active connections reached max_connections pool capacity",
            confidence_score=94.0,
            severity="CRITICAL",
            status="FIRING",
            affected_services=["database", "payment-service", "order-service"],
            alert_count=500,
            suppressed_count=493,
            notifications_count=1,
            evidence=["Database pool metric 100% saturation at T=0"]
        )
        db.add(inc)

        # Seed root alert and some suppressed alerts
        root_alert = Alert(
            id=1,
            alert_name="DatabaseConnectionExhausted",
            fingerprint="fp-db-connection-001",
            service="database",
            severity="CRITICAL",
            status="FIRING",
            notification_status="SENT",
            occurrence_count=1,
            correlation_group_id="INC-TEST-001",
            message="FATAL: remaining connection slots reserved for non-replication superuser connections"
        )
        suppressed_alert = Alert(
            id=2,
            alert_name="PaymentTimeout",
            fingerprint="fp-payment-timeout-002",
            service="payment-service",
            severity="HIGH",
            status="FIRING",
            notification_status="SUPPRESSED",
            occurrence_count=250,
            correlation_group_id="INC-TEST-001",
            message="Payment transaction timeout waiting for database connection"
        )
        db.add(root_alert)
        db.add(suppressed_alert)
        db.commit()

        yield db
    finally:
        db.close()


def test_1_incident_context_construction_and_no_secrets(memory_db):
    """Verifies that incident context is properly structured and contains zero secrets."""
    inc = memory_db.query(Incident).filter(Incident.id == "INC-TEST-001").first()
    ctx = build_incident_context(memory_db, inc)

    assert ctx["incident_id"] == "INC-TEST-001"
    assert ctx["severity"] == "CRITICAL"
    assert ctx["affected_service"] == "database"
    assert ctx["root_cause_alert"] == "DatabaseConnectionExhausted"
    assert ctx["correlated_alert_count"] == 500
    assert ctx["suppressed_alert_count"] == 493
    assert "database" in ctx["affected_services"]
    assert "payment-service" in ctx["affected_services"]
    assert any("database -> payment-service" in rel for rel in ctx["dependency_relationships"])

    # Stringified check: Absolutely no credentials or private tokens
    ctx_str = str(ctx).lower()
    for secret_keyword in ["secret", "password", "api_key", "token", "webhook", "bearer", "smtp"]:
        assert secret_keyword not in ctx_str or secret_keyword in ["paymenttimeout"]  # ensure no credentials leak


def test_2_deterministic_sre_fallback(memory_db):
    """Verifies the deterministic fallback generates 3 levels of actionable recommendations."""
    inc = memory_db.query(Incident).filter(Incident.id == "INC-TEST-001").first()
    ctx = build_incident_context(memory_db, inc)
    analysis = generate_deterministic_sre_analysis(ctx)

    assert len(analysis["immediate_mitigation"]) >= 3
    assert len(analysis["investigation_steps"]) >= 3
    assert len(analysis["long_term_prevention"]) >= 3
    assert analysis["confidence"] >= 70
    assert analysis["risk_level"] == "CRITICAL"
    assert "database" in analysis["root_cause_explanation"].lower()
    assert len(analysis["technical_reasoning"]) >= 2
    assert analysis["provider"] == "built-in SRE engine"


def test_3_response_validation_and_normalization():
    """Verifies that missing or partial AI responses are safely normalized."""
    ctx = {
        "incident_id": "INC-TEST-001",
        "affected_service": "auth-service",
        "root_cause_alert": "JWTSigningFailure",
        "root_cause_reason": "Signing key rotated with invalid format",
        "affected_services": ["auth-service", "api-gateway"],
        "confidence_score": 88.0,
        "severity": "HIGH",
        "correlated_alert_count": 40,
        "suppressed_alert_count": 39,
    }

    # Partial payload missing mitigation steps
    partial_ai_output = {
        "summary": "JWT authentication error on auth-service.",
        "root_cause_explanation": "Malformed signing key.",
        "confidence": "92",
    }

    normalized = validate_and_normalize_ai_response(partial_ai_output, ctx)
    assert normalized["summary"] == "JWT authentication error on auth-service."
    assert normalized["confidence"] == 92
    assert len(normalized["immediate_mitigation"]) >= 3
    assert len(normalized["investigation_steps"]) >= 3
    assert len(normalized["long_term_prevention"]) >= 3
    assert normalized["risk_level"] == "HIGH"


def test_4_api_endpoint_caching_and_regeneration(memory_db):
    """Verifies that the endpoint caches analysis and regenerates upon request."""
    # First call: generates analysis
    res1 = asyncio.run(
        get_or_generate_ai_incident_analysis(
            incident_id="INC-TEST-001",
            req=AIAnalysisRequest(regenerate=False),
            db=memory_db
        )
    )
    assert res1["incident_id"] == "INC-TEST-001"
    assert "analysis" in res1
    assert res1["cached"] is False
    assert len(res1["analysis"]["immediate_mitigation"]) >= 3

    # Second call without regenerate: returns cached version instantly
    res2 = asyncio.run(
        get_or_generate_ai_incident_analysis(
            incident_id="INC-TEST-001",
            req=AIAnalysisRequest(regenerate=False),
            db=memory_db
        )
    )
    assert res2["cached"] is True
    assert res2["analysis"]["summary"] == res1["analysis"]["summary"]

    # Third call with regenerate=True: regenerates fresh analysis
    res3 = asyncio.run(
        get_or_generate_ai_incident_analysis(
            incident_id="INC-TEST-001",
            req=AIAnalysisRequest(regenerate=True),
            db=memory_db
        )
    )
    assert res3["cached"] is False


def test_5_api_endpoint_404_handling(memory_db):
    """Verifies 404 when incident does not exist."""
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_or_generate_ai_incident_analysis(
                incident_id="INC-DOES-NOT-EXIST",
                req=AIAnalysisRequest(regenerate=False),
                db=memory_db
            )
        )
    assert exc_info.value.status_code == 404
