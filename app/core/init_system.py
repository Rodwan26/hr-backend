import logging
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services import auth as auth_service

logger = logging.getLogger(__name__)

def init_system_data():
    """
    Checks if the system needs initialization.
    If no organization exists, creates a default one and an admin user.
    """
    return # disable auto bootstrap during development
    db = SessionLocal()
    try:
        # Check if any organization exists
        org_count = db.query(Organization).count()
        if org_count == 0:
            logger.info("Running startup initialization...")
            
            # 1. Create Default Organization
            org = Organization(
                name="Alpha Corp",
                slug="alpha-corp",
                is_active=True
            )
            db.add(org)
            db.flush() # Get org ID
            
            # 2. Create Default HR Admin
            admin_email = "admin@alphacorp.com"
            admin_pwd = "AdminPassword123!"
            
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            if not existing_admin:
                hashed_pwd = auth_service.get_password_hash(admin_pwd)
                admin_user = User(
                    email=admin_email,
                    hashed_password=hashed_pwd,
                    role=UserRole.HR_ADMIN,
                    organization_id=org.id,
                    is_active=True
                )
                db.add(admin_user)
                logger.info(f"✓ Created default Admin: {admin_email} (password set from code — change immediately)")
            
            db.commit()
            logger.info("✓ System bootstrapped successfully with Alpha Corp.")
        else:
            logger.info(f"System initialization check: {org_count} organization(s) found.")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error during system initialization check: {str(e)}", exc_info=True)
    finally:
        db.close()
