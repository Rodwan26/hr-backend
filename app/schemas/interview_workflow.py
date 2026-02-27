from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.interview import InterviewStatus, InterviewSlotStatus, ScorecardRecommendation

# --- Slots ---
class InterviewSlotCreate(BaseModel):
    interviewer_id: int
    scheduled_at: datetime
    duration_minutes: int = 60
    meeting_link: Optional[str] = None

class InterviewSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    interviewer_id: int
    scheduled_at: datetime
    duration_minutes: int
    meeting_link: Optional[str]
    status: InterviewSlotStatus
    candidate_confirmed: bool
    created_at: datetime

# --- Invite ---
class InterviewInviteRequest(BaseModel):
    slot_ids: List[int] # Allow multiple slots to be proposed
    message: Optional[str] = None

# --- Kit ---
class Question(BaseModel):
    id: str
    text: str
    type: str = "text" # text, code, multiple_choice
    criteria: Optional[str] = None

class InterviewKitStructure(BaseModel):
    questions: List[Question]
    evaluation_guide: Optional[str] = None

class InterviewKitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    questions: List[Question]
    evaluation_guide: Optional[str]
    created_at: datetime

# --- Scorecard ---
class InterviewScorecardCreate(BaseModel):
    overall_rating: int = Field(..., ge=1, le=5)
    technical_score: Optional[int] = Field(None, ge=1, le=10)
    communication_score: Optional[int] = Field(None, ge=1, le=10)
    cultural_fit_score: Optional[int] = Field(None, ge=1, le=10)
    strengths: Optional[List[str]] = []
    concerns: Optional[List[str]] = []
    feedback_text: Optional[str] = None
    recommendation: ScorecardRecommendation

class InterviewScorecardResponse(InterviewScorecardCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    interviewer_id: int
    ai_consistency_check: Optional[Dict[str, Any]] = None
    submitted_at: datetime

# --- Consistency Check ---
class ConsistencyAnalysis(BaseModel):
    score_variance: float
    consensus_recommendation: str
    flags: List[str] # e.g., "Interviewer A rated Technical 2 while B rated 9"
    trust_score: float

# --- Interview Lifecycle ---
class InterviewCreate(BaseModel):
    candidate_name: str
    candidate_email: str
    interviewer_name: str
    interviewer_email: str
    job_title: str
    preferred_dates: str

class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    candidate_name: str
    candidate_email: str
    interviewer_name: Optional[str] = None
    interviewer_email: Optional[str] = None
    job_title: Optional[str] = None # We'll populate this in the router from Job or direct field
    status: InterviewStatus
    preferred_dates: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    meeting_link: Optional[str] = None
    stage: str

class SuggestSlotsRequest(BaseModel):
    preferred_dates: str
    interviewer_availability: str

class ConfirmInterviewRequest(BaseModel):
    date: str
    time: str

class GenerateQuestionsRequest(BaseModel):
    job_title: str
    candidate_resume: str

class AnalyzeFitRequest(BaseModel):
    job_requirements: str
    candidate_resume: str

class AnalyzeFitResponse(BaseModel):
    fit_score: float
    reasoning: str

class InterviewDecisionRequest(BaseModel):
    status: InterviewStatus
    reason: Optional[str] = None
