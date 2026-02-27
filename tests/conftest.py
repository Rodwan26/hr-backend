import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set env before importing app components
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient

# SQLite in-memory database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once for the whole test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Get a clean database session for each test function with rollback safety."""
    connection = engine.connect()
    transaction = connection.begin()
    # Use sessionmaker with the active connection
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def org(db_session):
    """Create a default organization for tests."""
    from app.models.organization import Organization
    import uuid
    org = Organization(name=f"Alpha Corp {uuid.uuid4()}", slug=f"alpha-corp-{uuid.uuid4()}")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture(scope="function")
def admin_user(db_session, org):
    """Create a default HR Admin user for tests."""
    from app.models.user import User, UserRole
    from app.services import auth as auth_service
    
    user = User(
        email="admin@alphacorp.com",
        hashed_password=auth_service.get_password_hash("AdminPassword123!"),
        role=UserRole.HR_ADMIN,
        organization_id=org.id,
        is_active=True,
        full_name="System Admin"
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture(scope="function")
def get_token():
    """Helper fixture to create access tokens with org_id."""
    from app.services.auth import create_access_token
    
    def _get_token(user, org_id):
        return create_access_token(data={
            "sub": user.email,
            "role": user.role.value,
            "org_id": org_id,
            "type": "access"
        })
    return _get_token

@pytest.fixture(scope="function")
def client(db_session):
    """Get a TestClient that uses the test database session via dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
