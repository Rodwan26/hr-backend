"""
Backward-compatible re-exports.

The canonical auth dependencies live in app.routers.auth_deps.
This module re-exports them so that existing code importing from
app.dependencies continues to work without changes.
"""
from app.routers.auth_deps import (
    get_current_user,
    require_role,
    require_org_context,
    get_current_org,
    require_hr,
    require_manager,
    require_admin,
    require_any_role,
    check_dept_access,
    check_employee_access,
)
from app.models.user import User, UserRole


def validate_organization_access(user: User, entity_org_id: int | None):
    """
    Ensure user can only access entities within their organization.
    """
    from fastapi import HTTPException, status

    if entity_org_id is None or user.organization_id is None:
        return  # Skip if data is global or system-wide

    if user.organization_id != entity_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Entity belongs to a different organization.",
        )


__all__ = [
    "get_current_user",
    "require_role",
    "require_org_context",
    "require_hr",
    "require_manager",
    "require_admin",
    "require_any_role",
    "validate_organization_access",
    "User",
    "UserRole",
]

