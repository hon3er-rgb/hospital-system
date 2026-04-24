from config import get_db
conn = get_db()
cursor = conn.cursor()
cursor.execute("DESCRIBE lab_tests")
print("LAB_TESTS COLUMNS:")
for c in cursor.fetchall():
    print(c)
cursor.execute("DESCRIBE radiology_tests")
print("\nRADIOLOGY_TESTS COLUMNS:")
for c in cursor.fetchall():
    print(c)
conn.close()
