from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class InterviewerAvailability(Base):
    __tablename__ = "interviewer_availabilities"
    
    id = Column(Integer, primary_key=True, index=True)
    interviewer_name = Column(String, index=True)
    interviewer_email = Column(String, index=True)
    available_dates = Column(Text)  # JSON string or comma-separated dates
    available_times = Column(Text)  # JSON string or comma-separated times
