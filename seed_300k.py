import sqlite3
import random
import datetime
import time

DB_PATH = 'HospitalSystem.db'

def seed_300k():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF") # Maximum seeding speed, safe for test
    cursor = conn.cursor()
    
    first_names = ["احمد", "محمد", "علي", "حسين", "سجاد", "مصطفى", "مرتضى", "عباس", "كاظم", "جعفر", "سيف", "عمر", "بكر", "ياسين", "طه", "باسم", "حيدر", "كريم", "جاسم", "راضي", "نور", "زينب", "فاطمة", "مريم", "زهراء", "رقية", "سارة", "هدى", "منى", "رنا"]
    last_names = ["الساعدي", "الخزاعي", "الموسوي", "الحسيني", "التميمي", "اللامي", "الكناني", "الزبيدي", "الدراجي", "الفريجي", "الأسدي", "الشيباني", "الجحيشي", "السامرائي", "البغدادي", "الجبوري", "العبيدي", "المحمداوي", "الكعبي", "الخزرجي"]
    
    cities = ["بغداد", "البصرة", "الناصرية", "النجف", "كربلاء", "الموصل", "العمارة", "الديوانية", "الحلة"]
    
    target = 300000
    batch_size = 50000
    total_added = 0
    
    print(f"Starting Ultra Seed: Adding {target} patients (Current total ~2.0M)...")
    start_total = time.time()
    
    for b in range(0, target, batch_size):
        batch_start = time.time()
        patients = []
        current_batch = min(batch_size, target - total_added)
        
        # Absolute Unique Sequence using high-res timestamp
        ts = int(time.time() * 10)
        for i in range(current_batch):
            f = random.choice(first_names)
            m = random.choice(first_names)
            l = random.choice(last_names)
            full_name = f"{f} {m} {l}"
            file_num = f"XP-{ts}{total_added + i}" # Timestamp + Counter = 100% Unique
            phone = f"077{random.randint(10000000, 99999999)}"
            dob = f"{random.randint(1950, 2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
            gender = "ذكر" if random.random() > 0.3 else "أنثى"
            city = random.choice(cities)
            
            patients.append((file_num, full_name, dob, gender, phone, city))
        
        # Batch Insert
        cursor.executemany("""
            INSERT INTO patients (file_number, full_name_ar, date_of_birth, gender, phone1, address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, patients)
        
        conn.commit()
        total_added += current_batch
        print(f"Batch Done: {total_added}/{target} in {time.time()-batch_start:.2f}s")

    # Update Global Counters
    print("Updating Global Counters Registry...")
    cursor.execute("SELECT COUNT(*) FROM patients")
    count = cursor.fetchone()[0]
    cursor.execute("UPDATE global_counters SET val = ? WHERE counter_key = 'total_patients'", (count,))
    
    conn.commit()
    conn.close()
    print(f"Total Seeding Time: {time.time()-start_total:.2f}s for 300,000 patients.")
    print(f"Final Count in registry: {count}")

if __name__ == '__main__':
    seed_300k()
