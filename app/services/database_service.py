import logging

logger = logging.getLogger(__name__)


def reset_organization_data(db, organization_id: int):
    """
    Reset all data for a specific organization.
    Deletes all related data while keeping the schema.
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.department import Department
    from app.models.notification import Notification
    from app.models.leave_request import LeaveRequest
    from app.models.leave_balance import LeaveBalance
    from app.models.leave_policy import LeavePolicy
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.interview import Interview
    from app.models.interviewer_availability import InterviewerAvailability
    from app.models.payroll import Payroll
    from app.models.payroll_policy import PayrollPolicy
    from app.models.salary_component import SalaryComponent
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.onboarding_employee import OnboardingEmployee
    from app.models.onboarding_task import OnboardingTask
    from app.models.onboarding_template import OnboardingTemplate
    from app.models.onboarding_chat import OnboardingChat
    from app.models.onboarding_document import OnboardingDocument
    from app.models.onboarding_reminder import OnboardingReminder
    from app.models.ticket import Ticket
    from app.models.task import Task
    from app.models.policy import Policy
    from app.models.burnout_assessment import BurnoutAssessment
    from app.models.wellbeing_assessment import WellbeingAssessment
    from app.models.performance_review import PerformanceReview
    from app.models.performance_metric import PerformanceMetric
    from app.models.activity import Activity
    from app.models.governance import EthicalAuditLog
    from app.models.embedding_cache import EmbeddingCache
    
    deleted_counts = {}
    
    try:
        # Delete activities (no org_id, but we can count them)
        try:
            count = db.query(Activity).delete()
            deleted_counts["activities"] = count
        except:
            pass
        
        # Delete document chunks
        try:
            count = db.query(DocumentChunk).delete()
            deleted_counts["document_chunks"] = count
        except:
            pass
        
        # Models with organization_id
        models_to_delete = [
            (AuditLog, "audit_logs"),
            (Notification, "notifications"),
            (LeaveRequest, "leave_requests"),
            (LeaveBalance, "leave_balances"),
            (LeavePolicy, "leave_policies"),
            (Job, "jobs"),
            (Resume, "resumes"),
            (Interview, "interviews"),
            (InterviewerAvailability, "interviewer_availability"),
            (Payroll, "payrolls"),
            (PayrollPolicy, "payroll_policies"),
            (SalaryComponent, "salary_components"),
            (Document, "documents"),
            (OnboardingEmployee, "onboarding_employees"),
            (OnboardingTask, "onboarding_tasks"),
            (OnboardingTemplate, "onboarding_templates"),
            (OnboardingChat, "onboarding_chats"),
            (OnboardingDocument, "onboarding_documents"),
            (OnboardingReminder, "onboarding_reminders"),
            (Ticket, "tickets"),
            (Task, "tasks"),
            (Policy, "policies"),
            (BurnoutAssessment, "burnout_assessments"),
            (WellbeingAssessment, "wellbeing_assessments"),
            (PerformanceReview, "performance_reviews"),
            (PerformanceMetric, "performance_metrics"),
            (EthicalAuditLog, "ethical_audit_logs"),
            (EmbeddingCache, "embedding_cache"),
            (Department, "departments"),
        ]
        
        for model, name in models_to_delete:
            try:
                if hasattr(model, 'organization_id'):
                    count = db.query(model).filter(model.organization_id == organization_id).delete()
                    deleted_counts[name] = count
            except Exception as e:
                logger.warning(f"Could not delete {name}: {e}")
        
        # Delete users (except super admin)
        count = db.query(User).filter(
            User.organization_id == organization_id,
            User.role != UserRole.SUPER_ADMIN
        ).delete()
        deleted_counts["users"] = count
        
        # Delete employees
        count = db.query(Employee).filter(Employee.organization_id == organization_id).delete()
        deleted_counts["employees"] = count
        
        # Delete organization
        count = db.query(Organization).filter(Organization.id == organization_id).delete()
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
    Deletes all organizations and their data.
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.department import Department
    from app.models.notification import Notification
    from app.models.leave_request import LeaveRequest
    from app.models.leave_balance import LeaveBalance
    from app.models.leave_policy import LeavePolicy
    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.interview import Interview
    from app.models.interviewer_availability import InterviewerAvailability
    from app.models.payroll import Payroll
    from app.models.payroll_policy import PayrollPolicy
    from app.models.salary_component import SalaryComponent
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from app.models.onboarding_employee import OnboardingEmployee
    from app.models.onboarding_task import OnboardingTask
    from app.models.onboarding_template import OnboardingTemplate
    from app.models.onboarding_chat import OnboardingChat
    from app.models.onboarding_document import OnboardingDocument
    from app.models.onboarding_reminder import OnboardingReminder
    from app.models.ticket import Ticket
    from app.models.task import Task
    from app.models.policy import Policy
    from app.models.burnout_assessment import BurnoutAssessment
    from app.models.wellbeing_assessment import WellbeingAssessment
    from app.models.performance_review import PerformanceReview
    from app.models.performance_metric import PerformanceMetric
    from app.models.activity import Activity
    from app.models.governance import EthicalAuditLog
    from app.models.embedding_cache import EmbeddingCache
    
    deleted_counts = {}
    
    try:
        # Delete all in correct order
        
        deleted_counts["activities"] = db.query(Activity).delete()
        deleted_counts["document_chunks"] = db.query(DocumentChunk).delete()
        deleted_counts["documents"] = db.query(Document).delete()
        
        models_to_delete = [
            (AuditLog, "audit_logs"),
            (Notification, "notifications"),
            (LeaveRequest, "leave_requests"),
            (LeaveBalance, "leave_balances"),
            (LeavePolicy, "leave_policies"),
            (Job, "jobs"),
            (Resume, "resumes"),
            (Interview, "interviews"),
            (InterviewerAvailability, "interviewer_availability"),
            (Payroll, "payrolls"),
            (PayrollPolicy, "payroll_policies"),
            (SalaryComponent, "salary_components"),
            (OnboardingEmployee, "onboarding_employees"),
            (OnboardingTask, "onboarding_tasks"),
            (OnboardingTemplate, "onboarding_templates"),
            (OnboardingChat, "onboarding_chats"),
            (OnboardingDocument, "onboarding_documents"),
            (OnboardingReminder, "onboarding_reminders"),
            (Ticket, "tickets"),
            (Task, "tasks"),
            (Policy, "policies"),
            (BurnoutAssessment, "burnout_assessments"),
            (WellbeingAssessment, "wellbeing_assessments"),
            (PerformanceReview, "performance_reviews"),
            (PerformanceMetric, "performance_metrics"),
            (EthicalAuditLog, "ethical_audit_logs"),
            (EmbeddingCache, "embedding_cache"),
            (Department, "departments"),
            (Employee, "employees"),
            (User, "users"),
            (Organization, "organizations"),
        ]
        
        for model, name in models_to_delete:
            try:
                count = db.query(model).delete()
                deleted_counts[name] = count
            except Exception as e:
                logger.warning(f"Could not delete {name}: {e}")
        
        db.commit()
        logger.info(f"Successfully reset all data: {deleted_counts}")
        return deleted_counts
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting all data: {str(e)}")
        raise
