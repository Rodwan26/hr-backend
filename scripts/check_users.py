import sqlite3
import os

db_path = "database.db"

def check_users():
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Users in DB:")
    cursor.execute("SELECT id, email, role, is_active FROM users")
    users = cursor.fetchall()
    if not users:
        print(" (No users found)")
    for user in users:
        print(f" - ID: {user[0]}, Email: {user[1]}, Role: {user[2]}, Active: {user[3]}")

    conn.close()

if __name__ == "__main__":
    check_users()
