
from config import get_db
import datetime

conn = get_db()
if not conn:
    print("No connection")
    exit()

cursor = conn.cursor(dictionary=True)
sql = """
    SELECT a.*, p.full_name_ar as p_name 
    FROM appointments a 
    JOIN patients p ON a.patient_id = p.patient_id 
    WHERE a.status = 'waiting_doctor'
"""
cursor.execute(sql)
rows = cursor.fetchall()
print(f"Found {len(rows)} waiting patients")
for r in rows:
    print(f"Patient: {r['p_name']}, created_at: {r['created_at']} (type: {type(r['created_at'])})")

conn.close()
