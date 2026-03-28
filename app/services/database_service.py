import logging
from typing import List

logger = logging.getLogger(__name__)


def reset_organization_data(db, organization_id: int):
    """
    Reset all data for a specific organization.
    Deletes all related data while keeping the schema.
    
    Deletion Order (respecting ALL foreign key constraints):
    Level 1: Tables with no dependencies (leaf nodes)
    Level 2-10: Tables pointing to previous levels
    Level N: Final tables (organizations, users, employees)
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole, UserSession
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.notification import Notification
    from app.models.department import Department
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.interview import Interview, InterviewSlot, InterviewScorecard, InterviewKit
    from app.models.governance import EthicalAuditLog
    from app.models.activity import Activity
    from app.models.performance_review import PerformanceReview
    from app.models.performance_metric import PerformanceMetric
    from app.models.burnout_assessment import BurnoutAssessment
    from app.models.wellbeing_assessment import WellbeingAssessment
    from app.models.leave_request import LeaveRequest
    from app.models.leave_balance import LeaveBalance
    from app.models.onboarding_employee import OnboardingEmployee
    from app.models.onboarding_task import OnboardingTask
    from app.models.onboarding_chat import OnboardingChat
    from app.models.onboarding_document import OnboardingDocument
    from app.models.onboarding_reminder import OnboardingReminder
    from app.models.payroll import Payroll
    from app.models.salary_component import SalaryComponent
    
    deleted_counts = {}
    
    try:
        # =====================================================================
        # PHASE 1: Collect all IDs we need
        # =====================================================================
        
        # Get all user IDs for this organization (excluding SUPER_ADMIN)
        org_user_ids = db.query(User.id).filter(
            User.organization_id == organization_id,
            User.role != UserRole.SUPER_ADMIN
        ).all()
        org_user_id_list = [uid[0] for uid in org_user_ids]
        
        # Get all employee IDs for this organization
        org_employee_ids = db.query(Employee.id).filter(
            Employee.organization_id == organization_id
        ).all()
        org_employee_id_list = [eid[0] for eid in org_employee_ids]
        
        # Get all department IDs for this organization
        org_department_ids = db.query(Department.id).filter(
            Department.organization_id == organization_id
        ).all()
        org_department_id_list = [did[0] for did in org_department_ids]
        
        # Get all document IDs for this organization
        org_document_ids = db.query(Document.id).filter(
            Document.organization_id == organization_id
        ).all()
        org_document_id_list = [did[0] for did in org_document_ids]
        
        # Get all job IDs for this organization
        org_job_ids = db.query(Job.id).filter(
            Job.organization_id == organization_id
        ).all()
        org_job_id_list = [jid[0] for jid in org_job_ids]
        
        # Get all interview IDs (related to org users)
        org_interview_ids = []
        if org_user_id_list:
            interviews = db.query(Interview.id).filter(
                (Interview.candidate_id.in_(org_user_id_list)) |
                (Interview.interviewer_id.in_(org_user_id_list))
            ).all()
            org_interview_ids = [iid[0] for iid in interviews]
        
        # Get all onboarding_employee IDs for this organization
        org_onboarding_emp_ids = db.query(OnboardingEmployee.id).filter(
            OnboardingEmployee.organization_id == organization_id
        ).all()
        org_onboarding_emp_id_list = [oeid[0] for oeid in org_onboarding_emp_ids]
        
        # Get all onboarding_task IDs (related to org onboarding_employees)
        org_onboarding_task_ids = []
        if org_onboarding_emp_id_list:
            tasks = db.query(OnboardingTask.id).filter(
                OnboardingTask.employee_id.in_(org_onboarding_emp_id_list)
            ).all()
            org_onboarding_task_ids = [tid[0] for tid in tasks]
        
        # =====================================================================
        # PHASE 2: Delete in correct order (deepest first)
        # =====================================================================
        
        # LEVEL 1: Document chunks (points to documents)
        if org_document_id_list:
            count = db.query(DocumentChunk).filter(
                DocumentChunk.document_id.in_(org_document_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["document_chunks"] = count
        
        # LEVEL 2: User sessions (points to users)
        if org_user_id_list:
            count = db.query(UserSession).filter(
                UserSession.user_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["user_sessions"] = count
        
        # LEVEL 3: Notifications (points to users, has CASCADE but explicit is better)
        if org_user_id_list:
            count = db.query(Notification).filter(
                Notification.user_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["notifications"] = count
        
        # LEVEL 4: Leave balances (points to users as employee_id)
        if org_user_id_list:
            count = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["leave_balances"] = count
        
        # LEVEL 5: Interview slots (points to users as interviewer_id, interviews)
        if org_user_id_list:
            count = db.query(InterviewSlot).filter(
                InterviewSlot.interviewer_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["interview_slots"] = count
        
        # LEVEL 6: Interview scorecards (points to users as interviewer_id)
        if org_user_id_list:
            count = db.query(InterviewScorecard).filter(
                InterviewScorecard.interviewer_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["interview_scorecards"] = count
        
        # LEVEL 7: Interview kits (points to interviews)
        if org_interview_ids:
            count = db.query(InterviewKit).filter(
                InterviewKit.interview_id.in_(org_interview_ids)
            ).delete(synchronize_session=False)
            deleted_counts["interview_kits"] = count
        
        # LEVEL 8: Resumes (points to jobs)
        if org_job_id_list:
            count = db.query(Resume).filter(
                Resume.job_id.in_(org_job_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["resumes"] = count
        
        # LEVEL 9: Salary components (points to payrolls)
        org_payroll_ids = db.query(Payroll.id).filter(
            Payroll.organization_id == organization_id
        ).all()
        org_payroll_id_list = [pid[0] for pid in org_payroll_ids]
        if org_payroll_id_list:
            count = db.query(SalaryComponent).filter(
                SalaryComponent.payroll_id.in_(org_payroll_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["salary_components"] = count
        
        # LEVEL 10: Performance metrics (points to employees)
        if org_employee_id_list:
            count = db.query(PerformanceMetric).filter(
                PerformanceMetric.employee_id.in_(org_employee_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["performance_metrics"] = count
        
        # LEVEL 11: Performance reviews (points to employees)
        if org_employee_id_list:
            count = db.query(PerformanceReview).filter(
                PerformanceReview.employee_id.in_(org_employee_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["performance_reviews"] = count
        
        # LEVEL 12: Burnout assessments (points to employees)
        if org_employee_id_list:
            count = db.query(BurnoutAssessment).filter(
                BurnoutAssessment.employee_id.in_(org_employee_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["burnout_assessments"] = count
        
        # LEVEL 13: Wellbeing assessments (points to employees)
        if org_employee_id_list:
            count = db.query(WellbeingAssessment).filter(
                WellbeingAssessment.employee_id.in_(org_employee_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["wellbeing_assessments"] = count
        
        # LEVEL 14: Activities (points to employees)
        if org_employee_id_list:
            count = db.query(Activity).filter(
                Activity.employee_id.in_(org_employee_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["activities"] = count
        
        # LEVEL 15: Onboarding reminders (points to onboarding_tasks)
        if org_onboarding_task_ids:
            count = db.query(OnboardingReminder).filter(
                OnboardingReminder.task_id.in_(org_onboarding_task_ids)
            ).delete(synchronize_session=False)
            deleted_counts["onboarding_reminders"] = count
        
        # LEVEL 16: Onboarding chats (points to onboarding_employees)
        if org_onboarding_emp_id_list:
            count = db.query(OnboardingChat).filter(
                OnboardingChat.employee_id.in_(org_onboarding_emp_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["onboarding_chats"] = count
        
        # LEVEL 17: Onboarding documents (points to onboarding_employees)
        if org_onboarding_emp_id_list:
            count = db.query(OnboardingDocument).filter(
                OnboardingDocument.employee_id.in_(org_onboarding_emp_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["onboarding_documents"] = count
        
        # LEVEL 18: Onboarding tasks (points to onboarding_employees)
        if org_onboarding_emp_id_list:
            count = db.query(OnboardingTask).filter(
                OnboardingTask.employee_id.in_(org_onboarding_emp_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["onboarding_tasks"] = count
        
        # LEVEL 19: Audit logs (points to users)
        if org_user_id_list:
            count = db.query(AuditLog).filter(
                AuditLog.user_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["audit_logs"] = count
        
        # LEVEL 20: Leave requests (points to users as employee/approver)
        if org_user_id_list:
            count = db.query(LeaveRequest).filter(
                (LeaveRequest.employee_id.in_(org_user_id_list)) |
                (LeaveRequest.approver_id.in_(org_user_id_list)) |
                (LeaveRequest.second_approver_id.in_(org_user_id_list))
            ).delete(synchronize_session=False)
            deleted_counts["leave_requests"] = count
        
        # LEVEL 21: Ethical audit logs (points to users as reviewer)
        if org_user_id_list:
            count = db.query(EthicalAuditLog).filter(
                EthicalAuditLog.reviewer_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["ethical_audit_logs"] = count
        
        # LEVEL 22: Interviews (points to users as candidate/interviewer, jobs)
        # Delete AFTER interview_scorecards, questions, kits
        if org_interview_ids:
            count = db.query(Interview).filter(
                Interview.id.in_(org_interview_ids)
            ).delete(synchronize_session=False)
            deleted_counts["interviews"] = count
        
        # LEVEL 23: Clear user department_id (points to departments)
        if org_department_id_list:
            db.query(User).filter(
                User.department_id.in_(org_department_id_list)
            ).update({"department_id": None}, synchronize_session=False)
        
        # LEVEL 24: Users (points to org, depts) - but NOT SUPER_ADMIN
        if org_user_id_list:
            count = db.query(User).filter(
                User.organization_id == organization_id,
                User.role != UserRole.SUPER_ADMIN
            ).delete(synchronize_session=False)
            deleted_counts["users"] = count
        
        # LEVEL 25: Employees (points to users, org)
        if org_employee_id_list:
            count = db.query(Employee).filter(
                Employee.organization_id == organization_id
            ).delete(synchronize_session=False)
            deleted_counts["employees"] = count
        
        # LEVEL 26: Documents (points to org)
        if org_document_id_list:
            count = db.query(Document).filter(
                Document.organization_id == organization_id
            ).delete(synchronize_session=False)
            deleted_counts["documents"] = count
        
        # LEVEL 27: Departments (points to org, users as manager)
        if org_department_id_list:
            count = db.query(Department).filter(
                Department.organization_id == organization_id
            ).delete(synchronize_session=False)
            deleted_counts["departments"] = count
        
        # LEVEL 28: Jobs (points to org)
        count = db.query(Job).filter(
            Job.organization_id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["jobs"] = count
        
        # LEVEL 29: Payrolls (points to org)
        count = db.query(Payroll).filter(
            Payroll.organization_id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["payrolls"] = count
        
        # LEVEL 30: Onboarding employees (points to org)
        count = db.query(OnboardingEmployee).filter(
            OnboardingEmployee.organization_id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["onboarding_employees"] = count
        
        # LEVEL 31: Delete remaining org-scoped data
        # Note: LeavePolicy, PayrollPolicy, EmbeddingCache are GLOBAL (no org_id)
        from app.models.ticket import Ticket
        from app.models.task import Task
        from app.models.policy import Policy
        from app.models.onboarding_template import OnboardingTemplate
        
        org_scoped_models = [
            (Ticket, "tickets"),
            (Task, "tasks"),
            (Policy, "policies"),
            (OnboardingTemplate, "onboarding_templates"),
        ]
        
        for model, name in org_scoped_models:
            if hasattr(model, 'organization_id'):
                count = db.query(model).filter(
                    model.organization_id == organization_id
                ).delete(synchronize_session=False)
                deleted_counts[name] = count
            else:
                deleted_counts[name] = 0  # Skip if no org_id
        
        # LEVEL 32: Finally delete the organization
        count = db.query(Organization).filter(
            Organization.id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["organizations"] = count
        
        db.commit()
        logger.info(f"Successfully reset organization {organization_id}: {deleted_counts}")
        return deleted_counts
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting organization {organization_id}: {str(e)}")
        raise


def reset_all_data(db):
    """
    Reset all data in the database.
    Deletes ALL organizations and their data.
    WARNING: This will delete ALL data except SUPER_ADMIN users.
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole, UserSession
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.notification import Notification
    from app.models.department import Department
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.interview import Interview, InterviewSlot, InterviewScorecard, InterviewKit
    from app.models.governance import EthicalAuditLog
    from app.models.activity import Activity
    from app.models.performance_review import PerformanceReview
    from app.models.performance_metric import PerformanceMetric
    from app.models.burnout_assessment import BurnoutAssessment
    from app.models.wellbeing_assessment import WellbeingAssessment
    from app.models.leave_request import LeaveRequest
    from app.models.leave_balance import LeaveBalance
    from app.models.leave_policy import LeavePolicy
    from app.models.onboarding_employee import OnboardingEmployee
    from app.models.onboarding_task import OnboardingTask
    from app.models.onboarding_chat import OnboardingChat
    from app.models.onboarding_document import OnboardingDocument
    from app.models.onboarding_reminder import OnboardingReminder
    from app.models.onboarding_template import OnboardingTemplate
    from app.models.payroll import Payroll, PayrollPolicy
    from app.models.salary_component import SalaryComponent
    from app.models.ticket import Ticket
    from app.models.task import Task
    from app.models.policy import Policy
    from app.models.embedding_cache import EmbeddingCache
    
    deleted_counts = {}
    
    try:
        # Delete in correct order (children first)
        
        # Level 1: Document chunks
        deleted_counts["document_chunks"] = db.query(DocumentChunk).delete(synchronize_session=False)
        
        # Level 2: User sessions
        deleted_counts["user_sessions"] = db.query(UserSession).delete(synchronize_session=False)
        
        # Level 3: Notifications
        deleted_counts["notifications"] = db.query(Notification).delete(synchronize_session=False)
        
        # Level 4: Leave balances
        deleted_counts["leave_balances"] = db.query(LeaveBalance).delete(synchronize_session=False)
        
        # Level 5: Interview slots
        deleted_counts["interview_slots"] = db.query(InterviewSlot).delete(synchronize_session=False)
        
        # Level 6: Interview scorecards
        deleted_counts["interview_scorecards"] = db.query(InterviewScorecard).delete(synchronize_session=False)
        
        # Level 7: Interview kits
        deleted_counts["interview_kits"] = db.query(InterviewKit).delete(synchronize_session=False)
        
        # Level 8: Interviews
        deleted_counts["interviews"] = db.query(Interview).delete(synchronize_session=False)
        
        # Level 9: Resumes
        deleted_counts["resumes"] = db.query(Resume).delete(synchronize_session=False)
        
        # Level 10: Salary components
        deleted_counts["salary_components"] = db.query(SalaryComponent).delete(synchronize_session=False)
        
        # Level 11: Performance metrics
        deleted_counts["performance_metrics"] = db.query(PerformanceMetric).delete(synchronize_session=False)
        
        # Level 12: Performance reviews
        deleted_counts["performance_reviews"] = db.query(PerformanceReview).delete(synchronize_session=False)
        
        # Level 13: Burnout assessments
        deleted_counts["burnout_assessments"] = db.query(BurnoutAssessment).delete(synchronize_session=False)
        
        # Level 14: Wellbeing assessments
        deleted_counts["wellbeing_assessments"] = db.query(WellbeingAssessment).delete(synchronize_session=False)
        
        # Level 15: Activities
        deleted_counts["activities"] = db.query(Activity).delete(synchronize_session=False)
        
        # Level 16: Onboarding reminders
        deleted_counts["onboarding_reminders"] = db.query(OnboardingReminder).delete(synchronize_session=False)
        
        # Level 17: Onboarding chats
        deleted_counts["onboarding_chats"] = db.query(OnboardingChat).delete(synchronize_session=False)
        
        # Level 18: Onboarding documents
        deleted_counts["onboarding_documents"] = db.query(OnboardingDocument).delete(synchronize_session=False)
        
        # Level 19: Onboarding tasks
        deleted_counts["onboarding_tasks"] = db.query(OnboardingTask).delete(synchronize_session=False)
        
        # Level 20: Audit logs
        deleted_counts["audit_logs"] = db.query(AuditLog).delete(synchronize_session=False)
        
        # Level 21: Leave requests
        deleted_counts["leave_requests"] = db.query(LeaveRequest).delete(synchronize_session=False)
        
        # Level 22: Ethical audit logs
        deleted_counts["ethical_audit_logs"] = db.query(EthicalAuditLog).delete(synchronize_session=False)
        
        # Level 23: Clear user department_id
        db.query(User).filter(User.department_id.isnot(None)).update(
            {"department_id": None}, synchronize_session=False
        )
        
        # Level 24: Users (except SUPER_ADMIN)
        deleted_counts["users"] = db.query(User).filter(
            User.role != UserRole.SUPER_ADMIN
        ).delete(synchronize_session=False)
        
        # Level 25: Employees
        deleted_counts["employees"] = db.query(Employee).delete(synchronize_session=False)
        
        # Level 26: Documents
        deleted_counts["documents"] = db.query(Document).delete(synchronize_session=False)
        
        # Level 27: Departments
        deleted_counts["departments"] = db.query(Department).delete(synchronize_session=False)
        
        # Level 28: Jobs
        deleted_counts["jobs"] = db.query(Job).delete(synchronize_session=False)
        
        # Level 29: Payrolls
        deleted_counts["payrolls"] = db.query(Payroll).delete(synchronize_session=False)
        
        # Level 30: Onboarding employees
        deleted_counts["onboarding_employees"] = db.query(OnboardingEmployee).delete(synchronize_session=False)
        
        # Level 31: Onboarding templates
        deleted_counts["onboarding_templates"] = db.query(OnboardingTemplate).delete(synchronize_session=False)
        
        # Level 32: Leave policies
        deleted_counts["leave_policies"] = db.query(LeavePolicy).delete(synchronize_session=False)
        
        # Level 33: Payroll policies
        deleted_counts["payroll_policies"] = db.query(PayrollPolicy).delete(synchronize_session=False)
        
        # Level 34: Tickets
        deleted_counts["tickets"] = db.query(Ticket).delete(synchronize_session=False)
        
        # Level 35: Tasks
        deleted_counts["tasks"] = db.query(Task).delete(synchronize_session=False)
        
        # Level 36: Policies
        deleted_counts["policies"] = db.query(Policy).delete(synchronize_session=False)
        
        # Level 37: Embedding cache
        deleted_counts["embedding_cache"] = db.query(EmbeddingCache).delete(synchronize_session=False)
        
        # Level 38: Organizations
        deleted_counts["organizations"] = db.query(Organization).delete(synchronize_session=False)
        
        # Check SUPER_ADMIN remains
        super_admin_count = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).count()
        deleted_counts["super_admins_remaining"] = super_admin_count
        
        db.commit()
        logger.info(f"Successfully reset all data: {deleted_counts}")
        return deleted_counts
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting all data: {str(e)}")
        raise
