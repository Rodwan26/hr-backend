from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class OnboardingChat(Base):
    __tablename__ = "onboarding_chats"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("onboarding_employees.id"), index=True)
    question = Column(Text)
    ai_response = Column(Text)
    is_helpful = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

