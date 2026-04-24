
import sqlite3
import os

db_path = 'HospitalSystem.db'
if not os.path.exists(db_path):
    print("DB not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for table in tables:
    tname = table[0]
    print(f"\n--- Schema for {tname} ---")
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{tname}'")
    print(cursor.fetchone()[0])

conn.close()
