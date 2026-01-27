from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.database import Base

class InterviewStatus(str, enum.Enum):
    pending = "pending"
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, index=True)
    candidate_email = Column(String, index=True)
    interviewer_name = Column(String)
    interviewer_email = Column(String)
    job_title = Column(String, index=True)
    preferred_dates = Column(Text)  # JSON string or comma-separated dates
    scheduled_date = Column(String, nullable=True)
    scheduled_time = Column(String, nullable=True)
    meeting_link = Column(String, nullable=True)
    status = Column(SQLEnum(InterviewStatus), default=InterviewStatus.pending, index=True)
    ai_suggestion = Column(Text, nullable=True)  # AI's reasoning for suggested slot
    created_at = Column(DateTime(timezone=True), server_default=func.now())
