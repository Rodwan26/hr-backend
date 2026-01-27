import json
import logging
import re
from datetime import date, timedelta, datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.onboarding_employee import OnboardingEmployee, OnboardingStatus
from app.models.onboarding_task import OnboardingTask, OnboardingTaskCategory
from app.models.document import Document
from app.services.openrouter_client import call_openrouter
from app.services.embedding_service import generate_embeddings, hybrid_search

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[dict]:
    """
    Best-effort JSON extraction from model responses.
    """
    if not text:
        return None
    text = text.strip()
    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a JSON object in the text
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
    except Exception:
        return None

    return None


def generate_onboarding_checklist(position: str, department: str) -> List[dict]:
    """
    Use AI to generate a personalized onboarding checklist (10-15 tasks).
    Returns tasks with categories, priorities, and day_offset (0-14).
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an HR onboarding specialist. Generate a practical onboarding checklist.\n"
                "Return ONLY valid JSON with this schema:\n"
                "{"
                "\"tasks\":["
                "{"
                "\"title\":\"...\","
                "\"description\":\"...\","
                "\"category\":\"documentation|training|setup|meeting|other\","
                "\"priority\":\"high|medium|low\","
                "\"day_offset\":0"
                "}"
                "]}\n"
                "Create 10-15 tasks spread across the first 2 weeks (day_offset 0-14)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Role: {position}\n"
                f"Department: {department}\n\n"
                "Generate an onboarding checklist tailored to this role and department."
            ),
        },
    ]

    raw = call_openrouter(messages, temperature=0.4)
    parsed = _extract_json(raw)

    tasks: List[dict] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("tasks"), list):
        for t in parsed["tasks"]:
            if not isinstance(t, dict):
                continue
            title = str(t.get("title", "")).strip()
            description = str(t.get("description", "")).strip()
            category = str(t.get("category", "other")).strip().lower()
            priority = str(t.get("priority", "medium")).strip().lower()
            day_offset = t.get("day_offset", 0)
            try:
                day_offset = int(day_offset)
            except Exception:
                day_offset = 0
            day_offset = max(0, min(14, day_offset))

            if not title:
                continue
            if category not in {c.value for c in OnboardingTaskCategory}:
                category = "other"
            if priority not in {"high", "medium", "low"}:
                priority = "medium"

            tasks.append(
                {
                    "title": title,
                    "description": description or "No description provided.",
                    "category": category,
                    "priority": priority,
                    "day_offset": day_offset,
                }
            )

    # Fallback tasks if AI output is malformed
    if len(tasks) < 8:
        tasks = [
            {
                "title": "Complete HR paperwork",
                "description": "Review and complete required employment forms and policies.",
                "category": "documentation",
                "priority": "high",
                "day_offset": 0,
            },
            {
                "title": "Set up accounts and access",
                "description": "Get access to email, HR portal, and required tools.",
                "category": "setup",
                "priority": "high",
                "day_offset": 0,
            },
            {
                "title": "Meet your manager",
                "description": "Discuss expectations, first-week goals, and success criteria.",
                "category": "meeting",
                "priority": "high",
                "day_offset": 1,
            },
            {
                "title": "Security & compliance training",
                "description": "Complete mandatory security/compliance modules.",
                "category": "training",
                "priority": "high",
                "day_offset": 2,
            },
            {
                "title": "Read company handbook",
                "description": "Review key policies, benefits, and company culture.",
                "category": "documentation",
                "priority": "medium",
                "day_offset": 2,
            },
            {
                "title": "Team introductions",
                "description": "Meet your immediate team and key cross-functional partners.",
                "category": "meeting",
                "priority": "medium",
                "day_offset": 3,
            },
            {
                "title": "Role-specific onboarding training",
                "description": f"Complete training relevant to {position} in {department}.",
                "category": "training",
                "priority": "medium",
                "day_offset": 5,
            },
            {
                "title": "First deliverable planning",
                "description": "Define and align on your first deliverable/project plan.",
                "category": "other",
                "priority": "medium",
                "day_offset": 7,
            },
            {
                "title": "Two-week check-in",
                "description": "Review progress and adjust goals for the next phase.",
                "category": "meeting",
                "priority": "medium",
                "day_offset": 14,
            },
        ]

    return tasks


def analyze_progress(employee_id: int, db: Session) -> dict:
    """
    Compute completion percentage, overdue tasks, and suggested priorities.
    Updates employee.completion_percentage and employee.status.
    """
    employee = db.query(OnboardingEmployee).filter(OnboardingEmployee.id == employee_id).first()
    if not employee:
        return {"error": "Employee not found"}

    tasks = db.query(OnboardingTask).filter(OnboardingTask.employee_id == employee_id).all()
    total = len(tasks)
    completed = len([t for t in tasks if t.is_completed])
    percent = int((completed / total) * 100) if total > 0 else 0

    today = date.today()
    overdue = []
    for t in tasks:
        if t.due_date and (not t.is_completed) and t.due_date < today:
            overdue.append(
                {
                    "task_id": t.id,
                    "title": t.task_title,
                    "due_date": t.due_date.isoformat(),
                    "category": str(t.task_category.value) if hasattr(t.task_category, "value") else str(t.task_category),
                }
            )

    # Update employee status
    if total > 0 and completed == total:
        status = OnboardingStatus.completed
    elif completed > 0:
        status = OnboardingStatus.in_progress
    else:
        status = OnboardingStatus.pending

    employee.completion_percentage = percent
    employee.status = status
    db.commit()

    # Suggest priorities: overdue first, then next due, then setup/training
    pending_tasks = [t for t in tasks if not t.is_completed]
    pending_tasks.sort(key=lambda t: (t.due_date is None, t.due_date or date.max, t.task_order))
    next_actions = [
        {
            "task_id": t.id,
            "title": t.task_title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "category": str(t.task_category.value) if hasattr(t.task_category, "value") else str(t.task_category),
        }
        for t in pending_tasks[:5]
    ]

    return {
        "employee_id": employee_id,
        "completion_percentage": percent,
        "status": status.value,
        "total_tasks": total,
        "completed_tasks": completed,
        "overdue_tasks": overdue,
        "next_actions": next_actions,
    }


def answer_onboarding_question(question: str, employee_context: dict, db: Session) -> dict:
    """
    Answer onboarding questions using ONLY employee tasks and context.
    Does NOT use document RAG to avoid irrelevant answers.
    """
    employee_id = employee_context.get("employee_id")
    company_id = int(employee_context.get("company_id", 1))
    
    # Get employee's tasks
    tasks = []
    pending_tasks = []
    completed_tasks = []
    
    if employee_id:
        all_tasks = db.query(OnboardingTask).filter(
            OnboardingTask.employee_id == employee_id
        ).order_by(OnboardingTask.task_order).all()
        
        for task in all_tasks:
            task_info = {
                "title": task.task_title,
                "description": task.task_description,
                "category": str(task.task_category.value) if hasattr(task.task_category, "value") else str(task.task_category),
                "completed": task.is_completed,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            }
            tasks.append(task_info)
            
            if task.is_completed:
                completed_tasks.append(task_info)
            else:
                pending_tasks.append(task_info)
    
    # Build employee summary
    employee_summary = (
        f"Employee: {employee_context.get('employee_name')} ({employee_context.get('employee_email')})\n"
        f"Position: {employee_context.get('position')}\n"
        f"Department: {employee_context.get('department')}\n"
        f"Start date: {employee_context.get('start_date')}\n"
        f"Manager: {employee_context.get('manager_name') or 'N/A'}\n"
        f"Total tasks: {len(tasks)}\n"
        f"Completed: {len(completed_tasks)}\n"
        f"Pending: {len(pending_tasks)}\n"
    )
    
    # Build tasks context
    tasks_context = "Pending tasks:\n"
    for i, task in enumerate(pending_tasks[:10], 1):
        due = f" (Due: {task['due_date']})" if task['due_date'] else ""
        tasks_context += f"{i}. [{task['category']}] {task['title']}{due}\n   {task['description']}\n"
    
    if completed_tasks:
        tasks_context += "\nRecently completed tasks:\n"
        for i, task in enumerate(completed_tasks[-5:], 1):
            tasks_context += f"{i}. {task['title']}\n"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an onboarding assistant helping new employees. "
                "Answer questions based ONLY on the employee's information and their onboarding tasks. "
                "Be specific, helpful, and friendly. "
                "If asked about tasks for today, list the pending tasks. "
                "If asked about progress, mention completion status. "
                "If the question is about something not in the context (like company policies, benefits, etc.), "
                "politely say you don't have that information and suggest they ask their manager or HR."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{employee_summary}\n"
                f"{tasks_context}\n\n"
                f"Question: {question}\n\n"
                "Answer based on the employee's tasks and information above. "
                "If you don't have the information, suggest who to contact."
            ),
        },
    ]

    answer = call_openrouter(messages, temperature=0.3)
    
    return {
        "answer": answer,
        "sources": [],  # No document sources for onboarding questions
        "confidence": 0.9 if tasks else 0.5  # High confidence if we have tasks
    }


def get_onboarding_tips(employee: OnboardingEmployee, db: Session) -> dict:
    """
    Generate daily tips and suggested next actions based on progress and tasks.
    """
    progress = analyze_progress(employee.id, db)
    next_actions = progress.get("next_actions", [])
    overdue = progress.get("overdue_tasks", [])

    messages = [
        {
            "role": "system",
            "content": (
                "You are an onboarding coach. Return ONLY JSON with:\n"
                "{"
                "\"tips\":[\"...\"],"
                "\"next_actions\":[\"...\"],"
                "\"motivation\":\"...\""
                "}\n"
                "Keep it concise and practical."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Employee: {employee.employee_name}\n"
                f"Role: {employee.position}\n"
                f"Department: {employee.department}\n"
                f"Start date: {employee.start_date.isoformat()}\n"
                f"Progress: {progress.get('completion_percentage', 0)}%\n"
                f"Overdue tasks: {len(overdue)}\n"
                f"Next actions (raw): {json.dumps(next_actions)}\n\n"
                "Generate today's onboarding tips, 3-5 items, and 2-3 next_actions suggestions."
            ),
        },
    ]

    raw = call_openrouter(messages, temperature=0.6)
    parsed = _extract_json(raw) or {}

    tips = parsed.get("tips") if isinstance(parsed, dict) else None
    next_actions_ai = parsed.get("next_actions") if isinstance(parsed, dict) else None
    motivation = parsed.get("motivation") if isinstance(parsed, dict) else None

    if not isinstance(tips, list) or not tips:
        tips = [
            "Block 30 minutes to review your checklist and pick 1-2 high-impact tasks for today.",
            "Schedule short intro chats with teammates you'll work with frequently.",
            "Write down open questions and ask your manager during your next check-in.",
        ]
    if not isinstance(next_actions_ai, list) or not next_actions_ai:
        next_actions_ai = [a["title"] for a in next_actions[:3]] if next_actions else ["Review your onboarding tasks."]
    if not isinstance(motivation, str) or not motivation.strip():
        motivation = "You're doing great—consistent small steps will compound quickly."

    return {
        "tips": [str(t).strip() for t in tips if str(t).strip()],
        "next_actions": [str(a).strip() for a in next_actions_ai if str(a).strip()],
        "motivation": motivation.strip(),
        "progress": progress,
    }