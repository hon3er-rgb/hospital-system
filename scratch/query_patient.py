import sqlite3
import json

def query_db():
    conn = sqlite3.connect('HospitalSystem.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Patient #4 ---")
    cursor.execute("SELECT * FROM patients WHERE patient_id = 4")
    row = cursor.fetchone()
    if row:
        print(dict(row))
    else:
        print("Patient #4 not found")
        
    print("\n--- Lab Requests for Patient #4 ---")
    cursor.execute("SELECT * FROM lab_requests WHERE patient_id = 4")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))
    
    if not rows:
        print("No lab requests found for patient #4")

    conn.close()

if __name__ == "__main__":
    query_db()
