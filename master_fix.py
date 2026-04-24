
import sqlite3
import datetime

db_path = 'HospitalSystem.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row['name'] for row in cursor.fetchall()]

now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

for table in tables:
    try:
        # Check if created_at exists in this table
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [c['name'] for c in cursor.fetchall()]
        
        if 'created_at' in columns:
            cursor.execute(f"UPDATE {table} SET created_at = ? WHERE created_at = 'CURRENT_DATETIME'", (now_str,))
            if cursor.rowcount > 0:
                print(f"Fixed {cursor.rowcount} rows in {table}")
    except Exception as e:
        print(f"Error fixing table {table}: {e}")

conn.commit()
conn.close()
print("Master fix complete.")
