import sqlite3

def check_logic():
    conn = sqlite3.connect('HospitalSystem.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    patient_id = 4
    
    print("Running query to find last_date...")
    cursor.execute("""
        SELECT DATE(created_at) as last_date 
        FROM lab_requests 
        WHERE patient_id = ? AND result IS NOT NULL 
        ORDER BY created_at DESC LIMIT 1;
    """, (patient_id,))
    row = cursor.fetchone()
    
    if row:
        print(f"Row found. last_date: {row['last_date']} (type: {type(row['last_date'])})")
        print(f"str(row['last_date']): {str(row['last_date'])}")
    else:
        print("No row found.")

    conn.close()

if __name__ == "__main__":
    check_logic()
