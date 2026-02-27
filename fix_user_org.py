from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization

def fix_admin_org():
    db: Session = SessionLocal()
    try:
        # 1. Check/Create Organization
        org = db.query(Organization).first()
        if not org:
            print("No organization found. Creating default organization...")
            org = Organization(name="Default Corp", domain="example.com")
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created organization: {org.name} (ID: {org.id})")
        else:
            print(f"Found existing organization: {org.name} (ID: {org.id})")
            
        # 2. Assign Admin to Organization
        # Assuming admin email is admin@example.com based on previous context
        admin_email = "admin@radwan.com" 
        user = db.query(User).filter(User.email == admin_email).first()
        
        if user:
            print(f"Found user: {user.email}, Role: {user.role}, Org ID: {user.organization_id}")
            if user.organization_id is None:
                print(f"Assigning user {user.email} to organization {org.id}...")
                user.organization_id = org.id
                db.commit()
                print("Assignment complete.")
            else:
                print("User already assigned to an organization.")
        else:
            print(f"User {admin_email} not found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_admin_org()
