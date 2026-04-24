import sqlite3
from datetime import datetime

def migrate_timestamps():
    conn = sqlite3.connect('HospitalSystem.db')
    cursor = conn.cursor()
    
    # Use current time for the migration
    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    tables = ['lab_requests', 'radiology_requests', 'prescriptions', 'consultations', 'triage', 'referrals', 'patients', 'invoices', 'appointments']
    
    total_updated = 0
    for tbl in tables:
        try:
            cursor.execute(f"UPDATE {tbl} SET created_at = ? WHERE created_at LIKE '%CURRENT%' OR created_at IS NULL OR created_at = ''", (now_ts,))
            total_updated += cursor.rowcount
            print(f"Updated {cursor.rowcount} rows in {tbl}")
        except Exception as e:
            print(f"Error updating {tbl}: {e}")

    # Special case for appointments which has appointment_date too
    try:
        cursor.execute("UPDATE appointments SET appointment_date = ? WHERE appointment_date LIKE '%CURRENT%' OR appointment_date IS NULL OR appointment_date = ''", (now_ts,))
        total_updated += cursor.rowcount
        print(f"Updated {cursor.rowcount} rows in appointments (appointment_date)")
    except Exception: pass

    if total_updated > 0:
        print(f"\nSuccessfully frozen {total_updated} floating timestamps into: {now_ts}")
        conn.commit()
    else:
        print("\nNo floating timestamps found to fix.")
        
    conn.close()

if __name__ == "__main__":
    migrate_timestamps()
