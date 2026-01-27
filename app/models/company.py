from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    settings = Column(Text, nullable=True)  # JSON string for settings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
