import sqlite3
import os

db_path = 'HospitalSystem.db'
if not os.path.exists(db_path):
    print("Database not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fix literal 'CURRENT_DATETIME' or similar in lab_requests
cursor.execute("UPDATE lab_requests SET created_at = '2026-04-03 14:00:00' WHERE created_at LIKE 'CURRENT%' OR created_at IS NULL")
print(f"Fixed {cursor.rowcount} lab_requests dates")

# Also check appointments if they have same issue
cursor.execute("UPDATE appointments SET appointment_date = '2026-04-03' WHERE appointment_date LIKE 'CURRENT%' OR appointment_date IS NULL")
print(f"Fixed {cursor.rowcount} appointments dates")

conn.commit()
conn.close()
