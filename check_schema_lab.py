import sqlite3

conn = sqlite3.connect('healthpro.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(lab_requests)")
columns = cursor.fetchall()
for col in columns:
    print(col)
conn.close()
