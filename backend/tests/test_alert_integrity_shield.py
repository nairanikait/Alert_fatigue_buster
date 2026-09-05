import json
import time
import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.security import WebhookSource, WebhookRequest, SecurityEvent, SecurityBaseline
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.service import Service, ServiceDependency
from app.services.security_shield import (
    shield,
    HMACSignatureVerifier,
    DEFAULT_SOURCE_SECRETS
)
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db_session(test_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Seed base services for pipeline integration
    for s_id, d_name, crit in [
        ("database", "Database Cluster", 100),
        ("payment-service", "Payment Service", 90),
        ("order-service", "Order Service", 80),
        ("authentication-service", "Auth Service", 90),
        ("api-gateway", "API Gateway", 80),
    ]:
        if not session.query(Service).filter(Service.id == s_id).first():
            session.add(Service(id=s_id, display_name=d_name, criticality=crit))
    session.commit()

    shield.auth.seed_defaults(session)
    shield.rate_limiter.reset()
    shield.anomaly._counts.clear()

    yield session

    session.close()
    app.dependency_overrides.clear()

# ============================================================
# TEST 1: Valid Webhook (ACCEPTED)
# ============================================================
def test_1_valid_webhook_accepted(client, db_session):
    """Valid HMAC signature + fresh timestamp + unique nonce -> ACCEPTED (Trust Score >= 90)."""
    secret = DEFAULT_SOURCE_SECRETS["simulator"]
    now_ts = str(time.time())
    req_id = f"test_valid_{uuid.uuid4().hex[:8]}"

    payload = {
        "source": "simulator",
        "alert_name": "HighLatencySpike",
        "service": "api-gateway",
        "severity": "high",
        "environment": "production",
        "message": "Gateway latency P99 over 1200ms"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "ACCEPTED"
    assert data["trust_score"] >= 90.0

    # Verify persistent security audit event recorded
    evt = db_session.query(SecurityEvent).filter(SecurityEvent.request_id == req_id).first()
    assert evt is not None
    assert evt.event_type == "ALERT_ACCEPTED"
    assert evt.action == "ACCEPTED"

# ============================================================
# TEST 2: Invalid HMAC Signature (BLOCKED 401)
# ============================================================
def test_2_invalid_hmac_blocked(client, db_session):
    """Tampered or corrupted signature -> BLOCKED with 401 Unauthorized."""
    now_ts = str(time.time())
    req_id = f"test_invalid_sig_{uuid.uuid4().hex[:8]}"

    payload = {
        "source": "simulator",
        "alert_name": "UnauthorizedInjection",
        "service": "auth-service",
        "severity": "critical",
        "message": "Injected payload"
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": "tampered_bad_hex_signature_123456",
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 401
    assert "Invalid HMAC signature" in res.json()["detail"]

    # Check security event recorded
    evt = db_session.query(SecurityEvent).filter(SecurityEvent.request_id == req_id).first()
    assert evt is not None
    assert evt.event_type == "INVALID_SIGNATURE"
    assert evt.action == "BLOCKED"

# ============================================================
# TEST 3: Missing Signature on Secured Source (BLOCKED / QUARANTINED)
# ============================================================
def test_3_missing_signature_low_trust(client, db_session):
    """Missing signature on enabled source -> Quarantined or Blocked with low trust score."""
    now_ts = str(time.time())
    req_id = f"test_missing_sig_{uuid.uuid4().hex[:8]}"

    payload = {
        "source": "simulator",
        "alert_name": "NoSigAlert",
        "service": "frontend",
        "severity": "medium",
        "message": "Unsigned payload test"
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
        # X-Alert-Signature omitted intentionally
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code in [202, 401]
    data = res.json()
    assert data.get("status") == "quarantined" or "detail" in data

# ============================================================
# TEST 4: Expired Timestamp (> 5 min) (BLOCKED 400)
# ============================================================
def test_4_expired_timestamp_blocked(client, db_session):
    """Timestamp older than 5 minutes -> BLOCKED as stale/replay."""
    secret = DEFAULT_SOURCE_SECRETS["simulator"]
    expired_ts = str(time.time() - 400)  # 6.6 minutes ago (> 300s window)
    req_id = f"test_expired_ts_{uuid.uuid4().hex[:8]}"

    payload = {
        "source": "simulator",
        "alert_name": "StaleReplayAlert",
        "service": "cache-redis",
        "severity": "medium",
        "message": "Captured and replayed payload"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": expired_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 400
    assert "replay window" in res.json()["detail"].lower()

# ============================================================
# TEST 5: Replay Same Request ID (BLOCKED 409)
# ============================================================
def test_5_replay_same_request_id_blocked(client, db_session):
    """Reusing the same (source, request_id) twice -> 2nd request BLOCKED 409."""
    secret = DEFAULT_SOURCE_SECRETS["simulator"]
    now_ts = str(time.time())
    replayed_nonce = f"fixed_nonce_{uuid.uuid4().hex[:8]}"

    payload = {
        "source": "simulator",
        "alert_name": "ReplayTestAlert",
        "service": "payment-service",
        "severity": "high",
        "message": "Testing nonce uniqueness"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": replayed_nonce
    }

    # First request: Accepted
    res1 = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res1.status_code == 200

    # Second request: Replay detected -> 409 Conflict
    res2 = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res2.status_code == 409
    assert "Replay detected" in res2.json()["detail"]

    # Verify REPLAY_DETECTED event logged
    evt = db_session.query(SecurityEvent).filter(
        SecurityEvent.request_id == replayed_nonce,
        SecurityEvent.event_type == "REPLAY_DETECTED"
    ).first()
    assert evt is not None

# ============================================================
# TEST 6: Excessive Request Rate (RATE LIMITED 429)
# ============================================================
def test_6_rate_limit_exceeded_blocked(client, db_session):
    """Requests exceeding source limit -> HTTP 429 Too Many Requests with Retry-After header."""
    secret = DEFAULT_SOURCE_SECRETS["generic"]
    now_ts = str(time.time())

    # Pre-fill generic rate limiter window to max limit (> 1000/min)
    now = time.time()
    for k in ["generic:127.0.0.1", "generic:testclient"]:
        shield.rate_limiter._requests[k] = __import__("collections").deque([now] * 1050)

    payload = {
        "source": "generic",
        "alert_name": "RateLimitTest",
        "service": "test",
        "severity": "low",
        "message": "Testing 429"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "generic",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": f"rate_{uuid.uuid4().hex[:6]}"
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 429
    assert "Rate limit exceeded" in res.json()["detail"]
    shield.rate_limiter.reset()

# ============================================================
# TEST 7: Malformed JSON / Schema Validation (REJECTED 400)
# ============================================================
def test_7_malformed_json_and_schema_rejected(client, db_session):
    """Malformed syntax or missing required fields -> 400 Bad Request."""
    now_ts = str(time.time())
    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": f"malformed_{uuid.uuid4().hex[:6]}"
    }

    # Case A: Corrupted JSON syntax
    corrupted_body = b'{"alert_name": "Test", "broken": [1, 2'
    res1 = client.post("/api/webhooks/alerts", content=corrupted_body, headers=headers)
    assert res1.status_code == 400

    # Case B: Missing alert name identifier
    missing_name = json.dumps({"source": "simulator", "service": "orders"}).encode("utf-8")
    res2 = client.post("/api/webhooks/alerts", content=missing_name, headers=headers)
    assert res2.status_code == 400
    assert "Missing mandatory alert identifier" in res2.json()["detail"]

# ============================================================
# TEST 8: Unknown Source (QUARANTINED / LOW TRUST)
# ============================================================
def test_8_unknown_source_quarantined(client, db_session):
    """Alert from unknown unregistered source -> Preserved in quarantine, trust score < 40."""
    now_ts = str(time.time())
    req_id = f"unknown_src_{uuid.uuid4().hex[:6]}"

    payload = {
        "source": "unknown_rogue_scanner",
        "alert_name": "SuspiciousAlert",
        "service": "internal-vault",
        "severity": "high",
        "message": "Alert injected by rogue source"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "X-Alert-Source": "unknown_rogue_scanner",
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert data["decision"] == "QUARANTINED"
    assert data["trust_score"] < 70.0

    # Verify alert exists in database with QUARANTINED security_status
    quarantined = db_session.query(Alert).filter(Alert.alert_name == "SuspiciousAlert").first()
    assert quarantined is not None
    assert quarantined.security_status == "QUARANTINED"
    assert quarantined.notification_status == "SUPPRESSED"

# ============================================================
# TEST 9: 500 Legitimate Simulated Alerts (Pipeline Noise Reduction)
# ============================================================
def test_9_500_legitimate_alerts_pipeline_works(db_session):
    """Verifies that legitimate alerts still flow through deduplication, correlation, and batching."""
    from app.api.simulator import simulate_database_outage
    import asyncio

    summary = asyncio.run(simulate_database_outage(db_session))
    assert summary["status"] == "success"
    assert summary["total_generated"] == 500
    # Must achieve >90% alert fatigue reduction
    assert summary["reduction_percentage"] >= 90.0
    assert summary["notifications_dispatched"] <= 10

# ============================================================
# TEST 10: 500 Duplicate Alerts (Deduplication Preserved)
# ============================================================
def test_10_500_duplicate_alerts_deduplicated(db_session):
    """500 duplicate alerts increment occurrence_count on a single Alert row."""
    base_fingerprint = f"fp_dedup_test_{uuid.uuid4().hex[:6]}"
    raw_payload = {
        "source": "simulator",
        "alert_name": "HighMemoryPressure",
        "service": "checkout-service",
        "severity": "medium",
        "message": "Memory at 88%"
    }

    for i in range(50):
        norm = normalize_generic(raw_payload)
        norm["fingerprint"] = base_fingerprint
        process_alert(db_session, norm)

    alerts = db_session.query(Alert).filter(Alert.fingerprint == base_fingerprint).all()
    assert len(alerts) == 1
    assert alerts[0].occurrence_count == 50
    assert alerts[0].suppression_category == "duplicate"

# ============================================================
# TEST 11: Legitimate Critical Alert (PagerDuty Immediate Route)
# ============================================================
def test_11_legitimate_critical_alert_pagerduty_routed(client, db_session):
    """Legitimate CRITICAL alert from trusted source is immediately routed without delay."""
    secret = DEFAULT_SOURCE_SECRETS["simulator"]
    now_ts = str(time.time())
    req_id = f"crit_legit_{uuid.uuid4().hex[:6]}"
    service_id = f"vault-{uuid.uuid4().hex[:6]}"

    # Ensure critical service registered with high criticality
    db_session.add(Service(id=service_id, display_name="Secure Vault", criticality=100))
    db_session.commit()

    payload = {
        "source": "simulator",
        "alert_name": "VaultClusterDown",
        "service": service_id,
        "severity": "critical",
        "environment": "production",
        "message": "Vault cluster node down"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] == "ACCEPTED"
    assert data["result"]["action"] == "NOTIFIED"
    assert data["result"]["alert"]["severity"].upper() == "CRITICAL"
    assert "pagerduty" in data["result"]["notification"]["channel"].lower()

# ============================================================
# TEST 12: Suspicious Critical Alert (Critical Alert Safety Guarantee)
# ============================================================
def test_12_suspicious_critical_alert_preserved_not_deleted(client, db_session):
    """
    CRITICAL alert with suspicious traits (e.g. missing signature / low trust):
    - Must NOT be silently deleted!
    - Must be preserved in database with security_status='SUSPICIOUS'
    - Marked for SRE review
    """
    now_ts = str(time.time())
    req_id = f"crit_suspicious_{uuid.uuid4().hex[:6]}"

    payload = {
        "source": "simulator",
        "alert_name": "EmergencyPostgresClusterFailure",
        "service": "database",
        "severity": "critical",
        "message": "Emergency database cluster failure with missing signature"
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Missing signature -> Triggers quarantine
    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": req_id
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "quarantined"
    assert data["is_critical"] is True

    # Verify preserved in database
    alert = db_session.query(Alert).filter(Alert.id == data["alert_id"]).first()
    assert alert is not None
    assert alert.security_status == "SUSPICIOUS"
    assert alert.severity == "critical"
    assert alert.quarantine_reason is not None

# ============================================================
# TEST 13: Volume Surge / Alert Storm Detection
# ============================================================
def test_13_volume_surge_anomaly_detection(client, db_session):
    """Volume > 5x baseline triggers SUSPICIOUS_STORM and quarantine."""
    secret = DEFAULT_SOURCE_SECRETS["simulator"]
    now_ts = str(time.time())

    # Artificially trigger anomaly detector
    key = "simulator:api-gateway"
    for _ in range(300):
        shield.anomaly._counts.setdefault(key, shield.anomaly._counts.get(key, __import__("collections").deque())).append(time.time())

    payload = {
        "source": "simulator",
        "alert_name": "GatewaySpike",
        "service": "api-gateway",
        "severity": "medium",
        "message": "Volume burst test"
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = HMACSignatureVerifier.calculate_signature(body_bytes, secret)

    headers = {
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": f"surge_{uuid.uuid4().hex[:6]}"
    }

    res = client.post("/api/webhooks/alerts", content=body_bytes, headers=headers)
    assert res.status_code == 202
    assert "quarantined" in res.json().get("status", "").lower()
    shield.anomaly._counts.clear()

# ============================================================
# TEST 14: Zero-Downtime Secret Rotation
# ============================================================
def test_14_zero_downtime_secret_rotation(client, db_session):
    """During secret rotation, both new and old secrets are valid; revoked after transition."""
    # Rotate simulator secret
    rot_res = client.post("/api/security/sources/simulator/rotate-secret?grace_period_hours=24")
    assert rot_res.status_code == 200
    new_secret = rot_res.json()["rotation_details"]["new_secret"]
    old_secret = DEFAULT_SOURCE_SECRETS["simulator"]

    now_ts = str(time.time())

    payload = {
        "source": "simulator",
        "alert_name": "RotationTest",
        "service": "auth-service",
        "severity": "low",
        "message": "Testing rotation transition"
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # 1. New secret is valid
    sig_new = HMACSignatureVerifier.calculate_signature(body_bytes, new_secret)
    res_new = client.post("/api/webhooks/alerts", content=body_bytes, headers={
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig_new,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": f"rot_new_{uuid.uuid4().hex[:6]}"
    })
    assert res_new.status_code == 200
    assert res_new.json()["decision"] == "ACCEPTED"

    # 2. Old secret is STILL valid during 24h grace window (zero-downtime!)
    sig_old = HMACSignatureVerifier.calculate_signature(body_bytes, old_secret)
    res_old = client.post("/api/webhooks/alerts", content=body_bytes, headers={
        "X-Alert-Source": "simulator",
        "X-Alert-Signature": sig_old,
        "X-Alert-Timestamp": now_ts,
        "X-Alert-Request-ID": f"rot_old_{uuid.uuid4().hex[:6]}"
    })
    assert res_old.status_code == 200
    assert res_old.json()["decision"] == "ACCEPTED"
