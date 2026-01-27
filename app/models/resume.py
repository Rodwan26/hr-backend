from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from app.database import Base

class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    name = Column(String)
    resume_text = Column(Text)
    ai_score = Column(Float)
    ai_feedback = Column(Text)
