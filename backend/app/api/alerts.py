import asyncio
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.events import ws_manager
from app.models.alert import Alert
from app.schemas.alert import GenericAlertInput, PrometheusWebhookInput, DatadogWebhookInput, AlertResponse
from app.services.normalization import normalize_generic, normalize_prometheus, normalize_datadog
from app.services.alert_processor import process_alert
from app.services.security import (
    verify_ingest_auth,
    validate_alert_payload_structure,
    security_audit_logger
)

logger = logging.getLogger("alert_buster.api.alerts")
router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.post("/webhook", summary="Ingest generic alert payload with auth, rate-limit & validation")
async def ingest_generic_webhook(
    payload: GenericAlertInput,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_auth)
):
    raw_dict = payload.model_dump()
    is_valid, error_msg = validate_alert_payload_structure(raw_dict, source_type="generic")
    if not is_valid:
        client_ip = request.client.host if request.client else "127.0.0.1"
        security_audit_logger.log_event(
            endpoint="/api/alerts/webhook",
            source=str(raw_dict.get("source", "generic")),
            client_ip=client_ip,
            reason="INVALID_SCHEMA",
            status_code=400,
            payload_raw=str(raw_dict)
        )
        raise HTTPException(status_code=400, detail=f"Bad Request: {error_msg}")

    normalized = normalize_generic(raw_dict)
    result = process_alert(db, normalized)
    
    # Non-blocking WebSocket broadcast
    asyncio.create_task(ws_manager.broadcast("ALERT_UPDATE", result))
    return {"status": "success", "result": result}

@router.post("/prometheus", summary="Ingest Prometheus Alertmanager webhook with auth, rate-limit & validation")
async def ingest_prometheus_webhook(
    payload: PrometheusWebhookInput,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_auth)
):
    raw_dict = payload.model_dump()
    is_valid, error_msg = validate_alert_payload_structure(raw_dict, source_type="prometheus")
    if not is_valid:
        client_ip = request.client.host if request.client else "127.0.0.1"
        security_audit_logger.log_event(
            endpoint="/api/alerts/prometheus",
            source="prometheus",
            client_ip=client_ip,
            reason="INVALID_SCHEMA",
            status_code=400,
            payload_raw=str(raw_dict)
        )
        raise HTTPException(status_code=400, detail=f"Bad Request: {error_msg}")

    normalized_items = normalize_prometheus(raw_dict)
    results = []
    for item in normalized_items:
        res = process_alert(db, item)
        results.append(res)
        asyncio.create_task(ws_manager.broadcast("ALERT_UPDATE", res))
    return {"status": "success", "processed_count": len(results), "results": results}

@router.post("/datadog", summary="Ingest Datadog webhook with auth, rate-limit & validation")
async def ingest_datadog_webhook(
    payload: DatadogWebhookInput,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_ingest_auth)
):
    raw_dict = payload.model_dump()
    is_valid, error_msg = validate_alert_payload_structure(raw_dict, source_type="datadog")
    if not is_valid:
        client_ip = request.client.host if request.client else "127.0.0.1"
        security_audit_logger.log_event(
            endpoint="/api/alerts/datadog",
            source="datadog",
            client_ip=client_ip,
            reason="INVALID_SCHEMA",
            status_code=400,
            payload_raw=str(raw_dict)
        )
        raise HTTPException(status_code=400, detail=f"Bad Request: {error_msg}")

    normalized = normalize_datadog(raw_dict)
    result = process_alert(db, normalized)
    asyncio.create_task(ws_manager.broadcast("ALERT_UPDATE", result))
    return {"status": "success", "result": result}

@router.get("/security-audit", summary="Get recent ingestion security & abuse rejections audit log")
def get_security_audit_log(limit: int = Query(50, ge=1, le=50)):
    """
    Returns the in-memory circular audit log of rejected ingestion attempts
    (rate limits, invalid API keys, malformed schemas). Maximum 50 entries.
    """
    entries = security_audit_logger.get_entries(limit)
    return {
        "status": "success",
        "total_entries": len(entries),
        "entries": entries
    }

@router.delete("/security-audit", summary="Clear security audit log")
def clear_security_audit_log():
    security_audit_logger.clear()
    return {"status": "success", "message": "Security audit log cleared"}

@router.get("", response_model=List[AlertResponse], summary="List and filter alerts")
def list_alerts(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    service: Optional[str] = None,
    source: Optional[str] = None,
    security_status: Optional[str] = None,
    is_flaky: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity.upper())
    if status:
        query = query.filter(Alert.status == status.upper())
    if service:
        query = query.filter(Alert.service == service)
    if source:
        query = query.filter(Alert.source == source)
    if security_status:
        query = query.filter(Alert.security_status == security_status.upper())
    if is_flaky is not None:
        query = query.filter(Alert.is_flaky == is_flaky)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Alert.alert_name.ilike(term),
                Alert.service.ilike(term),
                Alert.host.ilike(term),
                Alert.message.ilike(term)
            )
        )

    alerts = query.order_by(Alert.last_seen.desc()).offset(offset).limit(limit).all()
    return [AlertResponse.model_validate(a.to_dict()) for a in alerts]

@router.get("/{alert_id}", response_model=AlertResponse, summary="Get single alert detail")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert.to_dict())
