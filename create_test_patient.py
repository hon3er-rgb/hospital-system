
import sqlite3
from datetime import datetime, date

DB_PATH = 'HospitalSystem.db'

def create_test_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Ensure tables are created (just in case)
    # The schema should already be there but if not, this would error.
    # We assume schema.sql has been run.

    # 2. Add a test patient
    patient_name = "فاطمة عادل طلال"
    file_number = "TEST-2026-001"
    dob = "1981-04-06"
    gender = "أنثى"
    phone = "07830004266"
    address = "ذي قار - الناصرية"
    
    cursor.execute("INSERT OR REPLACE INTO patients (file_number, full_name_ar, date_of_birth, gender, phone1, address, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (file_number, patient_name, dob, gender, phone, address, 'VIP'))
    patient_id = cursor.lastrowid
    if not patient_id:
        cursor.execute("SELECT patient_id FROM patients WHERE file_number = ?", (file_number,))
        patient_id = cursor.fetchone()[0]

    # 3. Add a test doctor if none exists
    cursor.execute("SELECT user_id FROM users LIMIT 1")
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (username, password_hash, email, full_name_ar, full_name_en, role) VALUES (?, ?, ?, ?, ?, ?)",
                       ('admin', 'pbkdf2:sha256:260000$xyz', 'admin@thiqarld.com', 'أحمد يوسف', 'Ahmed Yousif', 'admin'))
        doctor_id = cursor.lastrowid
    else:
        doctor_id = user[0]

    # 4. Add a department
    cursor.execute("SELECT department_id FROM departments LIMIT 1")
    dept = cursor.fetchone()
    if not dept:
        cursor.execute("INSERT INTO departments (department_name_ar, department_name_en, department_type) VALUES (?, ?, ?)",
                       ('العيادة التنفسية', 'Respiratory Clinic', 'medical'))
        dept_id = cursor.lastrowid
    else:
        dept_id = dept[0]

    # 5. Create an appointment
    visit_date = date.today().strftime('%Y-%m-%d')
    cursor.execute("INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status) VALUES (?, ?, ?, ?, ?)",
                   (patient_id, doctor_id, dept_id, visit_date, 'completed'))
    appt_id = cursor.lastrowid

    # 6. Create Triage (Vitals)
    cursor.execute("INSERT INTO triage (appointment_id, weight, height, temperature, blood_pressure, pulse, oxygen, nurse_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (appt_id, '75', '168', '37.2', '121/89', 88, '98', 'Patient stable, routine follow-up.'))

    # 7. Create Consultation (The Report)
    subjective = "Cough, sputum fever for 5 days. Chest X ray right lower zone infiltration. She received ceftriaxone once."
    objective = "Lung US revealed mild right side pleural effusion. Patient refuses hospital admission."
    assessment = "Pneumonia / ذات الرئة"
    plan = "cefpodoxime 200 mg (cefpodoxime 200 mg) /-\nLEVOFLOXACIN 500 MG TA(NEXQUIN 500mg)/-\nparacetamol tab(paracetamol tab)/-\nbutamirate citrate syrup(sinecod syrup)/-"
    
    cursor.execute("INSERT INTO consultations (patient_id, doctor_id, appointment_id, subjective, objective, assessment, plan) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (patient_id, doctor_id, appt_id, subjective, objective, assessment, plan))

    conn.commit()
    conn.close()
    
    print(f"Test data created successfully!")
    print(f"Patient Name: {patient_name}")
    print(f"Patient ID: {patient_id}")
    print(f"Appointment ID: {appt_id}")
    print(f"Link: /medical_report?id={patient_id}&appointment_id={appt_id}")

if __name__ == '__main__':
    create_test_data()
