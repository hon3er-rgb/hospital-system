import sqlite3
import os

db_path = 'HospitalSystem.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = ['lab_requests', 'radiology_requests', 'appointments', 'invoices', 'system_settings']
    for table in tables:
        print(f"--- {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            for col in cursor.fetchall():
                print(col)
        except Exception as e:
            print(f"Error reading {table}: {e}")
    
    conn.close()
else:
    print("DB not found")
