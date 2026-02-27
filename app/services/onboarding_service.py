from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models.onboarding_employee import OnboardingEmployee
from app.models.onboarding_task import OnboardingTask, OnboardingTaskCategory
from app.services.onboarding_ai import generate_onboarding_checklist


def create_onboarding_tasks(
    db: Session,
    employee: OnboardingEmployee,
    use_ai: bool = True
):
    """
    Creates real onboarding tasks in the database.
    AI is ONLY used to suggest the checklist.
    System works even if AI fails.
    """

    tasks_data = []

    # Try AI suggestions
    if use_ai:
        try:
            tasks_data = generate_onboarding_checklist(
                position=employee.position,
                department=employee.department
            )
        except Exception:
            tasks_data = []

    # Fallback (system must always work)
    if not tasks_data:
        tasks_data = [
            {
                "title": "HR Orientation Meeting",
                "description": "Meet HR and review company policies.",
                "category": "meeting",
                "priority": "high",
                "day_offset": 0,
            },
            {
                "title": "System Access Setup",
                "description": "Receive accounts and credentials.",
                "category": "setup",
                "priority": "high",
                "day_offset": 0,
            },
        ]

    created_tasks = []

    for order, task in enumerate(tasks_data, start=1):

        due_date = None
        if employee.start_date:
            due_date = employee.start_date + timedelta(days=task.get("day_offset", 0))

        category_value = task.get("category", "other")
        try:
            category_enum = OnboardingTaskCategory(category_value)
        except Exception:
            category_enum = OnboardingTaskCategory.other

        new_task = OnboardingTask(
            employee_id=employee.id,
            task_title=task["title"],
            task_description=task.get("description", ""),
            task_category=category_enum,
            task_order=order,
            due_date=due_date,
            is_completed=False,
        )

        db.add(new_task)
        created_tasks.append(new_task)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return created_tasks
