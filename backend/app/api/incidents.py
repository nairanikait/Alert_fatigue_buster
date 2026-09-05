from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


class AIAnalysisRequest(BaseModel):
    regenerate: bool = False
    provider: Optional[str] = None
    api_key: Optional[str] = None


@router.post("/{incident_id}/ai-analysis", summary="Generate or retrieve AI SRE Incident Analysis")
async def get_or_generate_ai_incident_analysis(
    incident_id: str,
    req: Optional[AIAnalysisRequest] = None,
    db: Session = Depends(get_db)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    regenerate = req.regenerate if req else False
    override_key = req.api_key if req else None
    preferred_provider = req.provider if req else None

    # Return cached analysis if available and not requesting regeneration
    if not regenerate and incident.ai_analysis:
        return {
            "incident_id": incident.id,
            "cached": True,
            "analysis": incident.ai_analysis
        }

    # Generate fresh AI SRE solution
    from app.services.ai_incident_copilot import analyze_incident_with_ai
    from app.core.events import ws_manager

    analysis = await analyze_incident_with_ai(
        db=db,
        incident=incident,
        override_api_key=override_key,
        preferred_provider=preferred_provider
    )

    incident.ai_analysis = analysis
    try:
        db.commit()
        db.refresh(incident)
    except Exception as e:
        db.rollback()

    # Broadcast updated incident with AI analysis to frontend
    try:
        await ws_manager.broadcast("INCIDENT_UPDATE", incident.to_dict())
    except Exception:
        pass

    return {
        "incident_id": incident.id,
        "cached": False,
        "analysis": analysis
    }

