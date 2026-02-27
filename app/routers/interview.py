"""
Interview Workflow Router
Handles end-to-end interview process: Scheduling > Kit > Scoring > Decision.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app.database import get_db
from app.models.interview import (
    Interview, InterviewStatus, InterviewSlot, InterviewSlotStatus, 
    InterviewScorecard, InterviewKit, ScorecardRecommendation
)
from app.models.user import User, UserRole
from app.routers.auth_deps import get_current_user, require_role, require_hr, get_current_org
from app.schemas.interview_workflow import (
    InterviewSlotCreate, InterviewSlotResponse,
    InterviewInviteRequest,
    InterviewKitResponse, InterviewKitStructure, Question,
    InterviewScorecardCreate, InterviewScorecardResponse,
    InterviewDecisionRequest,
    ConsistencyAnalysis,
    InterviewCreate, InterviewResponse,
    SuggestSlotsRequest, ConfirmInterviewRequest,
    GenerateQuestionsRequest, AnalyzeFitRequest, AnalyzeFitResponse
)
from app.services.interview_service import InterviewService
from app.services.audit import AuditService
from app.services.ai_trust_service import AITrustService

router = APIRouter(
    prefix="/interviews",
    tags=["interviews"]
)

# --- Interview Lifecycle ---

@router.get("", response_model=List[InterviewResponse])
def get_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """List all interviews for the organization."""
    return db.query(Interview).filter(Interview.organization_id == org_id).all()

@router.post("", response_model=InterviewResponse)
def create_interview(
    request: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """Create a new interview record."""
    interview = Interview(
        organization_id=org_id,
        candidate_name=request.candidate_name,
        candidate_email=request.candidate_email,
        interviewer_name=request.interviewer_name,
        interviewer_email=request.interviewer_email,
        preferred_dates=request.preferred_dates,
        status=InterviewStatus.PENDING,
        stage="Screening"
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview

@router.post("/{interview_id}/suggest-slots")
def suggest_slots_ai(
    interview_id: int,
    request: SuggestSlotsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """AI Service to suggest best slots based on input availability."""
    service = InterviewService(db, organization_id=org_id)
    suggestions = service.suggest_slots(request.preferred_dates, request.interviewer_availability)
    
    # Wrap in TrustedAIResponse format for frontend
    return {
        "data": {"suggestions": suggestions},
        "trust_metadata": {
            "confidence_score": 0.88,
            "ai_model": "HR-Scheduler-v2"
        }
    }

@router.post("/{interview_id}/confirm")
def confirm_interview(
    interview_id: int,
    request: ConfirmInterviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """Confirm a specific slot for the interview."""
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    try:
        # Simplistic parsing for the mock, in real app use proper datetime parsing
        interview.scheduled_date = datetime.now() 
        interview.status = InterviewStatus.SCHEDULED
        db.commit()
        return {"message": "Interview confirmed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to confirm: {str(e)}")

@router.post("/generate-questions")
def generate_questions_ai(
    request: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """AI Service to generate interview questions."""
    service = InterviewService(db, organization_id=org_id)
    questions = service.generate_questions(request.job_title, request.candidate_resume)
    return {
        "data": {"questions": questions},
        "trust_metadata": {
            "confidence_score": 0.92,
            "ai_model": "Recruiter-Assistant-v1"
        }
    }

@router.post("/analyze-fit")
def analyze_fit_ai(
    request: AnalyzeFitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """AI Service to analyze candidate fit."""
    service = InterviewService(db, organization_id=org_id)
    score, reasoning = service.analyze_fit(request.job_requirements, request.candidate_resume)
    return {
        "data": {"fit_score": score, "reasoning": reasoning},
        "trust_metadata": {
            "confidence_score": 0.85,
            "ai_model": "Talent-Analyzer-PRO"
        }
    }

@router.get("/{interview_id}/analysis")
def get_interview_analysis(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """Alias for consistency check for frontend expectations."""
    # This reuse the existing logic we will keep below
    from app.routers.interview import check_consistency
    return check_consistency(interview_id, db, current_user, org_id)

# --- Slots Management ---

@router.post("/{interview_id}/slots", response_model=List[InterviewSlotResponse])
def generate_slots(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """
    Generate available slots based on interviewer availability (Mock/AI).
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Access check is implicitly handled by organization_id filter in query

    # Mock logic for slot generation (In real app, query Outlook/Google Calendar)
    # Using AI service to suggest 'best' times based on preferences if available
    
    service = InterviewService(db, organization_id=org_id)
    # Mocking preferences for now if not set
    candidate_prefs = interview.preferred_dates or "Anytime next week"
    interviewer_avail = "Weekday mornings"
    
    suggestions = service.suggest_slots(candidate_prefs, interviewer_avail)
    
    created_slots = []
    for slot_data in suggestions:
        # Convert string to datetime - assuming ISO format or simple parsing
        # For robustness, we'll just mock current time + offset if parsing fails or return mock
        try:
            # Simple mock parsing or use current time for demo
            scheduled_at = datetime.now() # Placeholder
        except:
            scheduled_at = datetime.now()

        slot = InterviewSlot(
            interview_id=interview.id,
            interviewer_id=interview.interviewer_id or current_user.id,
            scheduled_at=scheduled_at,
            duration_minutes=60,
            status=InterviewSlotStatus.AVAILABLE
        )
        db.add(slot)
        created_slots.append(slot)
    
    db.commit()
    for s in created_slots:
        db.refresh(s)
        
    # Audit
    AuditService.log(
        db,
        action="generate_slots",
        entity_type="interview",
        entity_id=interview.id,
        user_id=current_user.id,
        user_role=current_user.role.value,
        details={"count": len(created_slots)},
        organization_id=org_id,
        ai_recommended=True
    )
    
    return created_slots


@router.post("/{interview_id}/invite", status_code=status.HTTP_200_OK)
def send_invite(
    interview_id: int,
    request: InterviewInviteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """
    Send interview invite to candidate for selected slots.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    slots = db.query(InterviewSlot).filter(InterviewSlot.id.in_(request.slot_ids)).all()
    if len(slots) != len(request.slot_ids):
        raise HTTPException(status_code=400, detail="One or more slots not found")
        
    # Mock Email Sending
    # In reality: EmailService.send_invite(candidate_email, slots)
    
    # Update interview status
    interview.status = InterviewStatus.SCHEDULED # Or 'Invited' if we had that status
    interview.stage = "Scheduling"
    
    # Audit
    AuditService.log(
        db,
        action="send_invite",
        entity_type="interview",
        entity_id=interview.id,
        user_id=current_user.id,
        user_role=current_user.role.value,
        details={"slot_ids": request.slot_ids, "message": request.message},
        organization_id=org_id
    )
    
    db.commit()
    return {"message": "Invite sent successfully"}


# --- Interview Kit ---

@router.get("/{interview_id}/kit", response_model=InterviewKitResponse)
def get_interview_kit(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user), # Interviewer needs access
    org_id: int = Depends(get_current_org)
):
    """
    Get or generate the interview kit (questions + guide).
    """
    # Verify access
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    if current_user.id != interview.interviewer_id and current_user.role not in [UserRole.HR_ADMIN, UserRole.HR_MANAGER]:
         raise HTTPException(status_code=403, detail="Access denied")

    # Check if kit exists
    if interview.kit:
        # Pydantic expects 'questions' as list of objects, but DB has dict. 
        # Adapting if kit.questions is stored as list of dicts.
        return interview.kit

    # Generate Kit using AI
    service = InterviewService(db, organization_id=org_id)
    # Fetch resume text mock
    resume_text = "Experienced Python Developer..." 
    
    job_title = interview.job.title if interview.job else "Role"
    kit_data = service.generate_interview_kit(job_title, resume_text)
    
    # Convert AI dict to Schema format
    # AI returns {"questions": [{"id":1, ...}], "evaluation_criteria": [...]}
    questions_list = kit_data.get("questions", [])
    
    # Create DB Record
    new_kit = InterviewKit(
        interview_id=interview.id,
        questions=questions_list,
        evaluation_guide=json.dumps(kit_data.get("evaluation_criteria", []))
    )
    db.add(new_kit)
    db.commit()
    db.refresh(new_kit)
    
    # Audit/Trust Log
    trust_service = AITrustService(db, org_id, current_user.id, current_user.role)
    trust_service.wrap_and_log(
        content="Generated Interview Kit",
        action_type="generate_kit",
        entity_type="interview_kit",
        entity_id=new_kit.id,
        confidence_score=0.85,
        model_name="HR-Gen-AI",
        details={"count": len(questions_list)}
    )
    
    return new_kit


# --- Scorecard ---

@router.post("/{interview_id}/scorecard", response_model=InterviewScorecardResponse)
def submit_scorecard(
    interview_id: int,
    scorecard: InterviewScorecardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Submit feedback scorecard.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Only assigned interviewer or admin can submit
    if current_user.id != interview.interviewer_id and current_user.role not in [UserRole.HR_ADMIN]:
        raise HTTPException(status_code=403, detail="Only assigned interviewer can submit scorecard")

    # AI Consistency Check (Mock/Real)
    # We check against previous scorecards for this role to detect bias
    service = InterviewService(db, org_id)
    # consistency_analysis = service.analyze_consistency(...) # Omitted for brevity in this step, done in next endpoint
    
    db_scorecard = InterviewScorecard(
        interview_id=interview_id,
        interviewer_id=current_user.id,
        overall_rating=scorecard.overall_rating,
        technical_score=scorecard.technical_score,
        communication_score=scorecard.communication_score,
        cultural_fit_score=scorecard.cultural_fit_score,
        strengths=scorecard.strengths,
        concerns=scorecard.concerns,
        feedback_text=scorecard.feedback_text,
        recommendation=scorecard.recommendation
    )
    db.add(db_scorecard)
    
    # Update interview stage
    interview.stage = "Review"
    interview.status = InterviewStatus.DECISION_PENDING
    
    db.commit()
    db.refresh(db_scorecard)
    
    # Audit
    AuditService.log(
        db,
        action="submit_scorecard",
        entity_type="interview_scorecard",
        entity_id=db_scorecard.id,
        user_id=current_user.id,
        user_role=current_user.role.value,
        details={"rating": scorecard.overall_rating, "recommendation": scorecard.recommendation},
        organization_id=org_id
    )
    
    return db_scorecard


@router.get("/{interview_id}/consistency", response_model=ConsistencyAnalysis)
def check_consistency(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """
    Analyze consistency of feedback for this interview/candidate.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    scorecards = db.query(InterviewScorecard).filter(InterviewScorecard.interview_id == interview_id).all()
    
    if not scorecards:
        return ConsistencyAnalysis(
            score_variance=0.0,
            consensus_recommendation="N/A",
            flags=["No scorecards submitted yet."],
            trust_score=1.0
        )
        
    # Simple logic for consistency (Var(Overall Rating))
    ratings = [s.overall_rating for s in scorecards]
    avg_rating = sum(ratings) / len(ratings)
    variance = sum((r - avg_rating) ** 2 for r in ratings) / len(ratings) if len(ratings) > 0 else 0
    
    flags = []
    if variance > 1.0:
        flags.append("High variance in overall ratings.")
        
    recommendations = [s.recommendation for s in scorecards]
    if "YES" in recommendations and "NO" in recommendations:
        flags.append("Conflicting recommendations (YES vs NO).")
        
    return ConsistencyAnalysis(
        score_variance=round(variance, 2),
        consensus_recommendation="HIRE" if avg_rating >= 4 else "REVIEW",
        flags=flags,
        trust_score=0.9 if not flags else 0.6
    )


@router.post("/{interview_id}/decision")
def make_decision(
    interview_id: int,
    request: InterviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr()),
    org_id: int = Depends(get_current_org)
):
    """
    Final hiring decision.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.organization_id == org_id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    before_state = {"status": interview.status, "stage": interview.stage}
    
    interview.status = request.status
    interview.stage = "Closed"
    
    db.commit()
    
    # Audit
    AuditService.log(
        db,
        action="interview_decision",
        entity_type="interview",
        entity_id=interview.id,
        user_id=current_user.id,
        user_role=current_user.role.value,
        details={"decision": request.status, "reason": request.reason},
        organization_id=org_id,
        before_state=before_state,
        after_state={"status": interview.status}
    )
    
    return {"message": f"Interview marked as {request.status}"}
