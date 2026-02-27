from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.governance import EthicalAuditLog
import logging

logger = logging.getLogger(__name__)

class ComplianceService:
    @staticmethod
    def enforce_data_retention(db: Session, retention_days: int = 365):
        """
        Purge records older than retention_days.
        Default is 1 year (365 days).
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        try:
            # Purge Audit Logs
            audit_deleted = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
            
            # Purge Ethical Logs
            ethical_deleted = db.query(EthicalAuditLog).filter(EthicalAuditLog.timestamp < cutoff_date).delete()
            
            db.commit()
            
            logger.info(f"Data retention enforced. Purged {audit_deleted} audit logs and {ethical_deleted} ethical logs older than {cutoff_date}.")
            return {
                "audit_logs_purged": audit_deleted,
                "ethical_logs_purged": ethical_deleted,
                "cutoff_date": cutoff_date.isoformat()
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to enforce data retention: {e}")
            raise e
