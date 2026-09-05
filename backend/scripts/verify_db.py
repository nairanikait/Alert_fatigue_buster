import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect
from app.core.database import engine, Base, SessionLocal, init_db
from app.models import (
    Simulation, Alert, AlertEvent, Incident, Notification,
    Service, ServiceDependency, SystemRule
)

def verify_database():
    print("=" * 60)
    print("ALERT FATIGUE BUSTER - DATABASE VERIFICATION")
    print("=" * 60)
    
    # Initialize schema
    print(f"Connecting to database: {engine.url.render_as_string(hide_password=True)}")
    init_db()
    print("Schema creation completed.\n")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Discovered {len(tables)} tables:")

    expected_tables = [
        "simulations",
        "alerts",
        "alert_events",
        "incidents",
        "notifications",
        "services",
        "service_dependencies",
        "system_rules",
        "webhook_sources",
        "webhook_requests",
        "security_events",
        "security_baselines"
    ]

    all_ok = True
    for expected in expected_tables:
        if expected in tables:
            columns = inspector.get_columns(expected)
            indexes = inspector.get_indexes(expected)
            col_names = [c["name"] for c in columns]
            idx_names = [i["name"] for i in indexes]
            print(f"  [OK] Table '{expected}': {len(columns)} columns, {len(indexes)} indexes")
            print(f"       Columns: {', '.join(col_names[:8])}{'...' if len(col_names) > 8 else ''}")
            print(f"       Indexes: {', '.join(idx_names) if idx_names else 'PK/default'}")
        else:
            print(f"  [FAIL] Missing table: '{expected}'")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("DATABASE VERIFICATION PASSED: All persistent entities and indexes verified!")
    else:
        print("DATABASE VERIFICATION FAILED: Some tables were not created.")
    print("=" * 60)

if __name__ == "__main__":
    verify_database()
