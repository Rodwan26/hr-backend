import sqlite3
import os

# المسار إلى قاعدة البيانات
db_path = "database.db"

# الهاش المولد مسبقاً لكلمة المرور: AdminPassword123!
pwd_hash = "$2b$12$uSF4NKFEMsPmhy60HfSRzefo5JoGLTrKdsw0NBjzXPu2ZzetiYdji"
admin_email = "admin@radwan.com"

if not os.path.exists(db_path):
    print(f"Error: {db_path} not found!")
    exit(1)

try:
    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()
    
    # البحث عن المستخدمين المطلوبين
    cursor.execute("""
        SELECT email, role FROM users 
        WHERE email = ? OR role IN ('SUPER_ADMIN', 'HR_ADMIN', 'admin')
    """, (admin_email,))
    
    users = cursor.fetchall()
    print(f"Found users: {users}")
    
    if not users:
        print("No admin users found to update.")
    else:
        # تحديث كلمة المرور
        cursor.execute("""
            UPDATE users 
            SET hashed_password = ? 
            WHERE email = ? OR role IN ('SUPER_ADMIN', 'HR_ADMIN', 'admin')
        """, (pwd_hash, admin_email))
        
        conn.commit()
        print(f"Successfully updated {cursor.rowcount} admin user(s)!")
        print(f"New password: AdminPassword123!")

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if 'conn' in locals():
        conn.close()
