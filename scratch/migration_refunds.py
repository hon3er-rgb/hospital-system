import sqlite3
import os

db_path = 'HospitalSystem.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = ['lab_requests', 'radiology_requests', 'appointments']
    for table in tables:
        print(f"--- Modifying {table} ---")
        # Check if columns already exist
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cursor.fetchall()]
        
        if 'refund_status' not in cols:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN refund_status TEXT")
                print(f"Added refund_status to {table}")
            except Exception as e:
                print(f"Error adding refund_status to {table}: {e}")
        
        if 'cancelled_at' not in cols:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN cancelled_at DATETIME")
                print(f"Added cancelled_at to {table}")
            except Exception as e:
                print(f"Error adding cancelled_at to {table}: {e}")
        
        # Also ensure status can be set to 'cancelled' (not strictly necessary for ALTER, but good to know)
    
    conn.commit()
    conn.close()
    print("Migration completed.")
else:
    print("DB not found")
