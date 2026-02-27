from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.schemas.leave import (
    LeaveRequestCreate, LeaveRequestResponse, 
    LeaveBalanceResponse, LeaveEligibilityRequest, LeaveEligibilityResponse
)
from app.models.user import User, UserRole
from app.routers.auth_deps import get_current_user, require_role, get_current_org
from app.services.leave import detect_conflicts
from app.services.leave_ai import check_leave_eligibility as check_eligibility_service

router = APIRouter(prefix="/leave", tags=["leave"])

@router.post("/requests", response_model=LeaveRequestResponse)
def create_leave(
    request: LeaveRequestCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    # Detect conflict
    conflict = detect_conflicts(db, current_user.id, request.start_date, request.end_date)
    
    leave = LeaveRequest(
        employee_id=current_user.id,
        organization_id=org_id,
        start_date=request.start_date,
        end_date=request.end_date,
        leave_type=request.leave_type,
        conflict_detected=conflict,
        status=LeaveStatus.PENDING
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave

@router.get("/requests/{employee_id}", response_model=List[LeaveRequestResponse])
def list_leave_requests(
    employee_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    # Authorization check
    if current_user.role == UserRole.EMPLOYEE and current_user.id != employee_id:
         raise HTTPException(status_code=403, detail="Not authorized to view these requests")
         
    return db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.organization_id == org_id
    ).all()

@router.get("/balance/{employee_id}", response_model=List[LeaveBalanceResponse])
def get_leave_balance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    # Authorization check
    if current_user.role == UserRole.EMPLOYEE and current_user.id != employee_id:
         raise HTTPException(status_code=403, detail="Not authorized to view this balance")
         
    return db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.organization_id == org_id
    ).all()

@router.post("/eligibility", response_model=LeaveEligibilityResponse)
def check_leave_eligibility(
    request: LeaveEligibilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    result = check_eligibility_service(
        db, 
        current_user.id, # Using current user for eligibility check
        request.leave_type, 
        request.days_requested
    )
    
    return LeaveEligibilityResponse(
        eligible=result["eligible"],
        reason=result["reason"],
        remaining_balance=result.get("balance").remaining_days if result.get("balance") else None
    )
