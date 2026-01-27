from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    metric_type = Column(String)  # work_hours, tasks_completed, response_time
    value = Column(Float)
    date = Column(Date)
    created_at = Column(DateTime, default=datetime.now)

    employee = relationship("Employee", backref="performance_metrics")
