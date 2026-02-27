from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class CandidateProfile(BaseModel):
    education: Optional[str] = None
    experience: Optional[str] = None
    skills: List[str] = Field(default_factory=list)

class JobBase(BaseModel):
    title: str
    description: Optional[str] = None
    roles_responsibilities: Optional[str] = None
    desired_responsibilities: Optional[str] = None
    candidate_profile: Optional[CandidateProfile] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = "Full-time"
    experience_level: Optional[str] = "Mid"
    # Legacy field support
    requirements: Optional[str] = None 
    required_skills: Optional[List[str]] = Field(default_factory=list)

class JobCreate(JobBase):
    pass

class JobUpdate(JobBase):
    pass

class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    organization_id: int
    is_active: bool
