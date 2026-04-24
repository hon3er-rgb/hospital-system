from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, can_access # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
from datetime import datetime, date, timedelta

patient_index_bp = Blueprint('patient_index', __name__)

@patient_index_bp.route('/patient_index', methods=['GET'])
def patient_index():
    if not session.get('user_id') or (not can_access('registration') and not can_access('doctor') and not can_access('invoices') and not can_access('lab')):
        return redirect(url_for('login.login'))
        
    search = request.args.get('q', '')
    dept_id = request.args.get('dept', '')
    period = request.args.get('period', 'daily') 
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Stats
    today = date.today()
    if period == 'weekly': start_date = today - timedelta(days=today.weekday())
    elif period == 'monthly': start_date = today.replace(day=1)
    elif period == 'yearly': start_date = today.replace(month=1, day=1)
    else: start_date = today

    # 1. Fetch Real-time Stats
    today_str = date.today().strftime('%Y-%m-%d')
    start_str = start_date.strftime('%Y-%m-%d')

    # Total Patients in Index
    cursor.execute("SELECT COUNT(*) as c FROM patients")
    total_patients = cursor.fetchone()['c'] or 0

    # New Patients in selected period
    cursor.execute("SELECT COUNT(*) as p_count FROM patients WHERE strftime('%Y-%m-%d', created_at) >= ?", (start_str,))
    period_count = cursor.fetchone()['p_count'] or 0
    
    # 2. Fetch Departments
    cursor.execute("SELECT * FROM departments WHERE department_type = 'medical' ORDER BY department_name_ar")
    depts = cursor.fetchall()
    
    # 3. Optimized Main Query (Single table, absolute zero latency)
    sql = """
        SELECT p.*,
               (SELECT a.appointment_date FROM appointments a WHERE a.patient_id = p.patient_id ORDER BY a.appointment_id DESC LIMIT 1) as last_visit_date,
               (SELECT d.department_name_ar FROM appointments a JOIN departments d ON a.department_id = d.department_id WHERE a.patient_id = p.patient_id ORDER BY a.appointment_id DESC LIMIT 1) as last_dept
        FROM patients p
    """
    
    where_clauses = []
    params = []
    if search:
        search_term = f"{search}%" # Use prefix search for index
        where_clauses.append("(p.full_name_ar LIKE ? OR p.file_number LIKE ?)")
        params.extend([search_term, search_term])
        
    if dept_id:
        where_clauses.append("p.patient_id IN (SELECT patient_id FROM appointments WHERE department_id = ?)")
        params.append(dept_id)
    
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    sql += " ORDER BY p.patient_id DESC LIMIT 100"
    
    cursor.execute(sql, params)
    patients = cursor.fetchall()
    conn.close()

    def calculate_age(born):
        if not born: return "---"
        try:
            born_date = born if isinstance(born, date) else datetime.strptime(str(born), "%Y-%m-%d").date()
            today = date.today()
            return today.year - born_date.year - ((today.month, today.day) < (born_date.month, born_date.day))
        except: return "---"

    html = header_html + """
    <style>
        :root {
            --ui-blue: #007aff;
            --ui-canvas: #ffffff;
            --ui-text: #1c1c1e;
            --ui-border: rgba(0,0,0,0.04);
            --ui-panel: rgba(255, 255, 255, 0.7);
            --ui-gray: #f2f2f7;
            --ui-row-hover: rgba(0, 122, 255, 0.02);
        }

        

        .index-shell { padding: 1rem 4% 4rem; min-height: 100vh; background: transparent; color: var(--ui-text); }

        /* Compact Header Bar */
        .mock-panel {
            background: var(--ui-panel);
            backdrop-filter: blur(20px);
            border-radius: 18px;
            padding: 0.7rem 1.4rem;
            border: 1px solid var(--ui-border);
            margin-bottom: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }
        .panel-row-top { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-direction: row-reverse; }
        .segmented-control { display: flex; background: var(--ui-gray); padding: 3px; border-radius: 10px; gap: 2px; }
        .seg-btn { padding: 4px 14px; border-radius: 8px; font-size: 0.75rem; font-weight: 700; text-decoration: none; color: var(--ui-text); opacity: 0.4; transition: 0.2s; }
        .seg-btn.active { background: var(--ui-canvas); color: var(--ui-blue); opacity: 1; }
        
        .elegant-stats { display: flex; gap: 25px; align-items: center; }
        .e-stat { display: flex; flex-direction: column; align-items: center; }
        .e-val { font-size: 1.4rem; font-weight: 900; color: var(--ui-blue); line-height: 1; text-shadow: 0 0 15px rgba(0, 122, 255, 0.25); }
        .e-lab { font-size: 0.65rem; font-weight: 700; opacity: 0.35; margin-top: 3px; }
        .mock-search { flex-grow: 1; max-width: 320px; position: relative; }
        .mock-input {
            width: 100%; background: var(--ui-gray) !important; border: 1px solid transparent !important;
            border-radius: 10px !important; padding: 8px 36px 8px 12px !important;
            font-size: 0.85rem; font-weight: 600; color: var(--ui-text) !important; transition: 0.3s;
        }
        .mock-search i { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); opacity: 0.25; }
        .panel-row-bottom { display: flex; gap: 6px; border-top: 1px solid var(--ui-border); padding-top: 0.8rem; justify-content: flex-start; overflow-x: auto; scrollbar-width: none; }
        .mock-chip { padding: 6px 14px; background: var(--ui-gray); border-radius: 10px; color: var(--ui-text); text-decoration: none; font-size: 0.75rem; font-weight: 700; transition: 0.25s; }
        .mock-chip.active { background: var(--ui-blue) !important; color: white !important; }

        /* ULTRA SLIM THEMED TABLE */
        .listing-card { background: var(--ui-panel); backdrop-filter: blur(20px); border-radius: 18px; border: 1px solid var(--ui-border); overflow: hidden; }
        .mock-table { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
        .mock-table th { background: rgba(0,0,0,0.015); padding: 0.8rem 1rem; font-size: 0.65rem; font-weight: 900; opacity: 0.4; border: none; text-align: center; }
        
        .mock-table td { padding: 0.6rem 1rem; border-bottom: 1px solid var(--ui-border); vertical-align: middle; text-align: center; }
        .mock-table tr:hover td { background: var(--ui-row-hover); }

        .patient-row { display: flex; align-items: center; gap: 0.8rem; text-align: right; }
        .avatar-box { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1rem; }
        .avatar-box.male { background: rgba(0, 122, 255, 0.12); color: #007aff; }
        .avatar-box.female { background: rgba(216, 27, 96, 0.12); color: #d81b60; }
        .name-bold { font-weight: 800; font-size: 0.9rem; line-height: 1; }
        .sub-light { font-size: 0.68rem; opacity: 0.4; font-weight: 700; }

        /* Professional Action Icons */
        .icon-bar { display: flex; gap: 12px; justify-content: center; align-items: center; }
        .act-icon { font-size: 1.15rem; color: var(--ui-text); opacity: 0.4; transition: 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); text-decoration: none; position: relative; }
        .act-icon:hover { opacity: 1; transform: scale(1.3) translateY(-2px); }
        .act-icon.file:hover { color: #007aff; filter: drop-shadow(0 0 8px rgba(0, 122, 255, 0.5)); }
        .act-icon.edit:hover { color: #f39c12; filter: drop-shadow(0 0 8px rgba(243, 156, 18, 0.5)); }
        .act-icon.book:hover { color: #27ae60; filter: drop-shadow(0 0 8px rgba(39, 174, 96, 0.5)); }
        .act-icon.wa:hover { color: #25d366; filter: drop-shadow(0 0 8px rgba(37, 211, 102, 0.5)); }

        .date-text { font-weight: 800; color: #34c759; font-size: 0.8rem; }
        .dept-p { background: var(--ui-badge); color: #d07afb; padding: 2px 10px; border-radius: 12px; font-weight: 800; font-size: 0.68rem; display: inline-block; border: 1px solid rgba(208, 122, 251, 0.15); }
        
        body { background: var(--ui-canvas) !important; }
    </style>

    <div class="index-shell">
        <div class="mock-panel">
            <div class="panel-row-top">
                <div class="segmented-control">
                    <a href="?period=daily&q={{search}}&dept={{dept_id}}" class="seg-btn {{ 'active' if period == 'daily' else '' }}">يومي</a>
                    <a href="?period=weekly&q={{search}}&dept={{dept_id}}" class="seg-btn {{ 'active' if period == 'weekly' else '' }}">أسبوعي</a>
                    <a href="?period=monthly&q={{search}}&dept={{dept_id}}" class="seg-btn {{ 'active' if period == 'monthly' else '' }}">شهري</a>
                    <a href="?period=yearly&q={{search}}&dept={{dept_id}}" class="seg-btn {{ 'active' if period == 'yearly' else '' }}">سنوي</a>
                </div>
                <div class="elegant-stats">
                    <div class="e-stat"><div class="e-val">{{ period_count }}</div><div class="e-lab">المرضى الجدد</div></div>
                    <div class="e-stat"><div class="e-val">{{ total_patients }}</div><div class="e-lab">إجمالي الفهرس</div></div>
                </div>
                <div class="mock-search">
                    <form method="GET">
                        <i class="fas fa-search"></i>
                        <input type="text" name="q" class="mock-input" placeholder="بحث مريض..." value="{{ search|e }}">
                        <input type="hidden" name="period" value="{{ period }}">
                        <input type="hidden" name="dept" value="{{ dept_id }}">
                    </form>
                </div>
            </div>
            <div class="panel-row-bottom">
                <a href="?q={{search}}&period={{period}}" class="mock-chip {{ 'active' if not dept_id else '' }}">الكل</a>
                {% for d in depts %}
                <a href="?q={{search}}&period={{period}}&dept={{d.department_id}}" class="mock-chip {{ 'active' if dept_id|string == d.department_id|string else '' }}">{{ d.department_name_ar }}</a>
                {% endfor %}
            </div>
        </div>

        <div class="listing-card">
            <div class="table-responsive">
                <table class="mock-table">
                    <thead>
                        <tr>
                            <th style="width: 300px; text-align: right; padding-right: 30px;">المريض</th>
                            <th style="width: 150px;">رقم الملف</th>
                            <th style="width: 150px;">آخر مراجعة</th>
                            <th style="width: 150px;">القسم</th>
                            <th style="width: 250px; text-align: center;">إجراءات</th> <!-- CENTERED HEADER -->
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in patients %}
                        <tr>
                            <td style="padding-right: 30px;">
                                <div class="patient-row">
                                    <div class="avatar-box {{ p.gender }}"><i class="fas fa-{{ 'mars' if p.gender == 'male' else 'venus' if p.gender == 'female' else 'user' }}"></i></div>
                                    <div><div class="name-bold">{{ p.full_name_ar }}</div><div class="sub-light">{{ p.phone1 or '---' }} • {{ calculate_age(p.date_of_birth) }} سم</div></div>
                                </div>
                            </td>
                            <td><div class="fw-bold" style="font-size: 0.85rem;">#{{ p.file_number }}</div></td>
                            <td>
                                <div class="date-text">
                                    {% if p.last_visit_date %}
                                        {% if p.last_visit_date.__class__.__name__ in ['datetime', 'date'] %}{{ p.last_visit_date.strftime('%Y/%m/%d') }}{% else %}{{ p.last_visit_date|string|truncate(10, True, '')|replace('-', '/') }}{% endif %}
                                    {% else %}
                                        <span style="opacity: 0.3; font-size: 0.65rem;">جديد</span>
                                    {% endif %}
                                </div>
                            </td>
                            <td>{% if p.last_dept %}<span class="dept-p">{{ p.last_dept }}</span>{% else %}<span class="sub-light">---</span>{% endif %}</td>
                            <td>
                                <div class="icon-bar"> <!-- CENTERED ICONS -->
                                    <a href="{{ url_for('patient_file.patient_file') }}?id={{ p.patient_id }}" class="act-icon file" title="الملف"><i class="fas fa-folder-open"></i></a>
                                    <a href="{{ url_for('edit_patient.edit_patient') }}?id={{ p.patient_id }}" class="act-icon edit" title="تعديل"><i class="fas fa-user-edit"></i></a>
                                    <a href="{{ url_for('book.book') }}?id={{ p.patient_id }}" class="act-icon book" title="حجز"><i class="fas fa-calendar-plus"></i></a>
                                    {% if p.phone1 %}<a href="https://wa.me/{{ p.phone1|string|replace('+', '')|replace(' ', '') }}" target="_blank" class="act-icon wa" title="واتساب"><i class="fab fa-whatsapp"></i></a>{% endif %}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, patients=patients, search=search, period=period, 
                                period_count=period_count, total_patients=total_patients, 
                                depts=depts, dept_id=dept_id, calculate_age=calculate_age)
