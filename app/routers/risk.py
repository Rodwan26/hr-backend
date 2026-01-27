from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.employee import Employee
from app.models.activity import Activity
from app.services.risk_ai import analyze_risk, check_toxicity

router = APIRouter(prefix="/api/risk", tags=["risk"])

class RiskAnalysisResponse(BaseModel):
    risk_level: str
    details: str

class ToxicityCheckRequest(BaseModel):
    text: str

class ToxicityCheckResponse(BaseModel):
    is_toxic: bool
    explanation: str

@router.post("/analyze/{employee_id}", response_model=RiskAnalysisResponse)
def analyze_employee_risk(employee_id: int, db: Session = Depends(get_db)):
    """
    Analyze an employee's activities for potential risks.
    """
    try:
        result = analyze_risk(employee_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.post("/check-text", response_model=ToxicityCheckResponse)
def check_text_toxicity(request: ToxicityCheckRequest, db: Session = Depends(get_db)):
    """
    Check if text contains toxic language.
    """
    try:
        result = check_toxicity(request.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
