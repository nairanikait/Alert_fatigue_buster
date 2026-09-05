from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class Alert(BaseModel):
    id: str = Field(..., description="Unique alert identifier", min_length=1)
    title: str = Field(..., description="Alert title", min_length=1)
    description: str = Field(..., description="Alert description")
    service: str = Field(..., description="Affected service name", min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    root_cause: Optional[str] = None
    dedup_key: Optional[str] = None

    @field_validator("id", "title", "service", mode="before")
    @classmethod
    def check_not_empty_whitespace(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v

class RouteResponse(BaseModel):
    alert_id: str
    severity: str
    channels: List[str]
    results: Optional[List[Dict[str, Any]]] = None
