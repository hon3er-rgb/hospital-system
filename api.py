from flask import Blueprint, jsonify, session, request # type: ignore
from ai_assistant import analyze_symptoms, validate_api_key

from config import get_db, local_now_naive, local_today_str, get_system_entropy # type: ignore

import datetime
import time

api_bp = Blueprint('api', __name__)


def _fmt_time(dt):
    if isinstance(dt, (datetime.datetime, datetime.date)):
        return dt.strftime('%I:%M:%S %p')
    if isinstance(dt, str):
        try:
            # Using cast and explicit start to satisfy some linter environments
            s_dt = str(dt)
            return datetime.datetime.strptime(s_dt[0:19], '%Y-%m-%d %H:%M:%S').strftime('%I:%M:%S %p') # type: ignore
        except Exception:
            return ''
    return ''



def _wait_min(created_at):
    if not created_at:
        return 0
    now = local_now_naive()
    if isinstance(created_at, str):
        try:
            s_at = str(created_at)
            created_at = datetime.datetime.strptime(s_at[0:19], '%Y-%m-%d %H:%M:%S') # type: ignore
        except Exception:
            return 0
    try:
        # If appointment was created more than 24 hours ago, waiting time is 0 (it's a future booking)
        if (now - created_at).total_seconds() > 24 * 3600:
            return 0
        return max(0, int((now - created_at).total_seconds() / 60))
    except Exception:
        return 0



def _cleanup_late_appointments(cur, conn):
    """Automatically cancel appointments that are in 'scheduled' status and 5 minutes past their time."""
    now = local_now_naive()
    # 5 minutes grace period
    cutoff = (now - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Update appointments to cancelled if they are late and still in 'scheduled' status
    # Note: we only cancel unpaid appointments (is_free = 0)
    cur.execute("""
        UPDATE appointments 
        SET status = 'cancelled' 
        WHERE status = 'scheduled' 
          AND appointment_date < %s
          AND (is_free = 0 OR is_free IS NULL)
    """, (cutoff,))
    
    if cur.rowcount > 0:
        conn.commit()

# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_waiting', methods=['GET'])
def api_waiting():
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Database Connection Error'}), 500

    cur = conn.cursor(dictionary=True)
    
    # --- Auto-Cleanup Trigger ---
    _cleanup_late_appointments(cur, conn)

    today_str = local_today_str()

    # ── Column 1 : Reception + Triage ─────────────────────────────────────
    cur.execute("""
        SELECT a.created_at, p.full_name_ar AS p_name, a.status, a.is_free
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE (a.status = 'pending_triage' OR (a.status = 'scheduled' AND (a.is_free = 0 OR a.is_free IS NULL)))
          AND a.appointment_date LIKE ?
        ORDER BY a.created_at ASC
    """, (today_str + '%',))
    reception_list = []
    for r in cur.fetchall():
        sub = 'فحص أولي'
        if (r['status'] or '').lower() == 'scheduled':
            sub = 'بانتظار الدفع'
                
        reception_list.append({
            'name':       r['p_name'],
            'wait':       _wait_min(r['created_at']),
            'entrance':   _fmt_time(r['created_at']),
            'status':     r['status'],
            'sub_status': sub,
        })

    # ── Column 2 : Doctor queue (single query with aggregates) ────────────
    cur.execute("""
        SELECT
            a.appointment_id,
            a.created_at,
            a.status,
            a.is_urgent,
            a.call_status,
            p.full_name_ar  AS p_name,
            u.full_name_ar  AS doc_name,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status IN ('pending','pending_payment')) AS pend_lab,
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status IN ('pending','pending_payment')) AS pend_rad,
            (SELECT COUNT(*) FROM prescriptions      pr WHERE pr.appointment_id = a.appointment_id AND pr.status IN ('pending','pending_payment')) AS pend_rx,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status = 'completed') +
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status = 'completed') AS done_cnt,
            a.is_free
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        LEFT JOIN users u ON a.doctor_id = u.user_id
        WHERE (a.status IN ('waiting_doctor', 'in_progress') OR (a.status = 'scheduled' AND a.is_free = 1))
          AND a.appointment_date LIKE ?
        ORDER BY a.is_urgent DESC, a.created_at ASC
    """, (today_str + '%',))
    doctor_list = []
    for r in cur.fetchall():
        pending = (r.get('pend_lab') or 0) + (r.get('pend_rad') or 0) + (r.get('pend_rx') or 0)
        doctor_list.append({
            'patient':     r['p_name'],
            'doctor':      r['doc_name'] or 'عام',
            'wait':        _wait_min(r['created_at']),
            'entrance':    _fmt_time(r['created_at']),
            'is_ready':    (r.get('done_cnt') or 0) > 0,
            'is_urgent':   bool(r.get('is_urgent')),
            'status':      r['status'],
            'call_status': r.get('call_status') or 0,
            'in_lab':      pending > 0,
            'pending_cnt': pending,
            'is_free':     bool(r.get('is_free'))
        })

    # ── Column 3 : Medical/Exams queue ────────────────────────────────────
    cur.execute("""
        SELECT
            p.full_name_ar AS p_name,
            a.created_at,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status IN ('pending','pending_payment')) AS pend_labs,
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status IN ('pending','pending_payment')) AS pend_rads,
            (SELECT COUNT(*) FROM prescriptions      pr WHERE pr.appointment_id = a.appointment_id AND pr.status IN ('pending','pending_payment')) AS pend_pharma
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.status NOT IN ('completed','cancelled')
          AND a.appointment_date LIKE ?
        ORDER BY a.created_at ASC
    """, (today_str + '%',))
    exams_list = []
    for ex in cur.fetchall():
        pl = ex.get('pend_labs') or 0
        pr = ex.get('pend_rads') or 0
        pp = ex.get('pend_pharma') or 0
        if pl + pr + pp == 0:
            continue   # nothing pending – skip
        exams_list.append({
            'patient':    ex['p_name'],
            'entrance':   _fmt_time(ex['created_at']),
            'status_msg': 'قيد الانتظار',
            'has_lab':    pl > 0,
            'has_rad':    pr > 0,
            'has_pharma': pp > 0,
        })

    return jsonify({'reception': reception_list, 'doctor': doctor_list, 'medical': exams_list})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_ping', methods=['GET'])
def api_ping():
    return jsonify({
        'status': 'ok', 
        'time': int(time.time()),
        'sys_entropy': get_system_entropy()
    })



# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_patient_search', methods=['GET'])
def api_patient_search():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    q = request.args.get('q', '').strip()
    include_all = request.args.get('all', '0') == '1'
    if not q:
        return jsonify([])
    q_param = f"{q}%" # Prefix search is indexed (0ms)
    conn = get_db()
    if not conn:
        return jsonify([])
    cur = conn.cursor(dictionary=True)
    
    if include_all:
        cur.execute("""
            SELECT p.patient_id, p.full_name_ar, p.file_number, p.national_id
            FROM patients p
            WHERE (p.full_name_ar LIKE ? OR p.file_number LIKE ? OR p.national_id LIKE ?)
            LIMIT 10
        """, (q_param, q_param, q_param))
    else:
        cur.execute("""
            SELECT p.patient_id, p.full_name_ar, p.file_number, p.national_id
            FROM patients p
            WHERE (p.full_name_ar LIKE ? OR p.file_number LIKE ? OR p.national_id LIKE ?)
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  WHERE a.patient_id = p.patient_id
                    AND a.appointment_date LIKE ?
                    AND a.status NOT IN ('completed','cancelled')
              )
            LIMIT 10
        """, (q_param, q_param, q_param, local_today_str() + '%'))

    return jsonify(cur.fetchall())


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_get_appointment', methods=['GET'])
def api_get_appointment():
    appt_id = request.args.get('id')
    if not appt_id:
        return jsonify({'success': False})
    conn = get_db()
    if not conn:
        return jsonify({'success': False})
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appt_id,))
    row = cur.fetchone()
    if row:
        for k, v in row.items():
            if isinstance(v, datetime.datetime):
                row[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(v, datetime.date):
                row[k] = v.strftime('%Y-%m-%d')
        return jsonify({'success': True, 'data': row})
    return jsonify({'success': False})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_update_appointment', methods=['POST'])
def api_update_appointment():
    appt_id = request.form.get('id')
    if not appt_id:
        return jsonify({'success': False})
    date   = request.form.get('date')
    status = request.form.get('status')
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE appointments SET appointment_date=%s, status=%s WHERE appointment_id=%s",
                    (date, status, appt_id))
        conn.commit()
        return jsonify({'success': True, 'message': ''})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_cancel_appointment', methods=['POST'])
def api_cancel_appointment():
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    aid = request.form.get('id')
    if not aid:
        return jsonify({'success': False, 'message': 'Invalid Request'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id=%s AND status!='completed'", (aid,))
    conn.commit()
    return jsonify({'success': cur.lastrowid is not None or True})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_transfer_appointment', methods=['POST'])
def api_transfer_appointment():
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    aid = request.form.get('id')
    doc_id = request.form.get('doctor_id')
    dept_id = request.form.get('dept_id')
    if not aid or not doc_id or not dept_id:
        return jsonify({'success': False, 'message': 'Invalid Request'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    try:
        cur = conn.cursor()
        # Transfer only if not completed/cancelled
        cur.execute("UPDATE appointments SET doctor_id=%s, department_id=%s WHERE appointment_id=%s AND status NOT IN ('completed','cancelled')",
                    (doc_id, dept_id, aid))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_barcode_book', methods=['GET'])
def api_barcode_book():
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({'success': False, 'message': 'الباركود فارغ'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT patient_id, full_name_ar FROM patients WHERE file_number=%s OR national_id=%s LIMIT 1",
                (barcode, barcode))
    patient = cur.fetchone()
    if not patient:
        return jsonify({'success': False, 'message': 'لم يتم العثور على مريض'})
    pid = patient['patient_id']
    cur.execute("""
        SELECT department_id, doctor_id, appointment_date
        FROM appointments WHERE patient_id=%s ORDER BY appointment_id DESC LIMIT 1
    """, (pid,))
    last = cur.fetchone()
    dept_id   = (last or {}).get('department_id') or 1
    doctor_id = (last or {}).get('doctor_id') or 1
    last_date = (last or {}).get('appointment_date')
    now = local_now_naive()
    if isinstance(last_date, (datetime.date, datetime.datetime)):
        last_dt = datetime.datetime.combine(last_date, datetime.time()) if isinstance(last_date, datetime.date) and not isinstance(last_date, datetime.datetime) else last_date
    elif isinstance(last_date, str):
        try:
            s_ld = str(last_date)
            last_dt = datetime.datetime.strptime(s_ld[0:10], '%Y-%m-%d') # type: ignore
        except Exception:
            last_dt = datetime.datetime(2000, 1, 1)
    else:
        last_dt = datetime.datetime(2000, 1, 1)
    is_free = 1 if 0 <= (now - last_dt).days <= 7 else 0
    try:
        cur.execute("""
            INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status, is_free)
            VALUES (%s, %s, %s, %s, 'scheduled', %s)
        """, (pid, doctor_id, dept_id, local_now_naive().strftime('%Y-%m-%d %H:%M:%S'), is_free))
        conn.commit()
        msg = f"تم حجز موعد لـ {patient['full_name_ar']}" + (" (مراجعة مجانية)" if is_free else "")
        return jsonify({'success': True, 'message': msg, 'is_free': is_free})
    except Exception as e:
        return jsonify({'success': False, 'message': 'فشل الحجز'})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_chat', methods=['GET', 'POST'])
def api_chat():
    if not session.get('user_id'):
        return jsonify({'success': False}), 401
    my_id = session['user_id']
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Database Connection Error'}), 500
    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        receiver_id = int(request.form.get('receiver_id', 0))
        message     = request.form.get('message', '')
        cur.execute("INSERT INTO chat_messages (sender_id, receiver_id, message) VALUES (%s,%s,%s)",
                    (my_id, receiver_id, message))
        conn.commit()
        return jsonify({'success': True})
    # GET
    friend_id  = int(request.args.get('with', 0))
    get_status = request.args.get('get_status') is not None
    response   = {'messages': [], 'statuses': {}}
    if friend_id > 0:
        cur.execute("""
            SELECT * FROM chat_messages
            WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
            ORDER BY created_at ASC
        """, (my_id, friend_id, friend_id, my_id))
        response['messages'] = [
            {'text': m['message'],
             'type': 'sent' if m['sender_id'] == my_id else 'received',
             'time': _fmt_time(m['created_at'])}
            for m in cur.fetchall()
        ]
    if get_status:
        cur.execute("SELECT user_id, last_activity, current_task, active_patient_name FROM users WHERE is_active=1")
        now = local_now_naive()
        statuses = {}
        for u in cur.fetchall():
            la = u['last_activity']
            online = False
            if la:
                if isinstance(la, str):
                    try:
                        s_la = str(la)
                        la = datetime.datetime.strptime(s_la[0:19], '%Y-%m-%d %H:%M:%S') # type: ignore
                    except Exception:
                        la = None
                if la and isinstance(la, datetime.datetime):
                    online = (now - la).total_seconds() < 45
            statuses[u['user_id']] = {
                'online': online, 'task': u['current_task'], 'patient': u['active_patient_name']
            }
        response['statuses'] = statuses
    return jsonify(response)


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_recall', methods=['POST'])
def api_recall():
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Unauthorized'})
    appt_id = int(request.form.get('id', 0))
    action  = request.form.get('action', '')
    if appt_id <= 0:
        return jsonify({'success': False, 'error': 'Invalid ID'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'DB Error'})
    cur = conn.cursor()
    if action == 'trigger':
        cur.execute("UPDATE appointments SET call_status=1 WHERE appointment_id=%s", (appt_id,))
    elif action == 'complete':
        cur.execute("UPDATE appointments SET call_status=2 WHERE appointment_id=%s", (appt_id,))
    elif action == 'cancel':
        cur.execute("UPDATE appointments SET call_status=0 WHERE appointment_id=%s", (appt_id,))
    else:
        return jsonify({'success': False, 'error': 'Invalid action'})
    conn.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_server_stats', methods=['GET'])
def api_server_stats():
    try:
        import psutil # type: ignore
        return jsonify({'cpu': int(psutil.cpu_percent(interval=None)),
                        'ram': int(psutil.virtual_memory().percent)})
    except Exception:
        return jsonify({'cpu': 0, 'ram': 0})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_edit_lab_price', methods=['POST'])
def api_edit_lab_price():
    if not session.get('user_id'):
        return jsonify({'status': 'error', 'msg': 'Unauthorized'}), 401
    test_id   = int(request.form.get('test_id', 0))
    new_price = float(request.form.get('new_price', 0))
    conn = get_db()
    if not conn:
        return jsonify({'status': 'error', 'msg': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE lab_tests SET price=%s WHERE test_id=%s", (new_price, test_id))
        conn.commit()
        return jsonify({'status': 'success', 'msg': 'تم تعديل السعر بنجاح'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_toggle_lab_active', methods=['POST'])
def api_toggle_lab_active():
    if not session.get('user_id'):
        return jsonify({'status': 'error', 'msg': 'Unauthorized'}), 401
    test_id = int(request.form.get('test_id', 0))
    active  = int(request.form.get('active', 0))
    conn = get_db()
    if not conn:
        return jsonify({'status': 'error', 'msg': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE lab_tests SET is_active=%s WHERE test_id=%s", (active, test_id))
        conn.commit()
        return jsonify({'status': 'success', 'msg': 'تم تحديث حالة التفعيل'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})


# ══════════════════════════════════════════════════════════════════════════
# WEBRTC OFFLINE SIGNALING (NO INTERNET)
# ══════════════════════════════════════════════════════════════════════════

@api_bp.route('/api_send_signal', methods=['POST'])
def api_send_signal():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    sender_id   = int(session['user_id'])
    receiver_id = int(request.form.get('to_id', 0))
    sig_type    = request.form.get('type', '')
    sig_data    = request.form.get('data', '')
    now_str     = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO call_signaling (sender_id, receiver_id, signal_type, signal_data, created_at) 
        VALUES (%s, %s, %s, %s, %s)
    """, (sender_id, receiver_id, sig_type, sig_data, now_str))
    conn.commit()
    return jsonify({'success': True})


@api_bp.route('/api_get_signals', methods=['GET'])
def api_get_signals():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Cast to int to be safe in SQLite lookups
    try:
        my_id    = int(str(session['user_id']))
        since_id = int(request.args.get('since', 0))
    except:
        return jsonify([])
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # --- Ultra Speed: One-shot check, no long-polling loop ---
    cursor.execute("""
        SELECT s.id, s.sender_id as from_id, s.signal_type as type, s.signal_data as data, COALESCE(u.full_name_ar, 'زميل') as from_name 
        FROM call_signaling s 
        LEFT JOIN users u ON s.sender_id = u.user_id 
        WHERE s.receiver_id = %s AND s.id > %s AND s.created_at >= datetime('now', '-30 seconds')
        ORDER BY s.id ASC LIMIT 20
    """, (my_id, since_id))
    signals = cursor.fetchall()
    
    if signals:
        # Cleanup processed signals
        cursor.execute("DELETE FROM call_signaling WHERE receiver_id = %s OR created_at < datetime('now', '-5 minutes')", (my_id,))
        conn.commit()
        return jsonify(signals)
        
    return jsonify([]) 


@api_bp.route('/api_presence_heartbeat', methods=['GET', 'POST'])
def api_presence_heartbeat():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    uid = session['user_id']
    now_str = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cursor = conn.cursor()
    # Use REPLACE with local time
    cursor.execute("REPLACE INTO user_presence (user_id, last_seen) VALUES (%s, %s)", (uid, now_str))
    # Cleanup old signals (older than 1 minute) - SQLite syntax
    cursor.execute("DELETE FROM call_signaling WHERE created_at < datetime('now', '-1 minute')")
    conn.commit()
    return jsonify({'success': True})


@api_bp.route('/api_send_msg', methods=['POST'])
def api_send_msg():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    sender_id   = int(session['user_id'])
    receiver_id = int(request.form.get('to_id', 0))
    message     = request.form.get('message', '')
    
    if not receiver_id or not message:
        return jsonify({'error': 'Invalid data'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)",
                 (sender_id, receiver_id, message))
    conn.commit()
    return jsonify({'success': True})


@api_bp.route('/api_get_msgs', methods=['GET'])
def api_get_msgs():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    my_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT m.*, u.full_name_ar as sender_name 
        FROM messages m 
        JOIN users u ON m.sender_id = u.user_id 
        WHERE m.receiver_id = %s AND m.is_read = 0
        ORDER BY m.created_at ASC
    """, (my_id,))
    msgs = cursor.fetchall()
    
    if msgs:
        cursor.execute("UPDATE messages SET is_read = 1 WHERE receiver_id = %s", (my_id,))
        conn.commit()
        
    return jsonify(msgs)


# ══════════════════════════════════════════════════════════════════════════
# AI ASSISTANT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@api_bp.route('/api/verify_api_key', methods=['POST'])
def api_verify_api_key():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    keys = data.get('keys', '')
    if not keys:
        return jsonify({'results': [{'status': False, 'message': 'يرجى إدخال المفتاح'}]})
    
    # Split by comma or newline and take the first one (or we could loop, but programmer_settings seems to pass one string)
    token = keys.split(',')[0].strip()
    status, msg = validate_api_key(token)
    return jsonify({'results': [{'status': status, 'message': msg}]})


from ai_assistant import analyze_symptoms, suggest_treatment


@api_bp.route('/api/ai_analyze', methods=['POST'])
def api_ai_analyze():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'success': False, 'message': 'لا يوجد نص للتحليل'})
    
    result = analyze_symptoms(text)
    return jsonify({'success': True, 'result': result})

@api_bp.route('/api/ai_suggest_rx', methods=['POST'])
def api_ai_suggest_rx():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    diag = data.get('diagnosis', '')
    vitals = data.get('vitals', '')
    age = data.get('age', '')
    
    result = suggest_treatment(diag, vitals, age)
    return jsonify({'success': True, 'result': result})

