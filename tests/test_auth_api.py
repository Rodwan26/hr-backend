import pytest
from fastapi import status
from app.services import auth as auth_service
from app.models.user import User, UserRole
from app.models.organization import Organization

def test_login_success(client, admin_user):
    """Test successful login with valid credentials."""
    # admin_user is already created by fixture
    login_data = {
        "email": admin_user.email,
        "password": "AdminPassword123!"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client):
    """Test login failure with wrong password."""
    response = client.post("/api/auth/login", json={"email": "nonexistent@alphacorp.com", "password": "wrong"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
