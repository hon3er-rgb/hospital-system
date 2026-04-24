import sqlite3

def verify():
    conn = sqlite3.connect('HospitalSystem.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    patient_id = 4
    
    # Simulate print_lab logic
    print("Finding latest date...")
    cursor.execute("""
        SELECT DATE(created_at) as last_date 
        FROM lab_requests 
        WHERE patient_id = ? AND result IS NOT NULL 
        ORDER BY created_at DESC LIMIT 1;
    """, (patient_id,))
    row = cursor.fetchone()
    
    if row and row['last_date']:
        print_date = str(row['last_date'])
        print(f"Latest date found: {print_date}")
        
        print(f"Fetching labs for {print_date}...")
        cursor.execute("""
            SELECT lr.*
            FROM lab_requests lr
            WHERE lr.patient_id = ? 
              AND (DATE(lr.created_at) = ? OR lr.created_at LIKE ? || '%')
              AND lr.result IS NOT NULL
        """, (patient_id, print_date, print_date))
        labs = cursor.fetchall()
        print(f"Found {len(labs)} lab results.")
        for l in labs:
            print(f"- Request {l['request_id']}: {l['test_type']} = {l['result']} ({l['created_at']})")
    else:
        print("No date found.")

    conn.close()

if __name__ == "__main__":
    verify()
