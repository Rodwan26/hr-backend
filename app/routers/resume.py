from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Body
from sqlalchemy.orm import Session
from typing import List

from app.models.user import User, UserRole
from app.limiter import limiter

router = APIRouter()

from app.database import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.services.resume_ai import analyze_resume, anonymize_resume
from app.schemas.resume import (
    ResumeCreate, ResumeResponse, ResumeStatusUpdate, ResumeSubmissionResponse
)

# Authorization & Services
from app.routers.auth_deps import get_current_user, require_role, require_any_role, get_current_org
from app.services.task_service import TaskService
from app.services.audit import AuditService


@router.post("/{job_id}/resumes", response_model=ResumeSubmissionResponse)
@limiter.limit("10/minute")
def submit_resume(
    request: Request,
    job_id: int, 
    background_tasks: BackgroundTasks,
    resume: ResumeCreate = Body(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
    org_id: int = Depends(get_current_org)
):
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == org_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    anonymized_text = anonymize_resume(resume.resume_text, blind_screening=resume.blind_screening)
    
    db_resume = Resume(
        job_id=job_id,
        name=resume.name,
        resume_text=resume.resume_text,
        anonymized_text=anonymized_text,
        ai_score=0.0,
        ai_feedback="Processing...",
        status="Processing",
        blind_screening_enabled=resume.blind_screening or False,
        anonymization_status="VERIFIED" if anonymized_text else "PENDING",
        organization_id=org_id
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)

    task_service = TaskService(background_tasks, db)
    task_service.enqueue("resume_analysis", {
        "resume_id": db_resume.id, 
        "job_id": job_id,
        "user_id": current_user.id
    })
    
    AuditService.log(
        db,
        action="submit_resume",
        entity_type="resume",
        entity_id=db_resume.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"job_id": job_id, "blind_screening": resume.blind_screening},
        ai_recommended=True,
        organization_id=org_id
    )
    
    return ResumeSubmissionResponse(
        id=db_resume.id,
        job_id=db_resume.job_id,
        name=db_resume.name,
        status=db_resume.status,
        message="Resume submitted successfully. Analysis pending."
    )


@router.get("/{job_id}/resumes", response_model=List[ResumeResponse])
def get_resumes(
    job_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    job = db.query(Job).filter(Job.id == job_id, Job.organization_id == org_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    resumes = db.query(Resume).filter(
        Resume.job_id == job_id,
        Resume.organization_id == org_id
    ).all()
    return resumes


@router.patch("/{job_id}/resumes/{resume_id}/status", response_model=ResumeResponse)
def update_resume_status(
    job_id: int,
    resume_id: int,
    update: ResumeStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF])),
    org_id: int = Depends(get_current_org)
):
    db_resume = db.query(Resume).join(Job).filter(
        Resume.id == resume_id, 
        Resume.job_id == job_id,
        Job.organization_id == org_id
    ).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found for this job")
    
    db_resume.status = update.status
    db.commit()
    db.refresh(db_resume)
    
    AuditService.log(
        db,
        action="update_resume_status",
        entity_type="resume",
        entity_id=resume_id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"new_status": update.status, "job_id": job_id},
        organization_id=org_id
    )
    
    return db_resume
