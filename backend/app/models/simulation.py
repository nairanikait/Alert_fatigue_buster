import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from app.core.database import Base

class Simulation(Base):
    __tablename__ = "simulations"

    id = Column(String(64), primary_key=True, index=True)
    scenario = Column(String(128), index=True, nullable=False)
    status = Column(String(32), index=True, default="RUNNING")  # RUNNING, COMPLETED, STOPPED, FAILED
    
    total_alerts = Column(Integer, default=0)
    processed_alerts = Column(Integer, default=0)
    suppressed_alerts = Column(Integer, default=0)
    notifications = Column(Integer, default=0)
    reduction_percentage = Column(Float, default=0.0)
    
    speed = Column(String(32), default="normal")
    severity = Column(String(32), default="mixed")
    
    start_time = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    completion_time = Column(DateTime, nullable=True)
    
    metadata_json = Column(JSON, default=dict)

    __table_args__ = (
        Index("idx_simulation_scenario_status", "scenario", "status"),
        Index("idx_simulation_start_time", "start_time"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "scenario": self.scenario,
            "status": self.status,
            "total_alerts": self.total_alerts,
            "processed_alerts": self.processed_alerts,
            "suppressed_alerts": self.suppressed_alerts,
            "notifications": self.notifications,
            "reduction_percentage": self.reduction_percentage,
            "speed": self.speed,
            "severity": self.severity,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "metadata_json": self.metadata_json or {}
        }
