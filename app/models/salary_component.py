from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class ComponentType(str, enum.Enum):
    BONUS = "bonus"
    DEDUCTION = "deduction"
    ALLOWANCE = "allowance"
    BASE = "base"

class SalaryComponent(Base):
    __tablename__ = "salary_components"

    id = Column(Integer, primary_key=True, index=True)
    payroll_id = Column(Integer, ForeignKey("payrolls.id"))
    component_type = Column(String) # Store enum value as string
    name = Column(String)
    amount = Column(Float)
    description = Column(String, nullable=True)

    payroll = relationship("Payroll", back_populates="components")
