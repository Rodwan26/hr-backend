from fastapi import APIRouter
from app.routers import (
    helpdesk, resume, wellbeing, interview, documents, 
    onboarding, leave, leave_manager, payroll, burnout, auth, admin, jobs,
    departments, setup, notifications, risk
)

# Centralized API router hub
# This follows the "Leaf Node" pattern: Routers are aggregated here, 
# and main.py only imports this single hub.
api_router = APIRouter()

api_router.include_router(helpdesk.router, tags=["Help Desk"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(resume.router, prefix="/jobs", tags=["Resumes"])
api_router.include_router(wellbeing.router, tags=["Wellbeing"])
api_router.include_router(interview.router, tags=["Interviews"])
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(onboarding.router, tags=["Onboarding"])
api_router.include_router(leave.router, tags=["Leave"])
api_router.include_router(leave_manager.router, tags=["Leave Manager"])
api_router.include_router(payroll.router, tags=["Payroll"])
api_router.include_router(burnout.router, tags=["Wellbeing Trends"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(admin.router, tags=["Administration"])
api_router.include_router(risk.router, tags=["Organizational Risk"])
api_router.include_router(jobs.router, tags=["Jobs"])
api_router.include_router(departments.router, tags=["Departments"])
api_router.include_router(setup.router, prefix="/setup", tags=["System Setup"])
