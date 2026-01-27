from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.database import get_db
from app.models.performance_metric import PerformanceMetric
from app.models.burnout_assessment import BurnoutAssessment
from app.services.burnout_ai import calculate_burnout_risk, generate_performance_summary

router = APIRouter(
    prefix="/api/burnout",
    tags=["burnout"]
)

class MetricCreate(BaseModel):
    employee_id: int
    metric_type: str
    value: float
    date: date

class AssessmentResponse(BaseModel):
    id: int
    employee_id: int
    risk_level: str
    indicators: List[str]
    recommendations: List[str]
    ai_analysis: str
    assessed_at: str
    
    class Config:
        orm_mode = True

@router.post("/track-metric")
def track_metric(metric: MetricCreate, db: Session = Depends(get_db)):
    db_metric = PerformanceMetric(
        employee_id=metric.employee_id,
        metric_type=metric.metric_type,
        value=metric.value,
        date=metric.date
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

@router.get("/metrics/{employee_id}")
def get_metrics(employee_id: int, db: Session = Depends(get_db)):
    return db.query(PerformanceMetric).filter(
        PerformanceMetric.employee_id == employee_id
    ).order_by(PerformanceMetric.date.desc()).all()

@router.post("/analyze/{employee_id}")
def analyze_burnout(employee_id: int, db: Session = Depends(get_db)):
    result = calculate_burnout_risk(employee_id, db)
    
    # Save assessment
    assessment = BurnoutAssessment(
        employee_id=employee_id,
        risk_level=result.get("risk_level", "low"),
        indicators=result.get("indicators", []),
        recommendations=result.get("recommendations", []),
        ai_analysis=result.get("analysis", "")
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment

@router.get("/assessments/{employee_id}")
def get_assessments(employee_id: int, db: Session = Depends(get_db)):
    return db.query(BurnoutAssessment).filter(
        BurnoutAssessment.employee_id == employee_id
    ).order_by(BurnoutAssessment.assessed_at.desc()).all()

@router.get("/dashboard/{employee_id}")
def get_dashboard(employee_id: int, db: Session = Depends(get_db)):
    latest_assessment = db.query(BurnoutAssessment).filter(
        BurnoutAssessment.employee_id == employee_id
    ).order_by(BurnoutAssessment.assessed_at.desc()).first()
    
    metrics = db.query(PerformanceMetric).filter(
        PerformanceMetric.employee_id == employee_id
    ).order_by(PerformanceMetric.date.desc()).limit(30).all()
    
    return {
        "assessment": latest_assessment,
        "metrics": metrics
    }
