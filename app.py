import os
import secrets
from config import _check_pg_available, format_datetime, local_now, local_now_naive  # type: ignore
from flask import Flask, session, g, send_from_directory, redirect, url_for, request # type: ignore

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def template_dt(v, fmt='%Y-%m-%d %H:%M'):
    """Shorthand for templates: local date+time, or em dash if missing/invalid."""
    return format_datetime(v, fmt) or '—'


# ── Performance: pre-warm DB availability check at startup ─────────────────
_check_pg_available()

# ── Auto-initialize database for PostgreSQL on Render ────────────────────────
try:
    from config import get_db
    import os
    
    # Check if using PostgreSQL (Render)
    if os.getenv('PGHOST'):
        print("[Startup] PostgreSQL detected, initializing database...")
        import init_db
        init_db.init_db()
        print("[Startup] PostgreSQL database initialized successfully!")
except Exception as e:
    print(f"[Startup] Warning: Could not initialize database: {e}")

# ── Request lifecycle: close DB after each request ────────────────────────
@app.teardown_request
def teardown_request(exception):
    db = getattr(g, '_db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
        g._db = None

    # ── Auto-backup trigger on data changes ──────────────────────────────
    if request.method == 'POST' and not request.path.endswith(('.css', '.js', '.png', '.jpg')):
        try:
            from config import trigger_auto_backup
            trigger_auto_backup()
        except:
            pass

# ── Blueprints ─────────────────────────────────────────────────────────────
from index              import index_bp # type: ignore
from login              import login_bp # type: ignore
from logout             import logout_bp # type: ignore
from dashboard          import dashboard_bp # type: ignore
from patients           import patients_bp # type: ignore
from doctor_clinic      import doctor_clinic_bp # type: ignore
from consultation       import consultation_bp # type: ignore
from pharmacy           import pharmacy_bp # type: ignore
from lab                import lab_bp # type: ignore
from radiology          import radiology_bp # type: ignore
from triage             import triage_bp # type: ignore
from patient_index      import patient_index_bp # type: ignore
from patient_file       import patient_file_bp # type: ignore
from book               import book_bp # type: ignore
from connect            import connect_bp # type: ignore
from archive            import archive_bp # type: ignore
from system_data        import system_data_bp # type: ignore
from manage_staff       import manage_staff_bp # type: ignore
from waiting_list       import waiting_list_bp # type: ignore
from api                import api_bp # type: ignore
from billing            import billing_bp # type: ignore
from reservations       import reservations_bp # type: ignore
from add_patient        import add_patient_bp # type: ignore
from edit_patient       import edit_patient_bp # type: ignore
from settings           import settings_bp # type: ignore
from price_control      import price_control_bp # type: ignore
from print_rx           import print_rx_bp # type: ignore
from registration_settings import registration_settings_bp # type: ignore
from lab_maintenance    import lab_maintenance_bp # type: ignore
from manage_departments import manage_departments_bp # type: ignore
from nursing_lab        import nursing_lab_bp # type: ignore
from programmer_settings import programmer_settings_bp # type: ignore
from medical_report import medical_report_bp
from print_lab import print_lab_bp
from backup_logs import backup_logs_bp
from data_cleanup import data_cleanup_bp
from admin_reports import admin_reports_bp  # type: ignore


app.register_blueprint(index_bp)
app.register_blueprint(medical_report_bp)
app.register_blueprint(print_lab_bp)
app.register_blueprint(login_bp)
app.register_blueprint(logout_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(patients_bp)
app.register_blueprint(doctor_clinic_bp)
app.register_blueprint(consultation_bp)
app.register_blueprint(pharmacy_bp)
app.register_blueprint(lab_bp)
app.register_blueprint(radiology_bp)
app.register_blueprint(triage_bp)
app.register_blueprint(patient_index_bp)
app.register_blueprint(patient_file_bp)
app.register_blueprint(book_bp)
app.register_blueprint(connect_bp)
app.register_blueprint(archive_bp)
app.register_blueprint(system_data_bp)
app.register_blueprint(manage_staff_bp)
app.register_blueprint(waiting_list_bp)
app.register_blueprint(api_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(reservations_bp)
app.register_blueprint(add_patient_bp)
app.register_blueprint(edit_patient_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(price_control_bp)
app.register_blueprint(print_rx_bp)
app.register_blueprint(registration_settings_bp)
app.register_blueprint(lab_maintenance_bp)
app.register_blueprint(manage_departments_bp)
app.register_blueprint(nursing_lab_bp)
app.register_blueprint(programmer_settings_bp)
app.register_blueprint(backup_logs_bp)
app.register_blueprint(data_cleanup_bp)
app.register_blueprint(admin_reports_bp)
# ── Static uploads ─────────────────────────────────────────────────────────
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Ensure filename doesn't start with leading slash from DB string
    clean_filename = filename.lstrip('/').replace('uploads/', '', 1)
    
    # Try multiple base search paths to ensure absolute reliability
    search_dirs = [
        os.path.join(app.root_path, 'uploads'),
        'uploads',
        os.path.abspath('uploads')
    ]
    
    for base in search_dirs:
        if os.path.exists(os.path.join(base, clean_filename)):
            return send_from_directory(base, clean_filename)
            
    return f"File '{clean_filename}' not found in asset repository", 404

@app.route('/set_lang/<lang>')
def set_lang(lang):
    # System strictly Arabic only as per user request
    session['lang'] = 'ar'
    return redirect(request.referrer or url_for('dashboard.dashboard'))

@app.route('/api/ai_analyze', methods=['POST'])
def ai_analyze():
    if not session.get('user_id'):
        return {"error": "Unauthorized"}, 401
    from ai_assistant import analyze_symptoms
    symptoms = request.json.get('symptoms', '')
    print(f"[AI] Request symptoms: {symptoms}")
    if not symptoms:
        return {"result": "يرجى كتابة بعض الأعراض أولاً ليقوم الذكاء الاصطناعي بتحليلها."}
    
    result = analyze_symptoms(symptoms)
    print(f"[AI] Result: {result[:100]}...")
    return {"result": result}

@app.route('/api/verify_api_key', methods=['POST'])
def verify_api_key():
    if not session.get('user_id') or session.get('role') != 'admin':
        return {"error": "Unauthorized"}, 401
    
    from ai_assistant import validate_api_key
    raw_keys = request.json.get('keys', '')
    keys = [k.strip() for k in raw_keys.replace('\n', ',').replace(' ', ',').split(',') if k.strip()]
    
    results = []
    for k in keys:
        is_ok, msg = validate_api_key(k)
        results.append({
            "key": k[:6] + "..." + k[-4:] if len(k) > 10 else k,
            "status": is_ok,
            "message": msg
        })
    return {"results": results}
    
@app.route('/api/consultation/autosave', methods=['POST'])
def consultation_autosave():
    if not session.get('user_id'):
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    patient_id = data.get('patient_id')
    notes = data.get('notes')
    diag = data.get('diag')
    booking_id = data.get('booking_id')
    
    if not patient_id:
        return {"error": "Missing Patient ID"}, 400
        
    from config import get_db
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Check if a consultation record exists for this booking
        if booking_id:
            cursor.execute("SELECT consultation_id FROM consultations WHERE appointment_id = %s", (booking_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("UPDATE consultations SET subjective = %s, assessment = %s WHERE consultation_id = %s", (notes, diag, exists[0]))
            else:
                cursor.execute("INSERT INTO consultations (patient_id, appointment_id, subjective, assessment, created_at, doctor_id) VALUES (%s, %s, %s, %s, %s, %s)", 
                               (patient_id, booking_id, notes, diag, local_now(), session.get('user_id')))
        db.commit()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}, 500

@app.before_request
def force_defaults():
    session['theme'] = 'light'
    if session.get('lang') != 'ar':
        session['lang'] = 'ar'

# ── Error handlers ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    # If it's a file request that failed, don't redirect (prevents 'exiting' feeling)
    if '.' in request.path or '/uploads/' in request.path:
        return "File Not Found", 404
    return redirect(url_for('index.index'))

@app.errorhandler(500)
def internal_error(e):
    import traceback
    error_msg = traceback.format_exc()
    print(f"[ERROR] {error_msg}")
    return f"Internal Server Error: {str(e)}", 500

# ── Template globals ───────────────────────────────────────────────────────
@app.context_processor
def inject_now():
    return {
        'now': local_now(),
        'now_naive': local_now_naive(),
        'format_dt': format_datetime,
        'dt': template_dt,
    }

@app.context_processor
def inject_system_data():
    defaults = {'system_name': 'HealthPro Intelligence', 'system_icon': 'fas fa-hand-holding-medical'}
    try:
        from config import get_db # type: ignore
        db = get_db()
        if not db:
            return defaults
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ('hospital_name', 'system_icon')")
        rows = cur.fetchall()
        cur.close()
        
        data = defaults.copy()
        for row in rows:
            if row['setting_key'] == 'hospital_name' and row['setting_value']:
                data['system_name'] = row['setting_value']
            elif row['setting_key'] == 'system_icon' and row['setting_value']:
                data['system_icon'] = row['setting_value']
                
        return data
    except Exception:
        return defaults

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
