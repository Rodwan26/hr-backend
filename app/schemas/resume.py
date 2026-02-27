from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any, Dict

# --- JOB SCHEMAS ---

class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requirements: str  # Legacy field, kept for backward compatibility
    
    # New structured fields for HR feedback compliance
    roles_responsibilities: Optional[str] = None
    desired_responsibilities: Optional[str] = None
    candidate_profile: Optional[Dict[str, Any]] = None  # {education, experience, required_skills}
    
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    required_skills: Optional[List[str]] = None  # Legacy, use candidate_profile instead

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    requirements: str
    
    # New structured fields
    roles_responsibilities: Optional[str]
    desired_responsibilities: Optional[str]
    candidate_profile: Optional[Dict[str, Any]]
    
    department: Optional[str]
    location: Optional[str]
    employment_type: Optional[str]
    experience_level: Optional[str]
    required_skills: Optional[List[str]]
    is_active: bool

# --- RESUME SCHEMAS ---

class ResumeCreate(BaseModel):
    name: str
    resume_text: str
    blind_screening: Optional[bool] = False  # Enable bias mitigation

class ResumeStatusUpdate(BaseModel):
    status: str # New, Reviewing, Shortlisted, Rejected

class ResumeSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    name: str
    status: str
    message: str = "Resume submitted successfully. Analysis pending."

class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    name: str
    resume_text: str
    anonymized_text: Optional[str]
    
    # Legacy scoring
    ai_score: float
    ai_feedback: str
    ai_evidence: Optional[List[Any]]
    
    # New transparent scoring breakdown
    skills_match_score: Optional[float]
    seniority_match_score: Optional[float]
    domain_relevance_score: Optional[float]
    missing_requirements: Optional[List[Any]]
    rejection_reason: Optional[str] = None
    
    # Bias control
    blind_screening_enabled: bool
    
    status: str
    trust_metadata: Optional[Any]
