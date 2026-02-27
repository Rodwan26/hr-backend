"""
Payroll Router

Handles HTTP endpoints for payroll operations.
All business logic is delegated to the payroll service layer.
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.routers.auth_deps import require_role, get_current_user, get_current_org
from app.services.audit import AuditService
from app.services import payroll_service
from app.services.ai_trust_service import AITrustService
from pydantic import BaseModel


router = APIRouter(
    prefix="/payroll",
    tags=["payroll"],
    dependencies=[Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))]
)


class PayrollSummaryResponse(BaseModel):
    total_budget: float
    exceptions_count: int
    active_employees: int
    recent_payrolls: List[dict]

class PayrollRequest(BaseModel):
    employee_id: int
    month: int
    year: int
    base_salary: float

@router.get("/summary", response_model=PayrollSummaryResponse)
def get_payroll_summary(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    """
    Get high-level payroll summary for the current month.
    """
    return payroll_service.get_payroll_summary(db, org_id)

class LockPayrollRequest(BaseModel):
    month: int
    year: int


class ValidatePayrollRequest(BaseModel):
    employee_id: int
    base_salary: float
    estimated_deductions: float = 0.0


@router.post("/validate")
def validate_payroll(
    request: ValidatePayrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Validate prerequisites before running payroll.
    
    Checks for:
    - Missing bank account details
    - Negative net pay conditions
    - High deduction warnings
    
    Returns validation errors and warnings without executing payroll.
    """
    # Step 1: Validate employee prerequisites
    prereq_result = payroll_service.validate_payroll_prerequisites(
        db, request.employee_id, org_id
    )
    
    # Step 2: Validate calculation
    calc_result = payroll_service.validate_payroll_calculation(
        request.base_salary, request.estimated_deductions
    )
    
    # Combine results
    all_errors = prereq_result["errors"] + calc_result["errors"]
    all_warnings = prereq_result["warnings"] + calc_result["warnings"]
    
    return {
        "valid": len(all_errors) == 0,
        "can_proceed": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
        "employee_id": request.employee_id,
        "estimated_net_pay": calc_result.get("net_pay")
    }

@router.post("/calculate")
def calculate_payroll(
    request: PayrollRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Calculate payroll for a single employee.
    """
    # Check for lock via service
    lock = payroll_service.check_payroll_lock(
        db, request.month, request.year, org_id
    )
    
    if lock:
        raise HTTPException(
            status_code=400, 
            detail=f"Payroll for {request.month}/{request.year} is locked and cannot be recalculated."
        )

    # Delegate to service
    result = payroll_service.calculate_payroll(
        db, 
        request.employee_id, 
        request.month, 
        request.year, 
        request.base_salary,
        organization_id=org_id
    )
    
    AuditService.log(
        db,
        action="calculate_payroll",
        entity_type="payroll",
        entity_id=result.get("id"),
        user_id=current_user.id,
        user_role=current_user.role,
        details={
            "employee_id": request.employee_id, 
            "month": request.month, 
            "year": request.year
        },
        ai_recommended=True,
        organization_id= org_id,
        after_state={"net_salary": result.get("net_salary")}
    )
    
    return result


@router.post("/calculate-bulk")
def calculate_bulk_payroll(
    month: int, 
    year: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Run payroll for all employees in the current user's organization.
    """
    # Check for lock via service
    lock = payroll_service.check_payroll_lock(
        db, month, year, org_id
    )
    
    if lock:
        raise HTTPException(
            status_code=400, 
            detail=f"Payroll for {month}/{year} is locked."
        )

    return payroll_service.calculate_bulk_payroll(
        db, month, year, org_id
    )


@router.get("/history/{employee_id}")
def get_payroll_history(
    employee_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Get payroll history for an employee.
    """
    return payroll_service.get_employee_payroll_history(
        db, employee_id, organization_id=org_id
    )


@router.get("/{payroll_id}")
def get_payroll_details(
    payroll_id: int, 
    db: Session = Depends(get_db), 
    org_id: int = Depends(get_current_org)
):
    """
    Get detailed payroll record by ID.
    """
    try:
        return payroll_service.get_payroll_details(db, payroll_id, organization_id=org_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/ask")
def ask_payroll_question(
    question: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Ask AI questions about payroll policy/history.
    Response is wrapped in TrustedAIResponse.
    """
    try:
        answer = payroll_service.query_rag_for_payroll(
            db, question, org_id
        )
        
        trust_service = AITrustService(
            db, 
            org_id, 
            current_user.id, 
            current_user.role
        )
        return trust_service.wrap_and_log(
            content=answer,
            action_type="payroll_qa",
            entity_type="payroll_query",
            confidence_score=0.85,
            model_name="HR-Payroll-Assistant"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lock")
def lock_payroll_period(
    payload: LockPayrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN])),
    org_id: int = Depends(get_current_org)
):
    """
    Lock a payroll period to prevent further calculations/edits.
    Admin only.
    """
    result = payroll_service.lock_payroll_period(
        db,
        payload.month,
        payload.year,
        current_user.id,
        org_id
    )
    
    if result["status"] == "already_locked":
        return {"message": "Period already locked", "locked_at": result["lock"]["locked_at"]}
    
    AuditService.log(
        db,
        action="lock_payroll",
        entity_type="payroll_period",
        entity_id=result["lock"]["id"],
        user_id=current_user.id,
        user_role=current_user.role,
        details={"month": payload.month, "year": payload.year},
        organization_id=org_id
    )
    
    return {"message": f"Payroll for {payload.month}/{payload.year} locked successfully."}


@router.post("/explain/{payroll_id}")
def explain_payslip(
    payroll_id: int, 
    db: Session = Depends(get_db), 
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(get_current_user)
):
    """
    Generate AI explanation of a payslip.
    Response is wrapped in TrustedAIResponse.
    """
    try:
        explanation = payroll_service.generate_payslip_explanation(db, payroll_id, organization_id=org_id)
        
        trust_service = AITrustService(
            db, 
            org_id, 
            current_user.id, 
            current_user.role
        )
        return trust_service.wrap_and_log(
            content=explanation,
            action_type="explain_payslip",
            entity_type="payroll",
            entity_id=payroll_id,
            confidence_score=0.95,
            model_name="HR-Explain-v1"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/payslip/{payroll_id}/pdf")
def download_payslip_pdf(
    payroll_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Generate and download a PDF payslip.
    
    Returns an HTML document that can be printed to PDF in the browser.
    """
    from fastapi.responses import HTMLResponse
    
    try:
        html_bytes = payroll_service.generate_payslip_pdf(db, payroll_id, organization_id=org_id)
        
        # Log the download action
        AuditService.log(
            db,
            action="download_payslip",
            entity_type="payroll",
            entity_id=payroll_id,
            user_id=current_user.id,
            user_role=current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
            details={"format": "html/pdf"},
            organization_id=org_id
        )
        
        return HTMLResponse(
            content=html_bytes.decode('utf-8'),
            media_type="text/html",
            headers={
                "Content-Disposition": f"inline; filename=payslip_{payroll_id}.html"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

class ValidateAllPayrollRequest(BaseModel):
    month: int
    year: int


@router.post("/validate-all")
def validate_all_payroll(
    request: ValidateAllPayrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Validate prerequisites for ALL employees before running bulk payroll.
    """
    return payroll_service.validate_all_payroll_prerequisites(
        db, org_id, request.month, request.year
    )


@router.get("/payslips/pdf-all")
def download_all_payslips_zip(
    month: int, 
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Download ZIP containing PDF payslips for all employees for a given period.
    """
    from fastapi.responses import Response
    from app.services.notification_service import NotificationService
    
    zip_bytes = payroll_service.generate_all_payslips_zip(
        db, org_id, month, year
    )
    
    if not zip_bytes:
        raise HTTPException(status_code=404, detail="No payroll records found for this period")
        
    # Log the bulk download action
    AuditService.log(
        db,
        action="download_bulk_payslips",
        entity_type="payroll_bulk",
        entity_id=None,
        user_id=current_user.id,
        user_role=current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
        details={"month": month, "year": year, "format": "zip"},
        organization_id=org_id
    )
    
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=payslips_{year}_{month:02d}.zip"
        }
    )
