from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Enum as SQLEnum, Boolean, ForeignKey
from sqlalchemy.sql import func
import enum
from app.database import Base


class OnboardingTaskCategory(str, enum.Enum):
    documentation = "documentation"
    training = "training"
    setup = "setup"
    meeting = "meeting"
    other = "other"


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("onboarding_employees.id"), index=True)
    task_title = Column(String, index=True)
    task_description = Column(Text)
    task_category = Column(SQLEnum(OnboardingTaskCategory), default=OnboardingTaskCategory.other, index=True)
    is_completed = Column(Boolean, default=False)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    task_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

