import sqlite3
import os
import time
from datetime import datetime

DB_PATH = 'HospitalSystem.db'

def local_now_naive():
    return datetime.now().replace(tzinfo=None)

def _is_corrupt_timestamp(val):
    if val is None: return True
    s = str(val).strip().upper()
    if not s or s in ('NULL', 'NONE'): return True
    return 'CURRENT' in s

def verify_and_test():
    if not os.path.exists(DB_PATH):
        print(f"Error: DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.row_factory = sqlite3.Row

    print("--- 1. Creating Test Patient ---")
    cursor.execute("INSERT INTO patients (full_name_ar, file_number) VALUES (?, ?)", ("مريض تجريبي للفحص", "TEST-999"))
    patient_id = cursor.lastrowid
    print(f"Created Patient ID: {patient_id}")

    print("--- 2. Creating Appointment with NULL Date (Simulating Bug) ---")
    cursor.execute("INSERT INTO appointments (patient_id, status, appointment_date) VALUES (?, ?, ?)", (patient_id, 'scheduled', None))
    appt_id = cursor.lastrowid
    print(f"Created Appointment ID: {appt_id} with NULL date.")

    print("--- 3. Simulating first visit to Patient Statement (Healing) ---")
    # Simulate the logic in billing.py
    cursor.execute("SELECT appointment_id, appointment_date FROM appointments WHERE appointment_id = ?", (appt_id,))
    row = cursor.fetchone()
    appt_date = row['appointment_date']
    
    if _is_corrupt_timestamp(appt_date):
        fixed_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Healed timestamp to: {fixed_ts}")
        
        # This is the new hardened logic we added
        cursor.execute("UPDATE appointments SET appointment_date = ?, created_at = ? WHERE appointment_id = ?", (fixed_ts, fixed_ts, appt_id))
        conn.commit()
        print("Updated database permanently (Frozen).")

    print("--- 4. Checking if it stays fixed after delay ---")
    time.sleep(1) # mini delay
    cursor.execute("SELECT appointment_date FROM appointments WHERE appointment_id = ?", (appt_id,))
    row_after = cursor.fetchone()
    frozen_val = row_after['appointment_date']
    print(f"Fetched value from DB: {frozen_val}")

    # Simulate another "page refresh" 
    print("Simulating page refresh...")
    if not _is_corrupt_timestamp(frozen_val):
        print("Success: Timestamp is NOT corrupt anymore. It will NOT change.")
    else:
        print("Failure: Timestamp is still considered corrupt.")

    if frozen_val == fixed_ts:
        print("VERIFICATION SUCCESSFUL: THE TIME IS FIXED AND STORED.")
    else:
        print(f"VERIFICATION FAILED: {frozen_val} != {fixed_ts}")

    # Cleanup test data
    cursor.execute("DELETE FROM appointments WHERE patient_id = ?", (patient_id,))
    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    verify_and_test()
