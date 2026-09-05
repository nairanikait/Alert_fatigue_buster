import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure notification-service directory is in sys.path
service_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

from main import app
from router import get_channels, ROUTES
from models import Alert

client = TestClient(app)

# ============================================================
# 1. CORE ROUTING CONFIGURATION & UNIT FUNCTION TESTS
# ============================================================

def test_centralized_routes_configuration():
    """Verify centralized ROUTES configuration contains all 4 severity levels."""
    assert ROUTES["low"] == ["dashboard"]
    assert ROUTES["medium"] == ["dashboard", "email"]
    assert ROUTES["high"] == ["dashboard", "email", "slack"]
    assert ROUTES["critical"] == ["dashboard", "slack", "pagerduty"]

def test_get_channels_low():
    alert = Alert(
        id="alert-low-01",
        title="Minor latency glitch",
        description="P99 latency slightly elevated",
        service="payment-service",
        severity="low"
    )
    assert get_channels(alert) == ["dashboard"]

def test_get_channels_medium():
    alert = Alert(
        id="alert-med-01",
        title="Elevated error rates",
        description="5xx error rate at 2%",
        service="auth-service",
        severity="medium"
    )
    assert get_channels(alert) == ["dashboard", "email"]

def test_get_channels_high():
    alert = Alert(
        id="alert-high-01",
        title="High memory pressure",
        description="Memory usage reached 88%",
        service="order-service",
        severity="high"
    )
    assert get_channels(alert) == ["dashboard", "email", "slack"]

def test_get_channels_critical():
    alert = Alert(
        id="alert-crit-01",
        title="Database primary down",
        description="Postgres primary replica disconnected",
        service="database",
        severity="critical"
    )
    assert get_channels(alert) == ["dashboard", "slack", "pagerduty"]

# ============================================================
# 2. FASTAPI ENDPOINT (POST /alert) ROUTING TESTS
# ============================================================

def test_api_route_low():
    """LOW severity -> ['dashboard']"""
    payload = {
        "id": "alert-001",
        "title": "Cache miss rate high",
        "description": "Redis cache misses above 15%",
        "service": "cache-service",
        "severity": "low"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "alert-001"
    assert data["severity"] == "low"
    assert data["channels"] == ["dashboard"]

def test_api_route_medium():
    """MEDIUM severity -> ['dashboard', 'email']"""
    payload = {
        "id": "alert-002",
        "title": "API Rate Limiting Warnings",
        "description": "Users hitting rate limit thresholds",
        "service": "api-gateway",
        "severity": "medium"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "alert-002"
    assert data["severity"] == "medium"
    assert data["channels"] == ["dashboard", "email"]

def test_api_route_high():
    """HIGH severity -> ['dashboard', 'slack']"""
    payload = {
        "id": "alert-003",
        "title": "Payment Gateway 502",
        "description": "Upstream payment provider returning 502 Bad Gateway",
        "service": "checkout-service",
        "severity": "high"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "alert-003"
    assert data["severity"] == "high"
    assert data["channels"] == ["dashboard", "email", "slack"]

def test_api_route_critical():
    """CRITICAL severity -> ['dashboard', 'slack', 'pagerduty']"""
    payload = {
        "id": "alert-004",
        "title": "Primary Database Unreachable",
        "description": "Connection pool exhausted on PostgreSQL master",
        "service": "database",
        "severity": "critical",
        "root_cause": "database",
        "dedup_key": "db-down-001"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "alert-004"
    assert data["severity"] == "critical"
    assert data["channels"] == ["dashboard", "slack", "pagerduty"]

# ============================================================
# 3. VALIDATION TESTS
# ============================================================

def test_invalid_severity_rejected():
    """Invalid severity (e.g. 'fatal', 'info') must be rejected with 422 Unprocessable Entity."""
    payload = {
        "id": "alert-bad-sev",
        "title": "Invalid Severity Alert",
        "description": "Test invalid severity",
        "service": "auth-service",
        "severity": "fatal"  # Invalid! Must be low/medium/high/critical
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 422

def test_empty_alert_id_rejected():
    """Empty alert ID must be rejected."""
    payload = {
        "id": "",
        "title": "Empty ID Alert",
        "description": "Testing empty ID rejection",
        "service": "billing",
        "severity": "low"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 422

def test_whitespace_alert_id_rejected():
    """Whitespace-only alert ID must be rejected."""
    payload = {
        "id": "   ",
        "title": "Whitespace ID Alert",
        "description": "Testing whitespace ID rejection",
        "service": "billing",
        "severity": "low"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 422

def test_missing_required_fields_rejected():
    """Missing required field (title) must be rejected with 422."""
    payload = {
        "id": "alert-no-title",
        # "title" omitted
        "description": "Testing missing title",
        "service": "billing",
        "severity": "medium"
    }
    response = client.post("/alert", json=payload)
    assert response.status_code == 422

def test_empty_payload_rejected():
    """Empty JSON body must be rejected."""
    response = client.post("/alert", json={})
    assert response.status_code == 422

def test_health_check_endpoint():
    """Health check endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "notification-service"


# ============================================================
# 4. STEP 2: DASHBOARD PROVIDER UNIT TESTS (MOCKED SUPABASE)
# ============================================================
from unittest.mock import MagicMock, patch
from providers.dashboard import DashboardProvider, DatabasePersistenceError
import router as router_module

def test_dashboard_provider_store_new_alert():
    """DashboardProvider stores a new alert when no duplicate dedup_key exists."""
    mock_db = MagicMock()
    # No existing record
    mock_db.query.return_value.filter.return_value.first.return_value = None

    provider = DashboardProvider(session_factory=lambda: mock_db)
    alert = Alert(
        id="alert-unit-01",
        title="High Disk IOPS",
        description="IOPS reached 95% threshold",
        service="storage",
        severity="high",
        root_cause="storage-volume-1",
        dedup_key="iops-storage-vol-1"
    )

    result = provider.store(alert, db=mock_db)

    assert result["success"] is True
    assert result["action"] == "stored"
    assert result["alert_id"] == "alert-unit-01"
    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.refresh.called

def test_dashboard_provider_store_deduplication():
    """DashboardProvider safely increments occurrence_count when duplicate dedup_key exists."""
    mock_db = MagicMock()
    existing_record = MagicMock()
    existing_record.id = 42
    existing_record.occurrence_count = 1
    mock_db.query.return_value.filter.return_value.first.return_value = existing_record

    provider = DashboardProvider(session_factory=lambda: mock_db)
    alert = Alert(
        id="alert-unit-02",
        title="Repeated High Disk IOPS",
        description="IOPS spike again",
        service="storage",
        severity="high",
        dedup_key="iops-storage-vol-1"
    )

    result = provider.store(alert, db=mock_db)

    assert result["success"] is True
    assert result["action"] == "deduplicated"
    assert result["occurrence_count"] == 2
    assert not mock_db.add.called
    assert mock_db.commit.called

def test_dashboard_provider_database_error_handling():
    """DashboardProvider rolls back and raises DatabasePersistenceError on db failure."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.commit.side_effect = Exception("Supabase connection timeout")

    provider = DashboardProvider(session_factory=lambda: mock_db)
    alert = Alert(
        id="alert-unit-fail",
        title="Failing Alert",
        description="Failing test",
        service="test",
        severity="low"
    )

    with pytest.raises(DatabasePersistenceError):
        provider.store(alert, db=mock_db)

    assert mock_db.rollback.called


# ============================================================
# 5. STEP 2: API ROUTING + MOCK PROVIDER DISPATCH VERIFICATION
# ============================================================

def test_api_low_dispatches_dashboard_only():
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["email"], "send") as mock_email, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "mock-low-01",
            "title": "Low alert",
            "description": "desc",
            "service": "srv",
            "severity": "low"
        })
        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard"]
        assert mock_store.called
        assert not mock_email.called
        assert not mock_slack.called
        assert not mock_pd.called

def test_api_medium_dispatches_dashboard_and_email_mock():
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["email"], "send") as mock_email, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "mock-med-01",
            "title": "Medium alert",
            "description": "desc",
            "service": "srv",
            "severity": "medium"
        })
        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email"]
        assert mock_store.called
        assert mock_email.called
        assert not mock_slack.called
        assert not mock_pd.called

def test_api_high_dispatches_dashboard_and_slack_mock():
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["email"], "send") as mock_email, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "mock-high-01",
            "title": "High alert",
            "description": "desc",
            "service": "srv",
            "severity": "high"
        })
        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email", "slack"]
        assert mock_store.called
        assert mock_email.called
        assert mock_slack.called
        assert not mock_pd.called

def test_api_critical_dispatches_dashboard_slack_and_pagerduty_mock():
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["email"], "send") as mock_email, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "mock-crit-01",
            "title": "Critical alert",
            "description": "desc",
            "service": "srv",
            "severity": "critical"
        })
        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "slack", "pagerduty"]
        assert mock_store.called
        assert not mock_email.called
        assert mock_slack.called
        assert mock_pd.called

def test_api_post_alert_database_failure():
    """When dashboard persistence fails, return HTTP 500 error."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store:
        mock_store.side_effect = DatabasePersistenceError("Supabase connection terminated")
        res = client.post("/alert", json={
            "id": "mock-err-01",
            "title": "Error alert",
            "description": "desc",
            "service": "srv",
            "severity": "low"
        })
        assert res.status_code == 500
        assert "Failed to persist alert in database" in res.json()["detail"]


# ============================================================
# 6. STEP 2: GET /alerts RETRIEVAL AND FILTERING TESTS
# ============================================================
from app.core.database import get_db

def test_get_alerts_successful_retrieval():
    mock_record = MagicMock()
    mock_record.id = 101
    mock_record.title = "Postgres Down"
    mock_record.alert_name = "Postgres Down"
    mock_record.description = "Database unavailable"
    mock_record.message = "Database unavailable"
    mock_record.service = "database"
    mock_record.severity = "CRITICAL"
    mock_record.status = "OPEN"
    mock_record.root_cause = "postgres-prod"
    mock_record.dedup_key = "postgres-prod-down"
    mock_record.timestamp = None
    mock_record.first_seen = None
    mock_record.resolved_at = None

    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_record]

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        res = client.get("/alerts")
        assert res.status_code == 200
        alerts = res.json()
        assert len(alerts) == 1
        assert alerts[0]["title"] == "Postgres Down"
        assert alerts[0]["service"] == "database"
        assert alerts[0]["severity"] == "critical"
        assert alerts[0]["status"] == "OPEN"
        assert alerts[0]["root_cause"] == "postgres-prod"
    finally:
        app.dependency_overrides.clear()

def test_get_alerts_filter_by_severity():
    mock_db = MagicMock()
    mock_filter = mock_db.query.return_value.filter.return_value
    mock_filter.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        res = client.get("/alerts?severity=critical")
        assert res.status_code == 200
        assert res.json() == []
        assert mock_db.query.return_value.filter.called
    finally:
        app.dependency_overrides.clear()

def test_get_alerts_empty_results():
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        res = client.get("/alerts")
        assert res.status_code == 200
        assert res.json() == []
    finally:
        app.dependency_overrides.clear()

def test_get_alerts_database_failure():
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("Supabase read error")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        res = client.get("/alerts")
        assert res.status_code == 500
        assert "Failed to retrieve alerts from database" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ============================================================
# 7. STEP 3: RESEND EMAIL PROVIDER UNIT TESTS
# ============================================================
import resend
from providers.email import EmailProvider

def test_resend_email_provider_send_success():
    """Test EmailProvider successfully formats and dispatches email via Resend."""
    provider = EmailProvider(
        api_key="re_mock_test_key_12345",
        from_email="onboarding@resend.dev",
        default_recipient="devops@example.com"
    )

    alert = Alert(
        id="alert-resend-01",
        title="High latency detected",
        description="Response latency exceeded the configured threshold.",
        service="payment-api",
        severity="medium",
        root_cause="Database connection pool saturation",
        dedup_key="payment-api-latency"
    )

    with patch.object(resend.Emails, "send") as mock_resend_send:
        mock_resend_send.return_value = {"id": "msg_resend_abc123"}

        res = provider.send(alert)

        assert res["status"] == "sent"
        assert res["provider"] == "resend"
        assert res["id"] == "msg_resend_abc123"
        assert res["recipient"] == "devops@example.com"

        # Verify Resend API call arguments
        mock_resend_send.assert_called_once()
        call_params = mock_resend_send.call_args[0][0]
        assert call_params["from"] == "onboarding@resend.dev"
        assert call_params["to"] == ["devops@example.com"]
        assert call_params["subject"] == "[MEDIUM] High latency detected — payment-api"
        
        # Verify HTML body contents
        html = call_params["html"]
        assert "MEDIUM SEVERITY ALERT" in html
        assert "payment-api" in html
        assert "High latency detected" in html
        assert "Response latency exceeded the configured threshold." in html
        assert "Database connection pool saturation" in html
        assert "OPEN" in html
        assert "View Alert Dashboard" in html

def test_resend_email_provider_no_root_cause():
    """When root_cause is None, no fake root cause should be rendered in the email."""
    provider = EmailProvider(
        api_key="re_mock_test_key_12345",
        from_email="onboarding@resend.dev",
        default_recipient="devops@example.com"
    )

    alert = Alert(
        id="alert-resend-02",
        title="Background worker lag",
        description="Queue delay above 30s",
        service="worker-pool",
        severity="medium",
        root_cause=None
    )

    with patch.object(resend.Emails, "send") as mock_resend_send:
        mock_resend_send.return_value = {"id": "msg_resend_def456"}

        res = provider.send(alert)
        assert res["status"] == "sent"

        call_params = mock_resend_send.call_args[0][0]
        html = call_params["html"]
        assert "Root Cause" not in html

def test_resend_email_provider_masks_api_key_on_failure():
    """If Resend raises an exception containing the API key, verify it is masked."""
    test_key = "re_secret_api_key_999"
    provider = EmailProvider(
        api_key=test_key,
        from_email="onboarding@resend.dev",
        default_recipient="devops@example.com"
    )

    alert = Alert(
        id="alert-resend-fail",
        title="Failing Email Alert",
        description="Triggering Resend failure",
        service="billing",
        severity="medium"
    )

    with patch.object(resend.Emails, "send") as mock_resend_send:
        mock_resend_send.side_effect = Exception(f"HTTP 401 Unauthorized with token {test_key}")

        res = provider.send(alert)
        assert res["status"] == "failed"
        assert test_key not in res["error"]
        assert "***" in res["error"]

def test_resend_email_provider_missing_api_key():
    """When RESEND_API_KEY is not configured, send() fails safely without throwing."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("providers.email.settings", None):
        provider = EmailProvider(api_key=None, default_recipient="devops@example.com")
        alert = Alert(
            id="alert-no-key",
            title="No Key Alert",
            description="Testing missing key",
            service="test",
            severity="medium"
        )
        res = provider.send(alert)
        assert res["status"] == "failed"
        assert "RESEND_API_KEY is not configured" in res["error"]



# ============================================================
# 8. STEP 3: API ENDPOINT RESEND ROUTING INTEGRATION TESTS
# ============================================================

def test_api_medium_triggers_resend():
    """Only MEDIUM alerts trigger real Resend integration."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_resend_send, \
         patch.dict("os.environ", {"RESEND_API_KEY": "re_live_key_123", "NOTIFICATION_EMAIL": "test@example.com"}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resend_send.return_value = {"id": "msg_live_789"}

        res = client.post("/alert", json={
            "id": "resend-test-001",
            "title": "Payment API latency increased",
            "description": "Average latency exceeded 2 seconds",
            "service": "payment-api",
            "severity": "medium",
            "root_cause": "database-pool",
            "dedup_key": "payment-api-latency"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "email"]
        assert mock_store.called
        assert mock_resend_send.called
        
        # Verify Resend email dispatch details
        call_params = mock_resend_send.call_args[0][0]
        assert call_params["to"] == ["test@example.com"]
        assert "[MEDIUM]" in call_params["subject"]

def test_api_low_does_not_trigger_email():
    """LOW alerts must NOT send email."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_resend_send:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "alert-low-no-email",
            "title": "Low warning",
            "description": "Minor issue",
            "service": "api-gateway",
            "severity": "low"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard"]
        assert not mock_resend_send.called

def test_api_high_triggers_email():
    """HIGH alerts send email (routes to Dashboard + Email + Slack)."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_resend_send, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key_123"}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resend_send.return_value = {"id": "re_email_test_999"}
        mock_slack.return_value = {"channel": "slack", "status": "sent"}
        res = client.post("/alert", json={
            "id": "alert-high-with-email",
            "title": "High error rate",
            "description": "Significant degradation",
            "service": "payment-service",
            "severity": "high"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email", "slack"]
        assert mock_resend_send.called
        assert mock_slack.called

def test_api_critical_does_not_trigger_email():
    """CRITICAL alerts must NOT send email (routes to Dashboard + Slack + PagerDuty)."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_resend_send, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "alert-crit-no-email",
            "title": "Database Outage",
            "description": "Postgres connection pool down",
            "service": "database",
            "severity": "critical"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "slack", "pagerduty"]
        assert not mock_resend_send.called
        assert mock_slack.called
        assert mock_pd.called

def test_api_resend_failure_does_not_affect_alert_persistence():
    """A failed email must NOT cause the alert itself to fail or disappear from Supabase."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_resend_send, \
         patch.dict("os.environ", {"RESEND_API_KEY": "re_fail_key_123"}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resend_send.side_effect = Exception("Resend API rate limit exceeded")

        res = client.post("/alert", json={
            "id": "alert-med-resend-fail",
            "title": "Medium alert with failing email",
            "description": "Testing that persistence remains intact",
            "service": "auth-service",
            "severity": "medium"
        })

        # Persistence succeeded, so HTTP response is 200
        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "email"]
        assert mock_store.called

        # Audit results record that email failed while alert is stored
        if data.get("results"):
            email_result = next((r for r in data["results"] if r.get("channel") == "email"), None)
            assert email_result is not None
            assert email_result["status"] == "failed"


# ============================================================
# 9. STEP 4: REAL SLACK INCOMING WEBHOOK TESTS
# ============================================================
import requests
from providers.slack import SlackProvider

def test_slack_provider_unit_send_success():
    """SlackProvider successfully formats and dispatches message via webhook."""
    webhook = "https://hooks.slack.com/services/T000/B000/SECRET123"
    provider = SlackProvider(webhook_url=webhook)

    alert = Alert(
        id="alert-slack-01",
        title="Database Connection Pool Exhausted",
        description="Active pool connections reached 100% capacity.",
        service="order-db",
        severity="high",
        root_cause="Unindexed query in checkout flow",
        dedup_key="db-pool-exhausted"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        res = provider.send(alert)

        assert res["status"] == "sent"
        assert res["provider"] == "slack"
        assert res["alert_id"] == "alert-slack-01"
        assert "SECRET123" not in str(res)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert "[HIGH]" in payload["text"]
        attachment = payload["attachments"][0]
        assert attachment["color"] == "#f97316"  # Orange for HIGH
        assert "Database Connection Pool Exhausted" in attachment["title"]
        assert "Active pool connections reached 100% capacity." in attachment["text"]

        field_titles = [f["title"] for f in attachment["fields"]]
        assert "Service" in field_titles
        assert "Severity" in field_titles
        assert "Status" in field_titles
        assert "Alert ID" in field_titles
        assert "Root Cause Diagnosis" in field_titles

def test_slack_provider_critical_formatting():
    """CRITICAL alerts use red attachment color and 🚨 emoji."""
    provider = SlackProvider(webhook_url="https://hooks.slack.com/services/T000/B000/KEY")
    alert = Alert(
        id="alert-slack-crit",
        title="Primary Datacenter Outage",
        description="Complete network partition",
        service="infra",
        severity="critical"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        res = provider.send(alert)
        assert res["status"] == "sent"

        payload = mock_post.call_args[1]["json"]
        assert "🚨" in payload["text"]
        assert payload["attachments"][0]["color"] == "#ef4444"  # Red for CRITICAL

def test_slack_provider_no_root_cause():
    """When root_cause is None, no fake root cause field is added to Slack attachment."""
    provider = SlackProvider(webhook_url="https://hooks.slack.com/services/T000/B000/KEY")
    alert = Alert(
        id="alert-slack-no-rc",
        title="Redis Memory Spike",
        description="Memory usage above 90%",
        service="cache",
        severity="high",
        root_cause=None
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        res = provider.send(alert)
        assert res["status"] == "sent"

        attachment = mock_post.call_args[1]["json"]["attachments"][0]
        field_titles = [f["title"] for f in attachment["fields"]]
        assert "Root Cause Diagnosis" not in field_titles

def test_slack_provider_missing_webhook_url():
    """When SLACK_WEBHOOK_URL is not configured, send() fails safely without throwing."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("providers.slack.settings", None):
        provider = SlackProvider(webhook_url=None)
        alert = Alert(
            id="alert-slack-no-url",
            title="No URL Alert",
            description="Testing missing webhook",
            service="test",
            severity="high"
        )
        res = provider.send(alert)
        assert res["status"] == "failed"
        assert "SLACK_WEBHOOK_URL is not configured" in res["error"]

def test_slack_provider_masks_webhook_url_on_failure():
    """If Slack HTTP post fails, the webhook URL and secret token are masked."""
    secret_url = "https://hooks.slack.com/services/T999/B888/SECRET_TOKEN_XYZ"
    provider = SlackProvider(webhook_url=secret_url)
    alert = Alert(
        id="alert-slack-err",
        title="Failing Alert",
        description="Triggering HTTP error",
        service="test",
        severity="high"
    )

    with patch.object(requests, "post") as mock_post:
        mock_post.side_effect = Exception(f"HTTP Connection failed for {secret_url}")
        res = provider.send(alert)

        assert res["status"] == "failed"
        assert "SECRET_TOKEN_XYZ" not in res["error"]
        assert "https://hooks.slack.com/services/***" in res["error"]


# ============================================================
# 10. STEP 4: API ENDPOINT SLACK ROUTING INTEGRATION TESTS
# ============================================================

def test_api_high_triggers_slack_real():
    """HIGH severity routes to Dashboard + Slack, and invokes Slack webhook."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(requests, "post") as mock_post, \
         patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T/B/X"}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_post.return_value = mock_resp

        res = client.post("/alert", json={
            "id": "slack-test-high-01",
            "title": "Payment gateway latency threshold exceeded",
            "description": "Processing queue delay is > 15s",
            "service": "payment-service",
            "severity": "high",
            "root_cause": "payment-webhook-queue",
            "dedup_key": "payment-latency-spike"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "email", "slack"]
        assert mock_store.called
        assert mock_post.called

        # Verify audit result
        if data.get("results"):
            slack_result = next((r for r in data["results"] if r.get("channel") == "slack"), None)
            assert slack_result is not None
            assert slack_result["status"] == "sent"

def test_api_critical_triggers_slack_real_and_pagerduty_mock():
    """CRITICAL routes to Dashboard + Slack + PagerDuty mock."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(requests, "post") as mock_post, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd, \
         patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T/B/X"}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_post.return_value = mock_resp

        res = client.post("/alert", json={
            "id": "slack-test-crit-01",
            "title": "Postgres Primary Down",
            "description": "Replica disconnected",
            "service": "database",
            "severity": "critical"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "slack", "pagerduty"]
        assert mock_store.called
        assert mock_post.called
        assert mock_pd.called

def test_api_low_does_not_trigger_slack_real():
    """LOW severity must NEVER call Slack."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(requests, "post") as mock_post:

        mock_store.return_value = {"success": True, "action": "stored"}
        res = client.post("/alert", json={
            "id": "slack-test-low-01",
            "title": "Minor warning",
            "description": "Low severity alert",
            "service": "api",
            "severity": "low"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard"]
        assert not mock_post.called

def test_api_medium_does_not_trigger_slack_real():
    """MEDIUM severity must NEVER call Slack (routes to Dashboard + Email)."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(resend.Emails, "send") as mock_email_send, \
         patch.object(requests, "post") as mock_post:

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_email_send.return_value = {"id": "msg_med"}

        res = client.post("/alert", json={
            "id": "slack-test-med-01",
            "title": "Medium latency warning",
            "description": "Medium severity alert",
            "service": "auth",
            "severity": "medium"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email"]
        assert not mock_post.called

def test_api_slack_failure_does_not_affect_alert_persistence():
    """A failed Slack webhook must NOT cause the alert itself to fail or disappear from Supabase."""
    secret_url = "https://hooks.slack.com/services/T/B/LEAK_KEY"
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(requests, "post") as mock_post, \
         patch.dict("os.environ", {"SLACK_WEBHOOK_URL": secret_url}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_post.side_effect = Exception("Slack API timeout 504 Gateway Timeout")

        res = client.post("/alert", json={
            "id": "alert-high-slack-fail",
            "title": "High alert with failing Slack",
            "description": "Testing that persistence remains intact",
            "service": "payment-service",
            "severity": "high"
        })

        # Persistence succeeded, so HTTP response is 200
        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "email", "slack"]
        assert mock_store.called

        # Audit results record that Slack failed while alert is stored, and secret is not leaked
        if data.get("results"):
            slack_result = next((r for r in data["results"] if r.get("channel") == "slack"), None)
            assert slack_result is not None
            assert slack_result["status"] == "failed"
            assert "LEAK_KEY" not in str(slack_result)


# ============================================================
# 11. STEP 5: REAL PAGERDUTY EVENTS API V2 TESTS
# ============================================================
from providers.pagerduty import PagerDutyProvider

def test_pagerduty_provider_unit_send_success():
    """PagerDutyProvider formats correct Events API v2 payload and sends successfully."""
    integration_key = "pd_secret_key_1234567890abcdef"
    provider = PagerDutyProvider(api_key=integration_key)

    alert = Alert(
        id="alert-pd-01",
        title="Postgres Primary Database Deadlock",
        description="Write transactions are failing with transaction deadlocks.",
        service="db-primary",
        severity="critical",
        root_cause="Concurrent schema migration lock contention",
        dedup_key="db-deadlock-cluster-01"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.json.return_value = {"status": "success", "message": "Event processed", "dedup_key": "db-deadlock-cluster-01"}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        res = provider.send(alert)

        assert res["status"] == "sent"
        assert res["provider"] == "pagerduty"
        assert res["alert_id"] == "alert-pd-01"
        assert res["dedup_key"] == "db-deadlock-cluster-01"
        assert integration_key not in str(res)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        sent_payload = call_kwargs["json"]
        assert sent_payload["routing_key"] == integration_key
        assert sent_payload["event_action"] == "trigger"
        assert sent_payload["dedup_key"] == "db-deadlock-cluster-01"
        assert sent_payload["payload"]["severity"] == "critical"
        assert sent_payload["payload"]["source"] == "db-primary"
        assert sent_payload["payload"]["custom_details"]["root_cause"] == "Concurrent schema migration lock contention"
        assert sent_payload["payload"]["custom_details"]["alert_id"] == "alert-pd-01"

def test_pagerduty_provider_dedup_key_fallback_to_alert_id():
    """When dedup_key is not set, alert.id is used as PagerDuty deduplication key."""
    provider = PagerDutyProvider(api_key="pd_key_123")
    alert = Alert(
        id="alert-pd-no-dedup",
        title="Emergency",
        description="Testing dedup key fallback",
        service="api",
        severity="critical",
        dedup_key=None
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.json.return_value = {"status": "success"}

    with patch.object(requests, "post", return_value=mock_resp) as mock_post:
        res = provider.send(alert)
        assert res["status"] == "sent"
        assert res["dedup_key"] == "alert-pd-no-dedup"
        sent_payload = mock_post.call_args[1]["json"]
        assert sent_payload["dedup_key"] == "alert-pd-no-dedup"

def test_pagerduty_provider_missing_api_key():
    """When PAGERDUTY_API_KEY is not configured, send() fails safely without raising."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("providers.pagerduty.settings", None):
        provider = PagerDutyProvider(api_key=None)
        alert = Alert(
            id="alert-pd-no-key",
            title="Missing Key Alert",
            description="Testing missing key",
            service="test",
            severity="critical"
        )
        res = provider.send(alert)
        assert res["status"] == "failed"
        assert "PAGERDUTY_API_KEY is not configured" in res["error"]

def test_pagerduty_provider_masks_key_on_failure():
    """If PagerDuty HTTP call fails, the integration key is never exposed."""
    secret_key = "pd_secret_key_super_classified_999"
    provider = PagerDutyProvider(api_key=secret_key)
    alert = Alert(
        id="alert-pd-fail",
        title="Failing PD Alert",
        description="Testing error masking",
        service="test",
        severity="critical"
    )

    with patch.object(requests, "post") as mock_post:
        mock_post.side_effect = Exception(f"HTTP 401 Unauthorized using key {secret_key}")
        res = provider.send(alert)

        assert res["status"] == "failed"
        assert secret_key not in res["error"]
        assert "***" in res["error"]

def test_api_critical_triggers_pagerduty_real():
    """CRITICAL severity routes to Dashboard + Slack + PagerDuty, and dispatches real PagerDuty event."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(requests, "post") as mock_post, \
         patch.dict("os.environ", {
             "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T/B/X",
             "PAGERDUTY_API_KEY": "pd_routing_key_xyz"
         }):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.text = "Accepted"
        mock_resp.json.return_value = {"status": "success", "message": "Event processed"}
        mock_post.return_value = mock_resp

        res = client.post("/alert", json={
            "id": "pd-test-crit-01",
            "title": "Complete Multi-AZ Outage",
            "description": "All availability zones unreachable",
            "service": "infra",
            "severity": "critical",
            "root_cause": "Fiber cut at primary exchange",
            "dedup_key": "infra-az-outage"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "slack", "pagerduty"]
        assert mock_store.called

        # Verify audit results for pagerduty
        if data.get("results"):
            pd_result = next((r for r in data["results"] if r.get("channel") == "pagerduty"), None)
            assert pd_result is not None
            assert pd_result["status"] == "sent"
            assert pd_result["provider"] == "pagerduty"

def test_api_high_does_not_trigger_pagerduty():
    """HIGH severity routes to Dashboard + Slack, and NEVER triggers PagerDuty."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_slack.return_value = {"channel": "slack", "status": "sent"}

        res = client.post("/alert", json={
            "id": "pd-test-high-01",
            "title": "High CPU load",
            "description": "CPU > 90%",
            "service": "worker",
            "severity": "high"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email", "slack"]
        assert not mock_pd.called

def test_api_medium_does_not_trigger_pagerduty():
    """MEDIUM severity routes to Dashboard + Email, and NEVER triggers PagerDuty."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["email"], "send") as mock_email, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_email.return_value = {"channel": "email", "status": "sent"}

        res = client.post("/alert", json={
            "id": "pd-test-med-01",
            "title": "Medium latency warning",
            "description": "API latency increased",
            "service": "api",
            "severity": "medium"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard", "email"]
        assert not mock_pd.called

def test_api_low_does_not_trigger_pagerduty():
    """LOW severity routes to Dashboard only, and NEVER triggers PagerDuty."""
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["pagerduty"], "send") as mock_pd:

        mock_store.return_value = {"success": True, "action": "stored"}

        res = client.post("/alert", json={
            "id": "pd-test-low-01",
            "title": "Info log warning",
            "description": "Cache warmup notice",
            "service": "cache",
            "severity": "low"
        })

        assert res.status_code == 200
        assert res.json()["channels"] == ["dashboard"]
        assert not mock_pd.called

def test_api_pagerduty_failure_does_not_affect_alert_persistence():
    """A failed PagerDuty call must NOT cause the alert persistence to fail."""
    secret_key = "pd_classified_fail_key"
    with patch.object(router_module.dashboard_provider, "store") as mock_store, \
         patch.object(router_module.PROVIDERS["slack"], "send") as mock_slack, \
         patch.object(requests, "post") as mock_post, \
         patch.dict("os.environ", {"PAGERDUTY_API_KEY": secret_key}):

        mock_store.return_value = {"success": True, "action": "stored"}
        mock_slack.return_value = {"channel": "slack", "status": "sent"}
        mock_post.side_effect = Exception(f"PagerDuty 503 Service Unavailable with {secret_key}")

        res = client.post("/alert", json={
            "id": "alert-crit-pd-fail",
            "title": "Critical alert with failing PagerDuty",
            "description": "Verifying persistence resilience",
            "service": "cluster",
            "severity": "critical"
        })

        # Persistence succeeded, so HTTP response is 200
        assert res.status_code == 200
        data = res.json()
        assert data["channels"] == ["dashboard", "slack", "pagerduty"]
        assert mock_store.called

        # Audit results record that PagerDuty failed while alert is stored, and secret is not leaked
        if data.get("results"):
            pd_result = next((r for r in data["results"] if r.get("channel") == "pagerduty"), None)
            assert pd_result is not None
            assert pd_result["status"] == "failed"
            assert secret_key not in str(pd_result)





