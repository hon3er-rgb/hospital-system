from config import get_db

def update_schema():
    conn = get_db()
    if not conn:
        print("Failed to connect to DB")
        return
    
    cursor = conn.cursor()
    columns = [
        ('phone', 'VARCHAR(20)'),
        ('gender', 'VARCHAR(10)'),
        ('national_id', 'VARCHAR(20)'),
        ('employee_no', 'VARCHAR(20)')
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except Exception as e:
            print(f"Column {col_name} already exists or error: {e}")
            
    conn.commit()
    conn.close()
    print("Update complete")

if __name__ == "__main__":
    update_schema()
