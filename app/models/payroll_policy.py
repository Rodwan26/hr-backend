from sqlalchemy import Column, Integer, String, Float, Boolean, Enum
from app.database import Base
import enum

class CalculationType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"

class PayrollPolicy(Base):
    __tablename__ = "payroll_policies"

    id = Column(Integer, primary_key=True, index=True)
    component_name = Column(String, index=True, unique=True)
    calculation_type = Column(String) # Store enum as string
    default_value = Column(Float) # Amount or Percentage
    is_taxable = Column(Boolean, default=True)
