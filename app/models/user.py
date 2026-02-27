"""
User Model with Enhanced RBAC.
Supports organization and department context.
"""
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    """
    User roles with hierarchical permissions.
    
    Hierarchy (most to least permissions):
    - SUPER_ADMIN: Platform-wide access (multi-org management)
    - HR_ADMIN: Full HR access within organization
    - HR_MANAGER: Department-level HR access
    - MANAGER: Team manager (approvals, reviews for direct reports)
    - EMPLOYEE: Self-service access
    - CANDIDATE: External applicant (limited access)
    """
    SUPER_ADMIN = "SUPER_ADMIN"
    HR_ADMIN = "HR_ADMIN"
    HR_MANAGER = "HR_MANAGER"
    HR_STAFF = "HR_STAFF"  # Kept for backward compatibility
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"
    CANDIDATE = "CANDIDATE"
    CLIENT = "CLIENT"  # Kept for backward compatibility


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)  # Added for display purposes
    
    role = Column(Enum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    
    # Legacy department field (string) - kept for backward compatibility
    department = Column(String, nullable=True)
    
    # New department relationship (foreign key to departments table)
    department_id = Column(Integer, ForeignKey("departments.id", use_alter=True, name="fk_user_department_id"), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Organization context
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    employee_profile = relationship("Employee", back_populates="user", uselist=False, cascade="all, delete-orphan")
    department_rel = relationship("Department", foreign_keys=[department_id], back_populates="employees")
    managed_department = relationship("Department", foreign_keys="Department.manager_user_id", back_populates="manager")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    # Leave Workflow
    leave_requests = relationship("LeaveRequest", foreign_keys="[LeaveRequest.employee_id]", back_populates="employee", cascade="all, delete-orphan")
    leave_balances = relationship("LeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"
    
    @property
    def is_hr(self) -> bool:
        """Check if user has any HR role."""
        return self.role in [UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.HR_STAFF]
    
    @property
    def is_manager(self) -> bool:
        """Check if user is a manager (any level)."""
        return self.role in [UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER]
    
    @property
    def can_approve(self) -> bool:
        """Check if user can approve requests (leave, expenses, etc.)."""
        return self.role in [UserRole.HR_ADMIN, UserRole.HR_MANAGER, UserRole.MANAGER]


class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    refresh_token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_revoked = Column(Boolean, default=False, nullable=False)
    
    # Session metadata
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    user = relationship("User", back_populates="sessions")
