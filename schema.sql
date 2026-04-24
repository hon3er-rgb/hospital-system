-- PostgreSQL Schema for HealthPro

-- --- 1. Departments ---
CREATE TABLE IF NOT EXISTS departments (
    department_id SERIAL PRIMARY KEY,
    department_name_ar VARCHAR(100) NOT NULL,
    department_name_en VARCHAR(100),
    department_type VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- --- 2. Users ---
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name_ar VARCHAR(100) NOT NULL,
    full_name_en VARCHAR(100),
    role VARCHAR(50) NOT NULL,
    department_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    permissions TEXT DEFAULT '[]',
    last_activity TIMESTAMP,
    current_task VARCHAR(255),
    active_patient_name VARCHAR(255),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- --- 3. Patients ---
CREATE TABLE IF NOT EXISTS patients (
    patient_id SERIAL PRIMARY KEY,
    file_number VARCHAR(50) UNIQUE NOT NULL,
    national_id VARCHAR(20) UNIQUE,
    full_name_ar VARCHAR(100) NOT NULL,
    full_name_en VARCHAR(100),
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20) NOT NULL,
    phone1 VARCHAR(20) NOT NULL,
    address VARCHAR(255),
    photo VARCHAR(255),
    blood_group VARCHAR(10),
    category VARCHAR(50) DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- --- 4. Appointments ---
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id SERIAL PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    department_id INT NOT NULL,
    appointment_date TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    is_free INT DEFAULT 0,
    is_urgent INT DEFAULT 0,
    call_status INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES users(user_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- --- 5. Invoices (Billing) ---
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id SERIAL PRIMARY KEY,
    appointment_id INT,
    patient_id INT,
    amount DOUBLE PRECISION NOT NULL,
    status VARCHAR(50) DEFAULT 'unpaid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- --- 6. Triage ---
CREATE TABLE IF NOT EXISTS triage (
    triage_id SERIAL PRIMARY KEY,
    appointment_id INT,
    weight VARCHAR(50),
    height VARCHAR(50),
    temperature VARCHAR(50),
    blood_pressure VARCHAR(20),
    pulse INT,
    oxygen VARCHAR(20),
    nurse_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

-- --- 7. Consultations ---
CREATE TABLE IF NOT EXISTS consultations (
    consultation_id SERIAL PRIMARY KEY,
    patient_id INT,
    doctor_id INT,
    appointment_id INT,
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES users(user_id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

-- --- 8. Laboratory ---
CREATE TABLE IF NOT EXISTS lab_requests (
    request_id SERIAL PRIMARY KEY,
    appointment_id INT,
    patient_id INT,
    doctor_id INT,
    test_type VARCHAR(100) NOT NULL,
    result TEXT,
    price DOUBLE PRECISION DEFAULT 50.0,
    status VARCHAR(50) DEFAULT 'pending_payment',
    estimated_time_minutes INT DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES users(user_id)
);

-- --- 9. Radiology ---
CREATE TABLE IF NOT EXISTS radiology_requests (
    request_id SERIAL PRIMARY KEY,
    appointment_id INT,
    patient_id INT,
    doctor_id INT,
    scan_type VARCHAR(100) NOT NULL,
    report TEXT,
    image_path VARCHAR(255),
    price DOUBLE PRECISION DEFAULT 100.0,
    status VARCHAR(50) DEFAULT 'pending_payment',
    estimated_time_minutes INT DEFAULT 45,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES users(user_id)
);

-- --- 10. Pharmacy & Medicines ---
CREATE TABLE IF NOT EXISTS medicines (
    medicine_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DOUBLE PRECISION DEFAULT 0.0,
    stock_quantity INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id SERIAL PRIMARY KEY,
    appointment_id INT,
    patient_id INT,
    doctor_id INT,
    medicine_name TEXT,
    dosage VARCHAR(100),
    duration VARCHAR(100),
    price DOUBLE PRECISION DEFAULT 30.0,
    status VARCHAR(50) DEFAULT 'pending_payment',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES users(user_id)
);

-- --- 11. Referrals ---
CREATE TABLE IF NOT EXISTS referrals (
    referral_id SERIAL PRIMARY KEY,
    appointment_id INT,
    patient_id INT,
    from_doctor_id INT,
    to_department_id INT,
    reason TEXT,
    priority VARCHAR(50) DEFAULT 'normal',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (from_doctor_id) REFERENCES users(user_id),
    FOREIGN KEY (to_department_id) REFERENCES departments(department_id)
);

-- --- 12. Lab Maintenance ---
CREATE TABLE IF NOT EXISTS lab_tests (
    test_id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    unit VARCHAR(100),
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    is_profile INT DEFAULT 0,
    is_active INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS radiology_tests (
    test_id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    is_active INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lab_test_parameters (
    param_id SERIAL PRIMARY KEY,
    test_id INT NOT NULL,
    param_name VARCHAR(255) NOT NULL,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    unit VARCHAR(100),
    sort_order INT DEFAULT 0,
    FOREIGN KEY (test_id) REFERENCES lab_tests(test_id)
);

-- --- 13. System Settings ---
CREATE TABLE IF NOT EXISTS system_settings (
    setting_id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT
);

-- --- 14. Global Counters ---
CREATE TABLE IF NOT EXISTS global_counters (
    counter_name VARCHAR(50) PRIMARY KEY,
    val INT DEFAULT 0
);
