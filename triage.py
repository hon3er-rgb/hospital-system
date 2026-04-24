from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access, local_now_naive, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
import os

triage_bp = Blueprint('triage', __name__)

@triage_bp.route('/triage', methods=['GET', 'POST'])
def triage():
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)

    # SELF-HEALING: Update Schema
    try:
        cursor.execute("ALTER TABLE triage ADD COLUMN IF NOT EXISTS oxygen VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN height VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN weight VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN temperature VARCHAR(20)")

        cursor.execute("ALTER TABLE triage ADD COLUMN IF NOT EXISTS nurse_notes TEXT")
        cursor.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_urgent INT DEFAULT 0")
        conn.commit()
    except Exception as e:
        pass # Ignore errors if columns already exist or syntax unsupported

    if not session.get('user_id') or not can_access('triage'):
        return redirect(url_for('login.login'))

        
    # Handle save triage
    if request.method == 'POST' and 'save_triage' in request.form:
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = NULL, active_patient_name = NULL WHERE user_id = %s", (session['user_id'],))
            
        appt_id = request.form.get('appt_id')
        if not appt_id:
            return "Error: Appointment ID is missing"

            
        weight = request.form.get('weight', '')
        height = request.form.get('height', '')
        temp = request.form.get('temp', '')
        bp = request.form.get('bp', '')
        pulse = request.form.get('pulse', '')
        oxygen = request.form.get('oxygen', '')
        notes = request.form.get('notes', '')
        is_urgent = 1 if 'is_urgent' in request.form else 0
        
        insert_sql = """
            INSERT INTO triage (appointment_id, weight, height, temperature, blood_pressure, pulse, oxygen, nurse_notes) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (appt_id, weight, height, temp, bp, pulse, oxygen, notes))
        
        update_sql = "UPDATE appointments SET status = 'waiting_doctor', is_urgent = %s WHERE appointment_id = %s"
        cursor.execute(update_sql, (is_urgent, appt_id))
        
        conn.commit()
        
        flash("تم تسجيل البيانات وتحويل المريض للطبيب بنجاح", "success")
        return redirect(url_for('triage.triage'))

        
    # Handle active status update
    if request.method == 'POST' and 'appointment_id' in request.form and not 'save_triage' in request.form:
        aid = int(request.form.get('appointment_id'))
        cursor.execute("SELECT p.full_name_ar FROM patients p JOIN appointments a ON p.patient_id = a.patient_id WHERE a.appointment_id = %s", (aid,))
        p_info = cursor.fetchone()
        p_name = p_info['full_name_ar'] if p_info else 'مريض'
        
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = 'قياس العلامات الحيوية', active_patient_name = %s WHERE user_id = %s", (p_name, session['user_id']))
            conn.commit()

    today_str = local_today_str()

    # List patients
    sql_q = """
        SELECT a.*, p.full_name_ar as p_name, p.gender, p.file_number, p.photo, p.date_of_birth 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.status = 'pending_triage' 
        AND DATE(a.appointment_date) = %s
        ORDER BY a.created_at ASC

    """
    cursor.execute(sql_q, (today_str,))
    queue = cursor.fetchall()

    current_year = local_now_naive().year

    # Custom jinja function to check file existance
    def file_exists(path):
        if not path: return False
        try:
             # the execution happens from app.py root
             return os.path.exists(path)
        except:
             return False
    html = header_html + """
    <style>
        /* Force disable blurs on this page */
        * {
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }
    </style>
    <div class="container py-4 solid-mode">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="fw-bold mb-0"><i class="fas fa-user-nurse text-danger me-2"></i>قسم الفحص الأولي (Triage)</h2>
            <span class="badge bg-danger-subtle text-danger rounded-pill px-3 py-2">{{ queue|length }} في الانتظار</span>
        </div>

        <div class="d-flex flex-column gap-3">
            {% for r in queue %}
                <a href="{{ url_for('triage.start_triage', id=r.appointment_id) }}" class="text-decoration-none">
                <div class="patient-list-item d-flex align-items-center justify-content-between p-3 bg-card-adaptive rounded-4 shadow-sm border border-transparent"
                    style="cursor: pointer; transition: all 0.2s;">

                    <div class="d-flex align-items-center gap-3">
                        <div class="avatar-sm">
                            {% if r.photo and file_exists(r.photo) %}
                                <img src="/{{ r.photo }}" class="rounded-circle shadow-sm border border-2 border-white" style="width: 55px; height: 55px; object-fit: cover;">
                            {% else %}
                                <div class="rounded-circle bg-danger-subtle text-danger d-flex align-items-center justify-content-center border border-danger-subtle" style="width: 55px; height: 55px;">
                                    <i class="fas fa-user-injured fa-lg"></i>
                                </div>
                            {% endif %}
                        </div>
                        <div>
                            <h6 class="fw-bold mb-0 text-adaptive">{{ r.p_name }}</h6>
                            <div class="text-muted small d-flex align-items-center gap-2">
                                <span class="badge bg-adaptive text-adaptive border rounded-pill px-2">ID: {{ r.file_number }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="d-none d-md-flex align-items-center gap-4 text-secondary">
                        <div class="d-flex align-items-center gap-1" title="الجنس">
                            <i class="fas fa-venus-mars text-muted"></i>
                            <span>{{ 'ذكر' if r.gender == 'male' else 'أنثى' }}</span>
                        </div>
                        <div class="d-flex align-items-center gap-1" title="العمر">
                            <i class="fas fa-birthday-cake text-muted"></i>
                            <span>
                                {% if r.date_of_birth and r.date_of_birth.__class__.__name__ == 'datetime' %}
                                    {{ current_year - r.date_of_birth.strftime('%Y')|int }} سنة
                                {% elif r.date_of_birth and r.date_of_birth|string|length >= 4 %}
                                    {{ current_year - (r.date_of_birth|string)[:4]|int }} سنة
                                {% else %}
                                    0 سنة
                                {% endif %}
                            </span>
                        </div>
                    </div>

                    <div>
                        <span class="btn btn-danger-subtle btn-sm rounded-pill fw-bold px-4 py-2 border-0">
                            <i class="fas fa-stethoscope me-1"></i> فحص
                        </span>
                    </div>
                </div>
                </a>
            {% else %}
                <div class="text-center py-5 apple-card bg-white mt-4">
                    <i class="fas fa-check-circle text-success fa-4x mb-3 opacity-25"></i>
                    <h5 class="text-muted">لا يوجد مراجعين في قائمة الانتظار حالياً</h5>
                </div>
            {% endfor %}
        </div>
    </div>


    <style>
        .text-adaptive { color: var(--text) !important; }
        
        .bg-card-adaptive { background: var(--card) !important; }
        .bg-adaptive { background: var(--bg-card) !important; color: var(--text-main) !important; }
        
        .patient-file-card { cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); border: 2px solid transparent; background: #fff; }
        .patient-file-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(0, 0, 0, 0.08); border-color: rgba(220, 53, 69, 0.2); }
        .btn-danger-subtle { background: #fdf2f2; color: #dc3545; border: 1px solid #fee2e2; }
        .btn-danger-subtle:hover { background: #dc3545; color: #fff; }
        .form-check-input:checked { background-color: #dc3545; border-color: #dc3545; }
        .input-group-text { font-size: 1.1rem; }
    </style>

    <script>
        function updateActiveStatus(apptId) {
            const formData = new FormData();
            formData.append('appointment_id', apptId);
            
            fetch("{{ url_for('triage.triage') }}", {
                method: 'POST',
                body: formData
            });
        }
    </script>
    """ + footer_html
    
    return render_template_string(html, queue=queue, current_year=current_year, file_exists=file_exists)

@triage_bp.route('/start_triage/<int:id>', methods=['GET'])
def start_triage(id):
    if not session.get('user_id') or not can_access('triage'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get Appointment Info
    cursor.execute("""
        SELECT a.*, p.full_name_ar, p.file_number, p.gender, p.date_of_birth, p.photo
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.appointment_id = %s
    """, (id,))
    appt = cursor.fetchone()
    
    if not appt:
        return redirect(url_for('triage.triage'))


    # Update User Status
    cursor.execute("UPDATE users SET current_task = 'قياس العلامات الحيوية', active_patient_name = %s WHERE user_id = %s", 
                   (appt['full_name_ar'], session['user_id']))
    conn.commit()


    html = header_html + """
    <style>
        :root {
            --bg-body: #f1f5f9;
            --bg-card: #ffffff;
            --bg-vital: #ffffff;
            --border-color: #f1f5f9;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --shadow-card: 0 25px 70px rgba(0,0,0,0.07);
            --bg-header: #f8faff;
            --header-gradient: linear-gradient(135deg, #3b82f6, #2563eb);
        }

        html

        * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; transition: background 0.3s ease, color 0.3s ease, border-color 0.3s ease; }
        body { background: var(--bg-body); color: var(--text-main); }
        
        .triage-card { 
            border-radius: 35px; 
            box-shadow: var(--shadow-card); 
            border: 1px solid var(--border-color); 
            background: var(--bg-card); 
            position: relative; 
            overflow: hidden; 
        }

        .card-header-premium {
            background: var(--header-gradient) !important;
            border: none !important;
            padding: 1rem !important;
        }
        
        .vital-card { 
            background: var(--bg-vital); 
            border-radius: 16px; 
            padding: 8px 10px; 
            border: 1px solid var(--border-color);
            transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
            position: relative;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            height: 100%;
        }
        .vital-card:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); border-color: rgba(255,255,255,0.1); }
        .vital-card:focus-within { border-color: #3b82f6; }
        
        .vital-icon { 
            width: 26px; 
            height: 26px; 
            border-radius: 8px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-size: 0.75rem;
            flex-shrink: 0;
        }
        
        .bg-temp { background: rgba(248, 113, 113, 0.15); color: #f87171; }
        .bg-bp { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
        .bg-oxy { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
        .bg-pulse { background: rgba(251, 146, 60, 0.15); color: #fb923c; }
        .bg-neutral { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }
        
        .text-adaptive { color: var(--text-main) !important; }
        .bg-adaptive { background: var(--bg-card) !important; color: var(--text-main) !important; }
        .bg-card-adaptive { background: var(--bg-card) !important; }
        
        .form-control { border: none !important; background: transparent !important; padding: 2px 0 !important; font-weight: 800; font-size: 1.1rem; text-align: center; color: var(--text-main); letter-spacing: -0.5px; }
        .form-control::placeholder { color: #64748b; opacity: 0.5; }
        .form-control:focus { box-shadow: none !important; opacity: 1; }
        .form-label-small { font-size: 0.7rem; font-weight: 700; color: var(--text-muted); margin-bottom: 0; white-space: nowrap; }
        
        .patient-header { background: var(--bg-header); border-radius: 20px; padding: 12px 20px; margin-bottom: 25px; border: 1px solid var(--border-color); }
        
        .emergency-banner {
            display: none;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #f87171;
            padding: 15px;
            border-radius: 20px;
            margin-bottom: 20px;
            animation: pulse-red 2s infinite;
        }
        
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2); }
            70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        .is-critical { border-color: #ef4444 !important; background: rgba(239, 68, 68, 0.1) !important; }
        .is-critical .form-label-small { color: #f87171; }
        .is-critical .form-control { color: #f87171; }
        .is-critical .vital-icon { background: #ef4444; color: white; }

        .theme-toggle {
            cursor: pointer;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.1);
            color: #fff;
            border: none;
            transition: all 0.3s;
        }
        .theme-toggle:hover { background: rgba(255,255,255,0.2); transform: rotate(20deg); }
    </style>

    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-md-10 col-lg-8">
                <div class="card triage-card">
                    <div class="card-header card-header-premium text-center">
                        <h6 class="text-white fw-bold mb-0">
                            <i class="fas fa-microchip me-2" style="color: #fff;"></i> 
                            نظام الفحص الذكي (Smart Triage)
                        </h6>
                    </div>
                    
                    <div class="card-body p-4 text-end">
                        <!-- Emergency Alert -->
                        <div id="emergencyAlert" class="emergency-banner text-center fw-bold">
                            <i class="fas fa-exclamation-triangle me-2"></i> تنبيه: حالة حرجة جداً - تفعيل وضع الطوارئ
                        </div>

                        <div class="row g-4">
                            <!-- Left Side: Basic Info & Vital Stats -->
                            <div class="col-lg-12">
                                <!-- Patient Info Mini - Single Row -->
                                <div class="patient-header d-flex align-items-center justify-content-between gap-3 mb-4 py-2">
                                    <div class="d-flex align-items-center gap-3">
                                        """ + (f'<img src="/{appt["photo"]}" class="rounded-circle shadow-sm" style="width: 40px; height: 40px; object-fit: cover; border: 2px solid #fff;">' if appt["photo"] else '<div class="rounded-circle bg-white text-primary d-flex align-items-center justify-content-center shadow-sm" style="width: 40px; height: 40px;"><i class="fas fa-user-injured"></i></div>') + """
                                        <div class="fw-bold fs-5 text-adaptive mb-0">""" + appt['full_name_ar'] + """</div>
                                    </div>
                                    <div class="text-muted d-flex align-items-center gap-3" style="font-size: 0.85rem;">
                                        <span class="badge bg-adaptive text-adaptive border rounded-pill px-3">رقم الملف: #""" + appt['file_number'] + """</span>
                                        <span><i class="fas fa-venus-mars me-1"></i> """ + ('ذكر' if appt['gender'] == 'male' else 'أنثى') + """</span>
                                        <span><i class="fas fa-birthday-cake me-1"></i> 28 سنة</span>
                                    </div>
                                </div>

                                <form method="POST" action='""" + url_for('triage.triage') + """' id="triageForm">
                                    <input type="hidden" name="save_triage" value="1">
                                    <input type="hidden" name="appt_id" value='""" + str(id) + """'>

                                    <!-- Vitals Grid - Premium Horizontal Layout -->
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card h-100" id="card-bp">
                                                <div class="d-flex align-items-center gap-2 mb-2">
                                                    <div class="vital-icon bg-bp"><i class="fas fa-heartbeat"></i></div>
                                                    <span class="form-label-small">ضغط الدم</span>
                                                </div>
                                                <input type="text" name="bp" id="in-bp" class="form-control" placeholder="120/80" oninput="analyzeVitals()">
                                            </div>
                                        </div>
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card h-100" id="card-temp">
                                                <div class="d-flex align-items-center gap-2 mb-2">
                                                    <div class="vital-icon bg-temp"><i class="fas fa-thermometer-half"></i></div>
                                                    <span class="form-label-small">الحرارة °C</span>
                                                </div>
                                                <input type="text" name="temp" id="in-temp" class="form-control" placeholder="37.0" oninput="analyzeVitals()">
                                            </div>
                                        </div>
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card h-100" id="card-oxy">
                                                <div class="d-flex align-items-center gap-2 mb-2">
                                                    <div class="vital-icon bg-oxy"><i class="fas fa-lungs"></i></div>
                                                    <span class="form-label-small">الأوكسجين %</span>
                                                </div>
                                                <input type="text" name="oxygen" id="in-oxy" class="form-control" placeholder="98" oninput="analyzeVitals()">
                                            </div>
                                        </div>
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card h-100" id="card-pulse">
                                                <div class="d-flex align-items-center gap-2 mb-2">
                                                    <div class="vital-icon bg-pulse"><i class="fas fa-pills"></i></div>
                                                    <span class="form-label-small">النبض (BPM)</span>
                                                </div>
                                                <input type="text" name="pulse" id="in-pulse" class="form-control" placeholder="75" oninput="analyzeVitals()">
                                            </div>
                                        </div>
                                    </div>

                                    <div class="row g-3 mb-4">
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card" id="card-weight">
                                                <div class="d-flex align-items-center gap-2 mb-1">
                                                    <div class="vital-icon bg-neutral"><i class="fas fa-weight"></i></div>
                                                    <span class="form-label-small">الوزن (kg)</span>
                                                </div>
                                                <input type="text" name="weight" class="form-control" placeholder="0">
                                            </div>
                                        </div>
                                        <div class="col-md-3 col-6">
                                            <div class="vital-card" id="card-height">
                                                <div class="d-flex align-items-center gap-2 mb-1">
                                                    <div class="vital-icon bg-neutral"><i class="fas fa-ruler-vertical"></i></div>
                                                    <span class="form-label-small">الطول (cm)</span>
                                                </div>
                                                <input type="text" name="height" class="form-control" placeholder="0">
                                            </div>
                                        </div>
                                        <div class="col-md-6 col-12">
                                            <div class="form-check form-switch p-2 border rounded-4 d-flex justify-content-between align-items-center h-100 bg-card-adaptive" id="urgentToggleArea" style="transition: all 0.3s; border-color: var(--border-color) !important; border-radius: 16px !important;">
                                                <label class="form-check-label fw-bold text-adaptive mb-0 ms-0" for="isUrgentSwitch" style="font-size: 0.8rem;">
                                                    <i class="fas fa-star text-warning me-2" id="starIcon"></i> حالة طوارئ مستعجلة
                                                </label>
                                                <input class="form-check-input" type="checkbox" name="is_urgent" id="isUrgentSwitch" style="width: 2.5em; height: 1.25em; cursor: pointer;">
                                            </div>
                                        </div>
                                    </div>

                                    <div class="row">
                                        <div class="col-md-5 mx-auto">
                                            <button type="submit" class="btn btn-primary w-100 rounded-pill py-2 fw-bold shadow-sm hover-lift" style="background: linear-gradient(135deg, #1e293b, #0f172a); border: none; font-size: 1rem;">
                                                <i class="fas fa-check-circle me-1"></i> إرسال البيانات فوراً
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function analyzeVitals() {
            const temp = parseFloat(document.getElementById('in-temp').value);
            const oxy = parseFloat(document.getElementById('in-oxy').value);
            const pulse = parseFloat(document.getElementById('in-pulse').value);
            const bpStr = document.getElementById('in-bp').value;
            
            let isCritical = false;
            
            // Analyze Temperature
            if (temp > 39.0 || temp < 35.0) {
                document.getElementById('card-temp').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-temp').classList.remove('is-critical');
            }

            // Analyze Oxygen
            if (oxy > 0 && oxy < 91) {
                document.getElementById('card-oxy').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-oxy').classList.remove('is-critical');
            }

            // Analyze Pulse
            if (pulse > 130 || pulse < 45) {
                document.getElementById('card-pulse').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-pulse').classList.remove('is-critical');
            }

            // Analyze BP
            if (bpStr.includes('/')) {
                const parts = bpStr.split('/');
                const sys = parseInt(parts[0]);
                const dia = parseInt(parts[1]);
                if (sys > 180 || sys < 85 || dia > 110 || dia < 45) {
                    document.getElementById('card-bp').classList.add('is-critical');
                    isCritical = true;
                } else {
                    document.getElementById('card-bp').classList.remove('is-critical');
                }
            }

            // UI Feedback
            const banner = document.getElementById('emergencyAlert');
            const toggle = document.getElementById('isUrgentSwitch');
            const toggleArea = document.getElementById('urgentToggleArea');
            const star = document.getElementById('starIcon');

            if (isCritical) {
                banner.style.display = 'block';
                toggle.checked = true;
                toggleArea.style.background = 'rgba(239, 68, 68, 0.1)';
                toggleArea.style.borderColor = '#ef4444';
                star.className = 'fas fa-exclamation-circle text-danger me-2';
            } else {
                banner.style.display = 'none';
                toggleArea.style.background = 'var(--bg-card)';
                toggleArea.style.borderColor = 'var(--border-color)';
                star.className = 'fas fa-star text-warning me-2';
            }
        }
    </script>
    """ + footer_html
    return render_template_string(html)

