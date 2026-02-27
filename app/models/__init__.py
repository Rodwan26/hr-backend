# Models package
# Importing modules here ensures they are registered with SQLAlchemy Base
from . import (
    user, department, employee, job, resume, interview, 
    interviewer_availability, 
    leave_request, leave_balance, leave_policy, 
    payroll, salary_component, payroll_policy, 
    performance_metric, performance_review, 
    wellbeing_assessment, burnout_assessment,
    onboarding_employee, onboarding_task, onboarding_chat, onboarding_document,
    onboarding_template, onboarding_reminder,
    audit_log, ticket, organization, governance, task, notification
)

# Explicit class exports for cleaner imports
from .user import User
from .organization import Organization
from .department import Department
from .notification import Notification

__all__ = [
    "User",
    "Organization",
    "Department",
    "Notification",
]
