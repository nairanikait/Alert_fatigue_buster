import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.service import Service, ServiceDependency
from app.models.incident import Incident
from app.schemas.service import (
    ServiceCreate,
    ServiceUpdate,
    DependencyCreate,
    DependencyDeleteRequest,
    TopologyResponse,
    ServiceItem,
    DependencyItem
)

logger = logging.getLogger("alert_buster.api.services")
router = APIRouter(prefix="/services", tags=["Services"])

@router.get("", response_model=TopologyResponse, summary="Get services catalog and dependency topology")
def get_service_topology(db: Session = Depends(get_db)):
    services = db.query(Service).all()
    dependencies = db.query(ServiceDependency).all()
    
    # Active incidents for dynamic status overlay
    active_incidents = db.query(Incident).filter(Incident.status == "FIRING").all()
    root_cause_services = {inc.root_cause_service: inc for inc in active_incidents}
    
    impacted_services = set()
    for inc in active_incidents:
        for aff in (inc.affected_services or []):
            impacted_services.add(aff)

    service_list = []
    for s in services:
        status_val = "healthy"
        incident_info = None
        if s.id in root_cause_services:
            status_val = "root_cause"
            inc = root_cause_services[s.id]
            incident_info = {
                "incident_id": inc.id,
                "reason": inc.root_cause_reason,
                "confidence": inc.confidence_score,
                "severity": inc.severity
            }
        elif s.id in impacted_services:
            status_val = "impacted"

        service_list.append(ServiceItem(
            id=s.id,
            display_name=s.display_name,
            criticality=s.criticality,
            status=status_val,
            incident_info=incident_info
        ))

    dep_list = [
        DependencyItem(parent=d.parent_service, child=d.child_service)
        for d in dependencies
    ]

    return TopologyResponse(
        services=service_list,
        dependencies=dep_list
    )

@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a new service")
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    service_id = payload.id.strip().lower()
    existing = db.query(Service).filter(Service.id == service_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service with ID '{service_id}' already exists."
        )

    new_service = Service(
        id=service_id,
        display_name=payload.display_name.strip(),
        criticality=payload.criticality
    )
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    return {
        "status": "success",
        "message": f"Service '{new_service.display_name}' created successfully.",
        "service": new_service.to_dict()
    }

# -------------------------------------------------------------
# Dependency Routes (MUST be defined before /{service_id} routes)
# -------------------------------------------------------------

@router.get("/dependencies", summary="List all service dependencies")
def get_dependencies(db: Session = Depends(get_db)):
    dependencies = db.query(ServiceDependency).all()
    return [
        {"id": d.id, "parent": d.parent_service, "child": d.child_service}
        for d in dependencies
    ]

@router.post("/dependencies", status_code=status.HTTP_201_CREATED, summary="Create a dependency between two services")
def create_dependency(payload: DependencyCreate, db: Session = Depends(get_db)):
    parent = payload.parent_service.strip().lower()
    child = payload.child_service.strip().lower()

    if parent == child:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent and child cannot be the same service."
        )

    # Verify both services exist
    parent_exists = db.query(Service).filter(Service.id == parent).first()
    if not parent_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent service '{parent}' does not exist."
        )

    child_exists = db.query(Service).filter(Service.id == child).first()
    if not child_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Child service '{child}' does not exist."
        )

    # Check for duplicate dependency
    existing = db.query(ServiceDependency).filter(
        ServiceDependency.parent_service == parent,
        ServiceDependency.child_service == child
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dependency '{parent} -> {child}' already exists."
        )

    new_dep = ServiceDependency(parent_service=parent, child_service=child)
    db.add(new_dep)
    db.commit()
    db.refresh(new_dep)

    return {
        "status": "success",
        "message": f"Dependency '{parent} -> {child}' created successfully.",
        "dependency": {"parent": parent, "child": child}
    }

@router.delete("/dependencies", summary="Delete a service dependency")
def delete_dependency(
    parent: str = Query(..., description="Parent service ID"),
    child: str = Query(..., description="Child service ID"),
    db: Session = Depends(get_db)
):
    parent_val = parent.strip().lower()
    child_val = child.strip().lower()

    dep = db.query(ServiceDependency).filter(
        ServiceDependency.parent_service == parent_val,
        ServiceDependency.child_service == child_val
    ).first()

    if not dep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dependency '{parent_val} -> {child_val}' not found."
        )

    db.delete(dep)
    db.commit()

    return {
        "status": "success",
        "message": f"Dependency '{parent_val} -> {child_val}' deleted successfully."
    }

# -------------------------------------------------------------
# Service By ID Parameter Routes
# -------------------------------------------------------------

@router.put("/{service_id}", summary="Update an existing service")
def update_service(service_id: str, payload: ServiceUpdate, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' does not exist."
        )

    if payload.display_name is not None:
        service.display_name = payload.display_name.strip()
    if payload.criticality is not None:
        service.criticality = payload.criticality

    db.commit()
    db.refresh(service)
    return {
        "status": "success",
        "message": f"Service '{service.display_name}' updated successfully.",
        "service": service.to_dict()
    }

@router.delete("/{service_id}", summary="Delete a service and all its dependency links")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' does not exist."
        )

    # Delete all connected dependency edges
    deleted_deps = db.query(ServiceDependency).filter(
        or_(
            ServiceDependency.parent_service == service_id,
            ServiceDependency.child_service == service_id
        )
    ).delete(synchronize_session=False)

    db.delete(service)
    db.commit()

    return {
        "status": "success",
        "message": f"Service '{service_id}' and {deleted_deps} connected dependencies removed successfully."
    }
