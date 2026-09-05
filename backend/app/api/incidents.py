from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.incident import Incident
from app.models.alert import Alert
from app.schemas.incident import IncidentResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("", response_model=List[IncidentResponse], summary="List incidents")
def list_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status.upper())
    incidents = query.order_by(Incident.updated_at.desc()).limit(limit).all()
    return [IncidentResponse.model_validate(inc.to_dict()) for inc in incidents]

@router.get("/{incident_id}", summary="Get incident details with linked alerts")
def get_incident_details(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    linked_alerts = (
        db.query(Alert)
        .filter(Alert.correlation_group_id == incident_id)
        .order_by(Alert.first_seen.asc())
        .all()
    )

    return {
        "incident": incident.to_dict(),
        "alerts": [a.to_dict() for a in linked_alerts]
    }
