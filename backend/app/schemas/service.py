from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ServiceCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=128, description="Unique alphanumeric identifier (e.g. order-service)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Human readable service name")
    criticality: int = Field(50, ge=0, le=100, description="Service criticality score from 0 to 100")

class ServiceUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    criticality: Optional[int] = Field(None, ge=0, le=100)

class DependencyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    parent_service: str = Field(..., alias="parent", min_length=1, max_length=128)
    child_service: str = Field(..., alias="child", min_length=1, max_length=128)

class DependencyDeleteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    parent_service: str = Field(..., alias="parent")
    child_service: str = Field(..., alias="child")

class ServiceItem(BaseModel):
    id: str
    display_name: str
    criticality: int
    status: str = "healthy"
    incident_info: Optional[Dict[str, Any]] = None

class DependencyItem(BaseModel):
    parent: str
    child: str

class TopologyResponse(BaseModel):
    services: List[ServiceItem]
    dependencies: List[DependencyItem]
