import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
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

@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

client = TestClient(app)

def test_service_and_dependency_crud():
    # 1. Create service Alpha
    res1 = client.post("/api/services", json={"id": "alpha", "display_name": "Alpha Service", "criticality": 90})
    assert res1.status_code == 201
    assert res1.json()["service"]["id"] == "alpha"

    # 2. Create service Beta
    res2 = client.post("/api/services", json={"id": "beta", "display_name": "Beta Service", "criticality": 80})
    assert res2.status_code == 201

    # 3. Duplicate ID rejection (400)
    dup = client.post("/api/services", json={"id": "alpha", "display_name": "Duplicate Alpha", "criticality": 50})
    assert dup.status_code == 400

    # 4. Update service Beta
    res_up = client.put("/api/services/beta", json={"display_name": "Beta Worker Service", "criticality": 85})
    assert res_up.status_code == 200
    assert res_up.json()["service"]["display_name"] == "Beta Worker Service"
    assert res_up.json()["service"]["criticality"] == 85

    # 5. Create dependency Alpha -> Beta
    res_dep = client.post("/api/services/dependencies", json={"parent": "alpha", "child": "beta"})
    assert res_dep.status_code == 201

    # 6. Self-dependency rejection (400)
    self_dep = client.post("/api/services/dependencies", json={"parent": "alpha", "child": "alpha"})
    assert self_dep.status_code == 400

    # 7. Non-existent service dependency rejection (404)
    non_dep = client.post("/api/services/dependencies", json={"parent": "alpha", "child": "gamma"})
    assert non_dep.status_code == 404

    # 8. Duplicate dependency rejection (400)
    dup_dep = client.post("/api/services/dependencies", json={"parent": "alpha", "child": "beta"})
    assert dup_dep.status_code == 400

    # 9. List topology
    res_top = client.get("/api/services")
    assert res_top.status_code == 200
    top_data = res_top.json()
    assert len(top_data["services"]) == 2
    assert len(top_data["dependencies"]) == 1

    # 10. Delete dependency
    del_dep = client.delete("/api/services/dependencies?parent=alpha&child=beta")
    assert del_dep.status_code == 200

    # 11. Delete service
    del_svc = client.delete("/api/services/beta")
    assert del_svc.status_code == 200

    # 12. Confirm deleted
    top_after = client.get("/api/services").json()
    assert len(top_after["services"]) == 1
    assert len(top_after["dependencies"]) == 0
