from app.services.base import BaseService
from app.models.audit_log import AuditLog
from typing import Any, Optional

class AuditService(BaseService):
    def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        user_id: Optional[int],
        user_role: Optional[str],
        details: dict,
        ai_recommended: bool = False,
        organization_id: Optional[int] = None,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None
    ):
        """
        Create a centralized audit log entry.
        Strictly append-only.
        SAFE: Uses a separate/nested transaction strategy if needed, but for now relies on main DB session.
        TODO: For high criticality, consider a background task or separate DB connection to ensure logs persist even if main tx fails.
        For Phase 3 simple requirement: we commit to the current session.
        """
        try:
            # Ensure serialization of nested Pydantic models in details/states
            def sanitize(obj):
                if hasattr(obj, "model_dump"):
                    return obj.model_dump()
                if isinstance(obj, dict):
                    return {k: sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [sanitize(i) for i in obj]
                return obj

            db_log = AuditLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                user_role=user_role,
                details=sanitize(details),
                ai_recommended=ai_recommended,
                organization_id=organization_id or self.org_id,
                before_state=sanitize(before_state),
                after_state=sanitize(after_state)
            )
            self.db.add(db_log)
            # We do NOT commit here to allow atomic transactions with the main action. 
            # If the main action fails, we might logically want to roll back the "success" log.
            # However, for "attempted" actions that fail, we should log effectively.
            # Best practice: The Service should be called *after* a successful commit or in a `finally` block for attempts.
            # But to ensure IDs are generated, flushing is good.
            self.db.flush()
            return db_log
        except Exception as e:
            self._logger.error(f"FAILED TO AUDIT LOG: {e}", exc_info=True)
            pass # Never break the main app flow because of a logging failure

    def log_operational_event(self, event_type: str, status: str, details: dict, organization_id: Optional[int] = None):
        """
        Specialized logger for operational/compliance events.
        """
        return self.log_action(
            action=f"ops_{event_type}",
            entity_type="system",
            entity_id=None,
            user_id=None,
            user_role="system",
            details={**details, "ops_status": status},
            organization_id=organization_id
        )

    def flag_ethical_issue(self, domain: str, request_id: str, issue_type: str, details: dict, organization_id: Optional[int] = None):
        """
        Flag a high-risk AI decision or potential bias issue.
        """
        self.log_warning(f"Ethical issue flagged: {issue_type} in {domain} (Req: {request_id})")
        return self.log_action(
            action="ethical_violation_flagged",
            entity_type="ai_governance",
            entity_id=None,
            user_id=None,
            user_role="ai_system",
            details={
                "issue_type": issue_type,
                "request_id": request_id,
                "domain": domain,
                **details
            },
            organization_id=organization_id
        )

    # Static wrapper for backward compatibility
    @staticmethod
    def log(db, *args, **kwargs):
        service = AuditService(db)
        return service.log_action(*args, **kwargs)
