from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class DepartmentBase(BaseModel):
    """Base schema for department data."""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20, pattern="^[A-Z0-9_]+$")
    description: Optional[str] = None
    parent_id: Optional[int] = None
    manager_user_id: Optional[int] = None


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new department."""
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating a department."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20, pattern="^[A-Z0-9_]+$")
    description: Optional[str] = None
    parent_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    """Schema for department response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Computed fields
    full_path: Optional[str] = None
    employee_count: Optional[int] = None


class DepartmentWithChildren(DepartmentResponse):
    """Schema for department with nested children."""
    model_config = ConfigDict(from_attributes=True)
    
    children: List["DepartmentWithChildren"] = []


class DepartmentTree(BaseModel):
    """Schema for organization's full department tree."""
    organization_id: int
    departments: List[DepartmentWithChildren]


class DepartmentListResponse(BaseModel):
    """Paginated list of departments."""
    items: List[DepartmentResponse]
    total: int
    page: int
    page_size: int


# Update forward references
DepartmentWithChildren.model_rebuild()
