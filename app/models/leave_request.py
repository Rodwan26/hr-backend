from sqlalchemy import Column, Integer, String, Date, Float, Enum, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base
import enum

class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True) # Linking to generic employee ID string for now
    leave_type = Column(String, index=True)
    start_date = Column(Date)
    end_date = Column(Date)
    days_count = Column(Float)
    reason = Column(String)
    status = Column(String, default=LeaveStatus.PENDING) # Using String to store enum value for simplicity with SQLite
    ai_decision = Column(String, nullable=True) # "auto_approved", "suggested_approval", "flagged_for_review"
    ai_reasoning = Column(String, nullable=True) # Explanation from AI
    created_at = Column(DateTime(timezone=True), server_default=func.now())
