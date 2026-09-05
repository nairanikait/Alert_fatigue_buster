import pytest
from app.utils.fingerprint import generate_fingerprint

def test_fingerprint_basic_and_backward_compatibility():
    fp1 = generate_fingerprint(
        alert_name="HighCpuUsage",
        service="payment-service",
        host="node-01",
        environment="production",
        labels={"tier": "backend"}
    )
    assert isinstance(fp1, str)
    assert len(fp1) == 32

    # Verify idempotency
    fp2 = generate_fingerprint(
        alert_name="HighCpuUsage",
        service="payment-service",
        host="node-01",
        environment="production",
        labels={"tier": "backend"}
    )
    assert fp1 == fp2

def test_fingerprint_case_insensitivity_and_whitespace():
    fp1 = generate_fingerprint(
        alert_name="  HighCpuUsage  ",
        service="PAYMENT-SERVICE",
        host="Node-01 ",
        environment="Production"
    )
    fp2 = generate_fingerprint(
        alert_name="highcpuusage",
        service="payment-service",
        host="node-01",
        environment="production"
    )
    assert fp1 == fp2

def test_fingerprint_ignores_volatile_fields():
    # Alerts differing only in timestamps or ephemeral IDs must produce the SAME fingerprint
    fp1 = generate_fingerprint(
        alert_name="DatabaseConnectionTimeout",
        service="order-db",
        labels={"timestamp": "2026-09-05T10:00:00Z", "run_id": "run-123", "cluster": "prod-east"}
    )
    fp2 = generate_fingerprint(
        alert_name="DatabaseConnectionTimeout",
        service="order-db",
        labels={"timestamp": "2026-09-05T10:05:00Z", "run_id": "run-456", "cluster": "prod-east"}
    )
    assert fp1 == fp2

def test_fingerprint_topological_parameters_differentiation():
    base_args = {
        "alert_name": "DiskSpaceLow",
        "service": "database-cluster",
        "host": "db-node-01",
        "environment": "production"
    }
    
    fp_base = generate_fingerprint(**base_args)

    # Different cluster
    fp_cluster = generate_fingerprint(**base_args, cluster="k8s-us-east-1")
    assert fp_cluster != fp_base

    # Different namespace
    fp_ns = generate_fingerprint(**base_args, namespace="payments-prod")
    assert fp_ns != fp_base

    # Different region
    fp_region = generate_fingerprint(**base_args, region="eu-central-1")
    assert fp_region != fp_base

    # Different source
    fp_source = generate_fingerprint(**base_args, source="prometheus")
    assert fp_source != fp_base

    # Different severity
    fp_sev = generate_fingerprint(**base_args, severity="critical")
    assert fp_sev != fp_base

    # Different component
    fp_comp = generate_fingerprint(**base_args, component="wal-volume")
    assert fp_comp != fp_base

    # Different resource_id
    fp_res = generate_fingerprint(**base_args, resource_id="/dev/nvme0n1")
    assert fp_res != fp_base

def test_fingerprint_custom_attributes():
    fp1 = generate_fingerprint(
        alert_name="Api5xxSpike",
        service="auth-service",
        custom_attributes={"tenant_tier": "enterprise", "customer_id": "c-9901"}
    )
    fp2 = generate_fingerprint(
        alert_name="Api5xxSpike",
        service="auth-service",
        custom_attributes={"tenant_tier": "free", "customer_id": "c-1002"}
    )
    assert fp1 != fp2
