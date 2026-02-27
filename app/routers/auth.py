from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging
from app.database import get_db
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services.audit import AuditService
from app.schemas.auth import LoginRequest, Token, UserResponse, TokenData, UserUpdate, PasswordChange
from typing import List, Optional

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    # Note: Using JSON LoginRequest instead of form-data for frontend compatibility
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not auth_service.verify_password(login_data.password, user.hashed_password):
        # Log failed login
        AuditService.log(
            db,
            action="failed_login",
            entity_type="user",
            entity_id=None,
            user_id=None,
            user_role=None,
            details={"email": login_data.email, "reason": "invalid_credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        if not user.is_active:
            raise HTTPException(status_code=400, detail="User is inactive")
        
        # Get employee_id for token context
        from app.models.employee import Employee
        employee = db.query(Employee).filter(Employee.user_id == user.id).first()
        employee_id = employee.id if employee else None

        token_data = {
            "sub": user.email, 
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "user_id": user.id,
            "org_id": user.organization_id,
            "employee_id": employee_id
        }
        
        access_token = auth_service.create_access_token(data=token_data)
        refresh_token = auth_service.create_refresh_token(data={"sub": user.email})
        
        # Store session
        from app.models.user import UserSession
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=auth_service.REFRESH_TOKEN_EXPIRE_DAYS)
        session = UserSession(
            user_id=user.id,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        
        # Log successful login
        AuditService.log(
            db,
            action="login",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            user_role=user.role,
            details={"email": user.email},
            organization_id=user.organization_id
        )
        
        return {
            "access_token": access_token, 
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "employee_id": employee_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        # Catch DB or other unexpected errors
        db.rollback()
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal login error. Please check server logs."
        )

@router.post("/refresh", response_model=Token)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    from app.models.user import UserSession
    
    payload = auth_service.decode_access_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    email = payload.get("sub")
    db_session = db.query(UserSession).filter(
        UserSession.refresh_token == refresh_token,
        UserSession.is_revoked == False,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not db_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")
    
    user = db_session.user
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    
    # Rotation: Revoke old, create new
    db_session.is_revoked = True
    
    # Get context for new token
    from app.models.employee import Employee
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    employee_id = employee.id if employee else None

    token_data = {
        "sub": user.email, 
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "user_id": user.id,
        "org_id": user.organization_id,
        "employee_id": employee_id
    }
    
    new_access_token = auth_service.create_access_token(data=token_data)
    new_refresh_token = auth_service.create_refresh_token(data={"sub": user.email})
    
    new_expires_at = datetime.now(timezone.utc) + timedelta(days=auth_service.REFRESH_TOKEN_EXPIRE_DAYS)
    new_session = UserSession(
        user_id=user.id,
        refresh_token=new_refresh_token,
        expires_at=new_expires_at
    )
    db.add(new_session)
    db.commit()
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(refresh_token: str, db: Session = Depends(get_db)):
    from app.models.user import UserSession
    db_session = db.query(UserSession).filter(UserSession.refresh_token == refresh_token).first()
    if db_session:
        db_session.is_revoked = True
        db.commit()
    return {"message": "Successfully logged out"}

from app.routers.auth_deps import get_current_user

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    user_data = UserResponse.from_orm(current_user)
    user_data.employee_id = current_user.employee_profile.id if current_user.employee_profile else None
    return user_data

@router.patch("/profile", response_model=UserResponse)
def update_profile(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile information."""
    if update_data.email:
        # Check if email is already taken by another user
        existing_user = db.query(User).filter(User.email == update_data.email).first()
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = update_data.email
    
    if update_data.department:
        current_user.department = update_data.department
        
    if update_data.full_name:
        current_user.full_name = update_data.full_name
        
    db.commit()
    db.refresh(current_user)
    
    # Log the update
    AuditService.log(
        db,
        action="update_profile",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"email": current_user.email}
    )
    
    user_data = UserResponse.from_orm(current_user)
    user_data.employee_id = current_user.employee_profile.id if current_user.employee_profile else None
    return user_data

@router.post("/change-password")
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Securely update current user's password."""
    if not auth_service.verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    current_user.hashed_password = auth_service.get_password_hash(data.new_password)
    db.commit()
    
    # Log the update
    AuditService.log(
        db,
        action="change_password",
        entity_type="user",
        entity_id=current_user.id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"status": "success"}
    )
    
    return {"success": True, "message": "Password updated successfully"}
