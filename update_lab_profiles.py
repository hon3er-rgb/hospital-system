from config import get_db
conn = get_db()
cursor = conn.cursor()
try:
    # Add is_profile to lab_tests
    cursor.execute("ALTER TABLE lab_tests ADD COLUMN is_profile BOOLEAN DEFAULT FALSE")
    
    # Create lab_test_parameters table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_test_parameters (
        param_id INT AUTO_INCREMENT PRIMARY KEY,
        test_id INT NOT NULL,
        param_name VARCHAR(100) NOT NULL,
        min_value FLOAT,
        max_value FLOAT,
        unit VARCHAR(50),
        sort_order INT DEFAULT 0,
        FOREIGN KEY (test_id) REFERENCES lab_tests(test_id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    print("Database updated for Profiles.")
except Exception as e:
    print(f"Update info: {e}")
conn.close()
