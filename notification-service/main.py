import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI

# Ensure notification-service directory is in sys.path when run directly or imported
service_dir = os.path.dirname(os.path.abspath(__file__))
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

# Canonical environment configuration: load backend/.env as single source of truth
backend_dir = os.path.abspath(os.path.join(service_dir, "..", "backend"))
canonical_env = os.path.join(backend_dir, ".env")
if os.path.exists(canonical_env):
    load_dotenv(canonical_env, override=False)

from router import router

app = FastAPI(
    title="Alert Fatigue Buster — Notification Routing Service",
    description="Severity-based notification channel router (Step 1 Engine)",
    version="1.0.0"
)

# Mount routing endpoint (POST /alert)
app.include_router(router)

@app.get("/health", summary="Health check endpoint")
def health_check():
    return {
        "status": "healthy",
        "service": "notification-service",
        "step": 1,
        "engine": "routing-only"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
