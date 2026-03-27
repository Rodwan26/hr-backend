import logging
import os
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services import auth as auth_service

logger = logging.getLogger(__name__)


# System Admin Configuration
SYSTEM_ADMIN_EMAIL = os.getenv("SYSTEM_ADMIN_EMAIL", "radwan@company.com")
SYSTEM_ADMIN_PASSWORD = os.getenv("SYSTEM_ADMIN_PASSWORD", "12345678")


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


def ensure_system_admin():
    """
    Ensures the system admin user exists.
    Creates the system admin if it doesn't exist.
    
    This function should be called on application startup.
    The system admin is a special user with SUPER_ADMIN role
    who can manage all organizations and users across the platform.
    """
    db = SessionLocal()
    try:
        # Check if system admin already exists
        existing_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        
        if existing_admin:
            logger.info(f"System admin already exists: {existing_admin.email}")
            return existing_admin
        
        # Create system admin user (no organization - system-wide admin)
        hashed_password = auth_service.get_password_hash(SYSTEM_ADMIN_PASSWORD)
        system_admin = User(
            email=SYSTEM_ADMIN_EMAIL,
            hashed_password=hashed_password,
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            organization_id=None,  # System-wide admin, not tied to any organization
            is_active=True
        )
        db.add(system_admin)
        db.commit()
        db.refresh(system_admin)
        
        logger.info(f"✓ System admin created: {SYSTEM_ADMIN_EMAIL}")
        logger.info(f"  Role: SUPER_ADMIN")
        logger.info(f"  Password: {SYSTEM_ADMIN_PASSWORD}")
        
        return system_admin
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create system admin: {str(e)}")
        raise
    finally:
        db.close()


def init_system_data():
    """
    Initialize system data on application startup.
    
    - Ensures the system admin user exists (SUPER_ADMIN role)
    - This admin can manage all organizations and users
    """
    ensure_system_admin()
    return
