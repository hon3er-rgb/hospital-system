from flask import Blueprint, session, redirect, url_for, render_template_string # type: ignore
from config import get_db, can_access, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    role = session.get('role', '')
    
    conn = get_db()
    if not conn:
        return "Database connection error."

    cursor = conn.cursor()
    user_id = session.get('user_id')
    is_admin = (role == 'admin')

    today_str = local_today_str()

    # ── Daily Reset Logic (Every 24 Hours) ─────────────────────────
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'counters_last_reset'")
    reset_row = cursor.fetchone()
    last_reset = reset_row['setting_value'] if reset_row else None
    
    if last_reset != today_str:
        cursor.execute("UPDATE global_counters SET val = 0")
        if last_reset is None:
            cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('counters_last_reset', %s)", (today_str,))
        else:
            cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'counters_last_reset'", (today_str,))
        conn.commit()

    # ── Live Dashboard Counters (Direct DB queries for 100% accuracy) ──
    try:
        # Appointments today
        cursor.execute("SELECT COUNT(*) as cnt FROM appointments WHERE DATE(appointment_date) = %s AND status != 'cancelled'", (today_str,))
        q_scheduled = int(cursor.fetchone()['cnt'] or 0)
        
        # Triage
        cursor.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status = 'pending_triage' AND DATE(appointment_date) = %s", (today_str,))
        q_triage = int(cursor.fetchone()['cnt'] or 0)
        
        # Doctor
        cursor.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status = 'waiting_doctor' AND DATE(appointment_date) = %s", (today_str,))
        q_doctor = int(cursor.fetchone()['cnt'] or 0)
        
        # Lab
        cursor.execute("SELECT COUNT(*) as cnt FROM lab_requests WHERE status IN ('pending', 'pending_payment')")
        q_labs_items = int(cursor.fetchone()['cnt'] or 0)
        
        # Radiology
        cursor.execute("SELECT COUNT(*) as cnt FROM radiology_requests WHERE status IN ('pending', 'pending_payment')")
        q_rads_items = int(cursor.fetchone()['cnt'] or 0)
        
        # Pharmacy
        cursor.execute("SELECT COUNT(*) as cnt FROM prescriptions WHERE status IN ('pending', 'pending_payment')")
        q_pharmacy = int(cursor.fetchone()['cnt'] or 0)
        
        # Done
        cursor.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status = 'completed' AND DATE(appointment_date) = %s", (today_str,))
        q_done = int(cursor.fetchone()['cnt'] or 0)
    except Exception as e:
        q_scheduled = q_triage = q_doctor = q_labs_items = q_rads_items = q_pharmacy = q_done = 0

    # ── q_nursing: Live count — always calculated directly from DB ──
    # (global_counters never updates this key, so we query live)
    try:
        cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM lab_requests l
            LEFT JOIN nursing_lab_collections nc ON nc.request_id = l.request_id
            WHERE l.status IN ('pending', 'pending_payment')
              AND (nc.collected_at IS NULL OR nc.id IS NULL)
        """)
        nr = cursor.fetchone()
        q_nursing = int(nr['cnt'] or 0) if nr else 0
    except Exception:
        q_nursing = counters.get('q_nursing', 0)

    # ── Unpaid invoices: live count ─────────────────────────────────
    try:
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM invoices
            WHERE status IN ('pending', 'pending_payment', 'unpaid')
        """)
        inv_row = cursor.fetchone()
        unpaid_invoices = int(inv_row['cnt'] or 0) if inv_row else 0
    except Exception:
        unpaid_invoices = 0

    is_admin = (role == 'admin')

    
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0">{% if system_icon %}<i class="{{ system_icon }} me-2 text-primary"></i>{% endif %}{{ system_name }}</h2>
            <p class="text-muted small">نظام المسار الذكي لتتبع المرضى لحظياً</p>
        </div>
    </div>

        <style>
        .circular-badge {
            position: absolute;
            top: -10px;
            right: -10px;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            color: white !important;
            font-size: 0.85rem;
            border: 2.5px solid #fff;
            z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .circular-badge.bg-danger { background: #ef4444 !important; box-shadow: 0 4px 12px rgba(239,68,68,0.4); }
        .circular-badge.bg-warning { background: #f59e0b !important; box-shadow: 0 4px 12px rgba(245,158,11,0.4); }
        .circular-badge.bg-info { background: #06b6d4 !important; box-shadow: 0 4px 12px rgba(6,182,212,0.4); }
        .circular-badge.bg-success { background: #10b981 !important; box-shadow: 0 4px 12px rgba(16,185,129,0.4); }
        .circular-badge.bg-secondary { background: #64748b !important; box-shadow: 0 4px 12px rgba(100,116,139,0.4); }
        .circular-badge.bg-primary { background: #3b82f6 !important; box-shadow: 0 4px 12px rgba(59,130,246,0.4); }
        
        .neo-tile { 
            position: relative; 
            overflow: visible !important; /* Allow badge to float outside */
        }
        .neo-tile::before {
            border-radius: inherit; /* Keep animation bounds correct */
        }
    </style>
    <!-- Tiny Neo-Tiles Grid (Permission Based) -->
    <div class="row row-cols-3 row-cols-md-5 row-cols-lg-6 g-3 justify-content-center mb-5">

        <!-- Registration -->
        {% if can_access('registration') %}
            <div class="col">
                <a href="{{ url_for('patients.patients') }}" class="neo-tile tile-blue">
                    {% if q_scheduled > 0 %}
                        <div class="circular-badge bg-danger">{{ q_scheduled }}</div>
                    {% endif %}
                    <i class="fas fa-user-plus text-primary"></i>
                    <span>التسجيل</span>
                </a>
            </div>
        {% endif %}

        <!-- Triage -->
        {% if can_access('triage') %}
            <div class="col">
                <a href="{{ url_for('triage.triage') }}" class="neo-tile tile-red">
                    {% if q_triage > 0 %}
                        <div class="circular-badge bg-danger">{{ q_triage }}</div>
                    {% endif %}
                    <i class="fas fa-user-nurse text-danger"></i>
                    <span>الفحص الأولي</span>
                </a>
            </div>
        {% endif %}

        <!-- Doctor -->
        {% if can_access('doctor') %}
            <div class="col">
                <a href="{{ url_for('doctor_clinic.doctor_clinic') }}" class="neo-tile tile-indigo">
                    {% if q_doctor > 0 %}
                        <div class="circular-badge bg-danger">{{ q_doctor }}</div>
                    {% endif %}
                    <i class="fas fa-stethoscope text-primary"></i>
                    <span>العيادة</span>
                </a>
            </div>
        {% endif %}

        <!-- Lab -->
        {% if can_access('lab') %}
            <div class="col">
                <a href="{{ url_for('lab.lab') }}" class="neo-tile tile-cyan">
                    {% if q_labs_items > 0 %}
                        <div class="circular-badge bg-danger">{{ q_labs_items }}</div>
                    {% endif %}
                    <i class="fas fa-flask text-info"></i>
                    <span>المختبر</span>
                </a>
            </div>
        {% endif %}

        <!-- Radiology -->
        {% if can_access('radiology') %}
            <div class="col">
                <a href="{{ url_for('radiology.radiology') }}" class="neo-tile tile-gray">
                    {% if q_rads_items > 0 %}
                        <div class="circular-badge bg-danger">{{ q_rads_items }}</div>
                    {% endif %}
                    <i class="fas fa-x-ray text-secondary"></i>
                    <span>الأشعة</span>
                </a>
            </div>
        {% endif %}

        <!-- Pharmacy -->
        {% if can_access('pharmacy') %}
            <div class="col">
                <a href="{{ url_for('pharmacy.pharmacy') }}" class="neo-tile tile-green">
                    {% if q_pharmacy > 0 %}
                        <div class="circular-badge bg-danger">{{ q_pharmacy }}</div>
                    {% endif %}
                    <i class="fas fa-pills text-success"></i>
                    <span>الصيدلية</span>
                </a>
            </div>
        {% endif %}

        <!-- Nursing Lab -->
        {% if can_access('nursing') %}
            <div class="col">
                <a href="{{ url_for('nursing_lab.nursing_lab') }}" class="neo-tile tile-teal">
                    {% if q_nursing > 0 %}
                        <div class="circular-badge bg-danger">{{ q_nursing }}</div>
                    {% endif %}
                    <i class="fas fa-syringe text-info"></i>
                    <span>سحب العينات</span>
                </a>
            </div>
        {% endif %}


        <div class="col">
            <a href="{{ url_for('waiting_list.waiting_list') }}" class="neo-tile tile-teal">
                <i class="fas fa-desktop text-info"></i>
                <span>المراقب المباشر</span>
            </a>
        </div>

        {% if is_admin %}
            <div class="col">
                <a href="{{ url_for('system_data.system_data') }}" class="neo-tile tile-orange border border-danger border-opacity-25">
                    <i class="fas fa-database text-danger"></i>
                    <span>أداة البيانات</span>
                </a>
            </div>
        {% endif %}

        <div class="col">
            <a href="{{ url_for('connect.connect') }}" class="neo-tile tile-blue">
                <i class="fas fa-satellite-dish text-primary"></i>
                <span>مركز الاتصال</span>
            </a>
        </div>

        <!-- Settings -->
        {% if can_access('settings') %}
            <div class="col">
                <a href="{{ url_for('settings.view_settings') }}" class="neo-tile tile-slate">
                    <i class="fas fa-cog text-muted"></i>
                    <span>الإعدادات</span>
                </a>
            </div>
        {% endif %}

    </div>

    <!-- Real-time Connected Workflow Dashboard -->
    <div class="row justify-content-center mt-4 mb-5">
        <div class="col-lg-10">
            <div class="card border-0 shadow-sm overflow-hidden timeline-card" style="will-change: transform;">
                <div class="card-body p-3">

                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <div>
                            <h5 class="fw-bold mb-1 text-dark" style="font-family: 'Cairo', sans-serif;">
                                <i class="fas fa-stream text-primary me-2"></i>تدفق المرضى المباشر
                            </h5>
                            <span class="text-muted small">تحديث لحظي لحركة العيادة</span>
                        </div>
                        <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2 rounded-pill shadow-sm">
                            Live <i class="fas fa-wifi ms-1 fa-fade"></i>
                        </span>
                    </div>

                    <div class="position-relative px-3 py-2">
                        <div class="position-absolute top-50 start-0 w-100 translate-middle-y d-none d-md-block"
                            style="height: 3px; background: #e2e8f0; z-index: 0; margin-top: -15px;"></div>

                        <div class="d-flex justify-content-between position-relative flex-wrap gap-3" style="z-index: 1;">

                            <!-- Accounting -->
                            {% if can_access('invoices') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-primary transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-file-invoice-dollar text-primary fs-5"></i>
                                        </div>
                                        {% if unpaid_invoices > 0 %}
                                            <div class="circular-badge bg-danger">{{ unpaid_invoices }}</div>
                                        {% endif %}
                                    </div>
                                    <div class="fw-bold small text-dark d-block">المحاسبة</div>
                                </div>
                            {% endif %}

                            <!-- Triage -->
                            {% if can_access('triage') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-warning transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-user-nurse text-warning fs-5"></i>
                                        </div>
                                        {% if q_triage > 0 %}
                                            <div class="circular-badge bg-danger">{{ q_triage }}</div>
                                        {% endif %}
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الفحص الأولي</div>
                                </div>
                            {% endif %}

                            <!-- Doctor -->
                            {% if can_access('doctor') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-indigo transition-hover step-circle"
                                            style="width: 50px; height: 50px; border-color: #6366f1 !important;">
                                            <i class="fas fa-user-md fs-5" style="color: #6366f1;"></i>
                                        </div>
                                        {% if q_doctor > 0 %}
                                            <div class="circular-badge bg-danger">{{ q_doctor }}</div>
                                        {% endif %}
                                    </div>
                                    <div class="fw-bold small text-dark d-block">العيادة</div>
                                </div>
                            {% endif %}

                            <!-- Nursing Lab (Sample Collection) -->
                            {% if can_access('nursing') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <a href="{{ url_for('nursing_lab.nursing_lab') }}" class="text-decoration-none">
                                            <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-info transition-hover step-circle"
                                                style="width: 50px; height: 50px;">
                                                <i class="fas fa-syringe text-info fs-5"></i>
                                            </div>
                                            {% if q_nursing > 0 %}
                                                <div class="circular-badge bg-danger">{{ q_nursing }}</div>
                                            {% endif %}
                                        </a>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">سحب عينات</div>
                                </div>
                            {% endif %}

                            <!-- Lab/Radiology -->
                            {% if can_access('lab') or can_access('radiology') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <a href="{{ url_for('lab.lab') }}" class="text-decoration-none">
                                            <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-info transition-hover step-circle"
                                                style="width: 50px; height: 50px;">
                                                <i class="fas fa-microscope text-info fs-5"></i>
                                            </div>
                                            {% if (q_labs_items + q_rads_items) > 0 %}
                                                <div class="circular-badge bg-danger">{{ q_labs_items + q_rads_items }}</div>
                                            {% endif %}
                                        </a>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الفحوصات</div>
                                </div>
                            {% endif %}

                            <!-- Pharmacy -->
                            {% if can_access('pharmacy') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-success transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-pills text-success fs-5"></i>
                                        </div>
                                        {% if q_pharmacy > 0 %}
                                            <div class="circular-badge bg-danger">{{ q_pharmacy }}</div>
                                        {% endif %}
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الصيدلية</div>
                                </div>
                            {% endif %}

                            <!-- Done -->
                            <div class="text-center step-item flex-fill">
                                <div class="position-relative d-inline-block mb-2">
                                    <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-secondary transition-hover step-circle"
                                        style="width: 50px; height: 50px;">
                                        <i class="fas fa-check-circle text-secondary fs-5"></i>
                                    </div>
                                    {% if q_done > 0 %}
                                        <div class="circular-badge bg-success">{{ q_done }}</div>
                                    {% endif %}
                                </div>
                                <div class="fw-bold small text-muted d-block">تم الخروج</div>
                            </div>

                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html,
                                  can_access=can_access,
                                  is_admin=is_admin,
                                  q_scheduled=q_scheduled,
                                  q_triage=q_triage,
                                  q_doctor=q_doctor,
                                  q_labs_items=q_labs_items,
                                  q_rads_items=q_rads_items,
                                  q_pharmacy=q_pharmacy,
                                  q_nursing=q_nursing,
                                  q_done=q_done,
                                  unpaid_invoices=unpaid_invoices)
