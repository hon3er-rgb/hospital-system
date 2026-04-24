"""
Run once on PostgreSQL if appointments.appointment_date is still DATE.
New installs use TIMESTAMP from schema.sql (no action needed).
SQLite uses flexible typing — no migration required.
"""
from config import get_db


def main():
    db = get_db()
    if not db:
        print("No database connection.")
        return
    if not getattr(db, "is_pg", False):
        print("SQLite: no column migration needed.")
        return
    cur = db.cursor()
    try:
        cur.execute(
            """
            ALTER TABLE appointments
            ALTER COLUMN appointment_date TYPE TIMESTAMP WITHOUT TIME ZONE
            USING appointment_date::timestamp;
            """
        )
        db.commit()
        print("OK: appointment_date is now TIMESTAMP.")
    except Exception as e:
        db.rollback()
        print(f"Skipped or already migrated: {e}")


if __name__ == "__main__":
    main()
