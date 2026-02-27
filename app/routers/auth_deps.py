"""
Enhanced RBAC Dependencies.
Provides role-based and department-level access control for FastAPI endpoints.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Callable
from app.database import get_db
from app.models.user import User, UserRole
from app.models.department import Department
from app.services import auth as auth_service
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Extracts and validates the current user from the JWT token.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    payload = auth_service.decode_access_token(token)
    
    if payload is None:
        logger.warning("Authentication failed: Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if "error" in payload and payload["error"] == "TOKEN_EXPIRED":
        logger.info("Authentication failed: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if payload.get("type") != "access":
        logger.warning("Authentication failed: Invalid token type")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    role: str = payload.get("role")
    if email is None:
        logger.warning("Authentication failed: Missing subject (email) in token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing subject in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = TokenData(email=email, role=role)
    user = db.query(User).filter(User.email == token_data.email).first()
    
    if user is None:
        logger.warning(f"Authentication failed: User {email} not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        logger.warning(f"Authentication failed: User {email} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    return user


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """
    Dependency factory that checks if the user has one of the allowed roles.
    
    Usage:
        @router.get("/admin-only")
        def admin_endpoint(user: User = Depends(require_role([UserRole.HR_ADMIN]))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


def require_role_and_dept(
    allowed_roles: List[UserRole],
    require_same_dept: bool = False
) -> Callable:
    """
    Dependency factory that enforces both role and department-level access.
    
    - HR_ADMIN and SUPER_ADMIN bypass department checks.
    - HR_MANAGER can access only their assigned department.
    - MANAGER can access only their department's employees.
    
    Args:
        allowed_roles: List of roles that can access this endpoint.
        require_same_dept: If True, non-admin users must be in the same department as the resource.
    
    Usage:
        @router.get("/department/{dept_id}/employees")
        def get_dept_employees(
            dept_id: int,
            user: User = Depends(require_role_and_dept([UserRole.HR_ADMIN, UserRole.HR_MANAGER]))
        ):
            ...
    """
    def role_and_dept_checker(current_user: User = Depends(get_current_user)):
        # Check role first
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        
        return current_user
    
    return role_and_dept_checker


def require_org_context(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensures the user has an organization context.
    SUPER_ADMIN can operate without org context for multi-org admin.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return current_user
    
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization"
        )
    return current_user


def check_dept_access(user: User, target_department_id: int, db: Session) -> bool:
    """
    Helper to verify if a user has access to a specific department.
    
    Access rules:
    - SUPER_ADMIN, HR_ADMIN: Access all departments
    - HR_MANAGER: Access only managed department and its children
    - MANAGER: Access only their own department
    - EMPLOYEE: Access only their own department
    """
    if user.role in [UserRole.SUPER_ADMIN, UserRole.HR_ADMIN]:
        return True
    
    if user.department_id == target_department_id:
        return True
    
    # For HR_MANAGER, check if target is a child department
    if user.role == UserRole.HR_MANAGER and user.department_id:
        target_dept = db.query(Department).filter(Department.id == target_department_id).first()
        if target_dept and target_dept.parent_id == user.department_id:
            return True
    
    return False


def check_employee_access(user: User, employee_department_id: int, db: Session):
    """
    Validates that a user can access an employee's data based on department.
    Raises HTTPException if access is denied.
    """
    if not check_dept_access(user, employee_department_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only access employees in your department."
        )


def require_hr():
    """Shorthand for requiring any HR role."""
    return require_role([UserRole.SUPER_ADMIN, UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.HR_STAFF])


def require_manager():
    """Shorthand for requiring any manager role."""
    return require_role([UserRole.SUPER_ADMIN, UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER])


def require_admin():
    """Shorthand for requiring admin roles only."""
    return require_role([UserRole.SUPER_ADMIN, UserRole.HR_ADMIN])


def get_current_org(token: str = Depends(oauth2_scheme)) -> int:
    """
    Extracts and validates the organization ID from the JWT token.
    Fast context without a database hit.
    """
    import logging
    logger = logging.getLogger(__name__)

    payload = auth_service.decode_access_token(token)
    
    if payload is None:
        logger.warning("Org validation failed: Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if "error" in payload and payload["error"] == "TOKEN_EXPIRED":
        logger.info("Org validation failed: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    org_id = payload.get("org_id")
    if org_id is None:
        logger.error(f"Org validation failed: No org_id in token for user {payload.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No organization context in token"
        )
    return int(org_id)


# Alias for backward compatibility
require_any_role = get_current_user
