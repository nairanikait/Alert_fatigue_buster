import datetime
from sqlalchemy import Column, String, DateTime, JSON
from app.core.database import Base

class SystemRule(Base):
    __tablename__ = "system_rules"

    key = Column(String(128), primary_key=True) # e.g. "active_rules"
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
