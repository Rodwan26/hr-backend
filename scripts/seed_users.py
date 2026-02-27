from app.database import SessionLocal
from app.models.user import User, UserRole
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()

def create_user(email, password, role):
    # Check if user already exists to avoid unique constraint errors
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"User {email} already exists. Skipping.")
        return

    user = User(
        email=email,
        hashed_password=pwd_context.hash(password),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"Created {role} -> {email}")

# Employee
create_user(
    "employee@example.com",
    "Employee123!",
    UserRole.EMPLOYEE
)

# Manager
create_user(
    "manager@example.com",
    "Manager123!",
    UserRole.MANAGER
)
