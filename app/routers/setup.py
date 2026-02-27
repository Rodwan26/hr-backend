from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User, UserRole, UserSession
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.services import auth as auth_service
from pydantic import BaseModel, EmailStr
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class InitializeRequest(BaseModel):
    organization_name: str
    admin_name: str
    admin_email: EmailStr
    password: str

@router.get("/status")
def get_setup_status(db: Session = Depends(get_db)):
    """Check if the system is already initialized."""
    initialized = db.query(Organization).first() is not None
    return {"initialized": initialized}

@router.post("/initialize", status_code=status.HTTP_201_CREATED)
def initialize_system(data: InitializeRequest, db: Session = Depends(get_db)):
    """
    Bootstrap the system: Create Org, Admin User, and matched Employee Profile.
    Only runs if no organization exists.
    """
    # 1. Check if already initialized
    if db.query(Organization).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System already initialized. Initialization can only be performed once."
        )

    try:
        # 2. Create Organization
        slug = data.organization_name.lower().replace(" ", "-")
        org = Organization(
            name=data.organization_name,
            slug=slug,
            is_active=True
        )
        db.add(org)
        db.flush() # Get org.id

        # 3. Create Admin User
        hashed_password = auth_service.get_password_hash(data.password)
        user = User(
            email=data.admin_email,
            hashed_password=hashed_password,
            full_name=data.admin_name,
            role=UserRole.HR_ADMIN,
            organization_id=org.id,
            is_active=True
        )
        db.add(user)
        db.flush() # Get user.id

        # 4. Create Employee Profile (CRITICAL: Fixes User vs Employee gap)
        name_parts = data.admin_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        employee = Employee(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            email=data.admin_email,
            position="System Administrator",
            organization_id=org.id
        )
        db.add(employee)
        db.flush() # Get employee.id

        # 5. Create Default Leave Balance
        leave_balance = LeaveBalance(
            employee_id=user.id, 
            leave_type="Annual",
            total_days=30.0,
            remaining_days=30.0,
            year=2026,
            organization_id=org.id
        )
        db.add(leave_balance)

        db.commit()
        logger.info(f"System bootstrap complete for {data.organization_name} (Admin: {data.admin_email})")
        
        return {
            "success": True,
            "message": "System initialized successfully",
            "organization_id": org.id,
            "admin_user_id": user.id,
            "employee_id": employee.id
        }

    except Exception as e:
        db.rollback()
        logger.error(f"System initialization failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization failed: {str(e)}"
        )
