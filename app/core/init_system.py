import logging
import os
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services import auth as auth_service

logger = logging.getLogger(__name__)

def init_system_data():
    """
    System initialization on startup.
    Creates default organization and admin user if not exists.
    
    Admin credentials are controlled by environment variables:
    - DEFAULT_ADMIN_EMAIL (optional)
    - DEFAULT_ADMIN_PASSWORD (optional)
    
    Only runs in production or when env vars are set.
    """
    db = SessionLocal()
    try:
        # Check if any organization exists
        org_count = db.query(Organization).count()
        
        if org_count == 0:
            logger.info("Running system initialization...")
            
            # 1. Create Default Organization
            org = Organization(
                name="Alpha Corp",
                slug="alpha-corp",
                is_active=True
            )
            db.add(org)
            db.flush()
            
            # 2. Create Admin User from Environment Variables
            admin_email = os.getenv("DEFAULT_ADMIN_EMAIL")
            admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
            
            if admin_email and admin_password:
                # Check if admin already exists
                existing_admin = db.query(User).filter(User.email == admin_email).first()
                if not existing_admin:
                    hashed_pwd = auth_service.get_password_hash(admin_password)
                    admin_user = User(
                        email=admin_email,
                        hashed_password=hashed_pwd,
                        role=UserRole.HR_ADMIN,
                        organization_id=org.id,
                        is_active=True
                    )
                    db.add(admin_user)
                    logger.info(f"✓ Created default Admin: {admin_email}")
                else:
                    logger.info(f"Admin user {admin_email} already exists")
            else:
                logger.warning("⚠ DEFAULT_ADMIN_EMAIL or DEFAULT_ADMIN_PASSWORD not set. No admin created.")
                logger.warning("  Set these in your environment for production deployment.")
            
            db.commit()
            logger.info("✓ System bootstrapped successfully with Alpha Corp.")
        else:
            logger.info(f"System initialization check: {org_count} organization(s) found.")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error during system initialization check: {str(e)}", exc_info=True)
    finally:
        db.close()
