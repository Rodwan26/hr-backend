import logging
import os
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services import auth as auth_service

logger = logging.getLogger(__name__)


def check_system_status():
    """
    Check system initialization status.
    Returns (needs_setup: bool, message: str)
    """
    db = SessionLocal()
    try:
        org_count = db.query(Organization).count()
        
        if org_count == 0:
            return True, "System not initialized. Please run setup."
        
        return False, f"System has {org_count} organization(s)"
    finally:
        db.close()


def init_system_data():
    """
    DEPRECATED: This function is no longer used.
    System setup is now done via POST /api/setup endpoint.
    
    This function only logs a warning to prevent auto-initialization.
    """
    logger.warning(
        "init_system_data() is deprecated. "
        "Use POST /api/setup to initialize the system."
    )
    return
