from app.database import SessionLocal
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.models.organization import Organization

def seed():
    db = SessionLocal()
    try:
        # 1. Ensure an organization exists
        org = db.query(Organization).first()
        if not org:
            org = Organization(name="Default Org", slug="default")
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created organization: {org.name}")

        # 2. Check if admin exists
        admin_email = "admin@example.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        
        if not admin:
            hashed_password = auth_service.get_password_hash("123456")
            admin = User(
                email=admin_email,
                hashed_password=hashed_password,
                role=UserRole.HR_ADMIN,
                full_name="Admin User",
                organization_id=org.id,
                is_active=True
            )
            db.add(admin)
            db.commit()
            print(f"Admin user {admin_email} created with password '123456'")
        else:
            # Update password just in case
            admin.hashed_password = auth_service.get_password_hash("123456")
            db.commit()
            print(f"Admin user {admin_email} already exists. Password reset to '123456'")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
