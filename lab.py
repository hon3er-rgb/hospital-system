from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access, format_datetime, local_now_naive, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
from datetime import date, datetime, timedelta

lab_bp = Blueprint('lab', __name__)

@lab_bp.route('/lab', methods=['GET', 'POST'])
def lab():
    if not session.get('user_id') or not can_access('lab'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True) # type: ignore
    
    # --- Advanced Filters ---
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', 'all')

    # --- Action: Assign Tests (Direct Lab - no doctor) ---
    if request.method == 'POST' and 'assign_tests' in request.form:
        appt_id = int(request.form.get('appt_id', 0))
        patient_id = int(request.form.get('patient_id', 0))
        selected_tests = request.form.getlist('selected_tests[]')
        
        if selected_tests and appt_id:
            for test_id in selected_tests:
                test_id = int(test_id)
                cursor.execute("SELECT test_name, price FROM lab_tests WHERE test_id = %s", (test_id,))
                t = cursor.fetchone()
                if t:
                    now_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        "INSERT INTO lab_requests (appointment_id, patient_id, doctor_id, test_type, price, status, created_at) VALUES (%s, %s, %s, %s, %s, 'pending_payment', %s)",
                        (appt_id, patient_id, 1, t['test_name'], t['price'], now_ts)
                    )
            # Move appointment to 'scheduled' so it shows in Billing
            cursor.execute("UPDATE appointments SET status = 'scheduled' WHERE appointment_id = %s", (appt_id,))
            conn.commit()  # type: ignore
            flash(f"✅ تم تحديد {len(selected_tests)} تحليل — المريض انتقل للمحاسبة.", "success")
        else:
            flash("⚠️ الرجاء اختيار تحليل واحد على الأقل.", "warning")
        return redirect(url_for('lab.lab'))

    # --- Action: Save Estimated Time ---
    if request.method == 'POST' and 'save_time' in request.form:
        req_id = int(request.form.get('req_id', 0))
        est_time = request.form.get('est_time', '').strip()
        if est_time.isdigit():
            mins = int(est_time)
            end_time = (local_now_naive() + timedelta(minutes=mins)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE lab_requests SET estimated_time_minutes = %s, timer_end_time = %s WHERE request_id = %s", (mins, end_time, req_id))
            conn.commit() # type: ignore
            flash("تم تحديد وقت الإنجاز وإضافته لشاشة الانتظار", "success")
        return redirect(url_for('lab.lab', search=search_query, status=status_filter, date=date_filter))

    # --- Action: Save/Update Result ---
    if request.method == 'POST' and 'save_result' in request.form:
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = 'إجراء فحص مختبري' WHERE user_id = %s", (session['user_id'],))
            
        req_id = int(request.form.get('req_id', 0))
        main_result = request.form.get('result', '')
        
        cursor.execute("DELETE FROM lab_result_details WHERE request_id = %s", (req_id,))
        for key, val in request.form.items():
            if key.startswith('p_result_'):
                param_id = int(key.replace('p_result_', ''))
                if val.strip():
                    cursor.execute("INSERT INTO lab_result_details (request_id, param_id, value) VALUES (%s, %s, %s)", (req_id, param_id, val))

        cursor.execute("SELECT appointment_id FROM lab_requests WHERE request_id = %s", (req_id,))
        req_info = cursor.fetchone()
        
        if req_info:
            appt_id = req_info['appointment_id'] # type: ignore
            cursor.execute("UPDATE lab_requests SET result = %s, status = 'completed' WHERE request_id = %s", (main_result, req_id))
            
            cursor.execute("SELECT COUNT(*) as c FROM lab_requests WHERE appointment_id = %s AND status = 'pending'", (appt_id,))
            rem = cursor.fetchone()['c'] # type: ignore
            
            if rem == 0:
                # Check if this is a direct lab/rad appointment (Dept 3 or 4)
                cursor.execute("SELECT department_id FROM appointments WHERE appointment_id = %s", (appt_id,))
                appt_data = cursor.fetchone()
                if appt_data and appt_data['department_id'] in [3, 4]:
                    cursor.execute("UPDATE appointments SET status = 'completed' WHERE appointment_id = %s", (appt_id,))
                    flash("تم حفظ النتيجة وإكمال ملف المريض بنجاح", "success")
                else:
                    cursor.execute("UPDATE appointments SET status = 'waiting_doctor' WHERE appointment_id = %s", (appt_id,))
                    flash("تم حفظ النتيجة وتحديث حالة المريض", "success")
            else:
                flash("تم حفظ النتيجة بنجاح", "success")
            conn.commit() # type: ignore

        # Build redirect URL with existing filters
        return redirect(url_for('lab.lab', search=search_query, status=status_filter, date=date_filter))

    # 1. Fetch Lab Test Requests with Extended Info (Doctor, Urgent Status)
    query_base = """
        SELECT l.*, p.full_name_ar as p_name, p.file_number, p.photo, p.gender, p.date_of_birth,
               t.unit, t.min_value, t.max_value, t.is_profile, t.test_id,
               d.full_name_ar as doc_name,
               a.is_urgent
        FROM lab_requests l 
        JOIN patients p ON l.patient_id = p.patient_id 
        LEFT JOIN lab_tests t ON l.test_type = t.test_name
        LEFT JOIN users d ON l.doctor_id = d.user_id
        LEFT JOIN appointments a ON l.appointment_id = a.appointment_id
        WHERE 1=1
    """
    params = []

    # Search filter
    if search_query:
        query_base += " AND (p.full_name_ar LIKE %s OR p.file_number LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    
    # Status filter
    if status_filter != 'all':
        query_base += " AND l.status = %s"
        params.append(status_filter)
    elif not search_query:
        query_base += " AND l.status IN ('pending', 'pending_payment')"

    if date_filter == 'today':
        query_base += " AND DATE(l.created_at) = %s"
        params.append(local_today_str())
    
    query_base += " ORDER BY a.is_urgent DESC, l.created_at DESC LIMIT 100"
    
    # 2. Statistics (Pending/Unpaid are global, Completed is today — local calendar day)
    _td = local_today_str()
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN l.status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN l.status = 'pending_payment' THEN 1 END) as unpaid,
            COUNT(CASE WHEN l.status = 'completed' AND DATE(l.created_at) = %s THEN 1 END) as completed,
            COUNT(CASE WHEN a.is_urgent = 1 AND l.status != 'completed' THEN 1 END) as urgent
        FROM lab_requests l
        LEFT JOIN appointments a ON l.appointment_id = a.appointment_id
    """, (_td,))
    stats_row = cursor.fetchone()
    stats = {
        'pending': stats_row['pending'] if stats_row else 0, # type: ignore
        'unpaid': stats_row['unpaid'] if stats_row else 0, # type: ignore
        'completed': stats_row['completed'] if stats_row else 0, # type: ignore
        'urgent': stats_row['urgent'] if stats_row else 0 # type: ignore
    }

    cursor.execute(query_base, tuple(params))
    all_requests = cursor.fetchall()

    # 3. Grouping
    def calc_age(dob):
        if not dob: return "?"
        today = local_now_naive().date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    grouped = {}
    for r in all_requests:
        key = f"{r['appointment_id']}_{r['patient_id']}"
        if key not in grouped:
            grouped[key] = {
                'p_name': r['p_name'],
                'file_number': r['file_number'],
                'photo': r['photo'],
                'gender': r['gender'],
                'age': calc_age(r['date_of_birth']),
                'doc_name': r['doc_name'] or "غير محدد",
                'is_urgent': r['is_urgent'],
                'tests': []
            }
        
        params_list = []
        if r['is_profile']:
            q = """
                SELECT p.*, d.value as saved_val 
                FROM lab_test_parameters p
                LEFT JOIN lab_result_details d ON p.param_id = d.param_id AND d.request_id = %s
                WHERE p.test_id = %s 
                ORDER BY p.sort_order ASC
            """
            cursor.execute(q, (r['request_id'], r['test_id']))
            params_list = cursor.fetchall() # type: ignore
        
        r['params'] = params_list
        grouped[key]['tests'].append(r) # type: ignore

    # 4. Fetch patients waiting for test selection (Direct Lab bookings)
    cursor.execute("""
        SELECT a.appointment_id, a.patient_id, a.created_at,
               p.full_name_ar, p.file_number, p.photo, p.gender, p.date_of_birth
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.status = 'pending_lab_selection'
          AND DATE(a.appointment_date) = %s
        ORDER BY a.created_at ASC
    """, (local_today_str(),))  # type: ignore
    pending_selection = cursor.fetchall()

    # 5. Available lab tests for the selection panel
    cursor.execute("SELECT test_id, test_name, price, is_profile FROM lab_tests WHERE is_active = 1 ORDER BY test_name")
    available_tests = cursor.fetchall()

    html = header_html + """
    <style>
        /* ===== ADAPTIVE DESIGN SYSTEM ===== */
        :root {
            --lab-bg: #f0f2f5;
            --lab-card: #ffffff;
            --lab-header: rgba(255, 255, 255, 0.8);
            --lab-text: #1e293b;
            --lab-text-muted: #64748b;
            --lab-border: #e2e8f0;
            --lab-accent: #3b82f6;
            --lab-accent-gradient: linear-gradient(135deg, #3b82f6, #6366f1);
            --lab-input-bg: #ffffff;
            --lab-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            --lab-row-hover: #f8fafc;
            --lab-stat-bg: #ffffff;
        }

        

        body { background: var(--lab-bg) !important; color: var(--lab-text) !important; transition: background 0.4s ease, color 0.4s ease; }
        .lab-container { max-width: 1240px; margin: 0 auto; padding: 20px; font-family: 'Cairo', sans-serif; position: relative; min-height: 100vh; }

        /* ===== UNIFIED HEADER (ADAPTIVE) ===== */
        .lab-unified-header {
            background: var(--lab-header);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--lab-border);
            border-radius: 20px; padding: 10px 20px; margin-bottom: 30px;
            display: flex; align-items: center; justify-content: space-between;
            direction: rtl; gap: 20px; box-shadow: var(--lab-shadow);
        }

        .header-brand-mini { display: flex; align-items: center; gap: 12px; }
        .brand-icon-mini { 
            width: 42px; height: 42px; border-radius: 12px; 
            background: var(--lab-accent-gradient);
            display: flex; align-items: center; justify-content: center; color: #fff; font-size: 1.2rem;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        }
        .brand-text-mini h1 { font-size: 1rem; font-weight: 800; color: var(--lab-text) !important; margin: 0; letter-spacing: -0.3px; }
        .brand-text-mini p { font-size: 0.65rem; color: var(--lab-text-muted); margin: 0; font-weight: 600; }

        .header-tools-group { display: flex; align-items: center; gap: 8px; margin-right: auto; }
        .mini-btn {
            width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
            color: var(--lab-text-muted); background: var(--lab-stat-bg); border: 1px solid var(--lab-border);
            font-size: 0.9rem; transition: 0.3s; text-decoration: none;
        }
        .mini-btn:hover { background: var(--lab-row-hover); color: var(--lab-accent); transform: translateY(-3px); border-color: var(--lab-accent); }

        .search-mini {
            display: flex; align-items: center; background: var(--lab-input-bg); border-radius: 12px;
            padding: 0 14px; border: 1px solid var(--lab-border); width: 160px; margin-left: 5px;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .search-mini:focus-within { width: 240px; border-color: var(--lab-accent); box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15); }
        .search-mini input { background: none; border: none; outline: none; color: var(--lab-text); font-size: 0.8rem; width: 100%; padding: 8px 0; text-align: right; font-family: 'Cairo'; }
        .search-mini i { color: var(--lab-text-muted); font-size: 0.85rem; }
        
        .header-stats-group { display: flex; gap: 10px; align-items: center; }
        .mini-stat {
            display: flex; align-items: center; gap: 12px; padding: 6px 18px;
            background: var(--lab-stat-bg); border: 1px solid var(--lab-border);
            border-radius: 14px; text-decoration: none !important; transition: 0.3s; height: 44px;
        }
        .mini-stat:hover { transform: translateY(-3px); border-color: var(--lab-accent); background: var(--lab-row-hover); }
        .mini-stat-val { font-size: 1.2rem; font-weight: 800; line-height: 1; }
        .mini-stat-label { font-size: 0.6rem; color: var(--lab-text-muted); font-weight: 700; text-transform: uppercase; }
        
        .stat-purple { color: #8b5cf6; } .stat-orange { color: #f59e0b; } .stat-green { color: #10b981; } .stat-red { color: #ef4444; }
        .action-divider { width: 1px; height: 20px; background: var(--lab-border); margin: 0 10px; }

        /* ===== PATIENT CARDS (ADAPTIVE) ===== */
        .patient-card {
            background: var(--lab-card); border: 1px solid var(--lab-border); border-radius: 18px;
            margin-bottom: 15px; overflow: hidden; transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1); position: relative;
            box-shadow: var(--lab-shadow);
        }
        .patient-card:hover { transform: translateY(-4px); background: var(--lab-row-hover); border-color: var(--lab-accent); }
        
        .urgent-card { border: 1px solid rgba(239, 68, 68, 0.2) !important; }
        .urgent-card::after { content: ''; position: absolute; top:0; right:0; width:5px; height:100%; background:#ef4444; box-shadow: -2px 0 15px rgba(239, 68, 68, 0.4); }

        .card-header-lab { padding: 20px 25px; cursor: pointer; display: flex; align-items: center; justify-content: space-between; direction: rtl; }
        .p-name { color: var(--lab-text) !important; font-size: 1.05rem !important; font-weight: 800; }
        .p-meta { font-size: 0.8rem; color: var(--lab-text-muted); display: flex; gap: 20px; margin-top: 6px; font-weight: 600; }
        .p-avatar { width: 52px; height: 52px; border-radius: 14px; object-fit: cover; background: var(--lab-bg); border: 1px solid var(--lab-border); display: flex; align-items: center; justify-content: center; color: var(--lab-accent); font-size: 1.3rem; }
        
        .test-count-chip { font-size: 0.75rem; background: rgba(59, 130, 246, 0.1); color: #3b82f6; padding: 6px 18px; border-radius: 20px; font-weight: 800; border: 1px solid rgba(59, 130, 246, 0.2); }
        .chevron-icon { color: var(--lab-text-muted); font-size: 1rem; transition: 0.3s; }
        .patient-card.active .chevron-icon { transform: rotate(-90deg); color: var(--lab-accent); }
        .ai-assist-badge { font-size:0.65rem; background: linear-gradient(135deg, #FF6FD8, #3813C2); color:white; padding:3px 8px; border-radius:50px; font-weight:bold; margin-right:10px; }

        /* ===== TEST ITEM ===== */
        .test-item { padding: 20px 25px; border-top: 1px solid var(--lab-border); direction: rtl; }
        .test-header-row { 
            background: var(--lab-bg); border-radius: 16px; padding: 15px 22px;
            border: 1px solid var(--lab-border); display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 5px;
        }
        .test-title { color: var(--lab-text); font-weight: 800; font-size: 1rem; margin: 0; }
        .status-badge { font-size: 0.75rem; padding: 5px 15px; border-radius: 50px; font-weight: 700; display: inline-flex; align-items: center; gap: 8px; }
        .status-paid { background: rgba(16, 185, 129, 0.1); color: #10b981; }
        .status-unpaid { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }

        .param-table { width: 100%; border-collapse: separate; border-spacing: 0 5px; margin-top: 10px; }
        .param-table th { color: var(--lab-text-muted); font-size: 0.75rem; padding: 10px 18px; text-align: right; font-weight: 800; }
        .param-table td { background: var(--lab-card); padding: 12px 18px; color: var(--lab-text); font-size: 0.9rem; border-top: 1px solid var(--lab-border); }
        .param-table tr:hover td { background: var(--lab-row-hover); color: var(--lab-text); }
        
        .result-input { 
            background: var(--lab-bg); border: 1px solid var(--lab-border); 
            color: var(--lab-text); border-radius: 10px; padding: 8px 15px; width: 100%; text-align: center; font-size: 0.9rem; font-family: 'Cairo'; transition: 0.3s;
        }
        .result-input:focus { border-color: var(--lab-accent); outline: none; box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); }
        
        /* AI colors injected dynamically */

        .lab-time-control { display: flex; align-items: center; background: var(--lab-bg); border-radius: 10px; border: 1px solid var(--lab-border); height: 38px; overflow: hidden; }
        .time-btn-submit { background: var(--lab-accent); color: #fff; border: none; height: 100%; width: 38px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s; }
        .time-btn-submit:hover { background: #2563eb; }
        .time-input-field { background: none; border: none; width: 45px; text-align: center; color: var(--lab-text); font-size: 1rem; font-weight: 800; outline: none; }
        .time-label { font-size: 0.75rem; color: var(--lab-text-muted); padding-right: 12px; font-weight: 700; }

        .btn-save-mini { 
            background: var(--lab-accent-gradient); color: #fff; border: none; 
            padding: 0 25px; height: 38px; border-radius: 10px; font-size: 0.85rem; font-weight: 800; cursor: pointer; transition: all 0.3s;
            box-shadow: 0 6px 15px rgba(59, 130, 246, 0.3);
        }
        .btn-save-mini:hover { transform: scale(1.05); box-shadow: 0 8px 25px rgba(59, 130, 246, 0.4); }

        @keyframes animateIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        .animate-in { animation: animateIn 0.6s cubic-bezier(0.19, 1, 0.22, 1) both; }
    </style>

    <div class="lab-container">
        <!-- ===== UNIFIED HEADER PANEL ===== -->
        <div class="lab-unified-header animate-in">
            <!-- Brand -->
            <a href="{{ url_for('lab.lab') }}" class="header-brand-mini text-decoration-none">
                <div class="brand-icon-mini"><i class="fas fa-microscope"></i></div>
                <div class="brand-text-mini">
                    <h1>نظام المختبر المتطور</h1>
                    <p>الإدارة الذكية والنتائج</p>
                </div>
            </a>

            <!-- Actions -->
            <div class="header-tools-group">
                <a href="{{ url_for('dashboard.dashboard') }}" class="mini-btn" title="الرئيسية"><i class="fas fa-home"></i></a>
                <a href="{{ url_for('patient_index.patient_index') }}" class="mini-btn" title="الفهرس" style="color:#3b82f6;"><i class="fas fa-address-book"></i></a>
                <a href="{{ url_for('archive.archive') }}" class="mini-btn" title="سجل المرضى" style="color:#6366f1;"><i class="fas fa-history"></i></a>
                <a href="{{ url_for('lab.lab', status='completed', date='today') }}" class="mini-btn" title="مكتمل اليوم" style="color:#10b981;"><i class="fas fa-check-double"></i></a>
                <a href="{{ url_for('lab.lab') }}" class="mini-btn" title="تحديث"><i class="fas fa-sync-alt"></i></a>

                <div class="action-divider"></div>

                <!-- Mini Search -->
                <div class="search-mini">
                    <i class="fas fa-search"></i>
                    <form action="" method="GET" class="m-0 w-100">
                        <input type="text" name="search" placeholder="بحث سريع..." value="{{ request.args.get('search', '') }}">
                    </form>
                </div>
            </div>

            <!-- Stats -->
            <div class="header-stats-group">
                <a href="{{ url_for('lab.lab', status='pending') }}" class="mini-stat">
                    <div class="mini-stat-val stat-purple">{{ stats.pending }}</div>
                    <div class="mini-stat-label">قيد العمل</div>
                </a>
                <a href="{{ url_for('lab.lab', status='pending_payment') }}" class="mini-stat">
                    <div class="mini-stat-val stat-orange">{{ stats.unpaid }}</div>
                    <div class="mini-stat-label">المحاسبة</div>
                </a>
                <a href="{{ url_for('lab.lab', status='completed') }}" class="mini-stat">
                    <div class="mini-stat-val stat-green">{{ stats.completed }}</div>
                    <div class="mini-stat-label">منجز اليوم</div>
                </a>
                <a href="{{ url_for('lab.lab', search='urgent') }}" class="mini-stat">
                    <div class="mini-stat-val stat-red">{{ stats.urgent }}</div>
                    <div class="mini-stat-label">عاجل</div>
                </a>
            </div>
        </div>

        <!-- ===== DIRECT LAB: Pending Test Selection ===== -->
        {% if pending_selection %}
        <div class="animate-in" style="margin-bottom:25px;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding:8px 0;border-bottom:2px solid rgba(14,165,233,0.2);">
                <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#0ea5e9,#06b6d4);display:flex;align-items:center;justify-content:center;color:#fff;font-size:1rem;">
                    <i class="fas fa-clipboard-list"></i>
                </div>
                <div>
                    <span style="font-weight:800;font-size:0.95rem;color:var(--lab-text);">مرضى بانتظار تحديد التحاليل</span>
                    <span style="font-size:0.7rem;color:var(--lab-text-muted);display:block;">حجز مباشر — بدون كشفية</span>
                </div>
                <span style="margin-right:auto;background:rgba(14,165,233,0.1);color:#0ea5e9;padding:4px 14px;border-radius:20px;font-size:0.8rem;font-weight:800;border:1px solid rgba(14,165,233,0.2);">{{ pending_selection|length }}</span>
            </div>

            {% for ps in pending_selection %}
            <div class="patient-card" style="border:1.5px solid rgba(14,165,233,0.25);margin-bottom:12px;">
                <div class="card-header-lab" data-bs-toggle="collapse" data-bs-target="#sel-{{ ps.appointment_id }}" onclick="this.parentElement.classList.toggle('active')">
                    <div class="d-flex align-items-center gap-3 flex-grow-1">
                        {% if ps.photo %}
                            <img src="/{{ ps.photo }}" class="p-avatar shadow-sm border-0">
                        {% else %}
                            <div class="p-avatar border-0" style="background:rgba(14,165,233,0.08);"><i class="fas fa-user" style="color:#0ea5e9;"></i></div>
                        {% endif %}
                        <div>
                            <span class="p-name fs-6" style="font-weight:800;">{{ ps.full_name_ar }}</span>
                            <div style="font-size:0.78rem;color:var(--lab-text-muted);margin-top:2px;">
                                <span><i class="fas fa-hashtag"></i> {{ ps.file_number }}</span>
                                <span class="ms-3"><i class="fas fa-vial"></i> مختبر مباشر</span>
                            </div>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span style="font-size:0.75rem;background:rgba(14,165,233,0.1);color:#0ea5e9;padding:5px 14px;border-radius:20px;font-weight:800;border:1px solid rgba(14,165,233,0.2);"><i class="fas fa-hand-pointer me-1"></i> اختر التحاليل</span>
                        <i class="fas fa-chevron-left chevron-icon"></i>
                    </div>
                </div>

                <div id="sel-{{ ps.appointment_id }}" class="collapse">
                    <div class="px-4 pb-4 pt-2 border-top" style="direction:rtl;">
                        <form method="POST" class="m-0">
                            <input type="hidden" name="assign_tests" value="1">
                            <input type="hidden" name="appt_id" value="{{ ps.appointment_id }}">
                            <input type="hidden" name="patient_id" value="{{ ps.patient_id }}">
                            
                            <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
                                <input type="text" class="result-input" placeholder="ابحث عن تحليل..." oninput="filterTests(this, 'tests-grid-{{ ps.appointment_id }}')" style="max-width:300px;border-radius:10px;padding:8px 14px;font-size:0.85rem;">
                                <span style="font-size:0.72rem;color:var(--lab-text-muted);">اختر التحاليل المطلوبة:</span>
                            </div>

                            <div class="row g-2" id="tests-grid-{{ ps.appointment_id }}">
                                {% for t in available_tests %}
                                <div class="col-md-4 col-lg-3 test-item-box" data-name="{{ t.test_name }}">
                                    <label style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:12px;border:1.5px solid var(--lab-border);background:var(--lab-bg);cursor:pointer;transition:all 0.2s;font-size:0.82rem;font-weight:600;color:var(--lab-text);">
                                        <input type="checkbox" name="selected_tests[]" value="{{ t.test_id }}" style="width:18px;height:18px;accent-color:#0ea5e9;" onchange="this.closest('label').style.borderColor = this.checked ? '#0ea5e9' : ''; this.closest('label').style.background = this.checked ? 'rgba(14,165,233,0.06)' : '';">
                                        <span>{{ t.test_name }}</span>
                                        {% if t.is_profile %}<span style="font-size:0.6rem;background:rgba(59,130,246,0.1);color:#3b82f6;padding:1px 6px;border-radius:6px;margin-right:auto;">بروفايل</span>{% endif %}
                                        <span style="font-size:0.7rem;color:var(--lab-text-muted);margin-right:auto;">{{ "{:,.0f}".format(t.price) }}</span>
                                    </label>
                                </div>
                                {% endfor %}
                            </div>

                            <div class="d-flex justify-content-between align-items-center mt-3 pt-3 border-top">
                                <button type="submit" class="btn-save-mini d-flex align-items-center gap-2" style="border-radius:12px;padding:0 28px;height:42px;">
                                    <i class="fas fa-check-circle"></i> تأكيد التحاليل وإرسال للمحاسبة
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- ===== PATIENT LIST ===== -->
        {% for key, data in grouped.items() %}
        <div class="patient-card animate-in {{ 'urgent-card' if data.is_urgent }}" style="animation-delay: {{ loop.index0 * 0.07 }}s">

            <!-- Card Header Row -->
            <div class="card-header-lab" data-bs-toggle="collapse" data-bs-target="#collapse-{{ loop.index }}" onclick="this.parentElement.classList.toggle('active')">

                <!-- RIGHT: Avatar + Name + Meta -->
                <div class="d-flex align-items-center gap-3 flex-grow-1">
                    {% if data.photo %}
                        <img src="/{{ data.photo }}" class="p-avatar shadow-sm border-0">
                    {% else %}
                        <div class="p-avatar border-0" style="background:rgba(67, 24, 255, 0.05);"><i class="fas fa-user text-primary"></i></div>
                    {% endif %}
                    <div class="d-flex align-items-center flex-wrap gap-3">
                        <div class="d-flex align-items-center gap-2">
                            {% if data.is_urgent %}
                                <span class="badge-stat" style="background:rgba(239, 68, 68, 0.15);color:#dc3545;">STAT ⚡</span>
                            {% endif %}
                            <span class="p-name fs-6" style="font-weight: 800;">{{ data.p_name }}</span>
                            <span class="ai-assist-badge"><i class="fas fa-robot"></i> تقييم ذكي</span>
                        </div>
                        <div class="d-flex align-items-center gap-3 m-0" style="font-size: 0.8rem;">
                            <span class="text-primary fw-bold"><i class="fas fa-user-md"></i> د. {{ data.doc_name }}</span>
                            <span class="text-muted"><i class="fas fa-hashtag"></i> {{ data.file_number }}</span>
                            <span class="text-muted"><i class="fas fa-birthday-cake"></i> {{ data.age }} سنة</span>
                        </div>
                    </div>
                </div>

                <!-- LEFT: test count + chevron -->
                <div class="d-flex align-items-center gap-2">
                    <span class="test-count-chip">{{ data.tests|length }} تحليل</span>
                    <i class="fas fa-chevron-left chevron-icon"></i>
                </div>
            </div>

            <!-- COLLAPSE BODY -->
            <div id="collapse-{{ loop.index }}" class="collapse {{ 'show' if grouped|length == 1 else '' }}">
                <div class="px-4 pb-4 pt-1 border-top">
                    {% for t in data.tests %}
                    <div class="test-item border-0 p-0 mt-3">
                        <!-- AJAX FORM HERE -->
                        <form method="POST" class="m-0 ajax-lab-form" onsubmit="return saveTestAjax(event, this);" onkeydown="return event.key != 'Enter';">
                            <input type="hidden" name="req_id" value="{{ t.request_id }}">
                            
                            <div class="test-header-row mb-3">
                                <!-- RIGHT: Title & Status -->
                                <div class="d-flex flex-wrap align-items-center gap-3">
                                    <h6 class="test-title">
                                        {{ t.test_type }} 
                                        {% if t.is_profile %}<span class="badge rounded-pill px-2 bg-primary text-white">بروفايل</span>{% endif %}
                                    </h6>
                                    <div class="d-flex gap-2">
                                        {% if t.status == 'pending_payment' %}
                                            <span class="status-badge status-unpaid m-0"><i class="fas fa-exclamation-triangle ms-1"></i> بانتظار المحاسبة</span>
                                        {% elif t.status == 'completed' %}
                                            <span class="status-badge bg-info text-white m-0"><i class="fas fa-check-circle ms-1"></i> مكتمل</span>
                                        {% else %}
                                            <span class="status-badge status-paid m-0"><i class="fas fa-flask ms-1"></i> جاهز للعمل</span>
                                        {% endif %}
                                    </div>
                                </div>

                                <!-- LEFT: Time Input & Save Button -->
                                <div class="d-flex align-items-center flex-wrap gap-2">
                                    <div class="lab-time-control shadow-sm m-0">
                                        <button type="submit" name="save_time" value="1" class="time-btn-submit" title="تأكيد الوقت">
                                            <i class="fas fa-check"></i>
                                        </button>
                                        <input type="text" name="est_time" 
                                               value="{{ t.estimated_time_minutes if t.estimated_time_minutes else '' }}" 
                                               class="time-input time-input-field lab-countdown" placeholder="-"
                                               autocomplete="off"
                                               data-end-time="{{ t.timer_end_time or '' }}"
                                               data-orig-minutes="{{ t.estimated_time_minutes if t.estimated_time_minutes else '' }}"
                                               onfocus="this.value = this.getAttribute('data-orig-minutes') || ''"
                                               onblur="if(this.value == this.getAttribute('data-orig-minutes')) { window.updateCountdowns(); }">
                                        <span class="time-label">دقيقة</span>
                                    </div>
                                    
                                    {% if t.status != 'pending_payment' %}
                                    <button type="submit" name="save_result" class="btn btn-save-mini m-0 d-flex align-items-center gap-2">
                                        <i class="fas fa-save"></i> <span>{{ 'تعديل النتيجة' if t.status == 'completed' else 'حفظ' }}</span>
                                    </button>
                                    {% endif %}
                                </div>
                            </div>
                            
                            {% if t.is_profile %}
                                <div class="table-responsive">
                                    <table class="param-table">
                                        <thead>
                                            <tr>
                                                <th>المعلمة / الباراميتر</th>
                                                <th class="text-center">النتيجة</th>
                                                <th class="text-center">الوحدة</th>
                                                <th class="text-center">المعدل الطبيعي</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for p in t.params %}
                                            <tr>
                                                <td class="fw-bold">{{ p.param_name }}</td>
                                                <td style="width: 140px;">
                                                    <input type="text" name="p_result_{{ p.param_id }}" class="result-input" 
                                                        value="{{ p.saved_val if p.saved_val else '' }}"
                                                        oninput="validateRange(this, {{ p.min_value or -999999 }}, {{ p.max_value or 999999 }})"
                                                        placeholder="-" {{ 'disabled' if t.status == 'pending_payment' }}>
                                                </td>
                                                <td class="text-center text-muted small" style="direction:ltr;">{{ p.unit or '-' }}</td>
                                                <td class="text-center text-muted fw-bold" style="direction:ltr;">
                                                    {% if p.min_value is not none and p.max_value is not none %}
                                                        {{ p.min_value }} - {{ p.max_value }}
                                                    {% else %}
                                                        -
                                                    {% endif %}
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                <div class="mt-3 text-end">
                                    <label class="small fw-bold text-muted mb-1">:ملاحظات التحليل</label>
                                    <textarea name="result" class="result-input" rows="2" {{ 'disabled' if t.status == 'pending_payment' }}>{{ t.result if t.result else '' }}</textarea>
                                </div>
                            {% else %}
                                <div class="row g-2 align-items-center flex-row-reverse">
                                    <div class="col-md-4">
                                        <div class="p-2 rounded-3 text-center border" style="background: var(--lab-bg); border-color: var(--lab-border);">
                                            <div class="small mb-1" style="font-size: 0.65rem; color: var(--lab-text-muted);">المعدل الطبيعي</div>
                                            <div class="fw-bold small" style="color: var(--lab-text); direction:ltr;">
                                                {% if t.min_value is not none and t.max_value is not none %}
                                                    {{ t.min_value }} - {{ t.max_value }} <small class="text-muted">{{ t.unit }}</small>
                                                {% else %}
                                                    -- <small class="text-muted">{{ t.unit }}</small>
                                                {% endif %}
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-8">
                                        <input type="text" name="result" class="result-input py-2 fw-bold" 
                                            value="{{ t.result if t.result else '' }}"
                                            oninput="validateRange(this, {{ t.min_value or -999999 }}, {{ t.max_value or 999999 }})"
                                            placeholder="{{ 'بانتظار التحصيل...' if t.status == 'pending_payment' else 'أدخل النتيجة' }}" 
                                            {{ 'disabled' if t.status == 'pending_payment' }} required>
                                    </div>
                                </div>
                            {% endif %}
                        </form>
                    </div>
                    {% endfor %}
                    
                    <!-- Finish & Close Button at the bottom of the patient accordion -->
                    <div class="text-start mt-4 border-top pt-3">
                        <button type="button" class="btn btn-success fw-bold px-4 rounded-pill shadow-sm" style="background: linear-gradient(135deg, #10b981, #059669); border:none;" onclick="finishPatient(this)">
                            <i class="fas fa-check-double me-2"></i> إنهاء الملف وإغلاقه
                        </button>
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}

        {% if not grouped %}
        <div class="text-center py-5 animate-in">
            <div class="bg-light d-inline-block p-4 rounded-circle mb-3">
                <i class="fas fa-vial fa-3x text-muted opacity-25"></i>
            </div>
            <h4 class="fw-bold text-muted">لا توجد تحاليل حالياً</h4>
            <p class="text-muted small">بانتظار تحويلات المرضى من العيادات</p>
        </div>
        {% endif %}
    </div>
    
    <script>
    // Filter tests by name in the selection panel
    function filterTests(input, gridId) {
        const val = input.value.toLowerCase();
        const grid = document.getElementById(gridId);
        grid.querySelectorAll('.test-item-box').forEach(box => {
            const name = box.getAttribute('data-name').toLowerCase();
            box.style.display = name.includes(val) ? '' : 'none';
        });
    }

    // Visual removal of finished patient without refreshing the page
    function finishPatient(btn) {
        const card = btn.closest('.patient-card');
        card.style.transition = 'all 0.5s ease';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => {
            card.remove();
            let remaining = document.querySelectorAll('.patient-card');
            if(remaining.length === 0) {
                window.location.reload();
            }
        }, 500);
    }
    
    // 1. Time Countdown
    function updateCountdowns() {
        const inputs = document.querySelectorAll('.lab-countdown');
        const now = new Date();
        inputs.forEach(input => {
            if(document.activeElement === input) return;
            const endTimeStr = input.getAttribute('data-end-time');
            if(!endTimeStr) return;
            let endTime;
            if(endTimeStr.includes('T')) { endTime = new Date(endTimeStr); } 
            else {
                const parts = endTimeStr.split(' ');
                if(parts.length < 2) return;
                const dateParts = parts[0].split('-');
                const timeParts = parts[1].split(':');
                endTime = new Date(dateParts[0], dateParts[1] - 1, dateParts[2], timeParts[0], timeParts[1], timeParts[2].split('.')[0]);
            }
            const diffMs = endTime.getTime() - now.getTime();
            if(diffMs <= 0) {
                input.value = "00:00"; input.classList.add('text-danger'); return;
            }
            const diffSecs = Math.floor(diffMs / 1000);
            const mins = Math.floor(diffSecs / 60);
            const secs = diffSecs % 60;
            input.value = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        });
    }
    updateCountdowns();
    window.updateCountdowns = updateCountdowns;
    setInterval(updateCountdowns, 1000);

    // 2. AI Range Validation Function
    function validateRange(input, min, max) {
        if (!input.value) {
            input.style.color = ''; input.style.borderColor = ''; input.style.backgroundColor = '';
            input.style.boxShadow = '';
            return;
        }
        const val = parseFloat(input.value);
        if(isNaN(val)) return;
        
        // Exclude dummy limits (-999999 / 999999) from actual styling
        if (min === -999999 && max === 999999) return;

        if(val < min || val > max) {
            input.style.color = '#ef4444'; 
            input.style.borderColor = 'rgba(239, 68, 68, 0.4)'; 
            input.style.backgroundColor = 'rgba(239, 68, 68, 0.05)';
        } else {
            input.style.color = '#10b981'; 
            input.style.borderColor = 'rgba(16, 185, 129, 0.4)'; 
            input.style.backgroundColor = 'rgba(16, 185, 129, 0.05)';
        }
    }
    
    // Trigger validation on load
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.result-input').forEach(inp => {
            if(inp.value) inp.dispatchEvent(new Event('input'));
        });
    });

    // 3. AJAX Save Function (No Page Refresh)
    async function saveTestAjax(event, form) {
        event.preventDefault();
        const submitter = event.submitter || form.querySelector('button[type="submit"]:focus');
        const formData = new FormData(form);
        if (submitter && submitter.name) formData.append(submitter.name, submitter.value || '1');
        
        const origHtml = submitter ? submitter.innerHTML : '';
        if(submitter) { 
            submitter.innerHTML = '<i class="fas fa-spinner fa-spin"></i> الحفظ...'; 
            submitter.disabled = true; 
        }
        
        try {
            await fetch(window.location.href, { method: 'POST', body: formData });
            
            // Re-trigger visual validation
            form.querySelectorAll('.result-input').forEach(i => i.dispatchEvent(new Event('input')));
            
            if(submitter) {
                // Change visually to "Saved" in Green
                submitter.innerHTML = '<i class="fas fa-check-circle"></i> <span>تم الحفظ</span>';
                submitter.style.backgroundColor = '#10b981';
                submitter.style.boxShadow = '0 6px 20px rgba(16, 185, 129, 0.4)';
                
                // Update specific status badge inside the test
                const statusBadge = form.querySelector('.status-badge');
                if(statusBadge) {
                    statusBadge.className = 'status-badge bg-info text-white m-0';
                    statusBadge.innerHTML = '<i class="fas fa-check-circle ms-1"></i> مكتمل';
                }
                
                // Allow edit visually after 2 seconds
                setTimeout(() => {
                    submitter.innerHTML = '<i class="fas fa-edit"></i> <span>تعديل النتيجة</span>';
                    submitter.disabled = false;
                    submitter.style.backgroundColor = '';
                    submitter.style.boxShadow = '';
                }, 2000);
            }
            
            // Move focus down to next input automatically!
            if (submitter && submitter.name === 'save_result') {
                const inputs = Array.from(form.closest('.collapse').querySelectorAll('.result-input:not([disabled])'));
                const curr = Array.from(form.querySelectorAll('.result-input'));
                if(curr.length > 0) {
                    const idx = inputs.indexOf(curr[curr.length-1]);
                    if(idx >= 0 && idx < inputs.length - 1) inputs[idx + 1].focus();
                }
            }
        } catch(e) {
            if(submitter) { submitter.innerHTML = origHtml; submitter.disabled = false; }
            alert('حدث خطأ بالاتصال، يرجى المحاولة مرة أخرى.');
        }
        return false;
    }
    </script>
    """ + footer_html
    return render_template_string(html, grouped=grouped, stats=stats, pending_selection=pending_selection, available_tests=available_tests)

@lab_bp.route('/print_lab')
def print_lab():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
    
    req_id = request.args.get('id')
    conn = get_db()
    cursor = conn.cursor(dictionary=True) # type: ignore
    
    cursor.execute("""
        SELECT l.*, p.full_name_ar, p.file_number, p.gender, p.date_of_birth
        FROM lab_requests l
        JOIN patients p ON l.patient_id = p.patient_id
        WHERE l.request_id = %s
    """, (req_id,))
    r = cursor.fetchone()
    
    if not r:
        return "Request Not Found"
        
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <title>Lab Barcode - {r['full_name_ar']}</title>
        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <style>
            @page {{ size: 50mm 30mm; margin: 0; }}
            body {{ font-family: 'Arial', sans-serif; margin: 0; padding: 2mm; width: 46mm; height: 26mm; overflow: hidden; }}
            .sticker {{ border: 1px solid #eee; padding: 2mm; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
            .name {{ font-size: 10pt; font-weight: bold; white-space: nowrap; overflow: hidden; text-align: right; }}
            .info {{ font-size: 8pt; display: flex; justify-content: space-between; margin-top: 1mm; }}
            .test {{ font-size: 9pt; color: #000; margin-top: 1mm; font-weight: bold; border-top: 1px dashed #ccc; padding-top: 1mm; text-align: center; }}
            .barcode-container {{ text-align: center; margin-top: 2mm; }}
            #barcode {{ width: 100%; height: 12mm; }}
        </style>
    </head>
    <body onload="window.print();">
        <div class="sticker">
            <div class="name">{r['full_name_ar']}</div>
            <div class="info">
                <span>{r['file_number']}</span>
                <span>{format_datetime(r['created_at']) or '—'}</span>
            </div>
            <div class="test">{r['test_type']}</div>
            <div class="barcode-container">
                <svg id="barcode"></svg>
            </div>
        </div>
        <script>
            JsBarcode("#barcode", "{r['file_number']}-{r['request_id']}", {{
                format: "CODE128",
                width: 2,
                height: 40,
                displayValue: false,
                margin: 0
            }});
        </script>
    </body>
    </html>
    """
    return html
