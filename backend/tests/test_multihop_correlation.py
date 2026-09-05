import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.service import Service, ServiceDependency
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert
from app.services.topology import (
    build_topology_graph,
    get_downstream_services,
    get_upstream_services,
    are_services_topologically_related,
    get_all_related_services
)
from app.services.correlation import find_or_create_incident
from app.services.root_cause import identify_root_cause

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def db():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_1_two_hop_correlation(db):
    """
    Scenario 1: TWO-HOP CORRELATION
    Topology: A -> B -> C
    Alert on A first, then Alert on C.
    Expected: Both alerts correlate into the SAME incident and C is suppressed.
    """
    db.add_all([
        Service(id="svc-a", display_name="Service A", criticality=90),
        Service(id="svc-b", display_name="Service B", criticality=80),
        Service(id="svc-c", display_name="Service C", criticality=70),
        ServiceDependency(parent_service="svc-a", child_service="svc-b"),
        ServiceDependency(parent_service="svc-b", child_service="svc-c"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    # 1. Alert on A
    alert_a = normalize_generic({
        "alert_name": "FailureOnA",
        "service": "svc-a",
        "severity": "critical",
        "status": "firing",
        "message": "Service A encountered fatal exception",
        "timestamp": t0
    })
    res_a = process_alert(db, alert_a)
    assert res_a["action"] == "NOTIFIED"
    inc_a_id = res_a["incident"]["id"]

    # 2. Alert on C (2 hops downstream from A, B did not alert)
    alert_c = normalize_generic({
        "alert_name": "TimeoutOnC",
        "service": "svc-c",
        "severity": "high",
        "status": "firing",
        "message": "Service C timed out",
        "timestamp": t0 + datetime.timedelta(seconds=2)
    })
    res_c = process_alert(db, alert_c)
    assert res_c["action"] == "SUPPRESSED_DOWNSTREAM"
    assert res_c["incident"]["id"] == inc_a_id
    assert "svc-c" in res_c["incident"]["affected_services"]
    assert res_c["incident"]["root_cause_service"] == "svc-a"

def test_2_three_hop_correlation(db):
    """
    Scenario 2: THREE-HOP CORRELATION
    Topology: A -> B -> C -> D
    Alert on A, then Alert on D.
    Expected: Same incident.
    """
    db.add_all([
        Service(id="node-a", display_name="Node A", criticality=95),
        Service(id="node-b", display_name="Node B", criticality=85),
        Service(id="node-c", display_name="Node C", criticality=75),
        Service(id="node-d", display_name="Node D", criticality=65),
        ServiceDependency(parent_service="node-a", child_service="node-b"),
        ServiceDependency(parent_service="node-b", child_service="node-c"),
        ServiceDependency(parent_service="node-c", child_service="node-d"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    res_a = process_alert(db, normalize_generic({
        "alert_name": "CrashNodeA",
        "service": "node-a",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0
    }))
    inc_id = res_a["incident"]["id"]

    res_d = process_alert(db, normalize_generic({
        "alert_name": "GatewayErrorNodeD",
        "service": "node-d",
        "severity": "high",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=1)
    }))

    assert res_d["incident"]["id"] == inc_id
    assert res_d["incident"]["root_cause_service"] == "node-a"
    assert "node-d" in res_d["incident"]["affected_services"]

def test_3_depth_limit(db):
    """
    Scenario 3: DEPTH LIMIT
    Topology: A -> B -> C -> D
    max_depth = 2
    Expected:
      - B (dist 1) is reachable from A
      - C (dist 2) is reachable from A
      - D (dist 3) is NOT reachable from A with max_depth=2
    """
    db.add_all([
        ServiceDependency(parent_service="A", child_service="B"),
        ServiceDependency(parent_service="B", child_service="C"),
        ServiceDependency(parent_service="C", child_service="D"),
    ])
    db.commit()

    downstream_depth_2 = get_downstream_services(db, "A", max_depth=2)
    assert "B" in downstream_depth_2
    assert downstream_depth_2["B"] == 1
    assert "C" in downstream_depth_2
    assert downstream_depth_2["C"] == 2
    assert "D" not in downstream_depth_2

    assert are_services_topologically_related(db, "A", "C", max_depth=2) is True
    assert are_services_topologically_related(db, "A", "D", max_depth=2) is False

    # With max_depth=3, D is reachable
    downstream_depth_3 = get_downstream_services(db, "A", max_depth=3)
    assert "D" in downstream_depth_3
    assert downstream_depth_3["D"] == 3

def test_4_cycle_safety(db):
    """
    Scenario 4: CYCLE SAFETY
    Topology with cycles: A -> B -> C -> A (and B -> D -> B)
    Expected: Traversal terminates safely, never loops infinitely, and respects max_depth.
    """
    db.add_all([
        ServiceDependency(parent_service="cycle-a", child_service="cycle-b"),
        ServiceDependency(parent_service="cycle-b", child_service="cycle-c"),
        ServiceDependency(parent_service="cycle-c", child_service="cycle-a"),
        ServiceDependency(parent_service="cycle-b", child_service="cycle-d"),
        ServiceDependency(parent_service="cycle-d", child_service="cycle-b"),
    ])
    db.commit()

    # Downstream traversal from cycle-a
    downstream = get_downstream_services(db, "cycle-a", max_depth=10)
    assert isinstance(downstream, dict)
    assert "cycle-b" in downstream
    assert downstream["cycle-b"] == 1
    assert "cycle-c" in downstream
    assert downstream["cycle-c"] == 2
    assert "cycle-d" in downstream
    assert downstream["cycle-d"] == 2
    # The origin node is not included as its own downstream child
    assert "cycle-a" not in downstream

    # Upstream traversal from cycle-c
    upstream = get_upstream_services(db, "cycle-c", max_depth=10)
    assert "cycle-b" in upstream
    assert "cycle-a" in upstream

    # Related check terminates safely
    assert are_services_topologically_related(db, "cycle-a", "cycle-d", max_depth=5) is True

def test_5_skipped_intermediate_alert(db):
    """
    Scenario 5: SKIPPED INTERMEDIATE ALERT
    Topology: database -> order-service -> api-gateway
    Alerts:
      T0: database DOWN
      T1: api-gateway DOWN
      (NO alert for order-service)
    Expected:
      api-gateway alert correlates with database incident, root cause = database.
    """
    db.add_all([
        Service(id="database", display_name="Core DB", criticality=100),
        Service(id="order-service", display_name="Order Svc", criticality=85),
        Service(id="api-gateway", display_name="Gateway", criticality=80),
        ServiceDependency(parent_service="database", child_service="order-service"),
        ServiceDependency(parent_service="order-service", child_service="api-gateway"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    res1 = process_alert(db, normalize_generic({
        "alert_name": "DatabaseDown",
        "service": "database",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0
    }))
    assert res1["action"] == "NOTIFIED"

    res2 = process_alert(db, normalize_generic({
        "alert_name": "Gateway502Error",
        "service": "api-gateway",
        "severity": "high",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=1)
    }))
    assert res2["action"] == "SUPPRESSED_DOWNSTREAM"
    assert res2["incident"]["id"] == res1["incident"]["id"]
    assert res2["incident"]["root_cause_service"] == "database"

def test_6_root_cause_correctness(db):
    """
    Scenario 6: ROOT CAUSE CORRECTNESS
    Topology: database -> order-service -> api-gateway -> frontend
    Alerts:
      T0: database at T0
      T1: api-gateway at T1
      T2: frontend at T2
    Expected:
      Root cause remains 'database' throughout the cascade.
    """
    db.add_all([
        Service(id="database", display_name="Core DB", criticality=100),
        Service(id="order-service", display_name="Order Svc", criticality=85),
        Service(id="api-gateway", display_name="Gateway", criticality=80),
        Service(id="frontend", display_name="Web App", criticality=60),
        ServiceDependency(parent_service="database", child_service="order-service"),
        ServiceDependency(parent_service="order-service", child_service="api-gateway"),
        ServiceDependency(parent_service="api-gateway", child_service="frontend"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    res_db = process_alert(db, normalize_generic({
        "alert_name": "DBConnectionPoolExhausted",
        "service": "database",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0
    }))
    inc_id = res_db["incident"]["id"]

    res_gw = process_alert(db, normalize_generic({
        "alert_name": "BadGateway",
        "service": "api-gateway",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=1)
    }))

    res_fe = process_alert(db, normalize_generic({
        "alert_name": "FrontendHTTP500",
        "service": "frontend",
        "severity": "high",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=2)
    }))

    assert res_gw["incident"]["id"] == inc_id
    assert res_fe["incident"]["id"] == inc_id
    assert res_fe["incident"]["root_cause_service"] == "database"
    assert "frontend" in res_fe["incident"]["affected_services"]
    assert "api-gateway" in res_fe["incident"]["affected_services"]

def test_7_arbitrary_topology_generic_names(db):
    """
    Scenario 7: ARBITRARY TOPOLOGY
    Completely generic service names:
      alpha -> beta -> gamma -> delta
    No project-specific names.
    Verify algorithm correctly traverses multi-hop and groups into 1 incident.
    """
    db.add_all([
        Service(id="alpha", display_name="Alpha Core", criticality=99),
        Service(id="beta", display_name="Beta Proxy", criticality=80),
        Service(id="gamma", display_name="Gamma Cache", criticality=70),
        Service(id="delta", display_name="Delta UI", criticality=60),
        ServiceDependency(parent_service="alpha", child_service="beta"),
        ServiceDependency(parent_service="beta", child_service="gamma"),
        ServiceDependency(parent_service="gamma", child_service="delta"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    res_alpha = process_alert(db, normalize_generic({
        "alert_name": "AlphaFailure",
        "service": "alpha",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0
    }))

    res_delta = process_alert(db, normalize_generic({
        "alert_name": "DeltaUnreachable",
        "service": "delta",
        "severity": "medium",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=3)
    }))

    assert res_delta["incident"]["id"] == res_alpha["incident"]["id"]
    assert res_delta["incident"]["root_cause_service"] == "alpha"
    assert res_delta["action"] == "SUPPRESSED_DOWNSTREAM"

def test_8_existing_behavior_regression_1hop(db):
    """
    Scenario 8: EXISTING BEHAVIOR REGRESSION
    Direct 1-hop relationships:
      auth-service -> user-portal
    Alert on auth-service, then alert on user-portal.
    Expected: Same incident, 1-hop behavior functions seamlessly.
    """
    db.add_all([
        Service(id="auth-service", display_name="Auth Service", criticality=90),
        Service(id="user-portal", display_name="User Portal", criticality=70),
        ServiceDependency(parent_service="auth-service", child_service="user-portal"),
    ])
    db.commit()

    t0 = datetime.datetime.utcnow()
    res_auth = process_alert(db, normalize_generic({
        "alert_name": "JWTValidationError",
        "service": "auth-service",
        "severity": "critical",
        "status": "firing",
        "timestamp": t0
    }))

    res_portal = process_alert(db, normalize_generic({
        "alert_name": "LoginFailedSpike",
        "service": "user-portal",
        "severity": "high",
        "status": "firing",
        "timestamp": t0 + datetime.timedelta(seconds=1)
    }))

    assert res_portal["incident"]["id"] == res_auth["incident"]["id"]
    assert res_portal["incident"]["root_cause_service"] == "auth-service"
    assert res_portal["action"] == "SUPPRESSED_DOWNSTREAM"
