import sys
import os
import logging
from sqlalchemy.orm import Session

# Ensure we can import app modules
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.services.auth import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def create_admin_user():
    db: Session = SessionLocal()
    try:
        email = "admin@example.com"
        password = "Admin123!"
        
        # Check if admin already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            logger.warning(f"Admin user '{email}' already exists.")
            return

        # Create new admin user
        hashed_password = get_password_hash(password)
        admin_user = User(
            email=email,
            hashed_password=hashed_password,
            full_name="System Administrator",
            role=UserRole.HR_ADMIN, # Using HR_ADMIN as primary admin role
            is_active=True,
            department="HR", # Legacy field
            # department_id - Optional, letting it be null or handled later
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.info("Admin user created successfully. You can now login.")
        logger.info(f"Email: {email}")
        logger.info(f"Password: {password}")
        
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
