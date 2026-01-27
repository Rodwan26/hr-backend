from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.leave_balance import LeaveBalance
from app.models.leave_policy import LeavePolicy
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
from app.services.leave_ai import check_leave_eligibility, auto_approve_decision, calculate_leave_impact

router = APIRouter(
    prefix="/api/leave",
    tags=["leave"]
)

# --- Pydantic Schemas ---
class LeaveRequestBase(BaseModel):
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    days_count: float
    reason: str

class LeaveRequestCreate(LeaveRequestBase):
    pass

class LeaveRequestResponse(LeaveRequestBase):
    id: int
    status: str
    ai_decision: Optional[str] = None
    ai_reasoning: Optional[str] = None
    created_at: object  # datetime

    class Config:
        orm_mode = True

class LeaveBalanceResponse(BaseModel):
    id: int
    employee_id: str
    leave_type: str
    total_days: float
    used_days: float
    remaining_days: float
    year: int

    class Config:
        orm_mode = True

# --- Endpoints ---

@router.post("/request", response_model=LeaveRequestResponse)
def submit_leave_request(request: LeaveRequestCreate, db: Session = Depends(get_db)):
    # 1. Eligibility Check
    eligibility = check_leave_eligibility(db, request.employee_id, request.leave_type, request.days_count)
    if not eligibility["eligible"]:
        raise HTTPException(status_code=400, detail=eligibility["reason"])

    balance = eligibility.get("balance")
    policy = eligibility.get("policy")

    # 2. AI Decision (Auto Approve vs Manual)
    ai_result = auto_approve_decision(request, balance, policy)
    decision = ai_result.get("decision", "pending_approval")
    reasoning = ai_result.get("reasoning", "")

    new_status = LeaveStatus.APPROVED if decision == "auto_approved" else LeaveStatus.PENDING

    # 3. Create Record
    new_leave = LeaveRequest(
        employee_id=request.employee_id,
        leave_type=request.leave_type,
        start_date=request.start_date,
        end_date=request.end_date,
        days_count=request.days_count,
        reason=request.reason,
        status=new_status,
        ai_decision=decision,
        ai_reasoning=reasoning
    )
    db.add(new_leave)
    
    # 4. Update Balance if Approved
    if new_status == LeaveStatus.APPROVED:
        balance.used_days += request.days_count
        balance.remaining_days -= request.days_count
        db.add(balance)

    db.commit()
    db.refresh(new_leave)
    return new_leave

@router.get("/requests", response_model=List[LeaveRequestResponse])
def list_leave_requests(employee_id: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(LeaveRequest)
    if employee_id:
        query = query.filter(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.filter(LeaveRequest.status == status)
    return query.all()

@router.get("/balance/{employee_id}", response_model=List[LeaveBalanceResponse])
def get_leave_balance(employee_id: str, db: Session = Depends(get_db)):
    balances = db.query(LeaveBalance).filter(LeaveBalance.employee_id == employee_id).all()
    
    # Seed default balances if none exist (for demo purposes)
    if not balances:
        default_types = ["Vacation", "Sick", "Personal"]
        new_balances = []
        for l_type in default_types:
            total = 14.0 if l_type == "Vacation" else (10.0 if l_type == "Sick" else 3.0)
            bal = LeaveBalance(
                employee_id=employee_id,
                leave_type=l_type,
                total_days=total,
                used_days=0.0,
                remaining_days=total,
                year=2024 # Hardcoded for demo
            )
            db.add(bal)
            new_balances.append(bal)
            
            # Seed default policy if missing
            existing_policy = db.query(LeavePolicy).filter(LeavePolicy.leave_type == l_type).first()
            if not existing_policy:
                pol = LeavePolicy(
                    leave_type=l_type,
                    max_days_per_year=total + 5, # ample buffer
                    requires_approval=True,
                    auto_approve_threshold_days=2.0
                )
                db.add(pol)
        
        db.commit()
        for b in new_balances:
            db.refresh(b)
        balances = new_balances

    return balances

@router.put("/requests/{id}/approve")
def approve_request(id: int, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if req.status == LeaveStatus.APPROVED:
        return {"message": "Already approved"}

    # Update balance
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == req.employee_id,
        LeaveBalance.leave_type == req.leave_type
    ).first()

    if balance:
        if balance.remaining_days < req.days_count:
             raise HTTPException(status_code=400, detail="Insufficient balance to approve now")
        balance.used_days += req.days_count
        balance.remaining_days -= req.days_count
    
    req.status = LeaveStatus.APPROVED
    db.commit()
    return {"message": "Approved successfully"}

@router.put("/requests/{id}/reject")
def reject_request(id: int, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    req.status = LeaveStatus.REJECTED
    # If it was previously approved (unlikely flow, but safe to handle), we'd revert balance. 
    # But for now assuming reject only happens on pending.
    
    db.commit()
    return {"message": "Rejected"}

@router.post("/check-eligibility")
def api_check_eligibility(employee_id: str, leave_type: str, days_count: float, db: Session = Depends(get_db)):
    return check_leave_eligibility(db, employee_id, leave_type, days_count)

@router.get("/impact-analysis")
def get_impact_analysis(days_count: float, leave_type: str):
    return {"analysis": calculate_leave_impact(days_count, leave_type)}
