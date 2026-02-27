from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.job import Job
from app.models.user import User, UserRole
from app.routers.auth_deps import require_role, get_current_user, get_current_org
from app.schemas.job import JobCreate, JobUpdate, JobResponse
from app.services.audit import AuditService
from app.services.notification import NotificationService

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))]
)

@router.post("/", response_model=JobResponse)
def create_job(
    job_in: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Create a new job posting.
    Accessible by HR Admins and Managers.
    """
    # Convert Pydantic model to dict, handle nested JSON for candidate_profile
    job_data = job_in.model_dump()
    candidate_profile = job_data.pop("candidate_profile", None)
    
    # If candidate_profile is a dict (from Pydantic), store it directly as JSON
    # If it's a Pydantic model (not popped as dict), convert it
    if hasattr(candidate_profile, "model_dump"):
        candidate_profile = candidate_profile.model_dump()
        
    db_job = Job(
        **job_data,
        candidate_profile=candidate_profile,
        organization_id=org_id
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    AuditService.log(
        db,
        action="create_job",
        entity_type="job",
        entity_id=db_job.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"title": db_job.title, "department": db_job.department},
        organization_id=org_id,
        after_state=job_in.model_dump()
    )

    # Trigger Notification
    NotificationService.notify_user(
        db,
        user_id=current_user.id,
        title="New Job Created",
        message=f"Success! '{db_job.title}' is now live in {db_job.department}.",
        type="success",
        link=f"/jobs/{db_job.id}"
    )
    
    return db_job

@router.get("/", response_model=List[JobResponse])
def get_jobs(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    """
    List jobs for the organization.
    """
    query = db.query(Job).filter(Job.organization_id == org_id)
    if active_only:
        query = query.filter(Job.is_active == True)
        
    return query.offset(skip).limit(limit).all()

@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    """
    Get job details.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == org_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    job_in: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    """
    Update a job posting.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == org_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Capture before state for audit
    before_state = {
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "roles_responsibilities": job.roles_responsibilities,
        "desired_responsibilities": job.desired_responsibilities,
        "candidate_profile": job.candidate_profile
    }

    update_data = job_in.model_dump(exclude_unset=True)
    
    # Handle JSON field special case
    if "candidate_profile" in update_data:
         cp = update_data["candidate_profile"]
         if hasattr(cp, "model_dump"):
             update_data["candidate_profile"] = cp.model_dump()
    
    for field, value in update_data.items():
        setattr(job, field, value)
        
    db.commit()
    db.refresh(job)
    
    AuditService.log(
        db,
        action="update_job",
        entity_type="job",
        entity_id=job.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"job_id": job_id},
        organization_id=org_id,
        before_state=before_state,
        after_state=update_data
    )
    
    return job

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN])), # Admin only
    org_id: int = Depends(get_current_org)
):
    """
    Delete (soft delete logic preferred usually, but implementing hard delete per prompt implication, or soft via is_active)
    Let's do hard delete but restricted to Admin.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == org_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    before_state = {"title": job.title, "id": job.id}
    
    # We might want to cascade delete resumes? Model has cascade="all, delete-orphan", so SA handles it.
    db.delete(job)
    db.commit()
    
    AuditService.log(
        db,
        action="delete_job",
        entity_type="job",
        entity_id=job_id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"job_title": job.title},
        organization_id=org_id,
        before_state=before_state
    )
    
    return {"message": "Job deleted successfully"}
