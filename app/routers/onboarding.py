import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.models.onboarding_employee import OnboardingEmployee, OnboardingStatus
from app.models.onboarding_task import OnboardingTask, OnboardingTaskCategory
from app.models.onboarding_chat import OnboardingChat
from app.services.onboarding_ai import (
    generate_onboarding_checklist,
    answer_onboarding_question,
    get_onboarding_tips,
    analyze_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

DEFAULT_COMPANY_ID = 1


def get_or_create_default_company(db: Session) -> Company:
    company = db.query(Company).filter(Company.id == DEFAULT_COMPANY_ID).first()
    if not company:
        company = Company(id=DEFAULT_COMPANY_ID, name="Default Company")
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


class OnboardingEmployeeCreate(BaseModel):
    employee_name: str
    employee_email: EmailStr
    position: str
    department: str
    start_date: date
    manager_name: Optional[str] = None
    company_id: int = DEFAULT_COMPANY_ID


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
    company_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class OnboardingTaskCreate(BaseModel):
    task_title: str
    task_description: str
    task_category: str = "other"
    due_date: Optional[date] = None


class OnboardingTaskResponse(BaseModel):
    id: int
    employee_id: int
    task_title: str
    task_description: str
    task_category: str
    is_completed: bool
    due_date: Optional[date]
    completed_at: Optional[datetime]
    task_order: int
    created_at: datetime

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class ChatFeedbackRequest(BaseModel):
    is_helpful: bool


@router.post("/employees", response_model=OnboardingEmployeeResponse)
def create_employee(payload: OnboardingEmployeeCreate, db: Session = Depends(get_db)):
    logger.info("Creating onboarding employee")
    get_or_create_default_company(db)

    employee = OnboardingEmployee(
        employee_name=payload.employee_name,
        employee_email=str(payload.employee_email),
        position=payload.position,
        department=payload.department,
        start_date=payload.start_date,
        manager_name=payload.manager_name,
        status=OnboardingStatus.pending,
        completion_percentage=0,
        company_id=payload.company_id,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/employees", response_model=List[OnboardingEmployeeResponse])
def list_employees(db: Session = Depends(get_db)):
    employees = db.query(OnboardingEmployee).order_by(OnboardingEmployee.created_at.desc()).all()
    return employees


@router.get("/employees/{employee_id}", response_model=OnboardingEmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/employees/{employee_id}", response_model=OnboardingEmployeeResponse)
def update_employee(employee_id: int, payload: OnboardingEmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
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

    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/employees/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # delete children first (SQLite-safe)
    db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).delete()
    db.query(OnboardingChat).filter(OnboardingChat.employee_id == employee_id).delete()
    db.delete(employee)
    db.commit()
    return {"message": "Employee deleted successfully"}


@router.post("/employees/{employee_id}/generate-checklist", response_model=List[OnboardingTaskResponse])
def generate_checklist(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    logger.info(f"Generating onboarding checklist for employee_id={employee_id}")
    tasks = generate_onboarding_checklist(employee.position, employee.department)

    # Replace existing tasks (fresh generation)
    db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).delete()

    created: List[OnboardingTask] = []
    for idx, t in enumerate(tasks):
        category = str(t.get("category", "other")).lower()
        if category not in {c.value for c in OnboardingTaskCategory}:
            category = "other"

        due = None
        day_offset = t.get("day_offset", None)
        if day_offset is not None:
            try:
                due = employee.start_date + timedelta(days=int(day_offset))
            except Exception:
                due = None

        priority = str(t.get("priority", "medium")).lower()
        description = str(t.get("description", "")).strip() or "No description provided."
        description = f"[Priority: {priority}] {description}"

        task = OnboardingTask(
            employee_id=employee_id,
            task_title=str(t.get("title", "")).strip(),
            task_description=description,
            task_category=OnboardingTaskCategory(category),
            is_completed=False,
            due_date=due,
            completed_at=None,
            task_order=idx,
        )
        created.append(task)
        db.add(task)

    db.commit()

    # Update progress
    analyze_progress(employee_id, db)

    created = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.employee_id == employee_id)
        .order_by(OnboardingTask.task_order.asc(), OnboardingTask.created_at.asc())
        .all()
    )
    return created


@router.get("/employees/{employee_id}/tasks", response_model=List[OnboardingTaskResponse])
def list_tasks(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    tasks = (
        db.query(OnboardingTask)
        .filter(OnboardingTask.employee_id == employee_id)
        .order_by(OnboardingTask.is_completed.asc(), OnboardingTask.task_order.asc(), OnboardingTask.created_at.asc())
        .all()
    )
    return tasks


@router.post("/employees/{employee_id}/tasks", response_model=OnboardingTaskResponse)
def create_custom_task(employee_id: int, payload: OnboardingTaskCreate, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
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
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.is_completed:
        task.is_completed = True
        task.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        analyze_progress(task.employee_id, db)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    employee_id = task.employee_id
    db.delete(task)
    db.commit()
    analyze_progress(employee_id, db)
    return {"message": "Task deleted successfully"}


@router.post("/employees/{employee_id}/ask", response_model=AskResponse)
def ask_onboarding(employee_id: int, payload: AskRequest, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
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
        "company_id": employee.company_id,
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

    return AskResponse(
        chat_id=chat.id,
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        confidence=float(result.get("confidence", 0.0) or 0.0),
    )


@router.get("/employees/{employee_id}/chat-history", response_model=List[ChatResponse])
def chat_history(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
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
def chat_feedback(chat_id: int, payload: ChatFeedbackRequest, db: Session = Depends(get_db)):
    chat = db.query(OnboardingChat).filter(OnboardingChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.is_helpful = payload.is_helpful
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/employees/{employee_id}/tips")
def tips(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        return get_onboarding_tips(employee, db)
    except Exception as e:
        logger.error(f"Tips generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


@router.get("/employees/{employee_id}/progress")
def progress(employee_id: int, db: Session = Depends(get_db)):
    result = analyze_progress(employee_id, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

