import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
import os
from flask import session, g # type: ignore
from datetime import datetime, date
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None  # type: ignore


def get_app_timezone():
    """IANA zone for local business time (override with APP_TIMEZONE env)."""
    if ZoneInfo is None:
        return None
    tz_name = os.getenv('APP_TIMEZONE', 'Asia/Baghdad')
    try:
        return ZoneInfo(tz_name)
    except Exception:
        try:
            return ZoneInfo('UTC')
        except Exception:
            return None


def local_now():
    """Current date/time in the configured local timezone (naive if tz unavailable)."""
    tz = get_app_timezone()
    if tz is not None:
        return datetime.now(tz)
    return datetime.now()


def local_today_str():
    """Today's calendar date in local timezone as YYYY-MM-DD."""
    return local_now().strftime('%Y-%m-%d')


def local_now_naive():
    """Wall-clock local time as naive datetime (for DB fields & comparisons)."""
    n = local_now()
    if getattr(n, 'tzinfo', None) is not None:
        return n.replace(tzinfo=None)
    return n


def format_datetime(value, fmt='%Y-%m-%d %H:%M:%S', date_fmt='%Y-%m-%d'):
    """
    Safe display for DB/templating: datetime, date, or ISO string.
    Hides invalid literals like CURRENT_DATETIME left in old rows.
    """
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, date):
        return value.strftime(date_fmt)
    s = str(value).strip()
    if not s:
        return ''
    if 'CURRENT' in s.upper():
        return ''
    s = s.replace('T', ' ')
    if len(s) >= 16 and s[4] == '-' and s[7] == '-':
        return s[:16] if '%H' in fmt or '%I' in fmt else s[:10]
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10]
    return s


def sanitize_sql_params(params):
    """
    Prevent SQL keyword placeholders from being stored as literal strings
    (e.g. 'CURRENT_DATETIME' in a TIMESTAMP column). Applied to all bound parameters.
    """
    if params is None:
        return None
    if isinstance(params, (list, tuple)):
        return type(params)(sanitize_sql_params(p) for p in params)
    if isinstance(params, str):
        u = params.strip().upper()
        if u in ('CURRENT_DATETIME', 'CURRENT_TIMESTAMP', 'CURRENT_DATE', 'CURRENT_TIME'):
            return local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        return params
    return params


# ── Database Connection Settings (PostgreSQL) ──────────────────────────────
PG_HOST     = os.getenv('PGHOST',     'localhost')
PG_PORT     = os.getenv('PGPORT',     '5432')
PG_DB       = os.getenv('PGDATABASE', 'healthpro')
PG_USER     = os.getenv('PGUSER',     'postgres')
PG_PASSWORD = os.getenv('PGPASSWORD', 'postgres')

# ── Fallback SQLite Path (for local development only) ─────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'HospitalSystem.db')

# ── PostgreSQL availability cache ─────────────────────────────────────────
# Checked once at startup; avoids 3-second timeout on every request
_PG_AVAILABLE = None

def _check_pg_available():
    global _PG_AVAILABLE
    if _PG_AVAILABLE is not None:
        return _PG_AVAILABLE
        
    # One-time data correction for SQLite if we are in fallback mode
    # This freezes "Floating" timestamps like CURRENT_DATETIME into fixed strings.
    if not os.getenv('PGHOST') and os.path.exists(DB_PATH):
        try:
            _run_freeze_migration()
        except Exception as e:
            print(f"[Migration] Error: {e}")

    try:
        c = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            database=PG_DB, user=PG_USER,
            password=PG_PASSWORD, connect_timeout=2
        )
        c.close()
        _PG_AVAILABLE = True
    except Exception:
        _PG_AVAILABLE = False
    return _PG_AVAILABLE


def _run_freeze_migration():
    """Find and fix records where timestamp was stored as a literal string 'CURRENT_DATETIME'."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    now_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. Invoices
    cursor.execute("UPDATE invoices SET created_at = ? WHERE created_at LIKE '%CURRENT%' OR created_at IS NULL OR created_at = ''", (now_ts,))
    
    # 2. Appointments
    cursor.execute("UPDATE appointments SET created_at = ? WHERE created_at LIKE '%CURRENT%' OR created_at IS NULL OR created_at = ''", (now_ts,))
    cursor.execute("UPDATE appointments SET appointment_date = ? WHERE appointment_date LIKE '%CURRENT%' OR appointment_date IS NULL OR appointment_date = ''", (now_ts,))

    # 3. Clinical Tables (Lab, Rad, Rx, Consult, Triage, Patients)
    for tbl in ['lab_requests', 'radiology_requests', 'prescriptions', 'consultations', 'triage', 'referrals', 'patients']:
        try:
            cursor.execute(f"UPDATE {tbl} SET created_at = ? WHERE created_at LIKE '%CURRENT%' OR created_at IS NULL OR created_at = ''", (now_ts,))
        except Exception: pass


    
    if cursor.rowcount > 0:
        print(f"[Migration] Frozen {cursor.rowcount} floating timestamps into fixed value: {now_ts}")
        conn.commit()
    
    # --- 4. intelligent Free Follow-up Column ---
    try:
        cursor.execute("PRAGMA table_info(appointments)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'is_free_followup' not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN is_free_followup INTEGER DEFAULT 0")
            print("[Migration] Added missing column 'is_free_followup' to appointments table")
            conn.commit()
    except Exception as e:
        print(f"[Migration] Warning (is_free_followup): {e}")

    conn.close()



# ══════════════════════════════════════════════════════════════════════════
#  Cursor Wrappers
# ══════════════════════════════════════════════════════════════════════════

class PostgresCursor:
    def __init__(self, cursor, dictionary=False):
        self.cursor     = cursor
        self.dictionary = dictionary
        self.lastrowid  = None

    def execute(self, query, params=None):
        query = query.replace('?', '%s')
        query = re.sub(r'NOW\(\)', 'CURRENT_TIMESTAMP', query, flags=re.I)
        query = query.replace("date('now')", 'CURRENT_DATE')
        query = query.replace('CURRENT_DATETIME', 'CURRENT_TIMESTAMP')
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, sanitize_sql_params(params))
        try:
            if "RETURNING" in query.upper():
                self.lastrowid = self.cursor.fetchone()[0]
        except Exception:
            pass

    def _clean_row(self, row):
        if not row or not self.dictionary:
            return row
        d = dict(row)
        import datetime as _dt
        for k, v in list(d.items()):
            # REMOVED: Dynamic masking of CURRENT_DATETIME. 
            # We now allow the corrupt string to reach the application so it can be fixed permanently.
            if isinstance(v, str) and len(v) >= 10:

                v_clean = v.split('+')[0].split('Z')[0].strip()
                parsed = None
                if '-' in v_clean and ':' in v_clean:
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                        try:
                            parsed = _dt.datetime.strptime(v_clean, fmt)
                            break
                        except ValueError:
                            continue
                elif '-' in v_clean and len(v_clean) == 10:
                    try:
                        parsed = _dt.datetime.strptime(v_clean, '%Y-%m-%d')
                    except ValueError:
                        pass
                if parsed:
                    d[k] = parsed
        return d

    def fetchone(self):
        row = self.cursor.fetchone()
        return self._clean_row(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._clean_row(r) for r in rows]
    def close(self):     self.cursor.close()

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class SQLiteCursor:
    _CURDATE_RE = re.compile(r"CURDATE\(\)", re.I)
    _NOW_RE     = re.compile(r"NOW\(\)",     re.I)

    def __init__(self, cursor, dictionary=False):
        self.cursor     = cursor
        self.dictionary = dictionary
        self.lastrowid  = None

    def execute(self, query, params=None):
        query = query.replace('%s', '?')
        query = self._NOW_RE.sub('CURRENT_TIMESTAMP', query)
        query = self._CURDATE_RE.sub("date('now')", query)
        query = query.replace('CURRENT_DATETIME', 'CURRENT_TIMESTAMP')
        # MySQL date arithmetic  → SQLite
        query = query.replace("INTERVAL 1 DAY", "'+1 day'")
        query = query.replace("YEARWEEK(appointment_date, 1) = YEARWEEK(CURDATE(), 1)",
                              "strftime('%Y-%W', appointment_date) = strftime('%Y-%W', date('now'))")
        query = query.replace("MONTH(appointment_date) = MONTH(CURDATE()) AND YEAR(appointment_date) = YEAR(CURDATE())",
                              "strftime('%Y-%m', appointment_date) = strftime('%Y-%m', date('now'))")
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, sanitize_sql_params(params))
        self.lastrowid = self.cursor.lastrowid

    def _clean_row(self, row):
        if not row or not self.dictionary:
            return row
        d = dict(row)
        import datetime
        for k, v in d.items():
            # REMOVED: Dynamic masking of CURRENT_DATETIME. 
            # We now allow the corrupt string to reach the application so it can be fixed permanently in the DB.
            if isinstance(v, str) and len(v) >= 10:

                # Try common ISO-ish formats
                parsed = None
                # Clean up string: remove trailing Z or +00:00 often found in ISO strings
                v_clean = v.split('+')[0].split('Z')[0].strip()
                
                if '-' in v_clean and ':' in v_clean:
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                        try:
                            parsed = datetime.datetime.strptime(v_clean, fmt)
                            break
                        except ValueError:
                            continue
                elif '-' in v_clean and len(v_clean) == 10:
                    try:
                        parsed = datetime.datetime.strptime(v_clean, '%Y-%m-%d')
                    except ValueError:
                        pass
                if parsed:
                    d[k] = parsed
        return d

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def fetchone(self):
        row = self.cursor.fetchone()
        return self._clean_row(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._clean_row(r) for r in rows]

    def close(self):
        self.cursor.close()


# ══════════════════════════════════════════════════════════════════════════
#  DB Wrapper
# ══════════════════════════════════════════════════════════════════════════

class DBWrapper:
    def __init__(self, conn, is_pg=False):
        self.conn  = conn
        self.is_pg = is_pg
        if not is_pg:
            self.conn.row_factory = sqlite3.Row

    def cursor(self, dictionary=False):
        if self.is_pg:
            factory = RealDictCursor if dictionary else None
            return PostgresCursor(self.conn.cursor(cursor_factory=factory), dictionary)
        return SQLiteCursor(self.conn.cursor(), dictionary)

    def commit(self):  self.conn.commit()
    def close(self):   self.conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════

def get_db():
    """Return a DB connection.  Tries blueprint g-cache first, then connects."""
    # ── 1. Return already-opened connection for this request ──────────────
    try:
        db = getattr(g, '_db', None)
        if db is not None:
            return db
    except RuntimeError:
        pass  # outside app context (e.g. init_db.py)

    # ── 2. Try PostgreSQL if known to be available ─────────────────────────
    if _check_pg_available():
        try:
            conn    = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, database=PG_DB,
                user=PG_USER, password=PG_PASSWORD, connect_timeout=2
            )
            wrapper = DBWrapper(conn, is_pg=True)
            _store_g(wrapper)
            return wrapper
        except Exception:
            pass  # fall through to SQLite
    # ── 3. SQLite fallback ─────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60.0)
        # WAL mode: allows concurrent reads without locking
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-1000000")   # 1 GB RAM cache
        conn.execute("PRAGMA mmap_size=2000000000")  # 2 GB Memory Map
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=60000")
        wrapper = DBWrapper(conn, is_pg=False)
        _store_g(wrapper)
        return wrapper
    except Exception as e:
        print(f"[DB] Connection error: {e}")
        return None


def _store_g(wrapper):
    """Store wrapper in Flask g so the same connection is reused per request."""
    try:
        g._db = wrapper
    except RuntimeError:
        pass  # outside app context – fine


def log_activity(user_id, action, details=None):
    """Log user activity to the database."""
    db = get_db()
    if not db:
        return
    try:
        cur = db.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute(
            "INSERT INTO activity_logs (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
        db.commit()
        cur.close()
    except Exception as e:
        print(f"Logging error: {e}")


def trigger_auto_backup():
    """Trigger backup if enabled in settings."""
    db = get_db()
    if not db: return
    try:
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'backup_paths'")
        row = cur.fetchone()
        if not row or not row['setting_value']:
            return
            
        import shutil
        paths = row['setting_value'].split(',')
        source = DB_PATH
        
        for path in paths:
            path = path.strip()
            if not path: continue
            try:
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                filename = f"Backup_Hospital_{local_now().strftime('%Y%m%d_%H%M%S')}.db"
                dest = os.path.join(path, filename)
                shutil.copy2(source, dest)
                
                # Keep requested number of backups from system_settings
                cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'backup_limit'")
                limit_row = cur.fetchone()
                limit = int(limit_row['setting_value']) if limit_row and limit_row['setting_value'] else 5
                
                backups = sorted([f for f in os.listdir(path) if f.startswith("Backup_Hospital_")])
                while len(backups) > limit:
                    os.remove(os.path.join(path, backups.pop(0)))
            except Exception as e:
                print(f"Backup failed for path {path}: {e}")
        cur.close()
    except Exception as e:
        print(f"Auto-backup trigger error: {e}")


def update_last_activity(user_id):
    """Update last_activity at most once every 60 s per user (non-blocking)."""
    import time
    cache_key = f'_lact_{user_id}'
    now = time.time()
    try:
        last = getattr(g, cache_key, 0)
        if now - last < 60:          # throttle: max once per minute
            return
        setattr(g, cache_key, now)
    except RuntimeError:
        pass

    db = get_db()
    if not db:
        return
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET last_activity = %s WHERE user_id = %s",
            (local_now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
        )
        db.commit()
        cur.close()
    except Exception:
        pass


def can_access(permission_needed):
    if not session or 'user_id' not in session:
        return False
    role = session.get('role', '')
    if role == 'admin':
        return True
    user_perms = session.get('permissions', [])
    if permission_needed in user_perms:
        return True
    role_map = {
        'registration': ['receptionist', 'reception'],
        'triage':       ['nurse'],
        'doctor':       ['doctor'],
        'lab':          ['lab_tech', 'lab'],
        'radiology':    ['radiologist', 'rad'],
        'pharmacy':     ['pharmacist', 'pharmacy'],
        'invoices':     ['accountant'],
        'settings':     [],
        'nursing':      ['nurse', 'lab_tech', 'lab'],
    }
    if permission_needed in role_map and role in role_map[permission_needed]:
        return True
    return False


def get_system_entropy():
    """Returns a combined hash of the latest IDs across all critical tables to detect any change in milliseconds."""
    db = get_db()
    if not db: return 0
    try:
        cur = db.cursor()
        # High speed query over primary keys
        cur.execute("""
            SELECT 
                (SELECT COALESCE(MAX(invoice_id), 0) FROM invoices) +
                (SELECT COALESCE(MAX(appointment_id), 0) FROM appointments) +
                (SELECT COALESCE(MAX(request_id), 0) FROM lab_requests) +
                (SELECT COALESCE(MAX(request_id), 0) FROM radiology_requests) +
                (SELECT COALESCE(MAX(id), 0) FROM chat_messages) +
                (SELECT COUNT(*) FROM user_presence WHERE last_seen >= datetime('now', '-30 seconds'))
        """)

        res = cur.fetchone()
        cur.close()
        return res[0] if res else 0
    except Exception:
        return 0

