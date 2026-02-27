from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import Optional

class LeaveRequestCreate(BaseModel):
    start_date: date
    end_date: date
    leave_type: str

class LeaveRequestResponse(BaseModel):
    id: int
    employee_id: int
    start_date: date
    end_date: date
    leave_type: str
    status: str
    conflict_detected: bool
    
    model_config = ConfigDict(from_attributes=True)

class LeaveApprovalRequest(BaseModel):
    request_id: int
    approve: bool
    comment: Optional[str] = None

class CalendarLeave(BaseModel):
    employee_id: int
    full_name: str
    start_date: date
    end_date: date
    status: str # Using str to avoid enum issues for now, or import LeaveStatus
    conflict_detected: bool = False

class LeaveBalanceResponse(BaseModel):
    id: int
    leave_type: str
    total_days: float
    used_days: float
    remaining_days: float
    year: int

    model_config = ConfigDict(from_attributes=True)

class LeaveEligibilityRequest(BaseModel):
    leave_type: str
    days_requested: float

class LeaveEligibilityResponse(BaseModel):
    eligible: bool
    reason: str
    remaining_balance: Optional[float] = None

# Resolve forward references for Pydantic V2
LeaveRequestResponse.model_rebuild()
CalendarLeave.model_rebuild()
LeaveBalanceResponse.model_rebuild()
LeaveEligibilityResponse.model_rebuild()


