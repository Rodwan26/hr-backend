from sqlalchemy import Column, Integer, String, Float
from app.database import Base

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True)
    leave_type = Column(String, index=True) # e.g., "vacation", "sick", "personal"
    total_days = Column(Float, default=0.0)
    used_days = Column(Float, default=0.0)
    remaining_days = Column(Float, default=0.0)
    year = Column(Integer)
