from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import json
from app.database import get_db
from app.models.interview import Interview, InterviewStatus
from app.models.interviewer_availability import InterviewerAvailability
from app.services.interview_ai import suggest_interview_slot, generate_interview_questions, analyze_interview_fit
from datetime import datetime

router = APIRouter(prefix="/api/interviews", tags=["interviews"])

class InterviewCreate(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    interviewer_name: str
    interviewer_email: EmailStr
    job_title: str
    preferred_dates: str

class InterviewResponse(BaseModel):
    id: int
    candidate_name: str
    candidate_email: str
    interviewer_name: str
    interviewer_email: str
    job_title: str
    preferred_dates: str
    scheduled_date: Optional[str]
    scheduled_time: Optional[str]
    meeting_link: Optional[str]
    status: str
    ai_suggestion: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class SuggestSlotsRequest(BaseModel):
    candidate_preferences: str
    interviewer_availability: str

class SlotSuggestion(BaseModel):
    date: str
    time: str
    reasoning: str

class SuggestSlotsResponse(BaseModel):
    suggestions: List[SlotSuggestion]

class GenerateQuestionsRequest(BaseModel):
    job_title: str
    candidate_resume: str

class GenerateQuestionsResponse(BaseModel):
    questions: List[str]

class AnalyzeFitRequest(BaseModel):
    job_requirements: str
    candidate_background: str

class AnalyzeFitResponse(BaseModel):
    fit_score: float
    reasoning: str

class ConfirmInterviewRequest(BaseModel):
    scheduled_date: str
    scheduled_time: str
    meeting_link: Optional[str] = None

@router.post("/schedule", response_model=InterviewResponse)
def create_interview(interview: InterviewCreate, db: Session = Depends(get_db)):
    """
    Create a new interview request.
    """
    db_interview = Interview(
        candidate_name=interview.candidate_name,
        candidate_email=interview.candidate_email,
        interviewer_name=interview.interviewer_name,
        interviewer_email=interview.interviewer_email,
        job_title=interview.job_title,
        preferred_dates=interview.preferred_dates,
        status=InterviewStatus.pending
    )
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    return db_interview

@router.get("", response_model=List[InterviewResponse])
def get_interviews(db: Session = Depends(get_db)):
    """
    Get all interviews.
    """
    interviews = db.query(Interview).order_by(Interview.created_at.desc()).all()
    return interviews

@router.post("/{interview_id}/suggest-slots", response_model=SuggestSlotsResponse)
def suggest_slots(interview_id: int, request: SuggestSlotsRequest, db: Session = Depends(get_db)):
    """
    Get AI-suggested interview time slots.
    """
    # Verify interview exists
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    try:
        suggestions = suggest_interview_slot(
            request.candidate_preferences,
            request.interviewer_availability
        )
        
        # Update interview with AI suggestion
        interview.ai_suggestion = json.dumps(suggestions)
        db.commit()
        
        return SuggestSlotsResponse(suggestions=[
            SlotSuggestion(**s) for s in suggestions
        ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.post("/generate-questions", response_model=GenerateQuestionsResponse)
def generate_questions(request: GenerateQuestionsRequest, db: Session = Depends(get_db)):
    """
    Generate interview questions based on job title and candidate resume.
    """
    try:
        questions = generate_interview_questions(request.job_title, request.candidate_resume)
        return GenerateQuestionsResponse(questions=questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.post("/analyze-fit", response_model=AnalyzeFitResponse)
def analyze_fit(request: AnalyzeFitRequest, db: Session = Depends(get_db)):
    """
    Analyze candidate fit for the job.
    """
    try:
        fit_score, reasoning = analyze_interview_fit(
            request.job_requirements,
            request.candidate_background
        )
        return AnalyzeFitResponse(fit_score=fit_score, reasoning=reasoning)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.put("/{interview_id}/confirm", response_model=InterviewResponse)
def confirm_interview(interview_id: int, request: ConfirmInterviewRequest, db: Session = Depends(get_db)):
    """
    Confirm and schedule an interview.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview.scheduled_date = request.scheduled_date
    interview.scheduled_time = request.scheduled_time
    interview.meeting_link = request.meeting_link
    interview.status = InterviewStatus.scheduled
    
    db.commit()
    db.refresh(interview)
    return interview
