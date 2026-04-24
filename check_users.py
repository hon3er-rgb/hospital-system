import sys
import os
# Ensure current directory is in path
sys.path.append(os.getcwd())
from config import get_db
import json

def check():
    conn = get_db()
    if not conn:
        print("Could not connect to database")
        return
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT username, role, full_name_ar FROM users")
        users = cursor.fetchall()
        print(json.dumps(users, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check()
