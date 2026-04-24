import sqlite3
import os

db_path = 'HospitalSystem.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE users ADD COLUMN photo TEXT")
    conn.commit()
    print("Column 'photo' added successfully to users table.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column 'photo' already exists.")
    else:
        print(f"Error: {e}")

try:
    # Also ensure user_presence and call_signaling are perfect
    cur.execute("CREATE TABLE IF NOT EXISTS user_presence (user_id INTEGER PRIMARY KEY, last_seen DATETIME)")
    cur.execute("CREATE TABLE IF NOT EXISTS call_signaling (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, receiver_id INTEGER, signal_type TEXT, signal_data TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    print("Signaling tables verified.")
except Exception as e:
    print(f"Error during table creation: {e}")

conn.close()
