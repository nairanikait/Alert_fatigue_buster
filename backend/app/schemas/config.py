from typing import Dict, Any, Optional
from pydantic import BaseModel

class ConfigUpdateRequest(BaseModel):
    rules: Dict[str, Any]
