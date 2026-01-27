from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.payroll_ai import PayrollAIService
from app.models.payroll import Payroll
from app.models.salary_component import SalaryComponent # Needed for relationships
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(
    prefix="/api/payroll",
    tags=["payroll"]
)

payroll_service = PayrollAIService()

class PayrollRequest(BaseModel):
    employee_id: str
    month: int
    year: int
    base_salary: float

class QuestionRequest(BaseModel):
    question: str
    context: Optional[str] = None

class ExplanationRequest(BaseModel):
    payroll_id: int

@router.post("/calculate")
def calculate_payroll(request: PayrollRequest, db: Session = Depends(get_db)):
    return payroll_service.calculate_payroll(
        db, 
        request.employee_id, 
        request.month, 
        request.year, 
        request.base_salary
    )

@router.get("/{employee_id}")
def get_payroll_history(employee_id: str, db: Session = Depends(get_db)):
    return db.query(Payroll).filter(Payroll.employee_id == employee_id).order_by(Payroll.year.desc(), Payroll.month.desc()).all()

@router.get("/{id}/details")
def get_payroll_details(id: int, db: Session = Depends(get_db)):
    payroll = db.query(Payroll).filter(Payroll.id == id).first()
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    # Make sure components are loaded
    # SQLAlchemy default loading should work if we return the object and Pydantic handles it, 
    # but for manual serialization we might need more.
    # FastAPI will use ORM mode if we had a Pydantic schema, but we are returning ORM objects directly here which is okay-ish for rapid dev but often needs manual component fetching if lazy loading issues arise.
    # Let's ensure we return a structure that includes components.
    return {
        "payroll": payroll,
        "components": payroll.components
    }

@router.post("/ask")
def ask_payroll_question(request: QuestionRequest):
    return {"answer": payroll_service.answer_payroll_question(request.question, request.context)}

@router.post("/explain")
def explain_payslip(request: ExplanationRequest, db: Session = Depends(get_db)):
    payroll = db.query(Payroll).filter(Payroll.id == request.payroll_id).first()
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    return payroll_service.explain_payslip(payroll)
