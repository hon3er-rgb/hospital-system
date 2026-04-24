
import sqlite3
conn = sqlite3.connect('HospitalSystem.db')
cursor = conn.cursor()
cursor.execute("UPDATE patients SET full_name_en = 'Ali Hussain Ali' WHERE patient_id = 2450014")
conn.commit()
conn.close()
print("Updated patient 2450014 name to Ali Hussain Ali")
