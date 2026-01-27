from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    file_type = Column(String)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(String, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
