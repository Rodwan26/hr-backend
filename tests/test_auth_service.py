import pytest
from app.services import auth as auth_service
from app.models.user import User, UserRole

def test_password_hashing():
    """Test that password hashing and verification works correctly."""
    password = "MySecurePassword123!"
    hashed = auth_service.get_password_hash(password)
    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("WrongPassword", hashed)

def test_create_user(db_session):
    """Test creating a new user through the service."""
    email = "newuser@example.com"
    password = "Password123!"
    hashed_pwd = auth_service.get_password_hash(password)
    
    # Check if create_user exists or we need to use direct model creation
    # Based on init_system, direct creation is used: 
    # user = User(email=email, hashed_password=hashed_pwd, role=UserRole.EMPLOYEE)
    
    user = User(
        email=email,
        hashed_password=hashed_pwd,
        role=UserRole.EMPLOYEE,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    saved_user = db_session.query(User).filter(User.email == email).first()
    assert saved_user is not None
    assert saved_user.email == email
    assert auth_service.verify_password(password, saved_user.hashed_password)
