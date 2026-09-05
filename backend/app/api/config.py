from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import load_rules, save_rules
from app.models.system_rule import SystemRule
from app.schemas.config import ConfigUpdateRequest

router = APIRouter(prefix="/config", tags=["Configuration"])

@router.get("", summary="Get active alert rules configuration")
def get_config(db: Session = Depends(get_db)):
    # Try reading from DB first, fall back to rules.yaml
    rule_entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
    if rule_entry and rule_entry.value:
        return rule_entry.value
    return load_rules()

@router.put("", summary="Update alert rules configuration")
def update_config(payload: ConfigUpdateRequest, db: Session = Depends(get_db)):
    updated_rules = payload.rules
    
    # Save to rules.yaml
    save_rules(updated_rules)

    # Persist in database
    rule_entry = db.query(SystemRule).filter(SystemRule.key == "active_rules").first()
    if not rule_entry:
        rule_entry = SystemRule(key="active_rules", value=updated_rules)
        db.add(rule_entry)
    else:
        rule_entry.value = updated_rules
    db.commit()

    return {"status": "success", "message": "Rules configuration updated successfully", "rules": updated_rules}
