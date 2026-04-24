import os
import sqlite3
from werkzeug.security import generate_password_hash
from config import get_db

def init_db():
    db = get_db()
    if not db:
        print("Failed to initialize database connection.")
        return

    cursor = db.cursor()
    
    # Read schema
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()

    # Adapt schema for SQLite if falling back
    if not db.is_pg:
        schema = schema.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
        schema = schema.replace('DOUBLE PRECISION', 'REAL')
        # Use regex to replace TIMESTAMP only when it's a type name, not inside CURRENT_TIMESTAMP
        import re
        schema = re.sub(r'\bTIMESTAMP\b', 'DATETIME', schema)

    # Remove SQL Comments
    import re
    schema_clean = re.sub(r'--.*', '', schema)

    # Execute Schema
    for statement in schema_clean.split(';'):
        stmt = statement.strip()
        if stmt:
            if stmt.upper().startswith('USE '): continue
            if stmt.upper().startswith('CREATE DATABASE'): continue
            
            try:
                cursor.execute(stmt)
            except Exception as e:
                print(f"Schema Execution Warn: {e}\nStatement: {stmt[:50]}...")

    # Initialize System Settings
    cursor.execute("SELECT COUNT(*) FROM system_settings")
    if cursor.fetchone()[0] == 0:
        settings = [
            ('currency_label', 'د.ع'),
            ('hospital_name', 'HealthPro Intelligence'),
            ('system_icon', 'fas fa-hand-holding-medical'),
            ('price_consultation', '25000'),
            ('price_lab_default', '15000'),
            ('price_rad_default', '30000'),
            ('price_rx_default', '5000')
        ]
        
        # PostgreSQL handles multiple inserts differently if using execute, but executemany loop is safer across both
        if db.is_pg:
            for k, v in settings:
                cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES (%s, %s)", (k, v))
        else:
            for k, v in settings:
                cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES (?, ?)", (k, v))
        print("Initialized system settings")

    # Initialize Lab Tests
    cursor.execute("SELECT COUNT(*) FROM lab_tests")
    if cursor.fetchone()[0] == 0:
        labs = [
            ('الصورة الدموية الكاملة (CBC)', 15000, 'cells/uL', None, None, 0),
            ('السكر الصائم (FBS)', 10000, 'mg/dL', 70, 110, 0),
            ('بروفايل الدهون الشامل (Lipid)', 35000, None, None, None, 1),
            ('وظائف الكلى (RFT)', 20000, None, None, None, 1),
            ('فحص فيروس كورونا (PCR)', 50000, 'copies', None, None, 0)
        ]
        
        # Execute insert
        for lab in labs:
            if db.is_pg:
                cursor.execute("INSERT INTO lab_tests (test_name, price, unit, min_value, max_value, is_profile) VALUES (%s, %s, %s, %s, %s, %s)", lab)
            else:
                cursor.execute("INSERT INTO lab_tests (test_name, price, unit, min_value, max_value, is_profile) VALUES (?, ?, ?, ?, ?, ?)", lab)
        
        db.commit()
        
        # Lipid Profile parameters
        if db.is_pg:
            cursor.execute("SELECT test_id FROM lab_tests WHERE test_name = 'بروفايل الدهون الشامل (Lipid)'")
        else:
            cursor.execute("SELECT test_id FROM lab_tests WHERE test_name = 'بروفايل الدهون الشامل (Lipid)'")
            
        res = cursor.fetchone()
        if res:
            # Depending on RealDictCursor or tuple
            lipid_id = res['test_id'] if type(res) == dict else res[0]
            params = [
                (lipid_id, 'S. Cholesterol', 150, 200, 'mg/dL'),
                (lipid_id, 'S. Triglycerides', 100, 150, 'mg/dL'),
                (lipid_id, 'S. HDL', 40, 60, 'mg/dL')
            ]
            for p in params:
                if db.is_pg:
                    cursor.execute("INSERT INTO lab_test_parameters (test_id, param_name, min_value, max_value, unit) VALUES (%s, %s, %s, %s, %s)", p)
                else:
                    cursor.execute("INSERT INTO lab_test_parameters (test_id, param_name, min_value, max_value, unit) VALUES (?, ?, ?, ?, ?)", p)
            print("Initialized dummy lab tests & parameters")

    # Initialize Radiology
    cursor.execute("SELECT COUNT(*) FROM radiology_tests")
    if cursor.fetchone()[0] == 0:
        rads = [
            ('أشعة صدر (X-Ray Chest)', 15000),
            ('سونار بطن وأحشاء (U/S Abdomen)', 25000),
            ('سونار حمل (U/S Obstetrics)', 20000),
            ('مفراس دماغ (CT Brain)', 60000),
            ('رنين مغناطيسي للفقرات (MRI Spine)', 120000)
        ]
        for r in rads:
            if db.is_pg:
                cursor.execute("INSERT INTO radiology_tests (test_name, price) VALUES (%s, %s)", r)
            else:
                cursor.execute("INSERT INTO radiology_tests (test_name, price) VALUES (?, ?)", r)
        print("Initialized dummy radiology tests")

    # Check Admin
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pass = generate_password_hash('admin')
        admin_data = ('admin', hashed_pass, 'admin@healthpro.com', 'مدير النظام', 'admin', 1, '["admin"]')
        if db.is_pg:
            cursor.execute("""
                INSERT INTO users (username, password_hash, email, full_name_ar, role, is_active, permissions)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, admin_data)
        else:
            cursor.execute("""
                INSERT INTO users (username, password_hash, email, full_name_ar, role, is_active, permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, admin_data)
        print("Created default admin user (admin/admin)")

    # Check Departments
    cursor.execute("SELECT COUNT(*) FROM departments")
    if cursor.fetchone()[0] == 0:
        depts = [
            ('الاستقبال', 'Reception', 'administrative'),
            ('العيادة العامة', 'General Clinic', 'medical'),
            ('المختبر', 'Laboratory', 'support'),
            ('الأشعة', 'Radiology', 'support'),
            ('الصيدلية', 'Pharmacy', 'support')
        ]
        for d in depts:
            if db.is_pg:
                cursor.execute("INSERT INTO departments (department_name_ar, department_name_en, department_type) VALUES (%s, %s, %s)", d)
            else:
                cursor.execute("INSERT INTO departments (department_name_ar, department_name_en, department_type) VALUES (?, ?, ?)", d)
        print("Initialized default departments")

    # After creating tables, add indexes for faster queries
    index_statements = [
        # Appointments: fast lookup by date and status
        "CREATE INDEX IF NOT EXISTS idx_appointments_date_status ON appointments (appointment_date, status)",
        # Patients: search fields
        "CREATE INDEX IF NOT EXISTS idx_patients_search ON patients (full_name_ar, file_number, national_id)",
        # Lab requests, radiology requests, prescriptions, invoices, appointments foreign keys
        "CREATE INDEX IF NOT EXISTS idx_lab_requests_patient ON lab_requests (patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_radiology_requests_patient ON radiology_requests (patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions (patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices (patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments (patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments (doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_department ON appointments (department_id)"
    ]
    for idx_sql in index_statements:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            print(f"Index creation warning: {e}")
    # Commit indexes
    db.commit()
    db.close()

    if db.is_pg:
        print("PostgreSQL Database Initialization Complete!")
    else:
        print("SQLite Database Initialization Complete (Fallback Mode)!")

