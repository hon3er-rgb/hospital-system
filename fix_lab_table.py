from config import get_db
conn = get_db()
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE lab_tests ADD COLUMN min_value FLOAT DEFAULT NULL")
    cursor.execute("ALTER TABLE lab_tests ADD COLUMN max_value FLOAT DEFAULT NULL")
    cursor.execute("ALTER TABLE lab_tests ADD COLUMN unit VARCHAR(50) DEFAULT NULL")
    conn.commit()
    print("Columns added successfully.")
except Exception as e:
    print(f"Error or columns exist: {e}")
conn.close()
