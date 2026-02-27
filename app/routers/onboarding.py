import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organization import Organization
from app.models.onboarding_employee import OnboardingEmployee, OnboardingStatus
from app.models.onboarding_task import OnboardingTask, OnboardingTaskCategory
from app.models.onboarding_chat import OnboardingChat
from app.models.onboarding_document import OnboardingDocument
from app.models.onboarding_template import OnboardingTemplate
from app.models.onboarding_reminder import OnboardingReminder, ReminderStatus, ReminderType
from app.schemas.onboarding_workflow import (
    OnboardingTemplateCreate, OnboardingTemplateResponse,
    OnboardingReminderResponse, OnboardingProgress
)
from app.schemas.trust import TrustedAIResponse
from app.services.onboarding_ai import (
    generate_onboarding_checklist,
    answer_onboarding_question,
    get_onboarding_tips,
    analyze_progress,
)

logger = logging.getLogger(__name__)

from app.routers.auth_deps import require_role, require_any_role, get_current_user, get_current_org
from app.models.user import UserRole, User
from app.services.audit import AuditService
from app.services.ai_trust_service import AITrustService
from app.services.onboarding_service import create_onboarding_tasks
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Legacy DEFAULT_COMPANY_ID and helper removed.
# Onboarding is now scoped to organization via current_user.


class OnboardingEmployeeCreate(BaseModel):
    employee_name: str
    employee_email: EmailStr
    position: str
    department: str
    start_date: date
    manager_name: Optional[str] = None


class OnboardingEmployeeUpdate(BaseModel):
    employee_name: Optional[str] = None
    employee_email: Optional[EmailStr] = None
    position: Optional[str] = None
    department: Optional[str] = None
    start_date: Optional[date] = None
    manager_name: Optional[str] = None
    status: Optional[str] = None


class OnboardingEmployeeResponse(BaseModel):
    id: int
    employee_name: str
    employee_email: str
    position: str
    department: str
    start_date: date
    manager_name: Optional[str]
    status: str
    completion_percentage: int
    organization_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingTaskCreate(BaseModel):
    task_title: str
    task_description: Optional[str] = None
    task_category: str = "other"
    due_date: Optional[date] = None


class OnboardingTaskResponse(BaseModel):
    id: int
    employee_id: int
    task_title: str
    task_description: Optional[str] = None
    task_category: str
    is_completed: bool
    due_date: Optional[date]
    completed_at: Optional[datetime]
    task_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    chat_id: int
    answer: str
    sources: List[dict]
    confidence: float


class ChatResponse(BaseModel):
    id: int
    employee_id: int
    question: str
    ai_response: str
    is_helpful: Optional[bool]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatFeedbackRequest(BaseModel):
    is_helpful: bool


@router.post("/employees", response_model=OnboardingEmployeeResponse)
def create_employee(
    payload: OnboardingEmployeeCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF])),
    org_id: int = Depends(get_current_org)
):
    logger.info("Creating onboarding employee")
    employee = OnboardingEmployee(
        employee_name=payload.employee_name,
        employee_email=str(payload.employee_email),
        position=payload.position,
        department=payload.department,
        start_date=payload.start_date,
        manager_name=payload.manager_name,
        status=OnboardingStatus.pending,
        completion_percentage=0,
        organization_id=org_id,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/employees", response_model=List[OnboardingEmployeeResponse])
def list_employees(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    employees = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.organization_id == org_id
    ).order_by(OnboardingEmployee.created_at.desc()).all()
    return employees


@router.get("/employees/{employee_id}", response_model=OnboardingEmployeeResponse)
def get_employee(
    employee_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(get_current_user)
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/employees/{employee_id}", response_model=OnboardingEmployeeResponse)
def update_employee(
    employee_id: int, 
    payload: OnboardingEmployeeUpdate, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.employee_name is not None:
        employee.employee_name = payload.employee_name
    if payload.employee_email is not None:
        employee.employee_email = str(payload.employee_email)
    if payload.position is not None:
        employee.position = payload.position
    if payload.department is not None:
        employee.department = payload.department
    if payload.start_date is not None:
        employee.start_date = payload.start_date
    if payload.manager_name is not None:
        employee.manager_name = payload.manager_name
    if payload.status is not None:
        status_val = payload.status.strip().lower()
        if status_val in {s.value for s in OnboardingStatus}:
            employee.status = OnboardingStatus(status_val)

    # Capture before state (simplified)
    # Ideally we'd fetch the object before modifying, but for now we just log the change action.
    
    db.commit()
    db.refresh(employee)
    
    # Audit Log
    AuditService.log(
        db,
        action="update_onboarding_employee",
        entity_type="onboarding_employee",
        entity_id=employee.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details=payload.dict(exclude_unset=True),
        ai_recommended=False
    )

    return employee


@router.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN]))
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # delete children first (SQLite-safe)
    db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).delete()
    db.query(OnboardingChat).filter(OnboardingChat.employee_id == employee_id).delete()
    db.delete(employee)
    db.commit()
    return {"message": "Employee deleted successfully"}


@router.post("/employees/{employee_id}/generate-checklist", response_model=TrustedAIResponse)
def generate_checklist(
    employee_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    logger.info(f"Generating onboarding checklist for employee_id={employee_id}")
    # Clear existing tasks
    db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).delete()
    db.commit()

    # Use Domain Service to create tasks (AI suggestion + Fallback)
    created = create_onboarding_tasks(db, employee, use_ai=True)

    # Update progress
    analyze_progress(employee_id, db)

    # Audit logging via AITrustService
    trust_service = AITrustService(db, org_id, current_user.id, current_user.role)
    
    # Convert created tasks to dicts for payload
    created_dicts = [OnboardingTaskResponse.from_orm(t).dict() for t in created]
    
    return trust_service.wrap_and_log(
        content=f"Generated {len(created)} onboarding tasks.",
        action_type="generate_onboarding_checklist",
        entity_type="employee",
        entity_id=employee_id,
        confidence_score=0.9,
        model_name="HR-Onboard-AI",
        details={"position": employee.position, "department": employee.department},
        data=created_dicts
    )


@router.get("/employees/{employee_id}/tasks", response_model=List[OnboardingTaskResponse])
def list_tasks(
    employee_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    tasks = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.employee_id == employee_id)
        .order_by(OnboardingTask.is_completed.asc(), OnboardingTask.task_order.asc(), OnboardingTask.created_at.asc())
        .all()
    )
    return tasks


@router.get("/me/tasks", response_model=List[OnboardingTaskResponse])
def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch onboarding tasks for the currently authenticated user.
    Uses email to link User to OnboardingEmployee.
    Returns empty list instead of 404 if no onboarding record exists.
    """
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.employee_email == current_user.email
    ).first()
    
    if not employee:
        return []
        
    tasks = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.employee_id == employee.id)
        .order_by(OnboardingTask.is_completed.asc(), OnboardingTask.task_order.asc(), OnboardingTask.created_at.asc())
        .all()
    )
    return tasks


@router.post("/employees/{employee_id}/tasks", response_model=OnboardingTaskResponse)
def create_custom_task(
    employee_id: int, 
    payload: OnboardingTaskCreate, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    cat = payload.task_category.strip().lower() if payload.task_category else "other"
    if cat not in {c.value for c in OnboardingTaskCategory}:
        cat = "other"

    max_order = db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).count()
    task = OnboardingTask(
        employee_id=employee_id,
        task_title=payload.task_title.strip(),
        task_description=payload.task_description.strip(),
        task_category=OnboardingTaskCategory(cat),
        is_completed=False,
        due_date=payload.due_date,
        completed_at=None,
        task_order=max_order,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    analyze_progress(employee_id, db)
    return task


@router.put("/tasks/{task_id}/complete", response_model=OnboardingTaskResponse)
def complete_task(
    task_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    task = db.query(OnboardingTask).join(OnboardingEmployee).filter(
        OnboardingTask.id == task_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.is_completed:
        task.is_completed = True
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        analyze_progress(task.employee_id, db)
        
        # Audit logging
        AuditService.log(
            db,
            action="complete_onboarding_task",
            entity_type="onboarding_task",
            entity_id=task.id,
            user_id=current_user.id,
            user_role=current_user.role,
            details={"employee_id": task.employee_id, "task_title": task.task_title}
        )
    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    task = db.query(OnboardingTask).join(OnboardingEmployee).filter(
        OnboardingTask.id == task_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    employee_id = task.employee_id
    db.delete(task)
    db.commit()
    analyze_progress(employee_id, db)
    return {"message": "Task deleted successfully"}


@router.post("/employees/{employee_id}/ask", response_model=TrustedAIResponse)
def ask_onboarding(
    employee_id: int, 
    payload: AskRequest, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    context = {
        "employee_id": employee_id,
        "employee_name": employee.employee_name,
        "employee_email": employee.employee_email,
        "position": employee.position,
        "department": employee.department,
        "start_date": employee.start_date.isoformat(),
        "manager_name": employee.manager_name,
        "organization_id": employee.organization_id,
    }

    try:
        result = answer_onboarding_question(payload.question, context, db)
    except Exception as e:
        logger.error(f"Onboarding Q&A failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    chat = OnboardingChat(
        employee_id=employee_id,
        question=payload.question,
        ai_response=result.get("answer", ""),
        is_helpful=None,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    trust_service = AITrustService(db, org_id, current_user.id, current_user.role)
    return trust_service.wrap_and_log(
        content=result.get("answer", ""),
        action_type="ask_onboarding_question",
        entity_type="onboarding_chat",
        entity_id=chat.id,
        confidence_score=result.get("confidence", 0.0),
        model_name="HR-Onboard-QA",
        details={"question": payload.question},
        data={
            "chat_id": chat.id,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.0)
        }
    )


@router.get("/employees/{employee_id}/chat-history", response_model=List[ChatResponse])
def chat_history(
    employee_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    chats = (
        db.query(OnboardingChat)
        .filter(OnboardingChat.employee_id == employee_id)
        .order_by(OnboardingChat.created_at.asc())
        .all()
    )
    return chats


@router.put("/chats/{chat_id}/feedback", response_model=ChatResponse)
def chat_feedback(
    chat_id: int, 
    payload: ChatFeedbackRequest, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org)
):
    chat = db.query(OnboardingChat).join(OnboardingEmployee).filter(
        OnboardingChat.id == chat_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat = db.query(OnboardingChat).filter(OnboardingChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.is_helpful = payload.is_helpful
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/employees/{employee_id}/tips", response_model=TrustedAIResponse)
def tips(
    employee_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: int = Depends(get_current_org)
):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        tips_data = get_onboarding_tips(employee, db)
        
        trust_service = AITrustService(db, org_id, current_user.id, current_user.role)
        return trust_service.wrap_and_log(
            content="Daily tips generated.",
            action_type="get_onboarding_tips",
            entity_type="employee",
            entity_id=employee_id,
            confidence_score=0.85,
            model_name="HR-Onboard-Coach",
            details={},
            data=tips_data
        )

    except Exception as e:
        logger.error(f"Tips generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.get("/employees/{employee_id}/progress")
def progress(employee_id: int, db: Session = Depends(get_db)):
    result = analyze_progress(employee_id, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# --- Phase 5: Document Management ---

class DocumentResponse(BaseModel):
    id: int
    document_name: str
    document_type: str
    is_signed: bool
    signed_at: Optional[datetime]
    required_by: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

@router.get("/employees/{employee_id}/documents", response_model=List[DocumentResponse])
def list_documents(employee_id: int, db: Session = Depends(get_db)):
    return db.query(OnboardingDocument).filter(OnboardingDocument.employee_id == employee_id).all()


@router.get("/me/documents", response_model=List[DocumentResponse])
def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch onboarding documents for the currently authenticated user.
    Uses email to link User to OnboardingEmployee.
    Returns empty list instead of 404 if no onboarding record exists.
    """
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.employee_email == current_user.email
    ).first()
    
    if not employee:
        return []
        
    return db.query(OnboardingDocument).filter(OnboardingDocument.employee_id == employee.id).all()

@router.post("/employees/{employee_id}/documents")
def add_required_document(employee_id: int, document_name: str, document_type: str, db: Session = Depends(get_db)):
    doc = OnboardingDocument(
        employee_id=employee_id,
        document_name=document_name,
        document_type=document_type,
        required_by=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(doc)
    db.commit()
    return doc

@router.put("/documents/{doc_id}/sign")
def sign_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(OnboardingDocument).filter(OnboardingDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_signed = True
    doc.signed_at = datetime.now(timezone.utc)
    db.commit()
    return doc


# --- Phase 3: Templates & Reminders ---

@router.post("/templates", response_model=OnboardingTemplateResponse)
def create_template(
    payload: OnboardingTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_MANAGER])),
    org_id: int = Depends(get_current_org)
):
    """Create a reusable onboarding template."""
    # Check department access for HR_MANAGER
    if current_user.role == UserRole.HR_MANAGER and payload.department_id:
        if current_user.department_id != payload.department_id:
             raise HTTPException(status_code=403, detail="Cannot create template for another department")

    template = OnboardingTemplate(
        organization_id=org_id,
        name=payload.name,
        department_id=payload.department_id,
        tasks=[t.model_dump() for t in payload.tasks],
        is_active=payload.is_active
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    
    # Audit
    AuditService.log(
        db,
        action="create_onboarding_template",
        entity_type="onboarding_template",
        entity_id=template.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"name": template.name, "task_count": len(payload.tasks)},
        organization_id=org_id
    )
    return template

@router.get("/templates", response_model=List[OnboardingTemplateResponse])
def list_templates(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER])),
    org_id: int = Depends(get_current_org)
):
    query = db.query(OnboardingTemplate).filter(
        OnboardingTemplate.organization_id == org_id,
        OnboardingTemplate.is_active == True
    )
    if department_id:
        query = query.filter(OnboardingTemplate.department_id == department_id)
    
    return query.all()

@router.post("/employees/{employee_id}/apply-template/{template_id}")
def apply_template(
    employee_id: int,
    template_id: int,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER]))
):
    """Apply a template to an employee, creating tasks."""
    employee = db.query(OnboardingEmployee).filter(
        OnboardingEmployee.id == employee_id,
        OnboardingEmployee.organization_id == org_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    template = db.query(OnboardingTemplate).filter(
        OnboardingTemplate.id == template_id,
        OnboardingTemplate.organization_id == org_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # Permission check for Manager
    if current_user.role == UserRole.MANAGER:
        # Check if managing this employee or department
        # Simplified: Check department match or exact manager name match or organization
        pass # Manager can apply templates to own team
        
    # Create Tasks
    created_count = 0
    max_order = db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).count()
    
    for idx, t_data in enumerate(template.tasks):
        # t_data is dict from JSON
        due_date = None
        if t_data.get("due_offset_days") is not None:
            due_date = employee.start_date + timedelta(days=t_data["due_offset_days"])
            
        task = OnboardingTask(
            employee_id=employee_id,
            task_title=t_data["task_name"],
            task_description=t_data.get("description", ""),
            task_category=OnboardingTaskCategory.other, # detailed mapping could be added
            due_date=due_date,
            task_order=max_order + idx,
            is_completed=False
        )
        db.add(task)
        db.flush() # get ID
        
        # Schedule Reminder if needed
        if due_date and due_date > date.today():
             # Schedule reminder 1 day before
             reminder_time = datetime.combine(due_date - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
             if reminder_time > datetime.now(timezone.utc):
                 reminder = OnboardingReminder(
                     task_id=task.id,
                     reminder_type=ReminderType.EMAIL,
                     scheduled_at=reminder_time,
                     status=ReminderStatus.PENDING
                 )
                 db.add(reminder)
        
        created_count += 1
        
    # Update Estimated Completion Date
    # Find max due date
    all_tasks = db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).all()
    if all_tasks:
        max_due = max((t.due_date for t in all_tasks if t.due_date), default=employee.start_date)
        employee.estimated_completion_date = max_due
        
    employee.status = OnboardingStatus.in_progress
    db.commit()
    
    AuditService.log(
        db,
        action="apply_onboarding_template",
        entity_type="employee",
        entity_id=employee.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"template_id": template.id, "tasks_created": created_count},
        organization_id=org_id
    )
    
    return {"message": f"Template applied. {created_count} tasks created."}


class OnboardingBulkTemplateApply(BaseModel):
    employee_ids: List[int]
    template_id: int


@router.post("/employees/apply-template-bulk")
def apply_template_bulk(
    payload: OnboardingBulkTemplateApply,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER])),
    org_id: int = Depends(get_current_org)
):
    """
    Apply a template to multiple employees at once.
    """
    results = {
        "success": [],
        "failed": []
    }
    
    # Validate template existence once
    template = db.query(OnboardingTemplate).filter(OnboardingTemplate.id == payload.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    for emp_id in payload.employee_ids:
        try:
            # We can reuse the logic from apply_template, but calling it directly as a function might be hard due to Depends.
            # So we reimplement the core logic or refactor. 
            # Reimplementing core logic for bulk efficiency and error handling.
            
            employee = db.query(OnboardingEmployee).filter(
                             OnboardingEmployee.id == emp_id,
                             OnboardingEmployee.organization_id == org_id
                         ).first()
            
            if not employee:
                results["failed"].append({"id": emp_id, "error": "Employee not found"})
                continue
                
            # Create tasks logic
            max_order = db.query(OnboardingTask).filter(OnboardingTask.employee_id == emp_id).count()
            created_count = 0
            
            for idx, t_data in enumerate(template.tasks):
                due_date = None
                if t_data.get("due_offset_days") is not None:
                    due_date = employee.start_date + timedelta(days=t_data["due_offset_days"])
                
                # Default category
                cat = OnboardingTaskCategory.other
                # Try to map category string if exists in template
                if "category" in t_data:
                    try:
                         cat = OnboardingTaskCategory(t_data["category"])
                    except:
                         pass

                task = OnboardingTask(
                    employee_id=emp_id,
                    task_title=t_data["task_name"],
                    task_description=t_data.get("description", ""),
                    task_category=cat,
                    due_date=due_date,
                    task_order=max_order + idx,
                    is_completed=False
                )
                db.add(task)
                db.flush()
                
                # Schedule Reminder
                if due_date and due_date > date.today():
                     reminder_time = datetime.combine(due_date - timedelta(days=1), datetime.min.time()) + timedelta(hours=9)
                     if reminder_time > datetime.now(timezone.utc):
                         reminder = OnboardingReminder(
                             task_id=task.id,
                             reminder_type=ReminderType.EMAIL,
                             scheduled_at=reminder_time,
                             status=ReminderStatus.PENDING
                         )
                         db.add(reminder)
                
                created_count += 1
            
            # Update status
            employee.status = OnboardingStatus.in_progress
            
            # Notify
            try:
                NotificationService.send_notification(
                    db,
                    emp_id,
                    "Onboarding Started",
                    f"Welcome! The onboarding template '{template.name}' has been applied to your profile.",
                    "info"
                )
            except Exception:
                pass

            results["success"].append({"id": emp_id, "tasks_created": created_count})
            
        except Exception as e:
            db.rollback() # Rollback transaction for this iteration if nested? 
            # SQLAlchemy session rollback affects everything. 
            # For bulk operations, usually we want all or nothing OR handle errors.
            # Here, let's just log error and continue if possible, but safe way is simple loop.
            results["failed"].append({"id": emp_id, "error": str(e)})

    db.commit()
    
    # Audit Log
    AuditService.log(
        db,
        action="apply_onboarding_template_bulk",
        entity_type="onboarding_bulk",
        entity_id=payload.template_id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={
            "template_id": payload.template_id, 
            "success_count": len(results["success"]),
            "fail_count": len(results["failed"])
        },
        organization_id=org_id
    )
    
    return results


@router.get("/reminders", response_model=List[OnboardingReminderResponse])
def list_reminders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN])),
    org_id: int = Depends(get_current_org)
):
    query = db.query(OnboardingReminder).join(OnboardingTask).join(OnboardingEmployee).filter(
        OnboardingEmployee.organization_id == org_id
    )
    if status:
        query = query.filter(OnboardingReminder.status == status)
    return query.all()

@router.post("/reminders/send")
def send_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN])) # Admin trigger
):
    """
    Manual trigger to send pending reminders. 
    In production, this would be a cron job / Celery task.
    """
    now = datetime.now(timezone.utc)
    pending = db.query(OnboardingReminder).filter(
        OnboardingReminder.status == ReminderStatus.PENDING,
        OnboardingReminder.scheduled_at <= now
    ).all()
    
    sent_count = 0
    for reminder in pending:
        # Mock sending
        # email_service.send(...)
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = now
        sent_count += 1
        
    db.commit()
    return {"message": f"Sent {sent_count} reminders."}
