from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.services.resume_ai import analyze_resume

router = APIRouter(prefix="/api/jobs", tags=["resumes"])

class JobCreate(BaseModel):
    title: str
    requirements: str

class JobResponse(BaseModel):
    id: int
    title: str
    requirements: str
    
    class Config:
        from_attributes = True

class ResumeCreate(BaseModel):
    name: str
    resume_text: str

class ResumeResponse(BaseModel):
    id: int
    job_id: int
    name: str
    resume_text: str
    ai_score: float
    ai_feedback: str
    
    class Config:
        from_attributes = True

@router.post("", response_model=JobResponse)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    """
    Create a new job posting.
    """
    db_job = Job(title=job.title, requirements=job.requirements)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

@router.get("", response_model=List[JobResponse])
def get_jobs(db: Session = Depends(get_db)):
    """
    Get all job postings.
    """
    jobs = db.query(Job).all()
    return jobs

@router.post("/{job_id}/resumes", response_model=ResumeResponse)
def submit_resume(job_id: int, resume: ResumeCreate, db: Session = Depends(get_db)):
    """
    Submit a resume for a job and get AI analysis.
    """
    # Check if job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Analyze resume with AI
    try:
        score, feedback = analyze_resume(resume.resume_text, job.requirements)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    
    # Save resume
    db_resume = Resume(
        job_id=job_id,
        name=resume.name,
        resume_text=resume.resume_text,
        ai_score=score,
        ai_feedback=feedback
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    return db_resume

@router.get("/{job_id}/resumes", response_model=List[ResumeResponse])
def get_resumes(job_id: int, db: Session = Depends(get_db)):
    """
    Get all resumes for a job.
    """
    resumes = db.query(Resume).filter(Resume.job_id == job_id).all()
    return resumes
