import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings, load_rules, save_rules
from app.services.security import rate_limiter, security_audit_logger
from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.notification import Notification
from app.models.system_rule import SystemRule

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_state():
    """Cleans rate limiter, security audit buffer, and resets settings & DB rules before/after each test."""
    rate_limiter.reset()
    security_audit_logger.clear()
    orig_secret = settings.WEBHOOK_SECRET

    # Ensure DB has default rules
    db = SessionLocal()
    try:
        entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
        if entry:
            entry.value = load_rules()
            db.commit()
    finally:
        db.close()

    yield

    settings.WEBHOOK_SECRET = orig_secret
    rate_limiter.reset()
    security_audit_logger.clear()

    db = SessionLocal()
    try:
        entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
        if entry:
            entry.value = load_rules()
            db.commit()
    finally:
        db.close()

# 1. Cost calculation with zero alerts
def test_1_cost_calculation_zero_alerts():
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.query(Alert).delete()
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "cost_savings" in data
    cost = data["cost_savings"]
    assert cost["cost_saved_dedup_batching"] == 0.0
    assert cost["cost_saved_routing_triage"] == 0.0
    assert cost["total_cost_saved"] == 0.0
    assert cost["engineering_hours_saved"] == 0.0
    assert cost["interruption_minutes_saved"] == 0.0

# 2. Cost calculation with deduplication
def test_2_cost_calculation_with_deduplication():
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.query(Alert).delete()
        # Create 1 unique alert with occurrence_count = 10 (9 duplicates suppressed)
        a = Alert(
            fingerprint="fp_dedup_test_1",
            source="generic",
            alert_name="HighMemoryUsage",
            service="payment-service",
            severity="HIGH",
            severity_score=75.0,
            status="FIRING",
            message="Memory 90%",
            occurrence_count=10,
            notification_status="SUPPRESSED"
        )
        db.add(a)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    cost = data["cost_savings"]
    # 10 incoming, 0 notifications sent -> 10 suppressed * $4.0 = $40.0
    assert cost["cost_saved_dedup_batching"] == 40.0
    assert cost["incoming_alerts"] == 10
    assert cost["notifications_sent"] == 0
    assert cost["suppressed_alerts"] == 10

# 3. Cost calculation with downstream suppression
def test_3_cost_calculation_downstream_suppression():
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.query(Alert).delete()
        # 2 downstream alerts
        for i in range(2):
            a = Alert(
                fingerprint=f"fp_downstream_{i}",
                source="generic",
                alert_name="PaymentTimeout",
                service="checkout",
                severity="MEDIUM",
                severity_score=50.0,
                status="SUPPRESSED",
                suppression_category="downstream",
                message="Downstream failure",
                occurrence_count=1,
                notification_status="SUPPRESSED"
            )
            db.add(a)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    cost = data["cost_savings"]
    # 2 downstream * $15.0 = $30.0
    assert cost["cost_saved_routing_triage"] == 30.0
    assert cost["downstream_suppressed"] == 2

# 4. Combined cost calculation
def test_4_combined_cost_calculation():
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.query(Alert).delete()
        # 10 raw alerts (1 sent notification, 9 suppressed, including 2 downstream)
        a1 = Alert(
            fingerprint="fp_comb_1",
            source="generic",
            alert_name="DatabaseDown",
            service="database",
            severity="CRITICAL",
            severity_score=95.0,
            status="FIRING",
            message="Database connection pool exhausted",
            occurrence_count=8,
            notification_status="SENT"
        )
        a2 = Alert(
            fingerprint="fp_comb_2",
            source="generic",
            alert_name="QueryError",
            service="payment-service",
            severity="HIGH",
            severity_score=70.0,
            status="SUPPRESSED",
            suppression_category="downstream",
            message="Query timeout from database failure",
            occurrence_count=2,
            notification_status="SUPPRESSED"
        )
        n = Notification(
            channel="pagerduty",
            status="SENT",
            title="Database Outage",
            message="Root cause alert fired"
        )
        db.add_all([a1, a2, n])
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    cost = data["cost_savings"]
    # Total incoming = 8 + 2 = 10. Sent = 1. Suppressed = 9.
    # cost_saved_dedup_batching = (10 - 1) * 4.0 = 36.0
    # cost_saved_routing_triage = 1 downstream * 15.0 = 15.0
    # total_cost_saved = 36.0 + 15.0 = 51.0
    assert cost["cost_saved_dedup_batching"] == 36.0
    assert cost["cost_saved_routing_triage"] == 15.0
    assert cost["total_cost_saved"] == 51.0

# 5. Engineering time calculation
def test_5_engineering_time_calculation():
    db = SessionLocal()
    try:
        db.query(Notification).delete()
        db.query(Alert).delete()
        # 20 incoming alerts, 0 notifications -> 20 suppressed * 3 min = 60 min (1.0 hr)
        a = Alert(
            fingerprint="fp_time_1",
            source="generic",
            alert_name="CPUOverload",
            service="api-gateway",
            severity="HIGH",
            severity_score=75.0,
            status="SUPPRESSED",
            message="CPU spike 95%",
            occurrence_count=20,
            notification_status="SUPPRESSED"
        )
        db.add(a)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    time_saved = data["time_saved"]
    assert time_saved["total_minutes_saved"] == 60.0
    assert time_saved["total_hours_saved"] == 1.0
    assert "1h" in time_saved["human_readable"]

# 6. Configurable cost assumptions
def test_6_configurable_cost_assumptions():
    db = SessionLocal()
    try:
        # Update rules in DB with custom cost values
        custom_rules = {
            "cost_savings": {
                "engineer_hourly_rate": 120.0,
                "interruption_recovery_minutes": 5.0,
                "avoided_interruption_cost": 10.0,
                "avoided_downstream_triage_cost": 25.0
            }
        }
        entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
        if entry:
            entry.value = custom_rules
        else:
            db.add(SystemRule(key="active_rules", value=custom_rules))
        db.commit()

        # Add 10 suppressed alerts (including 1 downstream)
        db.query(Notification).delete()
        db.query(Alert).delete()
        a = Alert(
            fingerprint="fp_custom_cost_1",
            source="generic",
            alert_name="CustomTest",
            service="order-service",
            severity="HIGH",
            severity_score=75.0,
            status="SUPPRESSED",
            suppression_category="downstream",
            message="Custom order failure message",
            occurrence_count=10,
            notification_status="SUPPRESSED"
        )
        db.add(a)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/metrics")
    assert res.status_code == 200
    cost = res.json()["cost_savings"]
    assert cost["avoided_interruption_cost"] == 10.0
    assert cost["avoided_downstream_triage_cost"] == 25.0
    assert cost["cost_saved_dedup_batching"] == 100.0  # 10 * 10.0
    assert cost["cost_saved_routing_triage"] == 25.0   # 1 * 25.0
    assert cost["total_cost_saved"] == 125.0

    # Reset default rules in DB
    db = SessionLocal()
    try:
        entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
        if entry:
            entry.value = load_rules()
            db.commit()
    finally:
        db.close()

# 7. Auth disabled when WEBHOOK_SECRET is not configured
def test_7_auth_disabled_when_no_secret():
    settings.WEBHOOK_SECRET = None
    payload = {
        "alert_name": "TestOpenAuth",
        "service": "authentication-service",
        "message": "Auth disabled check"
    }
    res = client.post("/api/alerts/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

# 8. Valid secret accepted
def test_8_valid_secret_accepted():
    settings.WEBHOOK_SECRET = "super-secret-token-12345"
    payload = {
        "alert_name": "TestValidSecret",
        "service": "database",
        "message": "Authenticated webhook"
    }
    # Via X-API-Key
    res1 = client.post("/api/alerts/webhook", json=payload, headers={"X-API-Key": "super-secret-token-12345"})
    assert res1.status_code == 200
    # Via X-Webhook-Secret
    res2 = client.post("/api/alerts/webhook", json=payload, headers={"X-Webhook-Secret": "super-secret-token-12345"})
    assert res2.status_code == 200

# 9. Missing secret rejected with 401
def test_9_missing_secret_rejected_with_401():
    settings.WEBHOOK_SECRET = "super-secret-token-12345"
    payload = {
        "alert_name": "TestMissingSecret",
        "service": "database",
        "message": "Missing key"
    }
    res = client.post("/api/alerts/webhook", json=payload)
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]

# 10. Invalid secret rejected with 401
def test_10_invalid_secret_rejected_with_401():
    settings.WEBHOOK_SECRET = "super-secret-token-12345"
    payload = {
        "alert_name": "TestInvalidSecret",
        "service": "database",
        "message": "Invalid key attempt"
    }
    res = client.post("/api/alerts/webhook", json=payload, headers={"X-API-Key": "wrong-key-abc"})
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]

# 11. Rate limiting per source
def test_11_rate_limiting_per_source():
    settings.WEBHOOK_SECRET = None
    rate_limiter.reset()

    source = "test-rate-source"
    # Exhaust 150 allowed requests
    for _ in range(150):
        allowed, count, limit = rate_limiter.is_allowed(source, custom_limit=150)
        assert allowed is True

    # 151st request is throttled
    allowed, count, limit = rate_limiter.is_allowed(source, custom_limit=150)
    assert allowed is False
    assert count == 150

# 12. Different sources have independent rate limits
def test_12_different_sources_independent_limits():
    rate_limiter.reset()
    source_a = "prometheus:127.0.0.1"
    source_b = "datadog:127.0.0.1"

    # Fill source A to max limit (e.g. 5 for rapid test)
    for _ in range(5):
        rate_limiter.is_allowed(source_a, custom_limit=5)

    # Source A throttled
    allowed_a, _, _ = rate_limiter.is_allowed(source_a, custom_limit=5)
    assert allowed_a is False

    # Source B must still be permitted!
    allowed_b, _, _ = rate_limiter.is_allowed(source_b, custom_limit=5)
    assert allowed_b is True

# 13 & 14. Rate-limited request returns 429 and Retry-After header exists
def test_13_14_rate_limit_returns_429_with_retry_after():
    settings.WEBHOOK_SECRET = None
    rate_limiter.reset()

    # Artificially fill rate limiter for generic endpoint
    source_key = "generic:testclient"
    for _ in range(150):
        rate_limiter.is_allowed(source_key, custom_limit=150)

    payload = {
        "alert_name": "ThrottledAlert",
        "service": "payment-service",
        "message": "Burst spam"
    }
    res = client.post("/api/alerts/webhook", json=payload)
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    assert res.headers["Retry-After"] == "60"

# 15. Invalid JSON/schema returns 400
def test_15_invalid_json_schema_returns_400():
    # Empty JSON object
    res1 = client.post("/api/alerts/webhook", json={})
    assert res1.status_code == 400

    # Missing alert identifier
    res2 = client.post("/api/alerts/webhook", json={"service": "payment-service"})
    assert res2.status_code == 400

# 16. Security rejection creates audit event
def test_16_security_rejection_creates_audit_event():
    settings.WEBHOOK_SECRET = "sec-test-key"
    security_audit_logger.clear()

    # Trigger 401
    client.post("/api/alerts/webhook", json={"alert_name": "X", "service": "Y", "message": "Z"})

    audit_res = client.get("/api/alerts/security-audit")
    assert audit_res.status_code == 200
    entries = audit_res.json()["entries"]
    assert len(entries) >= 1
    assert entries[0]["reason"] == "AUTH_FAILED"
    assert entries[0]["status_code"] == 401

# 17. Audit buffer never exceeds 50 entries
def test_17_audit_buffer_never_exceeds_50():
    security_audit_logger.clear()
    for i in range(75):
        security_audit_logger.log_event(
            endpoint="/api/alerts/webhook",
            source="test_source",
            client_ip="127.0.0.1",
            reason="RATE_LIMITED",
            status_code=429,
            payload_raw=f"payload_{i}"
        )

    entries = security_audit_logger.get_entries(100)
    assert len(entries) <= 50

# 18. Secrets never appear in audit logs
def test_18_secrets_never_appear_in_audit_logs():
    settings.WEBHOOK_SECRET = "SUPER_SECRET_VALUE_9999"
    security_audit_logger.clear()

    # Attempt with wrong secret
    client.post(
        "/api/alerts/webhook",
        json={"alert_name": "LeakCheck", "service": "api", "message": "msg"},
        headers={"X-API-Key": "WRONG_SECRET_TOKEN"}
    )

    audit_data = client.get("/api/alerts/security-audit").json()
    for entry in audit_data["entries"]:
        log_str = str(entry)
        assert "SUPER_SECRET_VALUE_9999" not in log_str
        assert "WRONG_SECRET_TOKEN" not in log_str

# 19. Prometheus Alertmanager webhook still works
def test_19_prometheus_alertmanager_webhook_works():
    settings.WEBHOOK_SECRET = None
    payload = {
        "version": "4",
        "status": "firing",
        "receiver": "alert-buster-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "PrometheusHighCPU",
                    "service": "database",
                    "severity": "critical"
                },
                "annotations": {
                    "summary": "Database CPU usage is 98%"
                }
            }
        ]
    }
    res = client.post("/api/alerts/prometheus", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["processed_count"] == 1

# 20. Datadog webhook still works
def test_20_datadog_webhook_works():
    settings.WEBHOOK_SECRET = None
    payload = {
        "event_type": "error",
        "title": "Datadog Latency Spike",
        "alert_type": "error",
        "tags": ["service:payment-service", "env:production"],
        "body": "Latency exceeded 2000ms"
    }
    res = client.post("/api/alerts/datadog", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

# 21. Existing generic webhook still works
def test_21_existing_generic_webhook_works():
    settings.WEBHOOK_SECRET = None
    payload = {
        "source": "generic",
        "alert_name": "GenericDiskFull",
        "service": "redis",
        "severity": "high",
        "message": "Disk space critically low at 94%"
    }
    res = client.post("/api/alerts/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["result"]["alert"]["alert_name"] == "GenericDiskFull"

# 22. Existing backend test suite remains passing (executed via pytest)
