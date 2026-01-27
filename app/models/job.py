from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    requirements = Column(Text)
