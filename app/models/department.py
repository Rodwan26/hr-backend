"""
Department Model with Hierarchy Support.
Supports parent-child relationships for organizational structure.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    name = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False, index=True)  # Short code like "ENG", "HR", "FIN"
    description = Column(Text, nullable=True)
    
    # Hierarchy support: parent department for nested structures
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    
    # Department manager (user who manages this department)
    manager_user_id = Column(Integer, ForeignKey("users.id", use_alter=True, name="fk_department_manager_id"), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="departments")
    parent = relationship("Department", remote_side=[id], back_populates="children")
    children = relationship("Department", back_populates="parent")
    manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_department")
    employees = relationship("User", foreign_keys="User.department_id", back_populates="department_rel")
    onboarding_templates = relationship("OnboardingTemplate", back_populates="department")
    
    def __repr__(self):
        return f"<Department {self.code}: {self.name}>"
    
    @property
    def full_path(self) -> str:
        """Returns the full hierarchical path of the department."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name
