import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.service import Service, ServiceDependency

TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(Service(id="vendit-app", display_name="Vendit Public Web Application", criticality=95))
    db.commit()
    
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_monitoring_yaml_configs_exist_and_valid():
    """Verify monitoring configuration files exist and have valid YAML syntax."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    monitoring_dir = base_dir / "monitoring"

    # 1. blackbox.yml
    blackbox_file = monitoring_dir / "blackbox.yml"
    assert blackbox_file.exists(), "monitoring/blackbox.yml missing"
    with open(blackbox_file, "r") as f:
        bb_conf = yaml.safe_load(f)
    assert "modules" in bb_conf
    assert "http_2xx" in bb_conf["modules"]
    assert bb_conf["modules"]["http_2xx"]["prober"] == "http"
    assert bb_conf["modules"]["http_2xx"]["timeout"] == "5s"
    assert 200 in bb_conf["modules"]["http_2xx"]["http"]["valid_status_codes"]

    # 2. rules.yml
    rules_file = monitoring_dir / "rules.yml"
    assert rules_file.exists(), "monitoring/rules.yml missing"
    with open(rules_file, "r") as f:
        rules_conf = yaml.safe_load(f)
    assert "groups" in rules_conf
    rule_items = rules_conf["groups"][0]["rules"]
    project_down_rule = next((r for r in rule_items if r.get("alert") == "ProjectDown"), None)
    assert project_down_rule is not None
    assert project_down_rule["expr"] == "probe_success == 0"
    assert project_down_rule["for"] == "10s"
    assert project_down_rule["labels"]["severity"] == "critical"
    assert "{{ $labels.instance }}" in project_down_rule["annotations"]["summary"]

    # 3. prometheus.yml
    prom_file = monitoring_dir / "prometheus.yml"
    assert prom_file.exists(), "monitoring/prometheus.yml missing"
    with open(prom_file, "r") as f:
        prom_conf = yaml.safe_load(f)
    assert "scrape_configs" in prom_conf
    blackbox_job = next((j for j in prom_conf["scrape_configs"] if j.get("job_name") == "blackbox-http"), None)
    assert blackbox_job is not None
    assert blackbox_job["metrics_path"] == "/probe"
    assert blackbox_job["params"]["module"] == ["http_2xx"]
    assert "https://www.vendit.co.in/" in blackbox_job["static_configs"][0]["targets"]
    assert "/etc/prometheus/rules.yml" in prom_conf.get("rule_files", [])

    # 4. alertmanager.yml
    am_file = monitoring_dir / "alertmanager.yml"
    assert am_file.exists(), "monitoring/alertmanager.yml missing"
    with open(am_file, "r") as f:
        am_conf = yaml.safe_load(f)
    assert "receivers" in am_conf
    backend_rec = next((r for r in am_conf["receivers"] if r.get("name") == "alert_buster_backend"), None)
    assert backend_rec is not None
    webhook = backend_rec["webhook_configs"][0]
    assert webhook["url"] == "http://backend:8000/api/alerts/prometheus"
    assert webhook["send_resolved"] is True

def test_alertmanager_webhook_ingestion_standard_payload(db_session):
    """Verify standard Alertmanager webhook payload ingestion for ProjectDown."""
    payload = {
        "version": "4",
        "groupKey": "{}:{alertname=\"ProjectDown\", instance=\"https://www.vendit.co.in/\"}",
        "truncatedAlerts": 0,
        "status": "firing",
        "receiver": "alert_buster_backend",
        "groupLabels": {
            "alertname": "ProjectDown",
            "instance": "https://www.vendit.co.in/"
        },
        "commonLabels": {
            "alertname": "ProjectDown",
            "environment": "production",
            "instance": "https://www.vendit.co.in/",
            "job": "blackbox-http",
            "service": "vendit-app",
            "severity": "critical"
        },
        "commonAnnotations": {
            "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/",
            "description": "Blackbox prober reported probe_success == 0 for https://www.vendit.co.in/"
        },
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ProjectDown",
                    "environment": "production",
                    "instance": "https://www.vendit.co.in/",
                    "job": "blackbox-http",
                    "service": "vendit-app",
                    "severity": "critical"
                },
                "annotations": {
                    "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/",
                    "description": "Blackbox prober reported probe_success == 0 for https://www.vendit.co.in/"
                },
                "startsAt": "2026-09-04T18:45:00.000Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph?g0.expr=probe_success+%3D%3D+0",
                "fingerprint": "a1b2c3d4e5f60718"
            }
        ]
    }

    res = client.post("/api/alerts/prometheus", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["processed_count"] == 1
    assert data["results"][0]["action"] == "NOTIFIED"

    # Check alert was persisted in DB
    alert = db_session.query(Alert).filter(Alert.alert_name == "ProjectDown").first()
    assert alert is not None
    assert alert.service == "vendit-app"
    assert alert.severity == "CRITICAL"
    assert alert.status == "FIRING"
    assert alert.notification_status == "SENT"

    # Check incident was created
    incident = db_session.query(Incident).filter(Incident.root_cause_service == "vendit-app").first()
    assert incident is not None
    assert incident.root_cause_alert_name == "ProjectDown"
    assert incident.status == "FIRING"

    # Check notification dispatched
    notif = db_session.query(Notification).filter(Notification.alert_id == alert.id).first()
    assert notif is not None
    assert notif.channel == "pagerduty"

def test_alertmanager_webhook_resolved_payload(db_session):
    """Verify Alertmanager resolve signal transitions the alert and incident to RESOLVED."""
    # 1. Fire alert first
    firing_payload = {
        "version": "4",
        "status": "firing",
        "receiver": "alert_buster_backend",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ProjectDown",
                    "service": "vendit-app",
                    "severity": "critical",
                    "instance": "https://www.vendit.co.in/"
                },
                "annotations": {
                    "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/"
                },
                "startsAt": "2026-09-04T18:40:00Z",
                "fingerprint": "vendit_fp_123"
            }
        ]
    }
    client.post("/api/alerts/prometheus", json=firing_payload)

    # 2. Send resolve payload
    resolved_payload = {
        "version": "4",
        "status": "resolved",
        "receiver": "alert_buster_backend",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": "ProjectDown",
                    "service": "vendit-app",
                    "severity": "critical",
                    "instance": "https://www.vendit.co.in/"
                },
                "annotations": {
                    "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/"
                },
                "startsAt": "2026-09-04T18:40:00Z",
                "endsAt": "2026-09-04T18:42:30Z",
                "fingerprint": "vendit_fp_123"
            }
        ]
    }

    res = client.post("/api/alerts/prometheus", json=resolved_payload)
    assert res.status_code == 200

    alert = db_session.query(Alert).filter(Alert.alert_name == "ProjectDown").first()
    assert alert.status == "RESOLVED"
    assert alert.duration_seconds > 0

    incident = db_session.query(Incident).filter(Incident.root_cause_service == "vendit-app").first()
    assert incident.status == "RESOLVED"
