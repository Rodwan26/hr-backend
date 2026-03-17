from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User, UserRole, UserSession
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.services import auth as auth_service
from app.services.database_service import reset_all_data
from pydantic import BaseModel, EmailStr
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class InitializeRequest(BaseModel):
    organization_name: str
    admin_name: str
    admin_email: EmailStr
    password: str

class SetupStatusResponse(BaseModel):
    organizations_count: int
    can_create_new: bool = True

@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    """
    Get system setup status.
    Returns the number of organizations and whether new organizations can be created.
    This endpoint is always accessible - it does NOT restrict creating new organizations.
    """
    org_count = db.query(Organization).count()
    return SetupStatusResponse(
        organizations_count=org_count,
        can_create_new=True
    )

@router.post("/initialize", status_code=status.HTTP_201_CREATED)
def initialize_system(data: InitializeRequest, db: Session = Depends(get_db)):
    """
    Create a new organization with admin user.
    This is a MULTI-TENANT system - you can create multiple organizations.
    Each organization has its own independent data.
    """
    # Check if email already exists in ANY organization
    existing_user = db.query(User).filter(User.email == data.admin_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please use a different email or login."
        )
    
    # Check if organization name/slug already exists
    slug = data.organization_name.lower().replace(" ", "-")
    existing_org = db.query(Organization).filter(Organization.slug == slug).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An organization with this name already exists. Please choose a different name."
        )

    try:
        # 1. Create Organization
        org = Organization(
            name=data.organization_name,
            slug=slug,
            is_active=True
        )
        db.add(org)
        db.flush()

        # 2. Create Admin User
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
        db.flush()

        # 3. Create Employee Profile
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
        db.flush()

        # 4. Create Default Leave Balance
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
        logger.info(f"Organization '{data.organization_name}' created with admin: {data.admin_email}")
        
        return {
            "success": True,
            "message": f"Organization '{data.organization_name}' created successfully. You can now login.",
            "organization_id": org.id,
            "organization_name": org.name,
            "admin_user_id": user.id,
            "employee_id": employee.id
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Organization creation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create organization: {str(e)}"
        )


@router.delete("/reset", status_code=status.HTTP_200_OK)
def reset_system(db: Session = Depends(get_db)):
    """
    WARNING: This endpoint resets the ENTIRE database.
    Use only for development/testing purposes.
    This will delete ALL organizations and data!
    """
    try:
        deleted_counts = reset_all_data(db)
        return {
            "success": True,
            "message": "System reset successfully. All data has been deleted.",
            "deleted": deleted_counts
        }
    except Exception as e:
        logger.error(f"System reset failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset failed: {str(e)}"
        )
