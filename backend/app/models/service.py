import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(String(128), primary_key=True) # e.g. "payment-service"
    display_name = Column(String(255), nullable=False)
    criticality = Column(Integer, default=50) # 0 - 100
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "display_name": self.display_name,
            "criticality": self.criticality
        }

class ServiceDependency(Base):
    __tablename__ = "service_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_service = Column(String(128), nullable=False)
    child_service = Column(String(128), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "parent_service": self.parent_service,
            "child_service": self.child_service
        }
