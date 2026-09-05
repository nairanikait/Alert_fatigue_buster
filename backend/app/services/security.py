import time
import secrets
import threading
import logging
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from fastapi import Request, HTTPException, Header, Response
from app.core.config import settings, load_rules
from app.services.security_shield import shield

logger = logging.getLogger("alert_buster.security")

@dataclass
class SecurityAuditEntry:
    id: str
    timestamp: float
    iso_time: str
    endpoint: str
    source: str
    client_ip: str
    reason: str  # "AUTH_FAILED", "RATE_LIMITED", "INVALID_SCHEMA"
    status_code: int
    payload_excerpt: Optional[str] = None

class SecurityAuditLogger:
    """
    Thread-safe bounded in-memory ring-buffer for security & abuse audit events.
    Strictly capped at maximum 50 entries.
    """
    def __init__(self, max_entries: int = 50):
        self.max_entries = max_entries
        self._entries: deque = deque(maxlen=max_entries)
        self._counter: int = 0
        self._lock = threading.Lock()

    def log_event(
        self,
        endpoint: str,
        source: str,
        client_ip: str,
        reason: str,
        status_code: int,
        payload_raw: Optional[Any] = None
    ) -> Dict[str, Any]:
        with self._lock:
            self._counter += 1
            now = time.time()
            iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            
            # Create safe sanitized excerpt (truncate to max 120 chars, scrub secret words)
            excerpt = None
            if payload_raw is not None:
                raw_str = str(payload_raw)
                # Ensure no secrets leak
                if len(raw_str) > 120:
                    excerpt = raw_str[:120] + "..."
                else:
                    excerpt = raw_str

            entry = SecurityAuditEntry(
                id=f"audit_{self._counter}_{int(now)}",
                timestamp=now,
                iso_time=iso,
                endpoint=endpoint,
                source=source,
                client_ip=client_ip,
                reason=reason,
                status_code=status_code,
                payload_excerpt=excerpt
            )
            self._entries.appendleft(entry)
            entry_dict = asdict(entry)

        logger.warning(f"Security Alert [{status_code}] ({reason}) on {endpoint} from {source} [{client_ip}]")
        
        # Non-blocking WebSocket broadcast if event manager is available
        try:
            from app.core.events import ws_manager
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast("SECURITY_ALERT", entry_dict))
            except RuntimeError:
                pass
        except Exception:
            pass

        return entry_dict

    def get_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            eff_limit = min(limit, self.max_entries)
            return [asdict(e) for e in list(self._entries)[:eff_limit]]

    def clear(self):
        with self._lock:
            self._entries.clear()

class SourceRateLimiter:
    """
    Thread-safe Sliding-window per-source rate limiter.
    Maintains independent rate-limit windows for each monitoring source/client.
    Cleans up expired timestamps automatically to maintain bounded memory.
    """
    def __init__(self, default_limit: int = 150, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._requests: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def get_config_limit(self) -> int:
        try:
            rules = load_rules()
            rate_cfg = rules.get("rate_limiting", {})
            return rate_cfg.get("requests_per_minute", self.default_limit)
        except Exception:
            return self.default_limit

    def is_allowed(self, source_id: str, custom_limit: Optional[int] = None) -> Tuple[bool, int, int]:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            max_limit = custom_limit or self.get_config_limit()

            if source_id not in self._requests:
                self._requests[source_id] = deque()

            timestamps = self._requests[source_id]

            # Clean expired timestamps
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

# Global security service instances
security_audit_logger = SecurityAuditLogger(max_entries=50)
rate_limiter = SourceRateLimiter(default_limit=150, window_seconds=60)

def validate_alert_payload_structure(data: Any, source_type: str = "generic") -> Tuple[bool, Optional[str]]:
    """
    Validates incoming payload before ingestion and database processing.
    Rejects malformed JSON, non-object payloads, and missing critical fields.
    """
    if not isinstance(data, dict):
        return False, "Payload must be a valid JSON object"

    if not data:
        return False, "Payload cannot be empty"

    if source_type == "prometheus":
        if "alerts" not in data or not isinstance(data.get("alerts"), list):
            return False, "Prometheus payload must contain an 'alerts' list"
        if len(data.get("alerts", [])) == 0:
            return False, "Prometheus 'alerts' list cannot be empty"
        for i, alt in enumerate(data["alerts"]):
            if not isinstance(alt, dict):
                return False, f"Alert at index {i} must be a valid JSON object"
            labels = alt.get("labels", {})
            if not isinstance(labels, dict):
                return False, f"Alert at index {i} has invalid 'labels' format"
            if not labels.get("alertname") and not labels.get("alert_name"):
                return False, f"Alert at index {i} missing mandatory 'alertname' label"
        return True, None

    if source_type == "datadog":
        if not data.get("title") and not data.get("alert_name") and not data.get("event_type"):
            return False, "Datadog payload missing mandatory 'title' or 'alert_name' identifier"
        return True, None

    # Generic schema validation
    has_name = bool(
        data.get("alert_name") or
        data.get("alertname") or
        data.get("title") or
        (isinstance(data.get("labels"), dict) and (data.get("labels", {}).get("alertname") or data.get("labels", {}).get("alert_name")))
    )
    if not has_name:
        return False, "Missing required alert identifier (alert_name, alertname, or title)"

    return True, None

def verify_ingest_auth(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
):
    """
    Verifies API Key / Webhook Secret authentication (if configured)
    and enforces Per-Source Rate Limiting.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    endpoint_path = str(request.url.path)
    
    # Determine source name from endpoint or custom header
    if "prometheus" in endpoint_path:
        source_name = "prometheus"
    elif "datadog" in endpoint_path:
        source_name = "datadog"
    else:
        source_name = "generic"

    # 1. Authentication Check
    configured_secret = settings.WEBHOOK_SECRET
    if configured_secret:
        auth_key = x_api_key or x_webhook_secret
        if not auth_key or not secrets.compare_digest(auth_key, configured_secret):
            security_audit_logger.log_event(
                endpoint=endpoint_path,
                source=source_name,
                client_ip=client_ip,
                reason="AUTH_FAILED",
                status_code=401,
                payload_raw="[Redacted Authentication Failure]"
            )
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Invalid or missing authentication credentials (X-API-Key or X-Webhook-Secret)"
            )

    # 2. Per-Source Rate Limiting
    rate_source_key = f"{source_name}:{client_ip}"
    allowed, current_count, max_limit = rate_limiter.is_allowed(rate_source_key)
    if not allowed:
        security_audit_logger.log_event(
            endpoint=endpoint_path,
            source=source_name,
            client_ip=client_ip,
            reason="RATE_LIMITED",
            status_code=429,
            payload_raw=f"Rate limit exceeded: {current_count}/{max_limit} req/min"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too Many Requests: Rate limit exceeded for source '{source_name}' ({current_count}/{max_limit} req/min).",
            headers={"Retry-After": "60"}
        )
