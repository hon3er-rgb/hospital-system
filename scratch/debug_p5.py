from config import get_db
import json

def check_patient(pid):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    print(f"--- Records for Patient #{pid} ---")
    cursor.execute("SELECT * FROM lab_requests WHERE patient_id = %s", (pid,))
    rows = cursor.fetchall()
    for r in rows:
        print(f"ID: {r['request_id']}, Test: {r['test_type']}, Status: {r['status']}, Result: {r['result']}, Created: {r['created_at']}")
    
    conn.close()

if __name__ == "__main__":
    check_patient(5)
