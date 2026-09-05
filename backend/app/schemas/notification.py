from typing import Optional, Dict, Any
from pydantic import BaseModel

class NotificationResponse(BaseModel):
    id: int
    incident_id: Optional[str] = None
    alert_id: Optional[int] = None
    channel: str
    status: str
    title: str
    message: str
    payload: Dict[str, Any]
    reason: Optional[str] = None
    sent_at: Optional[str] = None

    class Config:
        from_attributes = True
