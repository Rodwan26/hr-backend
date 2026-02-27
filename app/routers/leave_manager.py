from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.user import User, UserRole
from app.schemas.leave import LeaveApprovalRequest, CalendarLeave
from app.routers.auth_deps import get_current_user, require_role, get_current_org
from app.services.audit import AuditService
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)
    
router = APIRouter(prefix="/leave", tags=["leave-manager"])


# Manager Approval endpoint
@router.post("/approve")
def approve_leave(
    approval: LeaveApprovalRequest,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER]))
):
    leave = db.query(LeaveRequest).filter(
        LeaveRequest.id == approval.request_id,
        LeaveRequest.organization_id == org_id
    ).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    # Check if user is authorized to approve (e.g. manager of the employee)
    # Generic check for now based on role
    
    if leave.status != LeaveStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Leave request already processed")

    # Capture before state for audit trail
    before_state = {
        "status": leave.status,
        "approver_id": leave.approver_id,
        "approved_at": str(leave.approved_at) if leave.approved_at else None
    }

    # Update leave request
    # Update leave request logic for multi-level approval
    if approval.approve:
        # Get current and required levels (default to 1 if not set)
        current_level = leave.approval_level if leave.approval_level else 0
        required = leave.required_levels if leave.required_levels else 1
        
        next_level = current_level + 1
        leave.approval_level = next_level
        
        if next_level < required:
            # Intermediate approval
            leave.status = LeaveStatus.PENDING.value
            leave.approver_id = current_user.id
            leave.approved_at = datetime.now(timezone.utc)
            audit_action = f"approve_leave_level_{next_level}"
        else:
            # Final approval
            leave.status = LeaveStatus.APPROVED.value
            if next_level == 1:
                leave.approver_id = current_user.id
                leave.approved_at = datetime.now(timezone.utc)
            elif next_level >= 2:
                leave.second_approver_id = current_user.id
                leave.second_approved_at = datetime.now(timezone.utc)
            audit_action = "approve_leave_final"
    else:
        # Rejection immediately terminates workflow
        leave.status = LeaveStatus.REJECTED.value
        leave.rejection_reason = getattr(approval, 'comment', None)
        # Record who rejected it
        current_level = leave.approval_level if leave.approval_level else 0
        if current_level == 0:
            leave.approver_id = current_user.id
            leave.approved_at = datetime.now(timezone.utc) # timestamp of rejection
        else:
            leave.second_approver_id = current_user.id
            leave.second_approved_at = datetime.now(timezone.utc)
            
        audit_action = "reject_leave"
    
    # Capture after state for audit trail
    after_state = {
        "status": leave.status,
        "approval_level": leave.approval_level,
        "approver_id": leave.approver_id,
        "second_approver_id": leave.second_approver_id
    }
    
    # Log to audit trail
    # ... (existing audit log code) ...
    AuditService.log(
        db,
        action=audit_action,
        entity_type="leave_request",
        entity_id=leave.id,
        user_id=current_user.id,
        user_role=current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
        details={
            "employee_id": leave.employee_id,
            "leave_type": leave.leave_type,
            "comment": getattr(approval, 'comment', None),
            "level": leave.approval_level
        },
        organization_id=org_id,
        before_state=before_state,
        after_state=after_state
    )
    
    # Send Notification
    try:
        approval_status_msg = ""
        if leave.status == LeaveStatus.APPROVED.value:
             approval_status_msg = f"Your {leave.leave_type} request for {leave.days_count} days has been APPROVED."
             NotificationService.send_notification(db, leave.employee_id, "Leave Approved", approval_status_msg, "success")
        elif leave.status == LeaveStatus.REJECTED.value:
             approval_status_msg = f"Your {leave.leave_type} request has been REJECTED. Reason: {leave.rejection_reason}"
             NotificationService.send_notification(db, leave.employee_id, "Leave Rejected", approval_status_msg, "error")
        else:
             # Intermediate approval
             approval_status_msg = f"Your {leave.leave_type} request has been approved by Level {leave.approval_level} and is pending next approval."
             NotificationService.send_notification(db, leave.employee_id, "Leave Update", approval_status_msg, "info")
    except Exception as e:
        # Don't fail the request if notification fails
        logger.warning(f"Notification failed: {e}", exc_info=True)
    
    db.commit()
    db.refresh(leave)
    return {
        "success": True, 
        "leave_status": leave.status, 
        "approval_level": leave.approval_level,
        "approved_by": current_user.id
    }


# Calendar View endpoint
@router.get("/calendar", response_model=List[CalendarLeave])
def leave_calendar(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(get_current_user)
):
    # Retrieve APPROVED leaves
    # Use join to get employee name
    leaves = db.query(LeaveRequest).join(User, LeaveRequest.employee_id == User.id).filter(
        LeaveRequest.status == LeaveStatus.APPROVED.value,
        LeaveRequest.organization_id == org_id
    ).all()
    
    calendar_data = [
        CalendarLeave(
            employee_id=leave.employee_id,
            full_name=leave.employee.full_name or "Unknown",
            start_date=leave.start_date,
            end_date=leave.end_date,
            status=leave.status,
            conflict_detected=leave.conflict_detected
        ) for leave in leaves
    ]
    return calendar_data

