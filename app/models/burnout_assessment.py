from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class BurnoutAssessment(Base):
    __tablename__ = "burnout_assessments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    risk_level = Column(String)  # low, medium, high, critical
    indicators = Column(JSON)  # List of detected indicators
    ai_analysis = Column(String)
    recommendations = Column(JSON)  # List of recommendations
    assessed_at = Column(DateTime, default=datetime.now)

    employee = relationship("Employee", backref="burnout_assessments")
