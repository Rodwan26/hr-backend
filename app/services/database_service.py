import logging

logger = logging.getLogger(__name__)


def reset_organization_data(db, organization_id: int):
    """
    Reset all data for a specific organization.
    Deletes all related data while keeping the schema.
    
    Deletion Order (respecting foreign key constraints):
    1. Child tables first (tables referencing users/organizations)
    2. Then parent tables (users, employees)
    3. Finally the organization
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole, UserSession
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.notification import Notification
    from app.models.leave_request import LeaveRequest
    from app.models.leave_balance import LeaveBalance
    from app.models.interview import Interview, InterviewScorecard, InterviewKit
    from app.models.governance import EthicalAuditLog
    from app.models.department import Department
    
    deleted_counts = {}
    
    try:
        # Step 1: Get all user IDs for this organization (excluding SUPER_ADMIN)
        org_user_ids = db.query(User.id).filter(
            User.organization_id == organization_id,
            User.role != UserRole.SUPER_ADMIN
        ).all()
        org_user_id_list = [uid[0] for uid in org_user_ids]
        
        # Step 2: Get all employee IDs for this organization
        org_employee_ids = db.query(Employee.id).filter(
            Employee.organization_id == organization_id
        ).all()
        org_employee_id_list = [eid[0] for eid in org_employee_ids]
        
        # Step 3: Delete user_sessions (references users)
        if org_user_id_list:
            count = db.query(UserSession).filter(
                UserSession.user_id.in_(org_user_id_list)
            ).delete(synchronize_session=False)
            deleted_counts["user_sessions"] = count
        
        # Step 4: Delete notifications (references users, has CASCADE but explicit is better)
        count = db.query(Notification).filter(
            Notification.user_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["notifications"] = count
        
        # Step 5: Delete leave_balances (references users)
        count = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["leave_balances"] = count
        
        # Step 6: Delete leave_requests (references users as employee/approver)
        count = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["leave_requests"] = count
        
        # Step 7: Delete interview scorecards (references users as interviewer)
        count = db.query(InterviewScorecard).filter(
            InterviewScorecard.interviewer_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["interview_scorecards"] = count
        
        # Step 8: Delete interview kits (references interviews)
        count = db.query(InterviewKit).filter(
            InterviewKit.interview_id.in_(
                db.query(Interview.id).filter(
                    (Interview.candidate_id.in_(org_user_id_list)) |
                    (Interview.interviewer_id.in_(org_user_id_list))
                )
            )
        ).delete(synchronize_session=False)
        deleted_counts["interview_kits"] = count
        
        # Step 9: Delete interviews (references users as candidate/interviewer)
        count = db.query(Interview).filter(
            (Interview.candidate_id.in_(org_user_id_list)) |
            (Interview.interviewer_id.in_(org_user_id_list))
        ).delete(synchronize_session=False)
        deleted_counts["interviews"] = count
        
        # Step 10: Delete ethical audit logs (references users as reviewer)
        count = db.query(EthicalAuditLog).filter(
            EthicalAuditLog.reviewer_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["ethical_audit_logs"] = count
        
        # Step 11: Delete audit logs (references users)
        count = db.query(AuditLog).filter(
            AuditLog.user_id.in_(org_user_id_list)
        ).delete(synchronize_session=False)
        deleted_counts["audit_logs"] = count
        
        # Step 12: Delete departments (references users as manager)
        count = db.query(Department).filter(
            Department.organization_id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["departments"] = count
        
        # Step 13: Delete employees (references users)
        count = db.query(Employee).filter(
            Employee.organization_id == organization_id
        ).delete(synchronize_session=False)
        deleted_counts["employees"] = count
        
        # Step 14: Delete users (excluding SUPER_ADMIN)
        count = db.query(User).filter(
            User.organization_id == organization_id,
            User.role != UserRole.SUPER_ADMIN
        ).delete(synchronize_session=False)
        deleted_counts["users"] = count
        
        # Step 14: Delete remaining org-scoped data (models with organization_id)
        from app.models.job import Job
        from app.models.resume import Resume
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
        from app.models.leave_policy import LeavePolicy
        from app.models.payroll import Payroll
        from app.models.payroll_policy import PayrollPolicy
        from app.models.salary_component import SalaryComponent
        from app.models.embedding_cache import EmbeddingCache
        
        org_scoped_models = [
            (Job, "jobs"),
            (Resume, "resumes"),
            (Document, "documents"),
            (DocumentChunk, "document_chunks"),
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
            (LeavePolicy, "leave_policies"),
            (Payroll, "payrolls"),
            (PayrollPolicy, "payroll_policies"),
            (SalaryComponent, "salary_components"),
            (EmbeddingCache, "embedding_cache"),
        ]
        
        for model, name in org_scoped_models:
            try:
                count = db.query(model).filter(
                    model.organization_id == organization_id
                ).delete(synchronize_session=False)
                deleted_counts[name] = count
            except AttributeError:
                pass  # Model doesn't have organization_id
        
        # Step 15: Delete organization
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
    Deletes all organizations and their data.
    """
    from app.models.audit_log import AuditLog
    from app.models.user import User, UserRole, UserSession
    from app.models.employee import Employee
    from app.models.organization import Organization
    from app.models.notification import Notification
    from app.models.department import Department
    from app.models.activity import Activity
    from app.models.embedding_cache import EmbeddingCache
    from app.models.document_chunk import DocumentChunk
    from app.models.document import Document
    
    deleted_counts = {}
    
    try:
        # Delete in correct order: children first
        
        # 1. User sessions (references users)
        count = db.query(UserSession).delete()
        deleted_counts["user_sessions"] = count
        
        # 2. Notifications
        count = db.query(Notification).delete()
        deleted_counts["notifications"] = count
        
        # 3. Audit logs
        count = db.query(AuditLog).delete()
        deleted_counts["audit_logs"] = count
        
        # 4. Activities
        count = db.query(Activity).delete()
        deleted_counts["activities"] = count
        
        # 5. Document chunks
        count = db.query(DocumentChunk).delete()
        deleted_counts["document_chunks"] = count
        
        # 6. Documents
        count = db.query(Document).delete()
        deleted_counts["documents"] = count
        
        # 7. Employees (references users)
        count = db.query(Employee).delete()
        deleted_counts["employees"] = count
        
        # 8. Departments
        count = db.query(Department).delete()
        deleted_counts["departments"] = count
        
        # 9. All users except SUPER_ADMIN
        count = db.query(User).filter(User.role != UserRole.SUPER_ADMIN).delete()
        deleted_counts["users"] = count
        
        # 10. Organizations
        count = db.query(Organization).delete()
        deleted_counts["organizations"] = count
        
        # 11. SUPER_ADMIN remains
        super_admin_count = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).count()
        deleted_counts["super_admins_remaining"] = super_admin_count
        
        db.commit()
        logger.info(f"Successfully reset all data: {deleted_counts}")
        return deleted_counts
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting all data: {str(e)}")
        raise
