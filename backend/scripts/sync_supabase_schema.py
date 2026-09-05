import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, text
from app.core.database import engine, Base, SessionLocal
from app.models import (
    Simulation, Alert, AlertEvent, Incident, Notification,
    Service, ServiceDependency, SystemRule
)
from app.main import seed_initial_topology
from app.services.alert_processor import process_alert
from app.services.normalization import normalize_generic

def sync_schema():
    print("=" * 60)
    print("SYNCING SUPABASE POSTGRESQL SCHEMA WITH APPLICATION MODELS")
    print("=" * 60)
    print(f"Target DB: {engine.url.render_as_string(hide_password=True)}")

    # 1. Drop existing tables with mismatched columns
    with engine.begin() as conn:
        print("Dropping existing mismatched tables in Supabase public schema...")
        conn.execute(text("DROP TABLE IF EXISTS alert_batches CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS alert_correlations CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS cooldowns CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS alert_events CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS notifications CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS alerts CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS incidents CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS simulations CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS service_dependencies CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS services CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS system_rules CASCADE;"))

    # 2. Recreate all tables using SQLAlchemy metadata
    print("Creating all tables and indexes matching backend models...")
    Base.metadata.create_all(bind=engine)

    # 3. Seed initial services and topology
    db = SessionLocal()
    try:
        seed_initial_topology(db)
        print("Seeded initial services, dependencies, and rules in Supabase.")

        # 4. Insert a test alert to verify full live persistence
        print("Inserting sample test alert to verify Supabase writes...")
        norm = normalize_generic({
            "source": "prometheus",
            "alert_name": "SupabaseSyncVerificationAlert",
            "service": "database",
            "severity": "critical",
            "status": "firing",
            "message": "Live alert stored in Supabase PostgreSQL database successfully."
        })
        result = process_alert(db, norm)
        print(f"Successfully processed and stored alert in Supabase! (Action: {result.get('action')})")

        # 5. Check row counts
        alert_count = db.query(Alert).count()
        event_count = db.query(AlertEvent).count()
        inc_count = db.query(Incident).count()
        notif_count = db.query(Notification).count()
        print(f"Supabase Table Counts -> Alerts: {alert_count}, Events: {event_count}, Incidents: {inc_count}, Notifications: {notif_count}")

    finally:
        db.close()

    print("=" * 60)
    print("SUPABASE SCHEMA SYNC COMPLETE AND VERIFIED!")
    print("=" * 60)

if __name__ == "__main__":
    sync_schema()
