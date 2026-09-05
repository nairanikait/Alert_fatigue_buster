import hmac
import hashlib
import time
import datetime
import json
import logging
import uuid
from typing import Dict, Any, Optional, Tuple, List
from collections import deque
import threading

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.models.security import WebhookSource, WebhookRequest, SecurityEvent, SecurityBaseline
from app.models.alert import Alert
from app.core.events import ws_manager

logger = logging.getLogger("alert_buster.security_shield")

# ============================================================
# DEFAULT BUILT-IN SECRETS & BASELINES
# (Server-side configuration; never exposed to clients/frontend)
# ============================================================
DEFAULT_SOURCE_SECRETS = {
    "prometheus": "prom-sec-8f4b2e910a3c7d6e",
    "datadog": "dd-sec-9a1b2c3d4e5f6071",
    "simulator": "sim-sec-5b7e1a3f9c2d8e40",
    "generic": "gen-sec-1122334455667788",
}

DEFAULT_RATE_LIMITS = {
    "simulator": 5000,
    "prometheus": 1000,
    "datadog": 1000,
    "generic": 500,
    "unknown": 50,
}

# ============================================================
# 1. SOURCE AUTHENTICATION & SECRET ROTATION
# ============================================================
class SourceAuthenticator:
    """
    Manages registered alert sources, secrets, and zero-downtime secret rotation.
    Maintains a fast in-memory cache to avoid database latency on every webhook.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def seed_defaults(self, db: Session):
        """Ensure default webhook sources exist in the database."""
        try:
            for name, secret in DEFAULT_SOURCE_SECRETS.items():
                existing = db.query(WebhookSource).filter(WebhookSource.source_name == name).first()
                if not existing:
                    src = WebhookSource(
                        id=str(uuid.uuid4()),
                        source_name=name,
                        source_identifier=f"src_{name}_default",
                        secret=secret,
                        is_enabled=True,
                        rate_limit_per_minute=DEFAULT_RATE_LIMITS.get(name, 1000),
                        trust_rating=100.0,
                    )
                    db.add(src)
            db.commit()
            self.refresh_cache(db)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to seed default webhook sources: {e}")

    def refresh_cache(self, db: Session):
        with self._lock:
            sources = db.query(WebhookSource).all()
            self._cache.clear()
            for s in sources:
                self._cache[s.source_name] = {
                    "id": s.id,
                    "source_name": s.source_name,
                    "source_identifier": s.source_identifier,
                    "secret": s.secret,
                    "secondary_secret": s.secondary_secret,
                    "rotation_expires_at": s.rotation_expires_at,
                    "is_enabled": s.is_enabled,
                    "rate_limit_per_minute": s.rate_limit_per_minute,
                    "trust_rating": s.trust_rating,
                }

    def get_source(self, source_name: str, db: Session) -> Optional[Dict[str, Any]]:
        with self._lock:
            if source_name in self._cache:
                return self._cache[source_name]

        # Query DB if not in cache
        src = db.query(WebhookSource).filter(WebhookSource.source_name == source_name).first()
        if src:
            data = {
                "id": src.id,
                "source_name": src.source_name,
                "source_identifier": src.source_identifier,
                "secret": src.secret,
                "secondary_secret": src.secondary_secret,
                "rotation_expires_at": src.rotation_expires_at,
                "is_enabled": src.is_enabled,
                "rate_limit_per_minute": src.rate_limit_per_minute,
                "trust_rating": src.trust_rating,
            }
            with self._lock:
                self._cache[source_name] = data
            return data
        return None

    def rotate_secret(self, source_name: str, db: Session, grace_period_hours: int = 24) -> Dict[str, str]:
        """
        Transition source secret:
        Current secret becomes secondary_secret (valid for grace_period_hours).
        New cryptographically secure secret is generated and made primary.
        """
        src = db.query(WebhookSource).filter(WebhookSource.source_name == source_name).first()
        if not src:
            raise ValueError(f"Source '{source_name}' not found")

        import secrets
        new_secret = f"{source_name[:3]}-sec-{secrets.token_hex(12)}"
        
        # Demote current secret to secondary with expiry
        src.secondary_secret = src.secret
        src.rotation_expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=grace_period_hours)
        src.secret = new_secret
        src.updated_at = datetime.datetime.utcnow()
        db.commit()

        self.refresh_cache(db)
        return {
            "source_name": source_name,
            "new_secret": new_secret,
            "grace_period_hours": grace_period_hours,
            "rotation_expires_at": src.rotation_expires_at.isoformat()
        }

# ============================================================
# 2. HMAC-SHA256 SIGNATURE VERIFICATION
# ============================================================
class HMACSignatureVerifier:
    """
    Verifies HMAC-SHA256 signatures over raw request body.
    Uses timing-safe comparison to prevent timing side-channel attacks.
    """
    @staticmethod
    def calculate_signature(raw_body: bytes, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    @staticmethod
    def verify(raw_body: bytes, received_signature: str, source_data: Dict[str, Any]) -> Tuple[bool, str]:
        if not received_signature:
            return False, "Missing signature header (X-Alert-Signature)"

        # Normalize signature string (strip 'sha256=' prefix if present)
        clean_sig = received_signature.strip()
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig[7:]

        primary_secret = source_data.get("secret")
        if primary_secret:
            expected_primary = HMACSignatureVerifier.calculate_signature(raw_body, primary_secret)
            if hmac.compare_digest(clean_sig, expected_primary):
                return True, "Valid signature (primary secret)"

        # Check secondary secret if secret rotation is active and not expired
        secondary_secret = source_data.get("secondary_secret")
        rotation_expires = source_data.get("rotation_expires_at")
        if secondary_secret:
            is_active = True
            if rotation_expires:
                if isinstance(rotation_expires, str):
                    rotation_expires = datetime.datetime.fromisoformat(rotation_expires)
                if datetime.datetime.utcnow() > rotation_expires:
                    is_active = False

            if is_active:
                expected_secondary = HMACSignatureVerifier.calculate_signature(raw_body, secondary_secret)
                if hmac.compare_digest(clean_sig, expected_secondary):
                    return True, "Valid signature (transition secondary secret)"

        return False, "Invalid signature"

# ============================================================
# 3. REPLAY ATTACK PROTECTION
# ============================================================
class ReplayProtector:
    """
    Enforces replay protection:
    1. Timestamp freshness window (default: 300 seconds / 5 minutes).
    2. Unique request_id per source in persistent storage (and in-memory buffer).
    """
    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._seen_requests: Dict[str, float] = {}
        self._lock = threading.Lock()

    def check_timestamp(self, timestamp_str: Optional[str]) -> Tuple[bool, str]:
        if not timestamp_str:
            return False, "Missing timestamp header (X-Alert-Timestamp)"

        try:
            # Parse Unix timestamp float or ISO format
            if timestamp_str.replace(".", "", 1).isdigit():
                ts = float(timestamp_str)
            else:
                dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                ts = dt.timestamp()
        except Exception:
            return False, "Malformed timestamp format"

        now = time.time()
        drift = abs(now - ts)
        if drift > self.window_seconds:
            return False, f"Timestamp outside allowed replay window (drift: {int(drift)}s, max: {self.window_seconds}s)"

        return True, "Timestamp valid"

    def check_and_record_request(
        self,
        source: str,
        request_id: Optional[str],
        timestamp_str: Optional[str],
        db: Session
    ) -> Tuple[bool, str]:
        if not request_id:
            return False, "Missing request ID header (X-Alert-Request-ID)"

        key = f"{source}:{request_id}"
        now = time.time()

        with self._lock:
            # Clean in-memory cache
            cutoff = now - (self.window_seconds * 2)
            self._seen_requests = {k: v for k, v in self._seen_requests.items() if v > cutoff}

            if key in self._seen_requests:
                return False, f"Replay detected: Request ID '{request_id}' was already processed"

        # Check DB persistent uniqueness
        existing = db.query(WebhookRequest).filter(
            WebhookRequest.source == source,
            WebhookRequest.request_id == request_id
        ).first()

        if existing:
            with self._lock:
                self._seen_requests[key] = now
            return False, f"Replay detected in persistent store: Request ID '{request_id}' previously recorded"

        # Record new request
        try:
            ts_dt = datetime.datetime.utcnow()
            if timestamp_str:
                try:
                    if timestamp_str.replace(".", "", 1).isdigit():
                        ts_dt = datetime.datetime.utcfromtimestamp(float(timestamp_str))
                    else:
                        ts_dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            record = WebhookRequest(
                id=str(uuid.uuid4()),
                source=source,
                request_id=request_id,
                timestamp=ts_dt,
                status="PROCESSED"
            )
            db.add(record)
            db.commit()

            with self._lock:
                self._seen_requests[key] = now

            return True, "Request ID accepted"
        except Exception as e:
            db.rollback()
            # If integrity error, another worker recorded it simultaneously
            return False, f"Replay detected (concurrent conflict): {e}"

# ============================================================
# 4. TIERED SLIDING-WINDOW RATE LIMITER
# ============================================================
class ShieldRateLimiter:
    """
    Sliding-window rate limiter per source/IP.
    Configurable limits:
    - Normal registered source: 1,000 req/min
    - Simulator: 5,000 req/min
    - Unknown source: 50 req/min
    """
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._requests: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_limit: int) -> Tuple[bool, int, int]:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            if key not in self._requests:
                self._requests[key] = deque()

            timestamps = self._requests[key]
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            current_count = len(timestamps)
            if current_count >= max_limit:
                return False, current_count, max_limit

            timestamps.append(now)
            return True, current_count + 1, max_limit

    def reset(self):
        with self._lock:
            self._requests.clear()

# ============================================================
# 5. STRICT SCHEMA & PAYLOAD VALIDATOR
# ============================================================
class PayloadSchemaValidator:
    """
    Strict payload sanity & boundary enforcement:
    - Max body size: 1 MB
    - String bounds: alert_name <= 256, service <= 128, message <= 4096
    - Label count <= 50
    - JSON nesting depth <= 5
    """
    MAX_BODY_BYTES = 1024 * 1024  # 1 MB
    MAX_NAME_LEN = 256
    MAX_SERVICE_LEN = 128
    MAX_MESSAGE_LEN = 4096
    MAX_LABELS = 50

    @classmethod
    def validate_raw(cls, raw_body: bytes) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        if len(raw_body) > cls.MAX_BODY_BYTES:
            return False, f"Payload size exceeds 1MB limit ({len(raw_body)} bytes)", None

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return False, "Malformed JSON syntax", None

        if not isinstance(data, dict):
            return False, "Payload must be a JSON object", None

        return True, None, data

    @classmethod
    def validate_schema(cls, data: Dict[str, Any], source_type: str = "generic") -> Tuple[bool, Optional[str]]:
        # Prometheus payload format
        if source_type == "prometheus" or "alerts" in data:
            alerts = data.get("alerts")
            if not isinstance(alerts, list):
                return False, "Prometheus payload must contain an 'alerts' array"
            if len(alerts) == 0:
                return False, "Prometheus 'alerts' array cannot be empty"
            if len(alerts) > 500:
                return False, "Prometheus batch exceeds max 500 alerts per webhook"
            for i, alt in enumerate(alerts):
                if not isinstance(alt, dict):
                    return False, f"Alert at index {i} must be a JSON object"
                labels = alt.get("labels", {})
                if not isinstance(labels, dict):
                    return False, f"Alert at index {i} has non-object 'labels'"
                name = labels.get("alertname") or labels.get("alert_name")
                if not name:
                    return False, f"Alert at index {i} missing mandatory 'alertname' label"
            return True, None

        # Datadog format
        if source_type == "datadog":
            has_name = bool(data.get("title") or data.get("alert_name") or data.get("event_type"))
            if not has_name:
                return False, "Datadog payload missing mandatory 'title' or 'alert_name'"
            return True, None

        # Generic format
        name = data.get("alert_name") or data.get("alertname") or data.get("title")
        if not name:
            labels = data.get("labels", {})
            if isinstance(labels, dict):
                name = labels.get("alertname") or labels.get("alert_name")

        if not name:
            return False, "Missing mandatory alert identifier ('alert_name' or 'title')"

        if len(str(name)) > cls.MAX_NAME_LEN:
            return False, f"Alert name exceeds maximum allowed length of {cls.MAX_NAME_LEN}"

        service = data.get("service")
        if service and len(str(service)) > cls.MAX_SERVICE_LEN:
            return False, f"Service name exceeds maximum allowed length of {cls.MAX_SERVICE_LEN}"

        msg = data.get("message")
        if msg and len(str(msg)) > cls.MAX_MESSAGE_LEN:
            return False, f"Alert message exceeds maximum allowed length of {cls.MAX_MESSAGE_LEN}"

        labels = data.get("labels")
        if isinstance(labels, dict) and len(labels) > cls.MAX_LABELS:
            return False, f"Alert labels count exceeds maximum of {cls.MAX_LABELS}"

        return True, None

# ============================================================
# 6. ALERT INJECTION & ANOMALY DETECTOR
# ============================================================
class AlertAnomalyDetector:
    """
    Detects abnormal alert storm injection by comparing current per-source/service
    rate against historical baselines:
    - Normal baseline: ~50 alerts/min
    - > 5x baseline: SUSPICIOUS (anomalous spike)
    - > 10x baseline: HIGH RISK (potential alert injection attack)
    Distinguishes legitimate infrastructure incident storms from unauthorized injection.
    """
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._counts: Dict[str, deque] = {}
        self._baselines: Dict[str, float] = {}
        self._lock = threading.Lock()

    def record_and_evaluate(
        self,
        source: str,
        service: Optional[str],
        db: Session
    ) -> Tuple[float, float, str]:
        key = f"{source}:{service or 'all'}"
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            if key not in self._counts:
                self._counts[key] = deque()

            deq = self._counts[key]
            while deq and deq[0] < cutoff:
                deq.popleft()

            deq.append(now)
            current_rate = float(len(deq))

            baseline = self._baselines.get(key, 50.0)

        # Periodically load baseline from DB
        try:
            base_rec = db.query(SecurityBaseline).filter(
                SecurityBaseline.source == source,
                SecurityBaseline.service == service
            ).first()
            if base_rec:
                baseline = base_rec.normal_rate_per_minute
                with self._lock:
                    self._baselines[key] = baseline
        except Exception:
            pass

        ratio = current_rate / max(baseline, 1.0)
        if ratio >= 10.0:
            status = "HIGH_RISK_INJECTION"
        elif ratio >= 5.0:
            status = "SUSPICIOUS_STORM"
        else:
            status = "NORMAL_VOLUME"

        return current_rate, ratio, status

# ============================================================
# 7. MODULAR TRUST SCORER (0 - 100)
# ============================================================
class TrustScorer:
    """
    Calculates a transparent composite security trust score (0 to 100):
    +25 Registered & enabled source
    +25 Valid HMAC signature
    +15 Unique request ID (no replay)
    +10 Valid timestamp within window
    +15 Valid schema & payload bounds
    +10 Normal volume rate

    Classifications:
    - 90 - 100: TRUSTED
    - 70 - 89:  LOW RISK
    - 40 - 69:  SUSPICIOUS
    - 0  - 39:  MALICIOUS / HIGH RISK
    """
    @staticmethod
    def calculate(
        is_known_source: bool,
        is_valid_sig: bool,
        is_fresh_time: bool,
        is_unique_req: bool,
        is_valid_schema: bool,
        volume_status: str,
        has_known_service: bool
    ) -> Tuple[float, str, List[str]]:
        score = 0.0
        factors = []

        if is_known_source:
            score += 25.0
            factors.append("+25: Registered Source")
        else:
            factors.append("-35: Unknown / Unregistered Source")

        if is_valid_sig:
            score += 25.0
            factors.append("+25: Valid HMAC-SHA256 Signature")
        else:
            factors.append("-60: Invalid or Missing Signature")

        if is_unique_req:
            score += 15.0
            factors.append("+15: Unique Nonce / Request ID")
        else:
            factors.append("-50: Replay Attempt Detected")

        if is_fresh_time:
            score += 10.0
            factors.append("+10: Fresh Timestamp")
        else:
            factors.append("-20: Expired / Stale Timestamp")

        if is_valid_schema:
            score += 15.0
            factors.append("+15: Valid Schema & Bounds")
        else:
            factors.append("-40: Malformed Schema")

        if volume_status == "NORMAL_VOLUME":
            score += 10.0
            factors.append("+10: Normal Volume")
        elif volume_status == "SUSPICIOUS_STORM":
            score = max(0.0, score - 20.0)
            factors.append("-20: Suspicious Volume Surge (>5x)")
        elif volume_status == "HIGH_RISK_INJECTION":
            score = max(0.0, score - 35.0)
            factors.append("-35: Alert Injection Storm (>10x)")

        if has_known_service:
            score = min(100.0, score + 5.0)

        score = max(0.0, min(100.0, score))

        if score >= 90.0:
            tier = "TRUSTED"
        elif score >= 70.0:
            tier = "LOW_RISK"
        elif score >= 40.0:
            tier = "SUSPICIOUS"
        else:
            tier = "HIGH_RISK"

        return score, tier, factors

# ============================================================
# 8. SECURITY AUDIT & QUARANTINE MANAGER
# ============================================================
class SecurityAuditManager:
    """
    Writes persistent audit events to `security_events` table,
    broadcasts live WebSocket alerts, and maintains bounded in-memory log.
    """
    def __init__(self, max_memory_entries: int = 100):
        self.max_entries = max_memory_entries
        self._memory_log: deque = deque(maxlen=max_memory_entries)
        self._lock = threading.Lock()

    def record_event(
        self,
        db: Session,
        event_type: str,
        source: str,
        action: str,
        reason: str,
        severity: str = "INFO",
        trust_score: float = 100.0,
        request_id: Optional[str] = None,
        alert_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        evt_id = str(uuid.uuid4())
        safe_meta = metadata or {}

        # Strip any accidental secrets from metadata
        for k in list(safe_meta.keys()):
            if any(w in k.lower() for w in ["secret", "password", "token", "key"]):
                safe_meta[k] = "[REDACTED]"

        event_rec = SecurityEvent(
            id=evt_id,
            event_type=event_type,
            source=source,
            request_id=request_id,
            alert_id=alert_id,
            severity=severity,
            trust_score=trust_score,
            action=action,
            reason=reason,
            metadata_json=safe_meta,
            created_at=datetime.datetime.utcnow()
        )

        try:
            db.add(event_rec)
            db.commit()
            evt_dict = event_rec.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist security event to DB: {e}")
            evt_dict = {
                "id": evt_id,
                "event_type": event_type,
                "source": source,
                "request_id": request_id,
                "alert_id": alert_id,
                "severity": severity,
                "trust_score": trust_score,
                "action": action,
                "reason": reason,
                "metadata": safe_meta,
                "created_at": datetime.datetime.utcnow().isoformat(),
            }

        with self._lock:
            self._memory_log.appendleft(evt_dict)

        # Broadcast real-time WebSocket security alert
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast("SECURITY_EVENT", evt_dict))
            except RuntimeError:
                pass
        except Exception:
            pass

        return evt_dict

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._memory_log)[:limit]

# ============================================================
# COMPOSITE ALERT INTEGRITY SHIELD ENGINE
# ============================================================
class AlertIntegrityShield:
    """
    Main entry point for the security layer sitting BEFORE the alert processing pipeline:
    Incoming Alert
          ↓
    Authentication
          ↓
    Signature Verification
          ↓
    Replay Protection
          ↓
    Rate Limiting
          ↓
    Schema Validation
          ↓
    Anomaly & Injection Detection
          ↓
    Alert Trust Score
          ↓
    Security Decision (TRUSTED / SUSPICIOUS -> QUARANTINE / MALICIOUS -> BLOCK)
    """
    def __init__(self):
        self.auth = SourceAuthenticator()
        self.signature = HMACSignatureVerifier()
        self.replay = ReplayProtector(window_seconds=300)
        self.rate_limiter = ShieldRateLimiter(window_seconds=60)
        self.schema = PayloadSchemaValidator()
        self.anomaly = AlertAnomalyDetector(window_seconds=60)
        self.trust_scorer = TrustScorer()
        self.audit = SecurityAuditManager(max_memory_entries=100)

    def guard_webhook(
        self,
        raw_body: bytes,
        headers: Dict[str, str],
        client_ip: str,
        endpoint_path: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Executes the full Alert Integrity Shield inspection pipeline.
        Returns a decision dictionary:
        {
          "decision": "ACCEPTED" | "QUARANTINED" | "BLOCKED",
          "trust_score": float,
          "risk_tier": "TRUSTED" | "LOW_RISK" | "SUSPICIOUS" | "HIGH_RISK",
          "reason": str,
          "source": str,
          "payload": dict,
          "status_code": int,
          "is_critical": bool
        }
        """
        # Normalize header keys to lowercase
        norm_headers = {k.lower(): v for k, v in headers.items()}
        
        # 1. Extract Headers
        received_sig = norm_headers.get("x-alert-signature")
        timestamp_str = norm_headers.get("x-alert-timestamp")
        request_id = norm_headers.get("x-alert-request-id")
        source_header = norm_headers.get("x-alert-source")
        api_key_header = norm_headers.get("x-api-key") or norm_headers.get("x-webhook-secret")

        # Deduce source from endpoint or header
        if source_header:
            source_name = source_header.lower()
        elif "prometheus" in endpoint_path.lower():
            source_name = "prometheus"
        elif "datadog" in endpoint_path.lower():
            source_name = "datadog"
        elif "simulator" in endpoint_path.lower():
            source_name = "simulator"
        else:
            source_name = "generic"

        # 2. Strict Payload Size & Syntax Check
        is_syntax_valid, syntax_err, parsed_payload = self.schema.validate_raw(raw_body)
        if not is_syntax_valid:
            self.audit.record_event(
                db=db,
                event_type="SCHEMA_VALIDATION_FAILED",
                source=source_name,
                action="BLOCKED",
                reason=f"Payload syntax rejected: {syntax_err}",
                severity="HIGH",
                trust_score=0.0,
                request_id=request_id,
                metadata={"client_ip": client_ip, "endpoint": endpoint_path}
            )
            return {
                "decision": "BLOCKED",
                "status_code": 400,
                "trust_score": 0.0,
                "risk_tier": "HIGH_RISK",
                "reason": f"Bad Request: {syntax_err}",
                "source": source_name,
                "payload": {},
                "is_critical": False
            }

        # 3. Payload Schema Structure Validation
        is_valid_schema, schema_err = self.schema.validate_schema(parsed_payload, source_type=source_name)
        if not is_valid_schema:
            self.audit.record_event(
                db=db,
                event_type="SCHEMA_VALIDATION_FAILED",
                source=source_name,
                action="BLOCKED",
                reason=f"Payload schema rejected: {schema_err}",
                severity="HIGH",
                trust_score=0.0,
                request_id=request_id,
                metadata={"client_ip": client_ip, "endpoint": endpoint_path}
            )
            return {
                "decision": "BLOCKED",
                "status_code": 400,
                "trust_score": 0.0,
                "risk_tier": "HIGH_RISK",
                "reason": f"Bad Request: {schema_err}",
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": False
            }

        # Check for CRITICAL severity in payload for Critical Alert Safety
        severity_in_payload = str(parsed_payload.get("severity", "")).lower()
        if not severity_in_payload and "alerts" in parsed_payload:
            for a in parsed_payload.get("alerts", []):
                if isinstance(a, dict) and str(a.get("labels", {}).get("severity", "")).lower() == "critical":
                    severity_in_payload = "critical"
                    break
        is_critical_alert = severity_in_payload == "critical"

        # 4. Source Lookup & Registration Check
        source_data = self.auth.get_source(source_name, db)
        is_known_source = bool(source_data and source_data.get("is_enabled"))

        if not is_known_source:
            # Check if source exists but is disabled
            if source_data and not source_data.get("is_enabled"):
                self.audit.record_event(
                    db=db,
                    event_type="AUTHENTICATION_FAILED",
                    source=source_name,
                    action="BLOCKED",
                    reason=f"Source '{source_name}' is disabled",
                    severity="HIGH",
                    trust_score=10.0,
                    request_id=request_id,
                    metadata={"client_ip": client_ip}
                )
                return {
                    "decision": "BLOCKED",
                    "status_code": 403,
                    "trust_score": 10.0,
                    "risk_tier": "HIGH_RISK",
                    "reason": f"Forbidden: Source '{source_name}' is disabled",
                    "source": source_name,
                    "payload": parsed_payload,
                    "is_critical": is_critical_alert
                }

        # 4. Rate Limiting Check
        max_rate = source_data.get("rate_limit_per_minute", 1000) if source_data else DEFAULT_RATE_LIMITS.get("unknown", 50)
        rate_key = f"{source_name}:{client_ip}"
        allowed_rate, current_count, limit_val = self.rate_limiter.is_allowed(rate_key, max_rate)
        if not allowed_rate:
            self.audit.record_event(
                db=db,
                event_type="RATE_LIMIT_EXCEEDED",
                source=source_name,
                action="THROTTLED",
                reason=f"Rate limit exceeded: {current_count}/{limit_val} req/min",
                severity="MEDIUM",
                trust_score=35.0,
                request_id=request_id,
                metadata={"client_ip": client_ip, "rate": current_count, "limit": limit_val}
            )

            # CRITICAL ALERT SAFETY: If authenticated critical alert is rate-limited, quarantine instead of hard dropping
            if is_critical_alert and is_known_source:
                return {
                    "decision": "QUARANTINED",
                    "status_code": 202,
                    "trust_score": 50.0,
                    "risk_tier": "SUSPICIOUS",
                    "reason": f"Rate limited ({current_count}/{limit_val}) but preserved due to CRITICAL severity",
                    "source": source_name,
                    "payload": parsed_payload,
                    "is_critical": True
                }

            return {
                "decision": "BLOCKED",
                "status_code": 429,
                "trust_score": 35.0,
                "risk_tier": "SUSPICIOUS",
                "reason": f"Too Many Requests: Rate limit exceeded ({current_count}/{limit_val} req/min)",
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": is_critical_alert
            }

        # 5. Signature & Authentication Verification
        is_valid_sig = False
        sig_reason = "No signature provided"
        if source_data:
            if received_sig:
                is_valid_sig, sig_reason = self.signature.verify(raw_body, received_sig, source_data)
            elif api_key_header:
                # Backward-compatibility fallback for X-API-Key / X-Webhook-Secret
                import secrets
                if secrets.compare_digest(api_key_header, source_data.get("secret", "")) or (
                    source_data.get("secondary_secret") and secrets.compare_digest(api_key_header, source_data.get("secondary_secret"))
                ):
                    is_valid_sig = True
                    sig_reason = "Valid API Key header"

        # 6. Replay Attack & Timestamp Freshness Check
        is_fresh_time = True
        time_reason = "Timestamp omitted"
        if timestamp_str:
            is_fresh_time, time_reason = self.replay.check_timestamp(timestamp_str)

        is_unique_req = True
        replay_reason = "No request ID provided"
        if request_id:
            is_unique_req, replay_reason = self.replay.check_and_record_request(
                source=source_name,
                request_id=request_id,
                timestamp_str=timestamp_str,
                db=db
            )

        # 7. Payload Schema Structure Validation
        is_valid_schema, schema_err = self.schema.validate_schema(parsed_payload, source_type=source_name)

        # 8. Anomaly & Alert Storm Detection
        service_name = parsed_payload.get("service")
        current_rate, storm_ratio, volume_status = self.anomaly.record_and_evaluate(
            source=source_name,
            service=service_name,
            db=db
        )

        has_known_service = bool(service_name and service_name != "unknown")

        # 9. Trust Scoring Calculation
        trust_score, risk_tier, score_factors = self.trust_scorer.calculate(
            is_known_source=is_known_source,
            is_valid_sig=is_valid_sig,
            is_fresh_time=is_fresh_time,
            is_unique_req=is_unique_req,
            is_valid_schema=is_valid_schema,
            volume_status=volume_status,
            has_known_service=has_known_service
        )

        # 10. Security Decision Engine
        # Case A: Hard Blatant Attacks (Invalid signature when provided/required, or Replay attack)
        if not is_unique_req:
            self.audit.record_event(
                db=db,
                event_type="REPLAY_DETECTED",
                source=source_name,
                action="BLOCKED",
                reason=replay_reason,
                severity="HIGH",
                trust_score=trust_score,
                request_id=request_id,
                metadata={"client_ip": client_ip}
            )
            return {
                "decision": "BLOCKED",
                "status_code": 409,
                "trust_score": trust_score,
                "risk_tier": risk_tier,
                "reason": replay_reason,
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": is_critical_alert
            }

        if source_data and not is_valid_sig:
            # If a signature was provided but is invalid, it is a cryptographic forgery (MALICIOUS) -> BLOCKED 401
            if received_sig:
                self.audit.record_event(
                    db=db,
                    event_type="INVALID_SIGNATURE",
                    source=source_name,
                    action="BLOCKED",
                    reason="Invalid HMAC signature",
                    severity="CRITICAL" if is_critical_alert else "HIGH",
                    trust_score=5.0,
                    request_id=request_id,
                    metadata={"client_ip": client_ip}
                )
                return {
                    "decision": "BLOCKED",
                    "status_code": 401,
                    "trust_score": 5.0,
                    "risk_tier": "HIGH_RISK",
                    "reason": "Unauthorized: Invalid HMAC signature",
                    "source": source_name,
                    "payload": parsed_payload,
                    "is_critical": is_critical_alert
                }

            # Signature was omitted:
            # Critical Alert Safety: If alert is CRITICAL severity, preserve in quarantine rather than dropping
            if is_critical_alert:
                self.audit.record_event(
                    db=db,
                    event_type="ALERT_QUARANTINED",
                    source=source_name,
                    action="QUARANTINED",
                    reason="Missing signature header (X-Alert-Signature) on CRITICAL alert — preserved for SRE review",
                    severity="CRITICAL",
                    trust_score=35.0,
                    request_id=request_id,
                    metadata={"client_ip": client_ip, "is_critical": True}
                )
                return {
                    "decision": "QUARANTINED",
                    "status_code": 202,
                    "trust_score": 35.0,
                    "risk_tier": "HIGH_RISK",
                    "reason": "Preserved in quarantine for review: Missing signature on CRITICAL alert",
                    "source": source_name,
                    "payload": parsed_payload,
                    "is_critical": True
                }

            # Non-critical alert with missing signature:
            self.audit.record_event(
                db=db,
                event_type="INVALID_SIGNATURE",
                source=source_name,
                action="BLOCKED",
                reason="Missing signature header (X-Alert-Signature)",
                severity="MEDIUM",
                trust_score=15.0,
                request_id=request_id,
                metadata={"client_ip": client_ip}
            )
            return {
                "decision": "BLOCKED",
                "status_code": 401,
                "trust_score": 15.0,
                "risk_tier": "HIGH_RISK",
                "reason": "Unauthorized: Missing signature header (X-Alert-Signature)",
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": False
            }

        if not is_fresh_time:
            self.audit.record_event(
                db=db,
                event_type="REPLAY_DETECTED",
                source=source_name,
                action="BLOCKED",
                reason=time_reason,
                severity="MEDIUM",
                trust_score=trust_score,
                request_id=request_id,
                metadata={"client_ip": client_ip}
            )
            return {
                "decision": "BLOCKED",
                "status_code": 400,
                "trust_score": trust_score,
                "risk_tier": risk_tier,
                "reason": f"Bad Request: {time_reason}",
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": is_critical_alert
            }

        # Case B: Volume Anomaly / Storm Injection
        if volume_status in ["SUSPICIOUS_STORM", "HIGH_RISK_INJECTION"]:
            self.audit.record_event(
                db=db,
                event_type="ALERT_INJECTION_DETECTED" if volume_status == "HIGH_RISK_INJECTION" else "ANOMALOUS_VOLUME",
                source=source_name,
                action="QUARANTINED",
                reason=f"Volume surge detected: rate={int(current_rate)}/min ({storm_ratio:.1f}x baseline)",
                severity="HIGH" if volume_status == "HIGH_RISK_INJECTION" else "MEDIUM",
                trust_score=trust_score,
                request_id=request_id,
                metadata={"rate": current_rate, "ratio": storm_ratio}
            )
            return {
                "decision": "QUARANTINED",
                "status_code": 202,
                "trust_score": trust_score,
                "risk_tier": risk_tier,
                "reason": f"Alert Storm / Anomaly ({storm_ratio:.1f}x baseline) — Quarantined for review",
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": is_critical_alert
            }

        # Case C: Unknown source or low trust score
        if not is_known_source or trust_score < 70.0:
            quarantine_msg = f"Low trust score ({trust_score:.0f}/100) or unregistered source '{source_name}'"
            self.audit.record_event(
                db=db,
                event_type="ALERT_QUARANTINED",
                source=source_name,
                action="QUARANTINED",
                reason=quarantine_msg,
                severity="HIGH" if is_critical_alert else "MEDIUM",
                trust_score=trust_score,
                request_id=request_id,
                metadata={"factors": score_factors}
            )
            return {
                "decision": "QUARANTINED",
                "status_code": 202,
                "trust_score": trust_score,
                "risk_tier": risk_tier,
                "reason": quarantine_msg,
                "source": source_name,
                "payload": parsed_payload,
                "is_critical": is_critical_alert
            }

        # Case D: Trusted / Low Risk -> Proceed to existing pipeline
        self.audit.record_event(
            db=db,
            event_type="ALERT_ACCEPTED",
            source=source_name,
            action="ACCEPTED",
            reason=f"Alert passed all security gates (Trust: {trust_score:.0f})",
            severity="INFO",
            trust_score=trust_score,
            request_id=request_id,
            metadata={"factors": score_factors}
        )
        return {
            "decision": "ACCEPTED",
            "status_code": 200,
            "trust_score": trust_score,
            "risk_tier": risk_tier,
            "reason": "Alert verified and accepted",
            "source": source_name,
            "payload": parsed_payload,
            "is_critical": is_critical_alert
        }

# Global singleton instance of AlertIntegrityShield
shield = AlertIntegrityShield()
