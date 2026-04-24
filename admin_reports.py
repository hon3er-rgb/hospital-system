import json
from flask import Blueprint, session, redirect, url_for, render_template_string  # type: ignore
from config import get_db, local_today_str, local_now  # type: ignore
from header import header_html  # type: ignore
from footer import footer_html  # type: ignore

admin_reports_bp = Blueprint('admin_reports', __name__)


def _sf(val):
    try: return float(val or 0)
    except: return 0.0

def _si(val):
    try: return int(val or 0)
    except: return 0

def _pct(a, b):
    try: return round(a / b * 100) if b else 0
    except: return 0


@admin_reports_bp.route('/admin_reports')
def admin_reports():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)
    now_str = local_now().strftime('%Y-%m-%d %H:%M')

    # ── System Info ───────────────────────────────────────────────────────────
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'system_name'")
    sn_row = cursor.fetchone()
    system_name = sn_row['setting_value'] if sn_row else 'نظام إدارة المستشفى'

    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'currency_label'")
    cur_row = cursor.fetchone()
    currency = cur_row['setting_value'] if cur_row else 'د.ع'

    # ── Date filters (SQLite) ─────────────────────────────────────────────────
    D = {
        'day':   "DATE(created_at) = DATE('now')",
        'week':  "strftime('%Y-%W', created_at) = strftime('%Y-%W', 'now')",
        'month': "strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')",
        'year':  "strftime('%Y',    created_at) = strftime('%Y',    'now')",
    }
    AD = {
        'day':   "DATE(appointment_date) = DATE('now')",
        'week':  "strftime('%Y-%W', appointment_date) = strftime('%Y-%W', 'now')",
        'month': "strftime('%Y-%m', appointment_date) = strftime('%Y-%m', 'now')",
        'year':  "strftime('%Y',    appointment_date) = strftime('%Y',    'now')",
    }
    P = ['day', 'week', 'month', 'year']

    # ══════════════════════════════════════════════════════════════════════════
    # 1.  INVOICES — إجمالي الإيرادات المسددة
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            COALESCE(SUM(CASE WHEN {D['day']}   AND status='paid' THEN amount ELSE 0 END),0) AS day_rev,
            COALESCE(SUM(CASE WHEN {D['week']}  AND status='paid' THEN amount ELSE 0 END),0) AS week_rev,
            COALESCE(SUM(CASE WHEN {D['month']} AND status='paid' THEN amount ELSE 0 END),0) AS month_rev,
            COALESCE(SUM(CASE WHEN {D['year']}  AND status='paid' THEN amount ELSE 0 END),0) AS year_rev,
            COUNT(CASE WHEN {D['day']}   AND status='paid' THEN 1 END) AS day_paid,
            COUNT(CASE WHEN {D['week']}  AND status='paid' THEN 1 END) AS week_paid,
            COUNT(CASE WHEN {D['month']} AND status='paid' THEN 1 END) AS month_paid,
            COUNT(CASE WHEN {D['year']}  AND status='paid' THEN 1 END) AS year_paid,
            COUNT(CASE WHEN {D['day']}   THEN 1 END) AS day_total,
            COUNT(CASE WHEN {D['week']}  THEN 1 END) AS week_total,
            COUNT(CASE WHEN {D['month']} THEN 1 END) AS month_total,
            COUNT(CASE WHEN {D['year']}  THEN 1 END) AS year_total,
            COUNT(CASE WHEN {D['day']}   AND status != 'paid' THEN 1 END) AS day_unpaid,
            COUNT(CASE WHEN {D['month']} AND status != 'paid' THEN 1 END) AS month_unpaid,
            COALESCE(SUM(CASE WHEN {D['day']}   AND status != 'paid' THEN amount ELSE 0 END),0) AS day_unpaid_amt,
            COALESCE(SUM(CASE WHEN {D['month']} AND status != 'paid' THEN amount ELSE 0 END),0) AS month_unpaid_amt,
            COALESCE(SUM(CASE WHEN {D['day']}   AND amount < 0 THEN amount ELSE 0 END),0) AS day_refunds,
            COALESCE(SUM(CASE WHEN {D['month']} AND amount < 0 THEN amount ELSE 0 END),0) AS month_refunds
        FROM invoices WHERE {D['year']} OR {D['week']} OR {D['day']} OR {D['month']}
    """)
    inv_all = cursor.fetchone() or {}

    revenue     = {p: _sf(inv_all.get(f'{p}_rev'))   for p in P}
    revenue_cnt = {p: _si(inv_all.get(f'{p}_paid'))  for p in P}
    total_inv   = {p: _si(inv_all.get(f'{p}_total')) for p in P}
    collection_rate = {p: _pct(revenue_cnt[p], total_inv[p]) for p in P}
    avg_invoice = {p: round(revenue[p] / revenue_cnt[p]) if revenue_cnt[p] else 0 for p in P}
    unpaid_cnt  = {'day': _si(inv_all.get('day_unpaid')), 'month': _si(inv_all.get('month_unpaid'))}
    unpaid_amt  = {'day': _sf(inv_all.get('day_unpaid_amt')), 'month': _sf(inv_all.get('month_unpaid_amt'))}
    refunds_amt = {'day': abs(_sf(inv_all.get('day_refunds'))), 'month': abs(_sf(inv_all.get('month_refunds')))}

    # ══════════════════════════════════════════════════════════════════════════
    # 2.  CONSULTATIONS — الكشوفات العيادية
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            COUNT(CASE WHEN {AD['day']}   AND i.status='paid' THEN 1 END) AS day_cnt,
            COUNT(CASE WHEN {AD['week']}  AND i.status='paid' THEN 1 END) AS week_cnt,
            COUNT(CASE WHEN {AD['month']} AND i.status='paid' THEN 1 END) AS month_cnt,
            COUNT(CASE WHEN {AD['year']}  AND i.status='paid' THEN 1 END) AS year_cnt,
            COALESCE(SUM(CASE WHEN {AD['day']}   AND i.status='paid' THEN i.amount ELSE 0 END),0) AS day_rev,
            COALESCE(SUM(CASE WHEN {AD['week']}  AND i.status='paid' THEN i.amount ELSE 0 END),0) AS week_rev,
            COALESCE(SUM(CASE WHEN {AD['month']} AND i.status='paid' THEN i.amount ELSE 0 END),0) AS month_rev,
            COALESCE(SUM(CASE WHEN {AD['year']}  AND i.status='paid' THEN i.amount ELSE 0 END),0) AS year_rev
        FROM appointments a
        JOIN invoices i ON a.appointment_id = i.appointment_id
    """)
    cr = cursor.fetchone() or {}
    consultations = {p: {'cnt': _si(cr.get(f'{p}_cnt')), 'rev': _sf(cr.get(f'{p}_rev'))} for p in P}

    # ══════════════════════════════════════════════════════════════════════════
    # 3.  LAB REQUESTS — فحوصات المختبر
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            COUNT(CASE WHEN {D['day']}   THEN 1 END) AS day_cnt,
            COUNT(CASE WHEN {D['week']}  THEN 1 END) AS week_cnt,
            COUNT(CASE WHEN {D['month']} THEN 1 END) AS month_cnt,
            COUNT(CASE WHEN {D['year']}  THEN 1 END) AS year_cnt,
            COALESCE(SUM(CASE WHEN {D['day']}   THEN price ELSE 0 END),0) AS day_rev,
            COALESCE(SUM(CASE WHEN {D['week']}  THEN price ELSE 0 END),0) AS week_rev,
            COALESCE(SUM(CASE WHEN {D['month']} THEN price ELSE 0 END),0) AS month_rev,
            COALESCE(SUM(CASE WHEN {D['year']}  THEN price ELSE 0 END),0) AS year_rev,
            COUNT(CASE WHEN status='completed' AND {D['month']} THEN 1 END) AS month_completed,
            COUNT(CASE WHEN status='pending'   AND {D['month']} THEN 1 END) AS month_pending
        FROM lab_requests WHERE status != 'cancelled'
    """)
    lr = cursor.fetchone() or {}
    labs = {p: {'cnt': _si(lr.get(f'{p}_cnt')), 'rev': _sf(lr.get(f'{p}_rev'))} for p in P}
    lab_comp_rate = _pct(_si(lr.get('month_completed')), _si(lr.get('month_cnt')))
    lab_pending   = _si(lr.get('month_pending'))

    # ══════════════════════════════════════════════════════════════════════════
    # 4.  RADIOLOGY — طلبات الأشعة
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            COUNT(CASE WHEN {D['day']}   THEN 1 END) AS day_cnt,
            COUNT(CASE WHEN {D['week']}  THEN 1 END) AS week_cnt,
            COUNT(CASE WHEN {D['month']} THEN 1 END) AS month_cnt,
            COUNT(CASE WHEN {D['year']}  THEN 1 END) AS year_cnt,
            COALESCE(SUM(CASE WHEN {D['day']}   THEN price ELSE 0 END),0) AS day_rev,
            COALESCE(SUM(CASE WHEN {D['week']}  THEN price ELSE 0 END),0) AS week_rev,
            COALESCE(SUM(CASE WHEN {D['month']} THEN price ELSE 0 END),0) AS month_rev,
            COALESCE(SUM(CASE WHEN {D['year']}  THEN price ELSE 0 END),0) AS year_rev,
            COUNT(CASE WHEN status='completed' AND {D['month']} THEN 1 END) AS month_completed,
            COUNT(CASE WHEN status='pending'   AND {D['month']} THEN 1 END) AS month_pending
        FROM radiology_requests WHERE status != 'cancelled'
    """)
    rr = cursor.fetchone() or {}
    radiology = {p: {'cnt': _si(rr.get(f'{p}_cnt')), 'rev': _sf(rr.get(f'{p}_rev'))} for p in P}
    rad_comp_rate = _pct(_si(rr.get('month_completed')), _si(rr.get('month_cnt')))
    rad_pending   = _si(rr.get('month_pending'))

    # ══════════════════════════════════════════════════════════════════════════
    # 5.  PHARMACY — الصيدلية (محاولة مرنة)
    # ══════════════════════════════════════════════════════════════════════════
    pharmacy = {p: {'cnt': 0, 'rev': 0.0} for p in P}
    try:
        cursor.execute(f"""
            SELECT
                COUNT(CASE WHEN {D['day']}   THEN 1 END) AS day_cnt,
                COUNT(CASE WHEN {D['week']}  THEN 1 END) AS week_cnt,
                COUNT(CASE WHEN {D['month']} THEN 1 END) AS month_cnt,
                COUNT(CASE WHEN {D['year']}  THEN 1 END) AS year_cnt,
                COALESCE(SUM(CASE WHEN {D['day']}   THEN total_price ELSE 0 END),0) AS day_rev,
                COALESCE(SUM(CASE WHEN {D['week']}  THEN total_price ELSE 0 END),0) AS week_rev,
                COALESCE(SUM(CASE WHEN {D['month']} THEN total_price ELSE 0 END),0) AS month_rev,
                COALESCE(SUM(CASE WHEN {D['year']}  THEN total_price ELSE 0 END),0) AS year_rev
            FROM prescriptions WHERE status='dispensed'
        """)
        pr = cursor.fetchone() or {}
        pharmacy = {p: {'cnt': _si(pr.get(f'{p}_cnt')), 'rev': _sf(pr.get(f'{p}_rev'))} for p in P}
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 6.  APPOINTMENTS — المواعيد الإجمالية
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            COUNT(CASE WHEN {AD['day']}   THEN 1 END) AS day_total,
            COUNT(CASE WHEN {AD['week']}  THEN 1 END) AS week_total,
            COUNT(CASE WHEN {AD['month']} THEN 1 END) AS month_total,
            COUNT(CASE WHEN {AD['year']}  THEN 1 END) AS year_total,
            COUNT(CASE WHEN {AD['day']}   AND status='cancelled'  THEN 1 END) AS day_cancelled,
            COUNT(CASE WHEN {AD['week']}  AND status='cancelled'  THEN 1 END) AS week_cancelled,
            COUNT(CASE WHEN {AD['month']} AND status='cancelled'  THEN 1 END) AS month_cancelled,
            COUNT(CASE WHEN {AD['year']}  AND status='cancelled'  THEN 1 END) AS year_cancelled,
            COUNT(CASE WHEN {AD['day']}   AND status='completed'  THEN 1 END) AS day_completed,
            COUNT(CASE WHEN {AD['week']}  AND status='completed'  THEN 1 END) AS week_completed,
            COUNT(CASE WHEN {AD['month']} AND status='completed'  THEN 1 END) AS month_completed,
            COUNT(CASE WHEN {AD['year']}  AND status='completed'  THEN 1 END) AS year_completed,
            COUNT(CASE WHEN {AD['day']}   AND status='scheduled'  THEN 1 END) AS day_scheduled,
            COUNT(CASE WHEN {AD['month']} AND status='scheduled'  THEN 1 END) AS month_scheduled,
            COUNT(CASE WHEN {AD['day']}   AND (is_free_followup=1 OR is_free_followup='1') THEN 1 END) AS day_free,
            COUNT(CASE WHEN {AD['month']} AND (is_free_followup=1 OR is_free_followup='1') THEN 1 END) AS month_free,
            COUNT(CASE WHEN {AD['year']}  AND (is_free_followup=1 OR is_free_followup='1') THEN 1 END) AS year_free
        FROM appointments
    """)
    ar = cursor.fetchone() or {}
    appointments = {p: {
        'total':     _si(ar.get(f'{p}_total')),
        'cancelled': _si(ar.get(f'{p}_cancelled')),
        'completed': _si(ar.get(f'{p}_completed')),
    } for p in P}
    cancel_rate  = {p: _pct(appointments[p]['cancelled'], appointments[p]['total']) for p in P}
    free_follows = {'day': _si(ar.get('day_free')), 'month': _si(ar.get('month_free')), 'year': _si(ar.get('year_free'))}
    scheduled_today = _si(ar.get('day_scheduled'))

    # ══════════════════════════════════════════════════════════════════════════
    # 7.  NEW PATIENTS — المرضى الجدد
    # ══════════════════════════════════════════════════════════════════════════
    new_patients = {p: 0 for p in P}
    total_patients = 0
    try:
        cursor.execute(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN {D['day']}   THEN 1 END) AS day_cnt,
                COUNT(CASE WHEN {D['week']}  THEN 1 END) AS week_cnt,
                COUNT(CASE WHEN {D['month']} THEN 1 END) AS month_cnt,
                COUNT(CASE WHEN {D['year']}  THEN 1 END) AS year_cnt
            FROM patients
        """)
        npr = cursor.fetchone() or {}
        new_patients   = {p: _si(npr.get(f'{p}_cnt')) for p in P}
        total_patients = _si(npr.get('total'))
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 8.  MONTH vs PREV MONTH — مقارنة الشهر الحالي بالسابق
    # ══════════════════════════════════════════════════════════════════════════
    month_vs_prev = {'current': 0.0, 'prev': 0.0, 'diff': 0.0, 'pct': 0, 'up': True}
    try:
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN strftime('%Y-%m',created_at)=strftime('%Y-%m','now')
                                  AND status='paid' THEN amount ELSE 0 END),0) AS curr,
                COALESCE(SUM(CASE WHEN strftime('%Y-%m',created_at)=strftime('%Y-%m',DATE('now','-1 month'))
                                  AND status='paid' THEN amount ELSE 0 END),0) AS prev
            FROM invoices
        """)
        mvp = cursor.fetchone() or {}
        curr = _sf(mvp.get('curr'))
        prev = _sf(mvp.get('prev'))
        diff = curr - prev
        month_vs_prev = {
            'current': curr, 'prev': prev, 'diff': diff,
            'pct': _pct(abs(diff), prev) if prev else 0,
            'up': diff >= 0
        }
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 9.  REVENUE TREND (آخر 7 أيام) — رسم بياني
    # ══════════════════════════════════════════════════════════════════════════
    trend_labels = []
    trend_values = []
    try:
        cursor.execute("""
            SELECT DATE(created_at) AS dday, COALESCE(SUM(amount),0) AS total
            FROM invoices
            WHERE status='paid' AND created_at >= DATE('now','-6 days')
            GROUP BY DATE(created_at) ORDER BY dday
        """)
        for row in (cursor.fetchall() or []):
            d = str(row.get('dday') or '')
            trend_labels.append(d[-5:] if len(d) >= 5 else d)
            trend_values.append(_sf(row.get('total')))
    except Exception:
        pass
    trend_json = json.dumps({'labels': trend_labels, 'values': trend_values})

    # ══════════════════════════════════════════════════════════════════════════
    # 10.  PEAK HOURS — ساعات الذروة
    # ══════════════════════════════════════════════════════════════════════════
    peak_hours = []
    try:
        cursor.execute("""
            SELECT strftime('%H',appointment_date) AS hr, COUNT(*) AS cnt
            FROM appointments
            WHERE strftime('%Y-%m',appointment_date)=strftime('%Y-%m','now')
            GROUP BY hr ORDER BY cnt DESC LIMIT 6
        """)
        peak_hours = cursor.fetchall() or []
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 11.  TOP LAB TESTS — أكثر التحاليل طلباً
    # ══════════════════════════════════════════════════════════════════════════
    top_labs = []
    try:
        cursor.execute(f"""
            SELECT test_name, COUNT(*) AS cnt, COALESCE(SUM(price),0) AS tot
            FROM lab_requests
            WHERE {D['month']} AND status!='cancelled'
              AND test_name IS NOT NULL AND test_name!=''
            GROUP BY test_name ORDER BY cnt DESC LIMIT 8
        """)
        top_labs = cursor.fetchall() or []
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 12.  TOP RADIOLOGY — أكثر الأشعة طلباً
    # ══════════════════════════════════════════════════════════════════════════
    top_rad = []
    for col in ('exam_type', 'request_type', 'type'):
        try:
            cursor.execute(f"""
                SELECT {col} AS rtype, COUNT(*) AS cnt, COALESCE(SUM(price),0) AS tot
                FROM radiology_requests
                WHERE {D['month']} AND status!='cancelled'
                  AND {col} IS NOT NULL AND {col}!=''
                GROUP BY {col} ORDER BY cnt DESC LIMIT 8
            """)
            top_rad = cursor.fetchall() or []
            break
        except Exception:
            continue

    # ══════════════════════════════════════════════════════════════════════════
    # 13.  DEPARTMENT REVENUE — إيراد الأقسام
    # ══════════════════════════════════════════════════════════════════════════
    dept_revenue = []
    try:
        cursor.execute(f"""
            SELECT
                COALESCE(d.department_name_ar,'عام') AS dept,
                COALESCE(SUM(CASE WHEN {D['day']}   AND i.status='paid' THEN i.amount ELSE 0 END),0) AS day_rev,
                COALESCE(SUM(CASE WHEN {D['month']} AND i.status='paid' THEN i.amount ELSE 0 END),0) AS month_rev,
                COALESCE(SUM(CASE WHEN {D['year']}  AND i.status='paid' THEN i.amount ELSE 0 END),0) AS year_rev,
                COUNT(CASE WHEN {AD['month']} AND i.status='paid' THEN 1 END) AS month_cnt
            FROM appointments a
            JOIN invoices i ON a.appointment_id = i.appointment_id
            LEFT JOIN users u ON a.doctor_id = u.user_id
            LEFT JOIN departments d ON u.department_id = d.department_id
            GROUP BY d.department_id, dept
            ORDER BY month_rev DESC
        """)
        dept_revenue = cursor.fetchall() or []
    except Exception:
        pass
    max_dept_rev = max((_sf(d.get('month_rev')) for d in dept_revenue), default=1) or 1

    # ══════════════════════════════════════════════════════════════════════════
    # 14.  DOCTORS TABLE + PATIENT LISTS — جدول الأطباء وتفاصيل المرضى
    # ══════════════════════════════════════════════════════════════════════════
    cursor.execute(f"""
        SELECT
            u.user_id, u.full_name_ar,
            COALESCE(d.department_name_ar,'عام') AS dept,
            COUNT(CASE WHEN {AD['day']}   AND a.status NOT IN ('cancelled','scheduled') THEN 1 END) AS day_seen,
            COUNT(CASE WHEN {AD['week']}  AND a.status NOT IN ('cancelled','scheduled') THEN 1 END) AS week_seen,
            COUNT(CASE WHEN {AD['month']} AND a.status NOT IN ('cancelled','scheduled') THEN 1 END) AS month_seen,
            COUNT(CASE WHEN {AD['year']}  AND a.status NOT IN ('cancelled','scheduled') THEN 1 END) AS year_seen,
            
            COUNT(CASE WHEN {AD['day']}   AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('ذكر','Male','male') THEN 1 END) AS day_male,
            COUNT(CASE WHEN {AD['week']}  AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('ذكر','Male','male') THEN 1 END) AS week_male,
            COUNT(CASE WHEN {AD['month']} AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('ذكر','Male','male') THEN 1 END) AS month_male,
            COUNT(CASE WHEN {AD['year']}  AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('ذكر','Male','male') THEN 1 END) AS year_male,

            COUNT(CASE WHEN {AD['day']}   AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('أنثى','Female','female') THEN 1 END) AS day_female,
            COUNT(CASE WHEN {AD['week']}  AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('أنثى','Female','female') THEN 1 END) AS week_female,
            COUNT(CASE WHEN {AD['month']} AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('أنثى','Female','female') THEN 1 END) AS month_female,
            COUNT(CASE WHEN {AD['year']}  AND a.status NOT IN ('cancelled','scheduled') AND p.gender IN ('أنثى','Female','female') THEN 1 END) AS year_female,

            (SELECT COUNT(*) FROM lab_requests lr JOIN appointments a2 ON lr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND DATE(a2.appointment_date) = DATE('now') AND lr.status != 'cancelled') AS day_lab,
            (SELECT COUNT(*) FROM lab_requests lr JOIN appointments a2 ON lr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y-%W', a2.appointment_date) = strftime('%Y-%W', 'now') AND lr.status != 'cancelled') AS week_lab,
            (SELECT COUNT(*) FROM lab_requests lr JOIN appointments a2 ON lr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y-%m', a2.appointment_date) = strftime('%Y-%m', 'now') AND lr.status != 'cancelled') AS month_lab,
            (SELECT COUNT(*) FROM lab_requests lr JOIN appointments a2 ON lr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y', a2.appointment_date) = strftime('%Y', 'now') AND lr.status != 'cancelled') AS year_lab,
            
            (SELECT COUNT(*) FROM appointments a2 WHERE a2.doctor_id = u.user_id AND DATE(a2.appointment_date) = DATE('now') AND (a2.is_free_followup=1 OR a2.is_free_followup='1')) AS day_free,
            (SELECT COUNT(*) FROM appointments a2 WHERE a2.doctor_id = u.user_id AND strftime('%Y-%W', a2.appointment_date) = strftime('%Y-%W', 'now') AND (a2.is_free_followup=1 OR a2.is_free_followup='1')) AS week_free,
            (SELECT COUNT(*) FROM appointments a2 WHERE a2.doctor_id = u.user_id AND strftime('%Y-%m', a2.appointment_date) = strftime('%Y-%m', 'now') AND (a2.is_free_followup=1 OR a2.is_free_followup='1')) AS month_free,
            (SELECT COUNT(*) FROM appointments a2 WHERE a2.doctor_id = u.user_id AND strftime('%Y', a2.appointment_date) = strftime('%Y', 'now') AND (a2.is_free_followup=1 OR a2.is_free_followup='1')) AS year_free,

            (SELECT COUNT(*) FROM radiology_requests rr JOIN appointments a2 ON rr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND DATE(a2.appointment_date) = DATE('now') AND rr.status != 'cancelled') AS day_rad,
            (SELECT COUNT(*) FROM radiology_requests rr JOIN appointments a2 ON rr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y-%W', a2.appointment_date) = strftime('%Y-%W', 'now') AND rr.status != 'cancelled') AS week_rad,
            (SELECT COUNT(*) FROM radiology_requests rr JOIN appointments a2 ON rr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y-%m', a2.appointment_date) = strftime('%Y-%m', 'now') AND rr.status != 'cancelled') AS month_rad,
            (SELECT COUNT(*) FROM radiology_requests rr JOIN appointments a2 ON rr.appointment_id = a2.appointment_id WHERE a2.doctor_id = u.user_id AND strftime('%Y', a2.appointment_date) = strftime('%Y', 'now') AND rr.status != 'cancelled') AS year_rad,

            COUNT(CASE WHEN {AD['day']}   THEN 1 END) AS day_total,
            COUNT(CASE WHEN {AD['week']}  THEN 1 END) AS week_total,
            COUNT(CASE WHEN {AD['month']} THEN 1 END) AS month_total,
            COUNT(CASE WHEN {AD['year']}  THEN 1 END) AS year_total,

            COALESCE(SUM(CASE WHEN {AD['day']}   AND i.status='paid' THEN i.amount ELSE 0 END),0) AS day_rev,
            COALESCE(SUM(CASE WHEN {AD['week']}  AND i.status='paid' THEN i.amount ELSE 0 END),0) AS week_rev,
            COALESCE(SUM(CASE WHEN {AD['month']} AND i.status='paid' THEN i.amount ELSE 0 END),0) AS month_rev,
            COALESCE(SUM(CASE WHEN {AD['year']}  AND i.status='paid' THEN i.amount ELSE 0 END),0) AS year_rev
        FROM users u
        LEFT JOIN appointments a ON u.user_id = a.doctor_id
        LEFT JOIN patients p     ON a.patient_id = p.patient_id
        LEFT JOIN invoices i     ON a.appointment_id = i.appointment_id
        LEFT JOIN departments d  ON u.department_id  = d.department_id
        WHERE u.role='doctor' AND u.is_active=1
        GROUP BY u.user_id, u.full_name_ar, dept
        ORDER BY month_seen DESC
    """)
    doctors = cursor.fetchall() or []
    max_day_seen = max((_si(dr.get('day_seen')) for dr in doctors), default=1) or 1

    # Fetch daily activity for each doctor (Current Month)
    dr_activity = {}
    for dr in doctors:
        did = dr['user_id']
        cursor.execute(f"""
            SELECT DATE(a.appointment_date) AS dday, COUNT(*) AS cnt, SUM(i.amount) AS day_rev
            FROM appointments a
            LEFT JOIN invoices i ON a.appointment_id = i.appointment_id
            WHERE a.doctor_id = ? AND {AD['month']}
            GROUP BY dday
            ORDER BY dday DESC
        """, (did,))
        dr_activity[did] = cursor.fetchall() or []

    # ══════════════════════════════════════════════════════════════════════════
    # 15.  STAFF SUMMARY — ملخص الموظفين
    # ══════════════════════════════════════════════════════════════════════════
    staff = {'total': 0, 'active': 0, 'doctors': 0, 'nurses': 0, 'admins': 0, 'others': 0}
    try:
        cursor.execute("SELECT role, is_active, COUNT(*) AS cnt FROM users GROUP BY role, is_active")
        for row in (cursor.fetchall() or []):
            n = _si(row.get('cnt'))
            staff['total'] += n
            if row.get('is_active') in (1, '1', True): staff['active'] += n
            r = (row.get('role') or '').lower()
            if r == 'doctor':  staff['doctors'] += n
            elif r in ('nurse', 'nursing'): staff['nurses'] += n
            elif r == 'admin': staff['admins'] += n
            else: staff['others'] += n
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════════════════════
    # 17.  FULL STATS JSON for dynamic JS usage
    # ══════════════════════════════════════════════════════════════════════════
    full_stats = {
        'revenue': revenue,
        'revenue_cnt': revenue_cnt,
        'total_inv': total_inv,
        'collection_rate': collection_rate,
        'consultations': consultations,
        'labs': labs,
        'radiology': radiology,
        'pharmacy': pharmacy,
        'unpaid_cnt': unpaid_cnt,
        'unpaid_amt': unpaid_amt,
        'refunds_amt': refunds_amt,
        'dept_revenue': dept_revenue,
        'max_dept_rev': max_dept_rev,
        'free_follows': free_follows,
        'currency': currency
    }
    full_stats_json = json.dumps(full_stats)

    conn.close()

    # ── Build chart month bars (last 6 months) ────────────────────────────────
    month_bar_labels = []
    month_bar_values = []
    try:
        conn2 = get_db()
        if conn2:
            cur2 = conn2.cursor(dictionary=True)
            cur2.execute("""
                SELECT strftime('%Y-%m', created_at) AS ym,
                       COALESCE(SUM(amount),0) AS total
                FROM invoices WHERE status='paid'
                  AND created_at >= DATE('now','-5 months','start of month')
                GROUP BY ym ORDER BY ym
            """)
            for row in (cur2.fetchall() or []):
                month_bar_labels.append(str(row.get('ym') or ''))
                month_bar_values.append(_sf(row.get('total')))
            conn2.close()
    except Exception:
        pass
    month_bar_json = json.dumps({'labels': month_bar_labels, 'values': month_bar_values})

    # ─────────────────────────────────────────────────────────────────────────
    #  HTML - HIGH-END PROFESSIONAL DESIGN
    # ─────────────────────────────────────────────────────────────────────────
    html = header_html + r"""
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

<style>
/* ═══════════════════════════════════════════════════════════════════
   MODERN DASHBOARD PRO - iOS STYLE
═══════════════════════════════════════════════════════════════════ */
:root {
  --primary-gradient: linear-gradient(135deg, #007aff 0%, #0056b3 100%);
  --success-gradient: linear-gradient(135deg, #30d158 0%, #248a3d 100%);
  --warning-gradient: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  --danger-gradient: linear-gradient(135deg, #ff3b30 0%, #c41e16 100%);
  --indigo-gradient: linear-gradient(135deg, #5e5ce6 0%, #4a49c9 100%);
}

.ar-reports {
  font-family: 'Tajawal', sans-serif;
  direction: rtl;
  padding: 20px;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
}

/* ── Hero Shell ── */
.rep-hero {
  background: var(--card);
  backdrop-filter: blur(25px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 30px;
  margin-bottom: 25px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 15px 35px rgba(0,0,0,0.05);
  position: relative;
  overflow: hidden;
}

.rep-hero::after {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(0,122,255,0.05) 0%, transparent 70%);
  pointer-events: none;
}

.rep-hero h1 {
  font-size: 1.8rem;
  font-weight: 900;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 15px;
}

.rep-hero h1 i {
  width: 50px;
  height: 50px;
  background: var(--primary-gradient);
  color: white;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  box-shadow: 0 8px 15px rgba(0,122,255,0.25);
}

.rep-hero p {
  opacity: 0.6;
  font-weight: 600;
  font-size: 0.9rem;
  margin: 5px 0 0;
}

/* ── Filter Tabs ── */
.rep-tabs-shell {
  display: inline-flex;
  background: var(--input-bg);
  padding: 6px;
  border-radius: 18px;
  border: 1px solid var(--border);
  margin-bottom: 25px;
  gap: 5px;
}

.rep-tab {
  padding: 10px 24px;
  border-radius: 14px;
  font-weight: 800;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  color: var(--text);
  opacity: 0.5;
  border: none;
  background: transparent;
}

.rep-tab:hover {
  opacity: 1;
  background: rgba(0,0,0,0.03);
}

.rep-tab.on {
  background: var(--card);
  color: #007aff;
  opacity: 1;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

/* ── KPI Widgets ── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-bottom: 25px;
}

.kpi-card {
  background: var(--card);
  backdrop-filter: blur(15px);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 22px;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 8px 25px rgba(0,0,0,0.03);
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 15px 35px rgba(0,0,0,0.08);
  border-color: rgba(0,122,255,0.3);
}

.kpi-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  flex-shrink: 0;
}

.kpi-icon.blue { background: rgba(0,122,255,0.08); color: #007aff; }
.kpi-icon.green { background: rgba(48,209,88,0.08); color: #30d158; }
.kpi-icon.orange { background: rgba(245,158,11,0.08); color: #f59e0b; }
.kpi-icon.purple { background: rgba(94,92,230,0.08); color: #5e5ce6; }

.kpi-label {
  font-size: 0.75rem;
  font-weight: 800;
  opacity: 0.5;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 1.7rem;
  font-weight: 900;
  line-height: 1;
}

.kpi-sub {
  font-size: 0.75rem;
  opacity: 0.7;
  font-weight: 700;
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ── Main Layout ── */
.dash-wrapper {
  display: flex;
  gap: 20px;
}

.dash-main { flex: 1; min-width: 0; }
.dash-side { flex: 0 0 320px; }

/* ── Glass Panes ── */
.glass-pane {
  background: var(--card);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 25px;
  margin-bottom: 20px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.04);
}

.glass-pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.pane-title {
  font-size: 1.05rem;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 10px;
}

.pane-title i { color: #007aff; }

/* ── Tables ── */
.modern-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.modern-table th {
  padding: 12px 15px;
  font-size: 0.7rem;
  font-weight: 900;
  opacity: 0.4;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
  text-align: right;
}

.modern-table td {
  padding: 15px;
  font-size: 0.9rem;
  font-weight: 700;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.modern-table tr:last-child td { border-bottom: none; }

.row-hover:hover { background: rgba(0, 122, 255, 0.02); }

/* ── Components ── */
.av-box {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--input-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  color: #007aff;
  font-size: 1.1rem;
  border: 1px solid var(--border);
}

.badge-pill {
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 0.8rem;
  font-weight: 800;
}

.badge-success { background: rgba(48,209,88,0.12); color: #248a3d; }
.badge-warning { background: rgba(245,158,11,0.12); color: #d97706; }
.badge-danger { background: rgba(255,59,48,0.12); color: #c41e16; }
.badge-primary { background: rgba(0,122,255,0.12); color: #007aff; }

.prog-bar {
  height: 6px;
  background: var(--input-bg);
  border-radius: 10px;
  overflow: hidden;
  margin-top: 6px;
}

.prog-fill {
  height: 100%;
  border-radius: 10px;
  background: var(--primary-gradient);
}

/* ── Chart Styles ── */
.chart-container {
  height: 300px;
  position: relative;
}

/* ── Comparison Banner ── */
.cmp-banner {
  background: var(--primary-gradient);
  border-radius: 22px;
  padding: 30px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 25px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 15px 35px rgba(0,122,255,0.3);
}

.cmp-banner::before {
  content: '';
  position: absolute;
  top: 0; left: 0; width: 100%; height: 200%;
  background: radial-gradient(circle at 10% 20%, rgba(255,255,255,0.1) 0%, transparent 60%);
  pointer-events: none;
}

.cmp-val { font-size: 2.5rem; font-weight: 900; line-height: 1; }
.cmp-lbl { font-size: 0.9rem; font-weight: 600; opacity: 0.8; margin-bottom: 5px; }

/* ── Animations ── */
.psec { display: none; }
.psec.on { display: block; animation: slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1); }

@keyframes slideUp {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Side Widgets ── */
.side-widget {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 20px;
  margin-bottom: 15px;
}

.side-widget-header {
  font-weight: 800;
  font-size: 0.85rem;
  opacity: 0.6;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.list-item:last-child { border: none; }

/* ── Responsive ── */
@media (max-width: 1200px) {
  .dash-wrapper { flex-direction: column; }
  .dash-side { flex: none; width: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .dash-side { grid-template-columns: 1fr; }
  .rep-hero { flex-direction: column; text-align: center; gap: 20px; }
  .cmp-banner { flex-direction: column; text-align: center; gap: 20px; }
}
</style>

<div class="ar-reports">

  <!-- 1. HERO -->
  <div class="rep-hero">
    <div>
      <h1><i class="fas fa-chart-line"></i> لوحة التحكم المركزية</h1>
      <p>الإحصائيات والتقارير الشاملة للنظام | <span class="text-primary">{{ now_str }}</span></p>
    </div>
    <div class="d-flex gap-3">
      <button class="btn btn-primary rounded-pill px-4 fw-bold" onclick="openReportModal()">
        <i class="fas fa-print me-2"></i> طباعة التقرير
      </button>
      <a href="{{ url_for('dashboard.dashboard') }}" class="btn btn-outline-secondary rounded-pill px-4 fw-bold">
        <i class="fas fa-chevron-right me-2"></i> العودة
      </a>
    </div>
  </div>

  <!-- 2. PERIOD SELECTOR -->
  <div class="rep-tabs-shell">
    <button class="rep-tab on" data-p="day" onclick="sw('day')">اليوم</button>
    <button class="rep-tab" data-p="week" onclick="sw('week')">الأسبوع</button>
    <button class="rep-tab" data-p="month" onclick="sw('month')">الشهر</button>
    <button class="rep-tab" data-p="year" onclick="sw('year')">السنة</button>
  </div>

  <!-- 3. DYNAMIC CONTENT -->
  {% for p in ['day','week','month','year'] %}
  <div class="psec {% if p == 'day' %}on{% endif %}" id="s-{{ p }}">

    <!-- KPI ROW -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon blue"><i class="fas fa-hand-holding-usd"></i></div>
        <div>
          <div class="kpi-label">الإيراد الصافي</div>
          <div class="kpi-value text-primary">{{ "{:,.0f}".format(revenue[p]) }}</div>
          <div class="kpi-sub d-flex flex-column align-items-start gap-1">
             <span><i class="fas fa-receipt me-1"></i> {{ revenue_cnt[p] }} فاتورة مسددة</span>
             {% if p in ['day', 'month'] and refunds_amt[p] > 0 %}
             <span class="text-danger"><i class="fas fa-undo me-1"></i> {{ "{:,.0f}".format(refunds_amt[p]) }} مستردة</span>
             {% endif %}
          </div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon green"><i class="fas fa-stethoscope"></i></div>
        <div>
          <div class="kpi-label">إيراد الكشوفات</div>
          <div class="kpi-value text-success">{{ "{:,.0f}".format(consultations[p]['rev']) }}</div>
          <div class="kpi-sub"><i class="fas fa-user-md"></i> {{ consultations[p]['cnt'] }} كشف طبي</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon purple"><i class="fas fa-flask"></i></div>
        <div>
          <div class="kpi-label">إيراد المختبر</div>
          <div class="kpi-value text-purple">{{ "{:,.0f}".format(labs[p]['rev']) }}</div>
          <div class="kpi-sub"><i class="fas fa-vial"></i> {{ labs[p]['cnt'] }} فحص مختبري</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon orange"><i class="fas fa-pills"></i></div>
        <div>
          <div class="kpi-label">إيراد الصيدلية</div>
          <div class="kpi-value text-warning">{{ "{:,.0f}".format(pharmacy[p]['rev']) }}</div>
          <div class="kpi-sub"><i class="fas fa-mortar-pestle"></i> {{ pharmacy[p]['cnt'] }} وصفة</div>
        </div>
      </div>
    </div>

    <div class="dash-wrapper">
      <div class="dash-main">
        
        <!-- DOCTORS PERFORMANCE -->
        <div class="glass-pane">
          <div class="glass-pane-header">
            <div class="pane-title"><i class="fas fa-user-md"></i> أداء الكادر الطبي - {{ plbl }}</div>
            <div class="d-flex gap-2">
               <button class="btn btn-sm btn-outline-primary rounded-pill px-3 fw-bold" onclick="printSelectedDoctors()">
                 <i class="fas fa-print me-1"></i> طباعة التقارير المختارة
               </button>
            </div>
          </div>
          <div class="table-responsive">
            <table class="modern-table" id="doctorsTable">
              <thead>
                <tr>
                  <th style="width: 40px; text-align: center;">
                    <input type="checkbox" id="selectAllDoctors" onchange="toggleAllDoctors(this)" style="width: 18px; height: 18px;">
                  </th>
                  <th>الطبيب</th>
                  <th>القسم</th>
                  <th class="text-center">فحص (مرضى)</th>
                  <th class="text-center">الإيراد</th>
                  <th class="text-center">نسبة الإنجاز</th>
                </tr>
              </thead>
              <tbody>
                {% for dr in doctors %}
                {% set seen = dr[p+'_seen'] | int %}
                {% set tot  = dr[p+'_total'] | int %}
                {% set rev  = dr[p+'_rev'] | float %}
                {% set pct  = ((seen / tot * 100) | int) if tot > 0 else 0 %}
                <tr class="row-hover dr-row" data-dept="{{ dr.dept or 'عام' }}">
                  <td style="text-align: center;">
                    <input type="checkbox" class="dr-checkbox" value="{{ dr.user_id }}" data-name="{{ dr.full_name_ar }}" data-dept="{{ dr.dept or 'عام' }}" data-seen="{{ seen }}" data-rev='{{ "{:,.0f}".format(rev) }}' style="width: 18px; height: 18px;">
                  </td>
                  <td>
                    <div class="d-flex align-items-center gap-3">
                      <div class="av-box">{{ dr.full_name_ar[:1] }}</div>
                      <div style="cursor: pointer;" onclick="showDoctorDetails('{{ dr.user_id }}', '{{ p }}')">
                        <div class="fw-bold text-primary">{{ dr.full_name_ar }}</div>
                        <div class="extra-small opacity-50">#{{ dr.user_id }}</div>
                      </div>
                    </div>
                  </td>
                  <td class="text-center"><span class="badge-pill badge-primary">{{ dr.dept or 'عام' }}</span></td>
                  <td class="text-center">
                    <div class="fw-bold">{{ seen }} <small class="opacity-50">/ {{ tot }}</small></div>
                  </td>
                  <td class="text-center text-success fw-bold">{{ "{:,.0f}".format(rev) }} {{ currency }}</td>
                  <td style="width: 150px;">
                    <div class="d-flex align-items-center gap-2">
                       <div class="prog-bar flex-grow-1"><div class="prog-fill" style="width: {{ pct }}%;"></div></div>
                       <small class="fw-bold">{{ pct }}%</small>
                    </div>
                  </td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </div>

        <!-- ADDITIONAL STATS -->
        <div class="row g-3">
          <div class="col-md-6">
            <div class="glass-pane">
              <div class="pane-title mb-3"><i class="fas fa-calendar-check"></i> حالة المواعيد</div>
              <div class="d-flex justify-content-between mb-2">
                <span class="fw-bold">إجمالي المواعيد</span>
                <span>{{ appointments[p]['total'] }}</span>
              </div>
              <div class="d-flex justify-content-between mb-2">
                <span class="fw-bold">مكتملة</span>
                <span class="text-success">{{ appointments[p]['completed'] }}</span>
              </div>
              <div class="d-flex justify-content-between">
                <span class="fw-bold text-danger">ملغاة</span>
                <span class="badge-pill badge-danger">{{ appointments[p]['cancelled'] }} ({{ cancel_rate[p] }}%)</span>
              </div>
            </div>
          </div>
          <div class="col-md-6">
            <div class="glass-pane">
              <div class="pane-title mb-3"><i class="fas fa-radiation"></i> الأشعة والسونار</div>
              <div class="d-flex justify-content-between mb-2">
                <span class="fw-bold">إجمالي الطلبات</span>
                <span>{{ radiology[p]['cnt'] }}</span>
              </div>
              <div class="d-flex justify-content-between">
                <span class="fw-bold">الإيراد</span>
                <span class="text-warning fw-bold">{{ "{:,.0f}".format(radiology[p]['rev']) }} {{ currency }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <div class="dash-side">
        <!-- SIDE WIDGETS -->
        <div class="side-widget">
          <div class="side-widget-header"><i class="fas fa-bell text-danger"></i> تنبيهات مالية</div>
          <div class="list-item">
            <span>ذمم غير مسددة (اليوم)</span>
            <span class="text-danger fw-bold">{{ unpaid_cnt['day'] }}</span>
          </div>
          <div class="list-item">
            <span>مبلغ الذمم (اليوم)</span>
            <span class="text-danger fw-bold">{{ "{:,.0f}".format(unpaid_amt['day']) }}</span>
          </div>
           <div class="list-item">
            <span>متابعات مجانية</span>
            <span class="text-success fw-bold">{{ free_follows['day'] }}</span>
          </div>
        </div>

        <div class="side-widget">
          <div class="side-widget-header"><i class="fas fa-flask"></i> أكثر التحاليل طلباً</div>
          {% for t in top_labs[:5] %}
          <div class="list-item">
            <span class="small fw-bold">{{ t.test_name }}</span>
            <span class="badge-pill badge-primary">{{ t.cnt }}</span>
          </div>
          {% endfor %}
        </div>

        <div class="side-widget">
          <div class="side-widget-header"><i class="fas fa-fire text-warning"></i> ساعات الذروة</div>
          <div class="hour-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            {% for h in peak_hours[:4] %}
            <div style="background: var(--input-bg); padding: 10px; border-radius: 12px; text-align: center;">
              <div class="small opacity-50 fw-bold">{{ h.hr }}:00</div>
              <div class="fw-900 text-primary">{{ h.cnt }}</div>
            </div>
            {% endfor %}
          </div>
        </div>

        <div class="side-widget">
          <div class="side-widget-header"><i class="fas fa-users"></i> المرضى الجدد</div>
          <div class="list-item">
            <span>مسجلين اليوم</span>
            <span class="fw-bold">{{ new_patients['day'] }}</span>
          </div>
          <div class="list-item">
            <span>هذا الأسبوع</span>
            <span class="fw-bold">{{ new_patients['week'] }}</span>
          </div>
          <div class="list-item">
            <span>هذا الشهر</span>
            <span class="fw-bold">{{ new_patients['month'] }}</span>
          </div>
        </div>
      </div>
    </div>

  </div>
  {% endfor %}

  <!-- 4. MONTHLY COMPARISON -->
  <div class="cmp-banner">
    <div>
      <div class="cmp-lbl">مقارنة الإيراد الشهري (الحالي vs السابق)</div>
      <div class="cmp-val">{{ "{:,.0f}".format(month_vs_prev['current']) }} <small style="font-size:1.5rem">{{ currency }}</small></div>
      <div class="mt-2 fw-bold opacity-75">
        {% if month_vs_prev['up'] %}
        <i class="fas fa-arrow-up me-1"></i> ارتفاع بنسبة {{ month_vs_prev['pct'] }}% عن الشهر الماضي
        {% else %}
        <i class="fas fa-arrow-down me-1"></i> انخفاض بنسبة {{ month_vs_prev['pct'] }}% عن الشهر الماضي
        {% endif %}
      </div>
    </div>
    <div style="text-align: left;">
      <div class="cmp-lbl">فارق الأداء النقدي</div>
      <div class="cmp-val" style="{% if month_vs_prev['up'] %}color:#30d158{% else %}color:#ff3b30{% endif %}">
        {{ "{:+,.0f}".format(month_vs_prev['diff']) }}
      </div>
    </div>
  </div>

  <!-- 5. TREND CHARTS -->
  <div class="row g-3">
    <div class="col-md-8">
      <div class="glass-pane">
        <div class="pane-title mb-4"><i class="fas fa-chart-area"></i> منحنى النمو المالي (آخر 7 أيام)</div>
        <div class="chart-container">
          <canvas id="mainTrendChart"></canvas>
        </div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="glass-pane">
        <div class="pane-title mb-4"><i class="fas fa-building"></i> إيراد الأقسام (شهري)</div>
        <div class="table-responsive">
          <table class="modern-table">
            <tbody>
              {% for dep in dept_revenue[:5] %}
              {% set bar_w = ((dep.month_rev / max_dept_rev * 100) | int) if max_dept_rev > 0 else 0 %}
              <tr>
                <td>{{ dep.dept }}</td>
                <td class="text-end fw-bold">{{ "{:,.0f}".format(dep.month_rev) }}</td>
                <td style="width:80px">
                  <div class="prog-bar"><div class="prog-fill" style="width:{{ bar_w }}%"></div></div>
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

</div>

<!-- ── GLOBAL REPORT BUILDER MODAL ── -->
<div id="ReportBuilderModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:9999; backdrop-filter: blur(8px); align-items:center; justify-content:center;">
  <div class="glass-pane" style="width: 700px; max-width: 95%; background: white; color: #1c1c1e; max-height: 90vh; overflow-y: auto;">
    <div class="glass-pane-header">
      <div class="pane-title"><i class="fas fa-file-invoice-dollar text-primary"></i> منشئ التقارير الاحترافي</div>
      <button class="btn btn-sm btn-light rounded-circle" onclick="closeReportModal()"><i class="fas fa-times"></i></button>
    </div>
    <div style="padding: 25px;">
      <p class="small opacity-75 mb-4">اختر الأقسام والبيانات التي تود تضمينها في التقرير المطبوع:</p>
      
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px;">
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="rev" checked> إجمالي الإيرادات</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="inv_cnt" checked> إحصائيات الفواتير</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="unpaid" checked> المستحقات والديون</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="avg_inv"> متوسط قيمة الفاتورة</label>
        
        <div style="font-weight: 800; font-size: 13px; grid-column: span 2; border-bottom: 1px solid #eee; padding-bottom: 5px; color: #28a745; margin-top: 10px;">النشاط الطبي والعيادات</div>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="pat_cnt" checked> عدد المرضى الكلي</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="labs" checked> قسم المختبر</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="rads" checked> قسم الأشعة</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="phar" checked> قسم الصيدلية</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="free" checked> المراجعات المجانية</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="apps"> حالة المواعيد (ملغاة/مكتملة)</label>

        <div style="font-weight: 800; font-size: 13px; grid-column: span 2; border-bottom: 1px solid #eee; padding-bottom: 5px; color: #6f42c1; margin-top: 10px;">الأداء والتحليل</div>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="docs_table"> جدول أداء الأطباء</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="depts_table"> جدول نشاط الأقسام</label>
        <label class="d-flex align-items-center gap-2 small"><input type="checkbox" class="rep-opt" value="peak"> أوقات ذروة الزيارات</label>
      </div>

      <div class="alert alert-secondary py-2 small mb-4">
        <i class="fas fa-magic me-1"></i> سيتم بناء التقرير بناءً على الفترة الزمنية المحددة حالياً في الشاشة.
      </div>

      <div class="d-flex gap-2">
        <button class="btn btn-primary flex-grow-1 rounded-pill fw-bold" onclick="printSummary()">
          <i class="fas fa-bolt me-1"></i> توليد وطباعة التقرير المخصص
        </button>
        <button class="btn btn-light rounded-pill px-4" onclick="closeReportModal()">إغاء</button>
      </div>
    </div>
  </div>
</div>

<script>
// ── DATA INITIALIZATION ──
const fullStats = {{ full_stats_json | safe }};
const drActivity = {{ dr_activity | tojson | safe }};
const doctorsData = {{ doctors | tojson | safe }};
const systemName = "{{ system_name }}";
const trendData = {{ trend_json | safe }};
const monthData = {{ month_bar_json | safe }};
const fmt = (v) => new Intl.NumberFormat('en-US').format(v || 0);

// ── DOCTOR DETAILS MODAL ──
function showDoctorDetails(id, p) {
    const dr = doctorsData.find(d => d.user_id == id);
    if(!dr) return;
    
    const seen = dr[p+'_seen'] || 0;
    const rev = dr[p+'_rev'] || 0;
    const male = dr[p+'_male'] || 0;
    const female = dr[p+'_female'] || 0;
    const labs = dr[p+'_lab'] || 0;
    const rads = dr[p+'_rad'] || 0;
    const period = p == 'day' ? 'اليوم' : p == 'week' ? 'الأسبوع' : p == 'month' ? 'الشهر' : 'السنة';

    let html = `
    <div style="text-align: right; direction: rtl; animation: modalFadeIn 0.4s ease-out;">
        <div style="background: linear-gradient(135deg, #007aff, #0056b3); margin: -40px -40px 30px -40px; padding: 40px; border-radius: 30px 30px 0 0; color: white;">
            <h3 class="fw-900 mb-1" style="letter-spacing: -0.5px;">${dr.full_name_ar}</h3>
            <div class="opacity-75 fw-bold"><i class="fas fa-id-card-alt me-1"></i> الملف التعريفي للأداء - ${period}</div>
        </div>

        <div class="row g-4">
            <div class="col-md-6">
                <div class="stat-premium-card" style="border-right: 4px solid #007aff;">
                    <div class="icon-circle" style="background: rgba(0,122,255,0.1); color: #007aff;"><i class="fas fa-users"></i></div>
                    <div>
                        <div class="label">إجمالي المرضى</div>
                        <div class="value">${seen}</div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="stat-premium-card" style="border-right: 4px solid #30d158;">
                    <div class="icon-circle" style="background: rgba(48,209,88,0.1); color: #30d158;"><i class="fas fa-wallet"></i></div>
                    <div>
                        <div class="label">الإيراد المحقق</div>
                        <div class="value" style="color: #248a3d;">${fmt(rev)}</div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-premium-card mini">
                    <div class="label text-primary"><i class="fas fa-mars"></i> ذكور</div>
                    <div class="value-mini">${male}</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-premium-card mini">
                    <div class="label text-danger"><i class="fas fa-venus"></i> إناث</div>
                    <div class="value-mini">${female}</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-premium-card mini">
                    <div class="label text-info"><i class="fas fa-vials"></i> مختبر</div>
                    <div class="value-mini">${labs}</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-premium-card mini">
                    <div class="label text-purple"><i class="fas fa-radiation"></i> أشعة</div>
                    <div class="value-mini">${rads}</div>
                </div>
            </div>
        </div>

        <div class="mt-5 d-flex gap-3 justify-content-center">
            <button class="btn btn-primary rounded-pill px-5 py-3 fw-900 shadow-lg" onclick="printOneDoctor('${id}', '${p}')">
                <i class="fas fa-print me-2"></i> استخراج التقرير الرسمي
            </button>
            <button class="btn btn-light rounded-pill px-4 fw-bold" onclick="document.getElementById('drDetailModal').remove()">إغلاق</button>
        </div>
    </div>
    <style>
        @keyframes modalFadeIn { from { opacity: 0; transform: scale(0.95) translateY(20px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        .stat-premium-card { background: #f8f9fa; padding: 20px; border-radius: 20px; display: flex; align-items: center; gap: 15px; border: 1px solid #eee; transition: 0.3s; }
        .stat-premium-card:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.05); background: #fff; }
        .stat-premium-card.mini { flex-direction: column; text-align: center; gap: 5px; padding: 15px; }
        .stat-premium-card .icon-circle { width: 45px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
        .stat-premium-card .label { font-size: 0.75rem; font-weight: 800; opacity: 0.6; text-transform: uppercase; }
        .stat-premium-card .value { font-size: 1.8rem; font-weight: 900; line-height: 1; }
        .stat-premium-card .value-mini { font-size: 1.3rem; font-weight: 900; }
    </style>`;

    const m = document.createElement('div');
    m.id = 'drDetailModal';
    m.style = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:10000; display:flex; align-items:center; justify-content:center; backdrop-filter:blur(15px); transition: 0.3s;';
    m.innerHTML = `<div style="width:750px; max-width:95%; background:white; padding:40px; border-radius:40px; position:relative; box-shadow: 0 25px 50px rgba(0,0,0,0.3);">
        ${html}
    </div>`;
    document.body.appendChild(m);
}

function printOneDoctor(id, p) {
    const dr = doctorsData.find(d => d.user_id == id);
    if(!dr) return;
    
    const seen = dr[p+'_seen'] || 0;
    const rev = dr[p+'_rev'] || 0;
    const male = dr[p+'_male'] || 0;
    const female = dr[p+'_female'] || 0;
    const labs = dr[p+'_lab'] || 0;
    const rads = dr[p+'_rad'] || 0;
    const period = p == 'day' ? 'اليوم' : p == 'week' ? 'الأسبوع' : p == 'month' ? 'الشهر' : 'السنة';

    const html = `
    <html><head><style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');
        @page { size: landscape; margin: 15mm; }
        body { direction: rtl; font-family: 'Tajawal', sans-serif; background: #fff; color: #1a1a1a; margin: 0; padding: 0; line-height: 1.5; }
        .print-container { padding: 0; }
        .p-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; border-bottom: 5px solid #000; padding-bottom: 20px; }
        .sys-name { font-size: 28px; font-weight: 900; color: #000; margin-bottom: 5px; }
        .rep-type { font-size: 16px; font-weight: 700; color: #666; background: #f0f0f0; display: inline-block; padding: 5px 15px; border-radius: 5px; }
        .meta-info { text-align: left; }
        .meta-info div { font-weight: 700; margin-bottom: 5px; }
        
        .dr-banner { background: #f8f9fa; border: 1px solid #ddd; padding: 25px; border-radius: 15px; margin-bottom: 35px; display: flex; justify-content: space-between; align-items: center; }
        .dr-name { font-size: 24px; font-weight: 900; color: #000; }
        .dr-dept { font-size: 18px; font-weight: 700; color: #007aff; }

        .stats-table { width: 100%; border-collapse: collapse; margin-bottom: 40px; box-shadow: 0 0 0 1px #000; border-radius: 10px; overflow: hidden; }
        .stats-table th { background: #000; color: #fff; padding: 18px; font-size: 15px; font-weight: 800; border: 1px solid #000; }
        .stats-table td { padding: 20px; font-size: 22px; font-weight: 900; text-align: center; border: 1px solid #ddd; }
        .stats-table tr:nth-child(even) { background: #fafafa; }

        .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .sum-card { border: 2px solid #eee; padding: 20px; border-radius: 15px; text-align: center; }
        .sum-card .label { font-size: 14px; font-weight: 800; color: #888; margin-bottom: 10px; }
        .sum-card .val { font-size: 26px; font-weight: 900; color: #000; }

        .p-footer { margin-top: 60px; padding-top: 20px; border-top: 1px solid #eee; display: flex; justify-content: space-between; font-size: 12px; opacity: 0.5; font-weight: 700; }
        .watermark { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-45deg); font-size: 120px; opacity: 0.03; font-weight: 900; pointer-events: none; white-space: nowrap; }
    </style></head><body>
        <div class="watermark">${systemName}</div>
        <div class="print-container">
            <div class="p-header">
                <div>
                    <div class="sys-name">${systemName}</div>
                    <div class="rep-type">تقرير الأداء المهني للطبيب</div>
                </div>
                <div class="meta-info">
                    <div style="font-size: 18px; color: #000;">الفترة: ${period}</div>
                    <div style="opacity: 0.6;">تاريخ الطباعة: ${new Date().toLocaleString('ar-EG')}</div>
                </div>
            </div>

            <div class="dr-banner">
                <div>
                    <div style="font-size: 14px; opacity: 0.6; margin-bottom: 5px;">الطبيب المعني</div>
                    <div class="dr-name">${dr.full_name_ar}</div>
                </div>
                <div style="text-align: left;">
                    <div style="font-size: 14px; opacity: 0.6; margin-bottom: 5px;">القسم الطبي</div>
                    <div class="dr-dept">${dr.dept || 'عام'}</div>
                </div>
            </div>

            <table class="stats-table">
                <thead>
                    <tr>
                        <th style="background:#007aff; border-color:#007aff;">إجمالي المرضى</th>
                        <th>عدد الذكور</th>
                        <th>عدد الإناث</th>
                        <th>المختبر</th>
                        <th>الأشعة</th>
                        <th style="background:#30d158; border-color:#30d158;">إجمالي الإيراد</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="color:#007aff;">${seen}</td>
                        <td>${male}</td>
                        <td>${female}</td>
                        <td>${labs}</td>
                        <td>${rads}</td>
                        <td style="color:#248a3d;">${fmt(rev)} <small style="font-size:12px">د.ع</small></td>
                    </tr>
                </tbody>
            </table>

            <div class="summary-grid">
                <div class="sum-card">
                    <div class="label">تحليل النشاط العام</div>
                    <div class="val">${seen + labs + rads} <small style="font-size:14px">وحدة نشاط</small></div>
                </div>
                <div class="sum-card">
                    <div class="label">نسبة النوع الاجتماعي</div>
                    <div class="val">${seen > 0 ? Math.round(male/seen*100) : 0}% ذكور / ${seen > 0 ? Math.round(female/seen*100) : 0}% إناث</div>
                </div>
                <div class="sum-card">
                    <div class="label">كفاءة التحويلات</div>
                    <div class="val">${seen > 0 ? Math.round((labs+rads)/seen*100) : 0}% <small style="font-size:14px">من المرضى</small></div>
                </div>
            </div>

            <div class="p-footer">
                <div>* هذا التقرير مخصص للإدارة ولا يعتد به كوثيقة طبية للمريض.</div>
                <div>نظام الإدارة المركزي | ${new Date().getFullYear()}</div>
            </div>
        </div>
    </body></html>`;

    const w = window.open('', '_blank');
    w.document.write(html);
    w.document.close();
    setTimeout(() => { w.print(); }, 500);
}

// ── CORE DASHBOARD LOGIC ──
function sw(p) {
    document.querySelectorAll('.rep-tab').forEach(t => t.classList.remove('on'));
    document.querySelectorAll('.psec').forEach(s => s.classList.remove('on'));
    const btn = event ? event.currentTarget : document.querySelector(`[data-p="${p}"]`);
    if(btn) btn.classList.add('on');
    const target = document.getElementById('s-'+p);
    if(target) target.classList.add('on');
}

// ── FINANCIAL MODAL & REPORT ──
// ── REPORT BUILDER LOGIC ──
function openReportModal() { document.getElementById('ReportBuilderModal').style.display='flex'; }
function closeReportModal() { document.getElementById('ReportBuilderModal').style.display='none'; }

function printSummary() {
    const opts = Array.from(document.querySelectorAll('.rep-opt:checked')).map(el => el.value);
    const p = document.querySelector('.rep-tab.on').dataset.p;
    const plbl = document.querySelector('.rep-tab.on').innerText;

    let html = `
    <html><head><style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');
        body { direction: rtl; font-family: 'Tajawal', sans-serif; padding: 40px; color: #1c1c1e; }
        .h-head { border-bottom: 4px solid #000; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
        .h-title { font-size: 24px; font-weight: 900; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-bottom: 15px; page-break-inside: avoid; }
        .c-title { font-size: 15px; font-weight: 800; border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 10px; color: #007aff; }
        .row-val { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 5px; }
        .big { font-size: 20px; font-weight: 900; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 10px; }
        th { background: #f5f5f5; padding: 8px; border: 1px solid #ddd; text-align: right; }
        td { padding: 8px; border: 1px solid #ddd; }
    </style></head><body>
    <div class="h-head">
        <div><div class="h-title">المستشفى التخصصي الحديث - التقرير الشامل</div><div style="opacity:0.7">الفترة: ${plbl} | التاريخ: ${new Date().toLocaleString('ar-EG')}</div></div>
    </div>`;

    if(opts.includes('rev') || opts.includes('pat_cnt')) {
        html += `<div class="grid-2">`;
        if(opts.includes('rev')) {
            html += `<div class="card"><div class="c-title">الملخص المالي</div><div class="big">${fmt(fullStats.revenue[p])} ${fullStats.currency}</div><div class="small opacity-50">صافي الإيرادات المسددة</div></div>`;
        }
        if(opts.includes('pat_cnt')) {
            html += `<div class="card"><div class="c-title">إجمالي عدد المرضى</div><div class="big">${fullStats.revenue_cnt[p]} مريض</div><div class="small opacity-50">زيارات مكتملة ومسددة</div></div>`;
        }
        html += `</div>`;
    }

    if(opts.includes('labs') || opts.includes('rads')) {
        html += `<div class="grid-2">`;
        if(opts.includes('labs')) {
            html += `<div class="card"><div class="c-title">قسم المختبر</div>
                <div class="row-val"><span>عدد الفحوصات</span> <strong>${fullStats.labs[p].cnt}</strong></div>
                <div class="row-val"><span>الإيراد</span> <strong>${fmt(fullStats.labs[p].rev)}</strong></div>
            </div>`;
        }
        if(opts.includes('rads')) {
            html += `<div class="card"><div class="c-title">قسم الأشعة</div>
                <div class="row-val"><span>عدد الطلبات</span> <strong>${fullStats.radiology[p].cnt}</strong></div>
                <div class="row-val"><span>الإيراد</span> <strong>${fmt(fullStats.radiology[p].rev)}</strong></div>
            </div>`;
        }
        html += `</div>`;
    }

    if(opts.includes('phar') || opts.includes('free')) {
        html += `<div class="grid-2">`;
        if(opts.includes('phar')) {
            html += `<div class="card"><div class="c-title">قسم الصيدلية</div>
                <div class="row-val"><span>الوصفات</span> <strong>${fullStats.pharmacy[p].cnt}</strong></div>
                <div class="row-val"><span>الإيراد</span> <strong>${fmt(fullStats.pharmacy[p].rev)}</strong></div>
            </div>`;
        }
        if(opts.includes('free')) {
            html += `<div class="card"><div class="c-title">الخدمات المجانية</div>
                <div class="row-val"><span>المراجعات المجانية</span> <strong style="color:red">${fullStats.free_follows[p]}</strong></div>
            </div>`;
        }
        html += `</div>`;
    }

    if(opts.includes('inv_cnt') || opts.includes('avg_inv')) {
        html += `<div class="grid-2">`;
        if(opts.includes('inv_cnt')) {
            html += `<div class="card"><div class="c-title">إحصائيات الفواتير</div>
                <div class="row-val"><span>إجمالي الفواتير</span> <strong>${fullStats.total_inv[p]}</strong></div>
                <div class="row-val"><span>نسبة التحصيل</span> <strong>${fullStats.collection_rate[p]}%</strong></div>
            </div>`;
        }
        if(opts.includes('avg_inv')) {
            html += `<div class="card"><div class="c-title">متوسط الفاتورة</div><div class="big">${fmt(fullStats.avg_invoice[p])}</div></div>`;
        }
        html += `</div>`;
    }

    if(opts.includes('unpaid')) {
        const up_p = (p === 'day') ? 'day' : 'month';
        html += `<div class="card" style="border-right: 5px solid red;"><div class="c-title text-danger">الذمم والديون المعلقة</div>
            <div class="row-val"><span>الفواتير غير المسددة</span> <strong>${fullStats.unpaid_cnt[up_p]}</strong></div>
            <div class="row-val"><span>إجمالي مبلغ الديون</span> <strong class="text-danger">${fmt(fullStats.unpaid_amt[up_p])}</strong></div>
        </div>`;
    }

    if(opts.includes('depts_table')) {
        html += `<div class="card"><div class="c-title">نشاط الأقسام الطبية</div>
            <table><thead><tr><th>القسم</th><th>الزيارات اليومية</th><th>الإيراد اليومي</th></tr></thead><tbody>
            ${fullStats.dept_revenue.map(d => `<tr><td>${d.dept}</td><td>${d.day_cnt || 0}</td><td>${fmt(d.day_rev || 0)}</td></tr>`).join('')}
            </tbody></table></div>`;
    }

    html += `<div style="margin-top: 50px; text-align: center; opacity: 0.5; font-size: 11px;">تم التوليد بواسطة نظام إدارة المستشفى الذكي</div></body></html>`;

    let f = document.getElementById('printFrame');
    if(!f) { f = document.createElement('iframe'); f.id = 'printFrame'; f.style.display = 'none'; document.body.appendChild(f); }
    const doc = f.contentWindow.document;
    doc.open(); doc.write(html); doc.close();
    setTimeout(() => { f.contentWindow.print(); }, 300);
}

// ── CHART INITIALIZATION ──
document.addEventListener('DOMContentLoaded', () => {
    const ctx = document.getElementById('mainTrendChart').getContext('2d');
    if(ctx) {
        const g = ctx.createLinearGradient(0, 0, 0, 300);
        g.addColorStop(0, 'rgba(0, 122, 255, 0.2)'); g.addColorStop(1, 'rgba(0, 122, 255, 0)');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: trendData.labels,
                datasets: [{ label: 'الإيراد', data: trendData.values, borderColor: '#007aff', backgroundColor: g, fill: true, tension: 0.4 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }
});

// ── DOCTOR PERFORMANCE PRINT ──
function toggleAllDoctors(master) { document.querySelectorAll('.dr-checkbox').forEach(cb => cb.checked = master.checked); }

function printSelectedDoctors() {
    const selectedIds = Array.from(document.querySelectorAll('.dr-checkbox:checked')).map(cb => cb.value);
    if (!selectedIds.length) { alert('يرجى اختيار طبيب واحد على الأقل'); return; }

    const p = document.querySelector('.rep-tab.on').dataset.p;
    const period = p == 'day' ? 'اليوم' : p == 'week' ? 'الأسبوع' : p == 'month' ? 'الشهر' : 'السنة';
    
    // Filter and prepare data
    let selectedDoctors = doctorsData.filter(d => selectedIds.includes(d.user_id.toString()));
    
    // Sort by seen count to find the top performer
    selectedDoctors.sort((a, b) => (b[p+'_seen'] || 0) - (a[p+'_seen'] || 0));
    const maxSeen = selectedDoctors.length > 0 ? (selectedDoctors[0][p+'_seen'] || 0) : 0;

    let rowsHtml = '';
    selectedDoctors.forEach((dr, index) => {
        const seen = dr[p+'_seen'] || 0;
        const free = dr[p+'_free'] || 0;
        const labs = dr[p+'_lab'] || 0;
        const rads = dr[p+'_rad'] || 0;
        const rev  = dr[p+'_rev'] || 0;
        
        // Highlight top performer in green if they have the max seen count and it's > 0
        const isTop = (seen === maxSeen && maxSeen > 0);
        const rowStyle = isTop ? 'background-color: #e8f5e9; font-weight: bold;' : '';
        const nameStyle = isTop ? 'color: #2e7d32;' : '';

        rowsHtml += `
            <tr style="${rowStyle}">
                <td style="text-align: center;">${index + 1}</td>
                <td style="${nameStyle}">${dr.full_name_ar}</td>
                <td style="text-align: center;">${dr.dept || 'عام'}</td>
                <td style="text-align: center;">${seen}</td>
                <td style="text-align: center; color: #d32f2f;">${free}</td>
                <td style="text-align: center;">${labs}</td>
                <td style="text-align: center;">${rads}</td>
                <td style="text-align: left; font-weight: 800;">${fmt(rev)}</td>
            </tr>
        `;
    });

    const html = `
    <html><head><style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');
        @page { size: A4 landscape; margin: 10mm; }
        body { direction: rtl; font-family: 'Tajawal', sans-serif; font-size: 10pt; color: #333; margin: 0; padding: 0; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .system-name { font-size: 16pt; font-weight: 900; }
        .report-title { font-size: 12pt; font-weight: 700; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { background: #f0f0f0; border: 1px solid #333; padding: 8px; font-weight: 800; font-size: 10pt; text-align: center; }
        td { border: 1px solid #333; padding: 8px; font-size: 10pt; }
        .footer { margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px; display: flex; justify-content: space-between; font-size: 8pt; opacity: 0.7; }
        .highlight-legend { margin-top: 15px; font-size: 9pt; display: flex; align-items: center; gap: 10px; }
        .color-box { width: 15px; height: 15px; background: #e8f5e9; border: 1px solid #2e7d32; display: inline-block; }
    </style></head><body>
        <div class="header">
            <div>
                <div class="system-name">${systemName}</div>
                <div class="report-title">تقرير إحصائيات أداء الكادر الطبي الإجمالي</div>
            </div>
            <div style="text-align: left;">
                <div style="font-weight: 800;">الفترة: ${period}</div>
                <div>تاريخ الطباعة: ${new Date().toLocaleString('ar-EG')}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 40px;">#</th>
                    <th>اسم الطبيب</th>
                    <th>القسم</th>
                    <th>عدد المرضى (كشف)</th>
                    <th>مراجعات مجانية</th>
                    <th>تحويلات المختبر</th>
                    <th>تحويلات الأشعة</th>
                    <th>إجمالي الإيرادات (د.ع)</th>
                </tr>
            </thead>
            <tbody>
                ${rowsHtml}
            </tbody>
        </table>

        <div class="highlight-legend">
            <div class="color-box"></div>
            <span>* اللون الأخضر يشير إلى الطبيب الأعلى إنجازاً (من حيث عدد الكشوفات) في هذه القائمة.</span>
        </div>

        <div class="footer">
            <div>تم استخراج هذا التقرير من نظام الإدارة المركزي آلياً.</div>
            <div>نظام الإدارة - جميع الحقوق محفوظة | ${new Date().getFullYear()}</div>
        </div>
    </body></html>`;

    const w = window.open('', '_blank');
    w.document.write(html);
    w.document.close();
    setTimeout(() => { w.print(); }, 500);
}
</script>
""" + footer_html

    return render_template_string(
        html,
        now_str=now_str,
        currency=currency,
        revenue=revenue,
        revenue_cnt=revenue_cnt,
        total_inv=total_inv,
        collection_rate=collection_rate,
        avg_invoice=avg_invoice,
        unpaid_cnt=unpaid_cnt,
        unpaid_amt=unpaid_amt,
        consultations=consultations,
        labs=labs,
        radiology=radiology,
        pharmacy=pharmacy,
        appointments=appointments,
        cancel_rate=cancel_rate,
        free_follows=free_follows,
        scheduled_today=scheduled_today,
        new_patients=new_patients,
        total_patients=total_patients,
        month_vs_prev=month_vs_prev,
        lab_comp_rate=lab_comp_rate,
        lab_pending=lab_pending,
        rad_comp_rate=rad_comp_rate,
        rad_pending=rad_pending,
        doctors=doctors,
        max_day_seen=max_day_seen,
        dept_revenue=dept_revenue,
        max_dept_rev=max_dept_rev,
        top_labs=top_labs,
        top_rad=top_rad,
        peak_hours=peak_hours,
        staff=staff,
        trend_json=trend_json,
        month_bar_json=month_bar_json,
        dr_activity=dr_activity,
        refunds_amt=refunds_amt,
        full_stats_json=full_stats_json,
    )
