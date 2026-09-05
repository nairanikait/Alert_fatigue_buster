import os
import sys
import logging
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, status as http_status, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

# Ensure backend directory is accessible for database & models
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
canonical_env = os.path.join(backend_dir, ".env")
if os.path.exists(canonical_env):
    load_dotenv(canonical_env, override=False)

try:
    from app.core.database import get_db, SessionLocal
    from app.models.alert import Alert as DbAlert
except Exception:
    get_db = None
    SessionLocal = None
    DbAlert = None

from models import Alert, RouteResponse
from providers import DashboardProvider, EmailProvider, SlackProvider, PagerDutyProvider
from providers.dashboard import DatabasePersistenceError

logger = logging.getLogger("notification_service.router")
router = APIRouter(tags=["Notification Routing"])

# Centralized routing configuration mapping severity to required channels
ROUTES: Dict[str, List[str]] = {
    "low": ["dashboard"],
    "medium": ["dashboard", "email"],
    "high": ["dashboard", "email", "slack"],
    "critical": ["dashboard", "slack", "pagerduty"]
}

# Modular notification providers registry
# Step 2: DashboardProvider connects to real Supabase PostgreSQL
# Step 3: EmailProvider connects to real Resend API; Slack and PagerDuty remain mock
dashboard_provider = DashboardProvider(session_factory=SessionLocal)
email_provider = EmailProvider()
slack_provider = SlackProvider()
pagerduty_provider = PagerDutyProvider()

PROVIDERS = {
    "dashboard": dashboard_provider,
    "email": email_provider,
    "slack": slack_provider,
    "pagerduty": pagerduty_provider,
}

def get_channels(alert: Alert) -> List[str]:
    """
    Determines the appropriate notification channels based on alert severity.
    Every alert routes to dashboard; severity determines additional channels.
    """
    severity_key = alert.severity.lower()
    return list(ROUTES.get(severity_key, ["dashboard"]))

def _get_db_session() -> Optional[Session]:
    if get_db:
        # FastAPI dependency resolution
        try:
            gen = get_db()
            return next(gen)
        except Exception:
            pass
    if SessionLocal:
        return SessionLocal()
    return None

@router.post("/alert", response_model=RouteResponse, status_code=http_status.HTTP_200_OK)
def route_alert(
    alert: Alert,
    db: Optional[Session] = Depends(get_db) if get_db else None
) -> RouteResponse:
    """
    Standardized alert notification routing endpoint:
    1. Validates alert model.
    2. Determines notification channels using centralized ROUTES.
    3. Persists alert to Supabase PostgreSQL via DashboardProvider.store().
    4. Dispatches real Resend email for MEDIUM alerts; mock providers for Slack/PagerDuty.
    5. Safely captures provider results without impacting alert persistence on delivery failure.
    6. Returns route response.
    """
    channels = get_channels(alert)

    # 1. Persist alert to Supabase PostgreSQL via DashboardProvider
    try:
        dashboard_provider.store(alert, db=db)
    except DatabasePersistenceError as e:
        logger.error(f"Error persisting alert {alert.id} to dashboard: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist alert in database"
        ) from e

    # 2. Dispatch notifications to other required channels
    provider_results = [
        {"channel": "dashboard", "provider": "supabase", "status": "stored"}
    ]

    for channel in channels:
        if channel == "dashboard":
            continue

        provider = PROVIDERS.get(channel)
        if not provider:
            continue

        try:
            if channel == "email":
                # Real Resend email delivery (Step 3)
                res = provider.send(alert)
                if isinstance(res, dict):
                    provider_results.append(res)
                else:
                    provider_results.append({
                        "channel": "email",
                        "provider": "resend",
                        "status": "sent" if res else "failed"
                    })
            elif channel == "slack":
                # Real Slack Incoming Webhook delivery (Step 4)
                res = provider.send(alert)
                if isinstance(res, dict):
                    provider_results.append(res)
                else:
                    provider_results.append({
                        "channel": "slack",
                        "provider": "slack",
                        "status": "sent" if res else "failed"
                    })
            elif channel == "pagerduty":
                # Real PagerDuty Events API v2 delivery (Step 5)
                res = provider.send(alert)
                if isinstance(res, dict):
                    provider_results.append(res)
                else:
                    provider_results.append({
                        "channel": "pagerduty",
                        "provider": "pagerduty",
                        "status": "sent" if res else "failed"
                    })
            else:
                provider.send(alert.id, alert.title, alert.severity)
                provider_results.append({
                    "channel": channel,
                    "provider": getattr(provider, "name", channel),
                    "status": "mock_sent"
                })
        except Exception as prov_err:
            # Failure in secondary channel MUST NOT impact alert persistence in Supabase
            logger.error(
                f"Secondary channel dispatch error for channel '{channel}' (alert '{alert.id}'): {prov_err}"
            )
            provider_results.append({
                "channel": channel,
                "provider": getattr(provider, "name", channel),
                "status": "failed",
                "error": str(prov_err)
            })

    return RouteResponse(
        alert_id=alert.id,
        severity=alert.severity,
        channels=channels,
        results=provider_results
    )

@router.get("/alerts", response_model=List[Dict[str, Any]], summary="Retrieve alerts from Supabase")
def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    status: Optional[str] = Query(None, description="Filter by status: OPEN, ACKNOWLEDGED, RESOLVED"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Optional[Session] = Depends(get_db) if get_db else None
):
    """
    Retrieves stored alerts from Supabase PostgreSQL with optional severity, status, and service filtering.
    """
    own_session = False
    if db is None:
        if not SessionLocal:
            raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database session not configured")
        db = SessionLocal()
        own_session = True

    try:
        query = db.query(DbAlert)

        if severity:
            query = query.filter(func.lower(DbAlert.severity) == severity.lower())
        if status:
            query = query.filter(func.lower(DbAlert.status) == status.lower())
        if service:
            query = query.filter(DbAlert.service == service)

        records = query.order_by(DbAlert.last_seen.desc()).offset(offset).limit(limit).all()

        def _to_utc_iso(dt):
            if not dt:
                return None
            s = dt.isoformat()
            return s if (s.endswith("Z") or "+" in s) else s + "Z"

        results = []
        for r in records:
            results.append({
                "id": r.dedup_key or str(r.id),
                "title": r.title or r.alert_name,
                "description": r.description or r.message,
                "service": r.service,
                "severity": r.severity.lower() if r.severity else "medium",
                "status": r.status or "OPEN",
                "root_cause": r.root_cause,
                "dedup_key": r.dedup_key or r.fingerprint,
                "created_at": _to_utc_iso(r.timestamp or r.first_seen),
                "resolved_at": _to_utc_iso(r.resolved_at)
            })
        return results
    except Exception as e:
        logger.error(f"Failed to query alerts from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts from database"
        ) from e
    finally:
        if own_session and db:
            db.close()
