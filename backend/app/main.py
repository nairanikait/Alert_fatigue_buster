import os
import sys
import logging
from contextlib import asynccontextmanager

# Automatically ensure backend folder is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.services.security import security_audit_logger

from app.core.config import settings, load_rules
from app.core.database import engine, SessionLocal, Base, get_db
from app.core.events import ws_manager
from app.models.service import Service, ServiceDependency
from app.models.system_rule import SystemRule

# Import all API routers
from app.api.alerts import router as alerts_router
from app.api.incidents import router as incidents_router
from app.api.metrics import router as metrics_router
from app.api.notifications import router as notifications_router
from app.api.services import router as services_router
from app.api.config import router as config_router
from app.api.demo import router as demo_router
from app.api.simulator import router as simulator_router
from app.api.simulations import router as simulations_router, handle_simulation_ws
from app.api.chat import router as chat_router
from app.api.security import router as security_router
from app.services.security_shield import shield

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("alert_buster")

def seed_initial_topology(db: Session):
    """
    Seeds initial services and dependencies from rules.yaml if database is empty.
    """
    rules = load_rules()
    services_data = rules.get("services", {})
    dependencies_data = rules.get("dependencies", [])

    existing_svc_count = db.query(Service).count()
    if existing_svc_count == 0:
        logger.info("Seeding initial service topology...")
        for svc_id, info in services_data.items():
            db.add(Service(
                id=svc_id,
                display_name=info.get("display_name", svc_id.replace("-", " ").title()),
                criticality=info.get("criticality", 50)
            ))
        
        for dep in dependencies_data:
            db.add(ServiceDependency(
                parent_service=dep["parent"],
                child_service=dep["child"]
            ))

        # Seed initial rules in DB (upsert safely)
        existing_rule = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
        if not existing_rule:
            db.add(SystemRule(key="active_rules", value=rules))
        else:
            existing_rule.value = rules
        db.commit()
        logger.info(f"Seeded {len(services_data)} services and {len(dependencies_data)} dependencies.")

from app.services.batch_flusher import batch_flusher

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    
    # Seed default services and security sources
    db = SessionLocal()
    try:
        seed_initial_topology(db)
        shield.auth.seed_defaults(db)
    finally:
        db.close()

    # Start background batch flush worker
    batch_flusher.start()

    # Safe check for Resend configuration (reports true/false only, never exposes the key)
    resend_is_configured = bool(os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None))
    logger.info(
        f"[STARTUP CONFIG] Resend Email Integration: configured={resend_is_configured} | "
        f"sender='{settings.RESEND_FROM_EMAIL}' | recipient='{settings.NOTIFICATION_EMAIL}'"
    )

    # Safe check for Slack configuration (reports true/false only, never exposes the webhook URL)
    slack_is_configured = bool(os.getenv("SLACK_WEBHOOK_URL") or getattr(settings, "SLACK_WEBHOOK_URL", None))
    logger.info(
        f"[STARTUP CONFIG] Slack Incoming Webhook: configured={slack_is_configured}"
    )

    # Safe check for PagerDuty configuration (reports true/false only, never exposes the key)
    pagerduty_is_configured = bool(os.getenv("PAGERDUTY_API_KEY") or getattr(settings, "PAGERDUTY_API_KEY", None))
    logger.info(
        f"[STARTUP CONFIG] PagerDuty Events API v2: configured={pagerduty_is_configured}"
    )

    yield

    # Shutdown background worker
    logger.info("Stopping batch flush background worker...")
    await batch_flusher.stop()
    logger.info("Shutting down Alert Fatigue Buster application...")

app = FastAPI(
    title="Alert Fatigue Buster",
    description="Smart alert intelligence middleware that turns alert noise into actionable incidents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Exception handler to normalize validation errors to 400 and record in security audit log
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    client_ip = request.client.host if request.client else "unknown"
    path = str(request.url.path)
    error_details = exc.errors()
    msg = "; ".join([f"{'.'.join(str(l) for l in err.get('loc', []))}: {err.get('msg')}" for err in error_details])
    
    if "/api/alerts" in path:
        security_audit_logger.log_event(
            endpoint=path,
            source="invalid_schema",
            client_ip=client_ip,
            reason="INVALID_SCHEMA",
            status_code=400,
            payload_raw=str(exc.body) if hasattr(exc, "body") else None
        )
        return JSONResponse(
            status_code=400,
            content={"detail": f"Bad Request: Missing required alert identifier or invalid payload structure ({msg})"}
        )
    return JSONResponse(
        status_code=422,
        content={"detail": error_details}
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Endpoint
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for client pings or queries
            data = await websocket.receive_text()
            # Echo heartbeat or pong if needed
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        ws_manager.disconnect(websocket)

# Simulation WebSocket Endpoints
@app.websocket("/api/ws/simulation/{simulation_id}")
@app.websocket("/ws/simulation/{simulation_id}")
async def simulation_websocket_endpoint(websocket: WebSocket, simulation_id: str):
    await handle_simulation_ws(websocket, simulation_id)

# Health Check
@app.get("/health", summary="Health Check")
def health_check():
    return {
        "status": "ok",
        "service": "alert-buster",
        "tagline": "Turn alert noise into actionable incidents."
    }

# Register API Routers
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(metrics_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(services_router, prefix=settings.API_V1_STR)
app.include_router(config_router, prefix=settings.API_V1_STR)
app.include_router(demo_router, prefix=settings.API_V1_STR)
app.include_router(simulator_router, prefix=settings.API_V1_STR)
app.include_router(simulations_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(security_router, prefix=settings.API_V1_STR)

# Aliases for webhook ingestion
from app.api.security import ingest_with_shield
@app.post("/api/webhooks/alerts", summary="Direct Webhook Ingestion with Alert Integrity Shield")
async def webhook_alerts_alias(request: Request, response: Response, db: Session = Depends(get_db)):
    return await ingest_with_shield(request, response, db)

# Analytics endpoint alias
from app.api.metrics import get_metrics
@app.get("/api/analytics/overview", summary="Analytics Overview")
@app.get("/api/analytics", summary="Analytics Overview Alias")
def get_analytics_overview(db: Session = Depends(get_db)):
    return get_metrics(db)

# Notification Routing Engine (Step 1, 2, 3: Persistence, /alerts, Resend Email)
try:
    notif_svc_path = os.path.join(os.path.dirname(backend_dir), "notification-service")
    if notif_svc_path not in sys.path:
        sys.path.insert(0, notif_svc_path)
    from router import router as notification_router
    app.include_router(notification_router)
except Exception as e:
    logging.getLogger("alert_buster").warning(f"Could not mount notification router: {e}")


