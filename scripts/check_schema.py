import sqlite3
import os

DB_FILE = "database.db"  # Found in directory listing

def check_schema():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found.")
        # Check if it's in a subdirectory or named differently
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    tables = ["users", "onboarding_employees", "organizations", "jobs"]
    
    print(f"--- Checking Schema for {DB_FILE} ---")
    
    for table in tables:
        print(f"\nTable: {table}")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            if not columns:
                print("  Table not found or empty.")
                continue
                
            # cid, name, type, notnull, dflt_value, pk
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
                
        except Exception as e:
            print(f"  Error inspecting table: {e}")
            
    conn.close()

if __name__ == "__main__":
    check_schema()
