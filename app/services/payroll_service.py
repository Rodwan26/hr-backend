"""
Payroll Service Layer

This module provides the business logic layer for payroll operations.
It encapsulates all database access and AI operations, keeping the router
focused on HTTP request/response handling.

Architecture:
- Router -> Service (this module) -> Models/AI
- All business rules are implemented here
- AI operations delegate to PayrollAIService
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
import zipfile
import io

from app.models.payroll import Payroll, PayrollLock, PayrollStatus
from app.models.employee import Employee
from app.services.payroll_ai import PayrollAIService

logger = logging.getLogger(__name__)

# Singleton-like instance for the AI service
_ai_service = PayrollAIService()


def validate_payroll_prerequisites(
    db: Session,
    employee_id: int,
    organization_id: int
) -> Dict[str, Any]:
    """
    Validate prerequisites before running payroll.
    
    Checks for:
    - Missing bank account details
    - Missing employee profile data
    
    Args:
        db: Database session
        employee_id: ID of the employee
        organization_id: Organization ID
    
    Returns:
        Dict with validation results: {valid: bool, errors: [], warnings: []}
    """
    errors = []
    warnings = []
    
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.organization_id == organization_id
    ).first()
    
    if not employee:
        return {
            "valid": False,
            "errors": ["Employee not found"],
            "warnings": []
        }
    
    # Check for bank details (if the model has these fields)
    if hasattr(employee, 'bank_account') and not employee.bank_account:
        errors.append("Missing bank account number")
    
    if hasattr(employee, 'bank_name') and not employee.bank_name:
        warnings.append("Missing bank name")
    
    if hasattr(employee, 'tax_id') and not employee.tax_id:
        warnings.append("Missing tax ID - may affect deductions")
    
    # Check for base salary info
    if hasattr(employee, 'base_salary'):
        if not employee.base_salary or employee.base_salary <= 0:
            errors.append("Invalid or missing base salary")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "employee_id": employee_id
    }


def validate_all_payroll_prerequisites(
    db: Session,
    organization_id: int,
    month: int,
    year: int
) -> Dict[str, Any]:
    """
    Validate prerequisites for ALL employees before running bulk payroll.
    
    Args:
        db: Database session
        organization_id: Organization ID
        month: Payroll month
        year: Payroll year
    
    Returns:
        Dict with validation results for all employees
    """
    employees = db.query(Employee).filter(
        Employee.organization_id == organization_id
    ).all()
    
    results = []
    has_errors = False
    
    for emp in employees:
        # Check individual prerequisites
        res = validate_payroll_prerequisites(db, emp.id, organization_id)
        
        # Check for duplicate payroll entry for this period
        existing_payroll = db.query(Payroll).filter(
            Payroll.employee_id == str(emp.id),
            Payroll.month == month,
            Payroll.year == year,
            Payroll.organization_id == organization_id
        ).first()
        
        if existing_payroll:
            res["warnings"].append(f"Payroll already exists for {month}/{year}")
        
        if not res["valid"]:
            has_errors = True
            
        results.append({
            "employee_id": emp.id,
            "employee_name": emp.name if hasattr(emp, 'name') else f"Employee #{emp.id}",
            "valid": res["valid"],
            "errors": res["errors"],
            "warnings": res["warnings"]
        })
    
    return {
        "valid_all": not has_errors,
        "total_employees": len(employees),
        "details": results
    }



def validate_payroll_calculation(
    base_salary: float,
    deductions: float
) -> Dict[str, Any]:
    """
    Validate payroll calculation result.
    
    Checks for:
    - Negative net pay
    - Unusually high deductions
    
    Args:
        base_salary: Base salary amount
        deductions: Total deductions amount
    
    Returns:
        Dict with validation results
    """
    warnings = []
    errors = []
    
    net_pay = base_salary - deductions
    
    if net_pay < 0:
        errors.append(f"Negative net pay detected: {net_pay:.2f}. Deductions ({deductions:.2f}) exceed base salary ({base_salary:.2f})")
    
    if deductions > base_salary * 0.5:
        warnings.append(f"High deductions: {deductions:.2f} is more than 50% of base salary")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "net_pay": net_pay
    }



def calculate_payroll(
    db: Session, 
    employee_id: int, 
    month: int, 
    year: int, 
    base_salary: float,
    organization_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calculate payroll for a single employee.
    
    Args:
        db: Database session
        employee_id: ID of the employee
        month: Payroll month (1-12)
        year: Payroll year
        base_salary: Base salary amount
        organization_id: Optional organization ID for multi-tenancy
    
    Returns:
        Dict with payroll calculation results
    """
    # Delegate to AI service for calculation logic
    payroll = _ai_service.calculate_payroll(
        db, 
        str(employee_id),  # AI service expects string
        month, 
        year, 
        base_salary
    )
    
    # Set organization_id if provided
    if organization_id and payroll.organization_id is None:
        payroll.organization_id = organization_id
        try:
            db.commit()
            db.refresh(payroll)
        except Exception:
            db.rollback()
            raise
    
    return _payroll_to_dict(payroll)


def calculate_bulk_payroll(
    db: Session, 
    month: int, 
    year: int, 
    organization_id: int
) -> Dict[str, Any]:
    """
    Calculate payroll for all employees in an organization.
    
    Args:
        db: Database session
        month: Payroll month (1-12)
        year: Payroll year
        organization_id: Organization ID for multi-tenancy
    
    Returns:
        Dict with bulk processing results
    """
    # Get active employees for this organization
    employees = db.query(Employee).filter(
        Employee.organization_id == organization_id
    ).all()
    
    if not employees:
        return {
            "processed": 0,
            "message": "No employees found for this organization",
            "payrolls": []
        }
    
    results = []
    errors = []
    
    for emp in employees:
        try:
            # TODO: In production, fetch base salary from employee contract/profile
            base_salary = 5000.0
            payroll = _ai_service.calculate_payroll(
                db, 
                str(emp.id), 
                month, 
                year, 
                base_salary
            )
            payroll.organization_id = organization_id
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            results.append(_payroll_to_dict(payroll))
        except Exception as e:
            errors.append({"employee_id": emp.id, "error": str(e)})
    
    return {
        "processed": len(results),
        "errors": len(errors),
        "payrolls": results,
        "error_details": errors if errors else None
    }


def get_employee_payroll_history(
    db: Session, 
    employee_id: int,
    organization_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get payroll history for an employee.
    
    Args:
        db: Database session
        employee_id: ID of the employee
        organization_id: Optional organization ID for security filtering
    
    Returns:
        List of payroll records as dicts
    """
    query = db.query(Payroll).filter(
        Payroll.employee_id == str(employee_id)
    )
    
    if organization_id:
        query = query.filter(Payroll.organization_id == organization_id)
    
    payrolls = query.order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    return [_payroll_to_dict(p) for p in payrolls]


def get_payroll_details(db: Session, payroll_id: int, organization_id: int) -> Dict[str, Any]:
    """
    Get detailed payroll record by ID.
    
    Args:
        db: Database session
        payroll_id: ID of the payroll record
        organization_id: Organization ID for security
    
    Returns:
        Dict with payroll details including components
    """
    payroll = db.query(Payroll).filter(
        Payroll.id == payroll_id,
        Payroll.organization_id == organization_id
    ).first()
    
    if not payroll:
        raise ValueError(f"Payroll record {payroll_id} not found or access denied")
    
    result = _payroll_to_dict(payroll)
    
    # Include components if available
    if hasattr(payroll, 'components') and payroll.components:
        result["components"] = [
            {
                "id": c.id,
                "name": c.name,
                "type": c.component_type if hasattr(c, 'component_type') else None,
                "amount": c.amount,
                "description": c.description if hasattr(c, 'description') else None
            }
            for c in payroll.components
        ]
    
    return result


def query_rag_for_payroll(
    db: Session, 
    question: str, 
    organization_id: int
) -> str:
    """
    Answer payroll-related questions using AI with RAG context.
    """
    # Build context from recent payroll data
    recent_payrolls = db.query(Payroll).filter(
        Payroll.organization_id == organization_id
    ).order_by(Payroll.created_at.desc()).limit(5).all()
    
    context = None
    if recent_payrolls:
        context = f"Recent payroll context: {len(recent_payrolls)} records found. "
        context += f"Latest net salary range: {min(p.net_salary for p in recent_payrolls):.2f} - {max(p.net_salary for p in recent_payrolls):.2f}"
    
    return _ai_service.answer_payroll_question(question, context)


def generate_payslip_explanation(db: Session, payroll_id: int, organization_id: int) -> str:
    """
    Generate AI explanation of a payslip.
    """
    payroll = db.query(Payroll).filter(
        Payroll.id == payroll_id,
        Payroll.organization_id == organization_id
    ).first()
    
    if not payroll:
        raise ValueError(f"Payroll record {payroll_id} not found or access denied")
    
    result = _ai_service.explain_payslip(payroll)
    return result.get("explanation", "Unable to generate explanation")


def check_payroll_lock(
    db: Session, 
    month: int, 
    year: int, 
    organization_id: int
) -> Optional[Dict[str, Any]]:
    """
    Check if a payroll period is locked.
    
    Args:
        db: Database session
        month: Payroll month
        year: Payroll year
        organization_id: Organization ID
    
    Returns:
        Lock info dict if locked, None otherwise
    """
    lock = db.query(PayrollLock).filter(
        PayrollLock.month == month,
        PayrollLock.year == year,
        PayrollLock.organization_id == organization_id
    ).first()
    
    if lock:
        return {
            "id": lock.id,
            "month": lock.month,
            "year": lock.year,
            "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
            "locked_by_user_id": lock.locked_by_user_id
        }
    return None


def lock_payroll_period(
    db: Session,
    month: int,
    year: int,
    user_id: int,
    organization_id: int
) -> Dict[str, Any]:
    """
    Lock a payroll period to prevent modifications.
    
    Args:
        db: Database session
        month: Payroll month
        year: Payroll year
        user_id: ID of user performing the lock
        organization_id: Organization ID
    
    Returns:
        Dict with lock status
    """
    existing = check_payroll_lock(db, month, year, organization_id)
    if existing:
        return {"status": "already_locked", "lock": existing}
    
    new_lock = PayrollLock(
        month=month,
        year=year,
        locked_by_user_id=user_id,
        organization_id=organization_id
    )
    db.add(new_lock)
    try:
        db.commit()
        db.refresh(new_lock)
    except Exception:
        db.rollback()
        raise
    
    return {
        "status": "locked",
        "lock": {
            "id": new_lock.id,
            "month": new_lock.month,
            "year": new_lock.year,
            "locked_at": new_lock.locked_at.isoformat() if new_lock.locked_at else None
        }
    }


def _payroll_to_dict(payroll: Payroll) -> Dict[str, Any]:
    """Convert Payroll model to dict representation."""
    return {
        "id": payroll.id,
        "employee_id": payroll.employee_id,
        "month": payroll.month,
        "year": payroll.year,
        "base_salary": payroll.base_salary,
        "bonuses": payroll.bonuses,
        "deductions": payroll.deductions,
        "net_salary": payroll.net_salary,
        "status": payroll.status,
        "payment_date": payroll.payment_date.isoformat() if payroll.payment_date else None,
        "created_at": payroll.created_at.isoformat() if payroll.created_at else None,
        "organization_id": payroll.organization_id
    }


def generate_payslip_pdf(db: Session, payroll_id: int, organization_id: int) -> bytes:
    """
    Generate a PDF payslip for a given payroll record.
    """
    payroll = db.query(Payroll).filter(
        Payroll.id == payroll_id,
        Payroll.organization_id == organization_id
    ).first()
    
    if not payroll:
        raise ValueError(f"Payroll record {payroll_id} not found or access denied")
    
    # Get employee details
    employee = db.query(Employee).filter(
        Employee.id == int(payroll.employee_id),
        Employee.organization_id == organization_id
    ).first()
    
    employee_name = employee.name if employee and hasattr(employee, 'name') else f"Employee #{payroll.employee_id}"
    
    # Get month name
    month_names = ["", "January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    month_name = month_names[payroll.month] if 1 <= payroll.month <= 12 else str(payroll.month)
    
    # Build components section
    components_html = ""
    if hasattr(payroll, 'components') and payroll.components:
        for comp in payroll.components:
            comp_name = comp.name if hasattr(comp, 'name') else "Component"
            comp_amount = comp.amount if hasattr(comp, 'amount') else 0
            comp_type = getattr(comp, 'component_type', 'other')
            sign = "+" if comp_type == "earning" else "-"
            components_html += f"<tr><td>{comp_name}</td><td style='text-align:right'>{sign} ${comp_amount:.2f}</td></tr>"
    
    # Generate HTML payslip
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payslip - {month_name} {payroll.year}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #2563eb; padding-bottom: 20px; }}
            .header h1 {{ color: #2563eb; margin: 0; }}
            .header p {{ color: #666; margin: 5px 0; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
            .info-box {{ background: #f8fafc; padding: 15px; border-radius: 8px; }}
            .info-box h3 {{ margin: 0 0 10px 0; color: #1e40af; font-size: 14px; }}
            .info-box p {{ margin: 5px 0; font-size: 13px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background: #f1f5f9; color: #1e40af; font-weight: 600; }}
            .total-row {{ background: #2563eb; color: white; font-weight: bold; }}
            .total-row td {{ border: none; }}
            .footer {{ margin-top: 40px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>PAYSLIP</h1>
            <p>{month_name} {payroll.year}</p>
        </div>
        
        <div class="info-grid">
            <div class="info-box">
                <h3>EMPLOYEE DETAILS</h3>
                <p><strong>Name:</strong> {employee_name}</p>
                <p><strong>Employee ID:</strong> {payroll.employee_id}</p>
            </div>
            <div class="info-box">
                <h3>PAY PERIOD</h3>
                <p><strong>Period:</strong> {month_name} {payroll.year}</p>
                <p><strong>Payment Date:</strong> {payroll.payment_date.strftime('%B %d, %Y') if payroll.payment_date else 'Pending'}</p>
                <p><strong>Status:</strong> {payroll.status}</p>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th style="text-align: right">Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Base Salary</td>
                    <td style="text-align: right">${payroll.base_salary:.2f}</td>
                </tr>
                {components_html}
                <tr>
                    <td>Bonuses</td>
                    <td style="text-align: right">+ ${payroll.bonuses:.2f}</td>
                </tr>
                <tr>
                    <td>Deductions</td>
                    <td style="text-align: right">- ${payroll.deductions:.2f}</td>
                </tr>
                <tr class="total-row">
                    <td>NET PAY</td>
                    <td style="text-align: right">${payroll.net_salary:.2f}</td>
                </tr>
            </tbody>
        </table>
        
        <div class="footer">
            <p>This is a computer-generated document. No signature required.</p>
            <p>Generated on: {payroll.created_at.strftime('%B %d, %Y') if payroll.created_at else 'N/A'}</p>
        </div>
    </body>
    </html>
    """
    
    return html_content.encode('utf-8')


def generate_all_payslips_zip(
    db: Session,
    organization_id: int,
    month: int,
    year: int
) -> bytes:
    """
    Generate a ZIP file containing PDF payslips for all employees in an organization for a specific period.
    
    Args:
        db: Database session
        organization_id: Organization ID
        month: Payroll month
        year: Payroll year
        
    Returns:
        bytes: ZIP file content
    """
    payrolls = db.query(Payroll).filter(
        Payroll.organization_id == organization_id,
        Payroll.month == month,
        Payroll.year == year
    ).all()
    
    if not payrolls:
        return b""
        
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for payroll in payrolls:
            try:
                # Generate PDF (using HTML for now)
                pdf_bytes = generate_payslip_pdf(db, payroll.id, organization_id)
                
                # Get employee name for filename
                employee = db.query(Employee).filter(
                    Employee.id == int(payroll.employee_id)
                ).first()
                emp_name = "Employee"
                if employee and hasattr(employee, 'name'):
                    emp_name = employee.name.replace(" ", "_")
                
                filename = f"Payslip_{year}_{month:02d}_{emp_name}_{payroll.employee_id}.html"
                
                zip_file.writestr(filename, pdf_bytes)
            except Exception as e:
                # Log error but continue with other payslips
                logger.error(f"Error generating payslip for payroll {payroll.id}: {str(e)}")
                # Potentially write an error log file into the zip
                zip_file.writestr(f"Error_{payroll.id}.txt", str(e))
    
    return zip_buffer.getvalue()


from sqlalchemy import func
from datetime import datetime

def get_payroll_summary(db: Session, organization_id: int) -> Dict[str, Any]:
    """
    Get aggregated payroll statistics for an organization.
    """
    now = datetime.now()
    month = now.month
    year = now.year

    # 1. Total Budget (Sum of net_salary for current month/year)
    total_budget = db.query(func.sum(Payroll.net_salary)).filter(
        Payroll.organization_id == organization_id,
        Payroll.month == month,
        Payroll.year == year
    ).scalar() or 0.0

    # 2. Exceptions Count (Validation issues)
    # We'll use the validate_all_payroll_prerequisites logic here or a simplified version
    val_results = validate_all_payroll_prerequisites(db, organization_id, month, year)
    exceptions_count = sum(1 for d in val_results["details"] if not d["valid"])

    # 3. Recent Payrolls
    recent_payrolls = db.query(Payroll).filter(
        Payroll.organization_id == organization_id
    ).order_by(Payroll.created_at.desc()).limit(5).all()

    return {
        "total_budget": total_budget,
        "exceptions_count": exceptions_count,
        "active_employees": val_results["total_employees"],
        "recent_payrolls": [_payroll_to_dict(p) for p in recent_payrolls]
    }
