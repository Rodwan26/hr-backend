from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    period_start = Column(Date)
    period_end = Column(Date)
    overall_score = Column(Integer)  # 1-10 or 1-5
    strengths = Column(Text)
    weaknesses = Column(Text)
    ai_summary = Column(Text)

    employee = relationship("Employee", backref="performance_reviews")
