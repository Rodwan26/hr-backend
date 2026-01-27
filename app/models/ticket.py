from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text)
    ai_response = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
