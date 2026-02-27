from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.ticket import Ticket
from app.models.onboarding_employee import OnboardingEmployee
from app.routers.auth_deps import require_role, get_current_org
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import func

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role([UserRole.HR_ADMIN]))]
)

class DashboardStat(BaseModel):
    name: str
    value: str
    change: str
    changeType: str # "increase" | "decrease"

class DashboardSummary(BaseModel):
    stats: List[DashboardStat]
    wellbeing_score: float
    onboarding_avg_progress: int
    recent_activity_count: int

class AuditLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    user_id: Optional[int]
    user_role: Optional[str]
    details: Optional[dict]
    ai_recommended: bool
    timestamp: datetime
    organization_id: Optional[int]
    before_state: Optional[dict]
    after_state: Optional[dict]

    class Config:
        orm_mode = True

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    """
    Get aggregated dashboard statistics for the organization.
    """
    # 1. Employee Count
    emp_count = db.query(Employee).filter(Employee.organization_id == org_id).count()
    
    # 2. Active Requests (Pending Leave Requests)
    active_requests = db.query(LeaveRequest).filter(
        LeaveRequest.organization_id == org_id,
        LeaveRequest.status == LeaveStatus.PENDING
    ).count()
    
    # 3. AI Tickets Resolved
    ai_tickets = db.query(Ticket).filter(Ticket.organization_id == org_id).count()
    
    # 4. Onboarding Progress Average
    avg_progress = db.query(func.avg(OnboardingEmployee.completion_percentage)).filter(
        OnboardingEmployee.organization_id == org_id
    ).scalar() or 0
    
    # Construct Stats
    stats = [
        {"name": "Total Employees", "value": f"{emp_count:,}", "change": "+0%", "changeType": "increase"},
        {"name": "Active Requests", "value": str(active_requests), "change": "+0%", "changeType": "increase"},
        {"name": "AI Tickets Resolved", "value": f"{ai_tickets:,}", "change": "+0%", "changeType": "increase"},
        {"name": "Onboarding Progress", "value": f"{int(avg_progress)}%", "change": "+0%", "changeType": "increase"},
    ]
    
    return DashboardSummary(
        stats=stats,
        wellbeing_score=8.4, # Hardcoded for now until risk/wellbeing services are fully connected
        onboarding_avg_progress=int(avg_progress),
        recent_activity_count=db.query(AuditLog).filter(AuditLog.organization_id == org_id).count()
    )

@router.get("/audit-logs", response_model=List[AuditLogResponse])
@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN])),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g. 'leave_request')"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    limit: int = 100,
    skip: int = 0
):
    """
    Get audit logs. READ-ONLY.
    Restricted to HR_ADMIN only, scoped to their organization.
    """
    query = db.query(AuditLog).filter(
        AuditLog.organization_id == org_id
    )
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
        
    return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

@router.get("/audit-logs/{id}", response_model=AuditLogResponse)
def get_audit_log_detail(
    id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    """
    Get specific audit log entry. READ-ONLY.
    """
    log_entry = db.query(AuditLog).filter(
        AuditLog.id == id,
        AuditLog.organization_id == org_id
    ).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Audit log entry not found")
    return log_entry
