"""
System Admin Router
Provides endpoints for SUPER_ADMIN to manage the entire platform.
Only accessible by users with SUPER_ADMIN role.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services.database_service import reset_organization_data
from app.routers.auth_deps import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/system", tags=["System Administration"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class OrganizationSummary(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    users_count: int
    employees_count: int

    class Config:
        from_attributes = True


class UserSummary(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    organization_id: Optional[int]
    organization_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SystemStatus(BaseModel):
    total_organizations: int
    total_users: int
    total_active_users: int
    total_inactive_users: int
    system_admin_email: str


class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_id: int


# =============================================================================
# Dependencies
# =============================================================================

def require_super_admin(current_user: User = Depends(get_current_user)):
    """Dependency to ensure user is a SUPER_ADMIN."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint requires SUPER_ADMIN privileges."
        )
    return current_user


# =============================================================================
# System Status Endpoints
# =============================================================================

@router.get("/status", response_model=SystemStatus)
def get_system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get overall system status and statistics.
    Only accessible by SUPER_ADMIN.
    """
    total_orgs = db.query(Organization).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = total_users - active_users
    
    # Get system admin email
    system_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    
    return SystemStatus(
        total_organizations=total_orgs,
        total_users=total_users,
        total_active_users=active_users,
        total_inactive_users=inactive_users,
        system_admin_email=system_admin.email if system_admin else "N/A"
    )


# =============================================================================
# Organization Management Endpoints
# =============================================================================

@router.get("/organizations", response_model=List[OrganizationSummary])
def get_all_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get all organizations with user and employee counts.
    Only accessible by SUPER_ADMIN.
    """
    organizations = db.query(Organization).order_by(Organization.created_at.desc()).all()
    
    result = []
    for org in organizations:
        users_count = db.query(User).filter(User.organization_id == org.id).count()
        
        # Get employee count (from employees table)
        from app.models.employee import Employee
        employees_count = db.query(Employee).filter(Employee.organization_id == org.id).count()
        
        result.append(OrganizationSummary(
            id=org.id,
            name=org.name,
            slug=org.slug,
            is_active=org.is_active,
            created_at=org.created_at,
            users_count=users_count,
            employees_count=employees_count
        ))
    
    return result


@router.delete("/organizations/{org_id}", response_model=DeleteResponse)
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete an organization and all its related data.
    WARNING: This will permanently delete all data for this organization.
    Only accessible by SUPER_ADMIN.
    """
    # Check if organization exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with ID {org_id} not found."
        )
    
    org_name = org.name
    
    try:
        # Reset organization data
        reset_organization_data(db, org_id)
        
        return DeleteResponse(
            success=True,
            message=f"Organization '{org_name}' and all its data have been deleted.",
            deleted_id=org_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete organization: {str(e)}"
        )


# =============================================================================
# User Management Endpoints
# =============================================================================

@router.get("/users", response_model=List[UserSummary])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
    role_filter: Optional[str] = None,
    org_filter: Optional[int] = None
):
    """
    Get all users with their organization information.
    Only accessible by SUPER_ADMIN.
    """
    query = db.query(User).order_by(User.created_at.desc())
    
    # Apply filters
    if role_filter:
        try:
            role_enum = UserRole(role_filter)
            query = query.filter(User.role == role_enum)
        except ValueError:
            pass
    
    if org_filter is not None:
        query = query.filter(User.organization_id == org_filter)
    
    users = query.all()
    
    result = []
    for user in users:
        org_name = None
        if user.organization_id:
            org = db.query(Organization).filter(Organization.id == user.organization_id).first()
            org_name = org.name if org else None
        
        result.append(UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            organization_id=user.organization_id,
            organization_name=org_name,
            is_active=user.is_active,
            created_at=user.created_at
        ))
    
    return result


@router.delete("/users/{user_id}", response_model=DeleteResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete a user account.
    Cannot delete other SUPER_ADMIN users.
    Only accessible by SUPER_ADMIN.
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    # Cannot delete other SUPER_ADMIN users
    if user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete SUPER_ADMIN users. This action is not allowed."
        )
    
    # Cannot delete yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account."
        )
    
    user_email = user.email
    user_org = user.organization_id
    
    try:
        db.delete(user)
        db.commit()
        
        return DeleteResponse(
            success=True,
            message=f"User '{user_email}' has been deleted.",
            deleted_id=user_id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.patch("/users/{user_id}/deactivate", response_model=UserSummary)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Deactivate a user account (soft delete).
    Only accessible by SUPER_ADMIN.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    if user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate SUPER_ADMIN users."
        )
    
    user.is_active = False
    db.commit()
    db.refresh(user)
    
    org_name = None
    if user.organization_id:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        org_name = org.name if org else None
    
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        organization_id=user.organization_id,
        organization_name=org_name,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.patch("/users/{user_id}/activate", response_model=UserSummary)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Activate a user account.
    Only accessible by SUPER_ADMIN.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    user.is_active = True
    db.commit()
    db.refresh(user)
    
    org_name = None
    if user.organization_id:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        org_name = org.name if org else None
    
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        organization_id=user.organization_id,
        organization_name=org_name,
        is_active=user.is_active,
        created_at=user.created_at
    )
