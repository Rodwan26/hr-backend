import sqlite3
import os

db_path = "database.db"

def check_db():
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Tables in DB:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f" - {table[0]}")
        cursor.execute(f"PRAGMA table_info({table[0]})")
        cols = cursor.fetchall()
        for col in cols:
            print(f"   * {col[1]} ({col[2]})")

    conn.close()

if __name__ == "__main__":
    check_db()
