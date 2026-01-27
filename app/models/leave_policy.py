from sqlalchemy import Column, Integer, String, Float, Boolean
from app.database import Base

class LeavePolicy(Base):
    __tablename__ = "leave_policies"

    id = Column(Integer, primary_key=True, index=True)
    leave_type = Column(String, unique=True, index=True)
    max_days_per_year = Column(Float)
    requires_approval = Column(Boolean, default=True)
    auto_approve_threshold_days = Column(Float, default=2.0) # Requests <= this days can be auto-approved
