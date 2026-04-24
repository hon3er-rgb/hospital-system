from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from datetime import timedelta
from config import get_db, can_access, local_now_naive, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

patients_bp = Blueprint('patients', __name__)

@patients_bp.route('/patients', methods=['GET', 'POST'])
def patients():
    if not session.get('user_id') or not can_access('registration'):
        return redirect(url_for('login.login'))
    
    conn = get_db()
    if not conn:
        return "Database connection error."
        
    cursor = conn.cursor(dictionary=True)
    
    # Update current task
    try:
        cursor.execute("UPDATE users SET current_task = %s WHERE user_id = %s", ('إدارة ملفات المرضى', session['user_id']))
        conn.commit()
    except:
        pass

    # --- Handle Deletion ---
    if request.args.get('delete_patient') and session.get('role') == 'admin':
        pid = int(request.args.get('delete_patient'))
        cursor.execute("DELETE FROM lab_requests WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM radiology_requests WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM prescriptions WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM triage WHERE appointment_id IN (SELECT appointment_id FROM appointments WHERE patient_id = %s)", (pid,))
        cursor.execute("DELETE FROM consultations WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM invoices WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM appointments WHERE patient_id = %s", (pid,))
        cursor.execute("DELETE FROM patients WHERE patient_id = %s", (pid,))
        conn.commit()
        
        flash("تم حذف سجل المريض بنجاح", "danger")
        return redirect(url_for('patients.patients'))

    # --- Handle Cancellation ---
    if request.args.get('cancel_appt'):
        aid = int(request.args.get('cancel_appt'))
        cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE appointment_id = %s AND status NOT IN ('completed', 'cancelled')", (aid,))
        conn.commit()
        flash("تم إلغاء الحجز بنجاح", "warning")
        return redirect(url_for('patients.patients'))

    search = request.args.get('q', '')
    result = None

    ln = local_now_naive()
    today_str = local_today_str()
    tom_str = (ln + timedelta(days=1)).strftime('%Y-%m-%d')
    week_str = ln.strftime('%Y-%W')
    month_str = ln.strftime('%Y-%m')

    if search:
        search_param = f"%{search}%"
        sql = """
            SELECT p.*, (SELECT COUNT(*) FROM appointments WHERE patient_id = p.patient_id) AS visit_count
            FROM patients p
            WHERE (p.full_name_ar LIKE %s OR p.file_number LIKE %s OR p.national_id LIKE %s)
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  WHERE a.patient_id = p.patient_id
                    AND DATE(a.appointment_date) = %s
                    AND a.status != 'cancelled'
              )
            ORDER BY p.created_at DESC
        """
        cursor.execute(sql, (search_param, search_param, search_param, today_str))
        result = cursor.fetchall()

    # ── Today's appointments (one join query used for both confirmed and today_apps) ──
    cursor.execute("""
        SELECT a.appointment_id, a.patient_id, a.doctor_id, a.department_id,
               a.status, a.is_urgent, a.is_free, a.created_at,
               p.full_name_ar, p.file_number,
               d.department_name_ar
        FROM appointments a
        JOIN patients p    ON a.patient_id    = p.patient_id
        JOIN departments d ON a.department_id = d.department_id
        WHERE DATE(a.appointment_date) = %s
          AND a.status != 'cancelled'
        ORDER BY a.created_at DESC
    """, (today_str,))
    today_apps      = cursor.fetchall()
    
    confirmed_today = today_apps   # same data set

    # ── Stats: one aggregated query instead of 4 ──────────────────────────
    cursor.execute("""
        SELECT
            SUM(CASE WHEN DATE(appointment_date) = ?             THEN 1 ELSE 0 END) AS s_today,
            SUM(CASE WHEN DATE(appointment_date) = ?    THEN 1 ELSE 0 END) AS s_tom,
            SUM(CASE WHEN strftime('%Y-%W', appointment_date) = ?            THEN 1 ELSE 0 END) AS s_week,
            SUM(CASE WHEN strftime('%Y-%m', appointment_date) = ?            THEN 1 ELSE 0 END) AS s_month
        FROM appointments
        WHERE status != 'cancelled'
    """, (today_str, tom_str, week_str, month_str))
    st = cursor.fetchone()
    if type(st) is dict:
        vals = list(st.values())
    else:
        vals = st if st else [0, 0, 0, 0]
        
    s_today = int(vals[0] or 0)
    s_tom   = int(vals[1] or 0)
    s_week  = int(vals[2] or 0)
    s_month = int(vals[3] or 0)
    
    # ── Unpaid invoices count for billing badge ─────────────────────────
    try:
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM invoices
            WHERE status IN ('pending', 'pending_payment', 'unpaid')
        """)
        inv_row = cursor.fetchone()
        unpaid_count = int(inv_row['cnt'] or 0) if inv_row else 0
    except Exception:
        unpaid_count = 0

    html_template = header_html + """

    <style>
        .interactive-card {
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            border: 1px solid rgba(0,0,0,0.05);
        }
        .interactive-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 15px 30px rgba(0,0,0,0.08) !important;
            border-color: rgba(0,0,0,0.1);
        }
        .icon-circle {
            width: 55px;
            height: 55px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: all 0.3s ease;
        }
        .interactive-card:hover .icon-circle {
            transform: scale(1.1) rotate(-5deg);
        }
    </style>
    <div class="patients-redesign py-4">
        <!-- Section 1: Quick Access Center -->
        <div class="row g-3 mb-4">
            <!-- Card 1: Registration -->
            <div class="col-12 col-md-6 col-xl-3">
                <a href="{{ url_for('add_patient.add_patient') }}" class="text-decoration-none">
                    <div class="premium-card interactive-card d-flex flex-column p-4 shadow-sm rounded-4 bg-white h-100 position-relative" style="min-height: 140px;">
                        <div class="d-flex justify-content-between align-items-start mb-auto">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.1rem;">تسجيل ملف</h5>
                                <small class="text-muted d-block">إضافة مريض جديد</small>
                            </div>
                            <div class="icon-circle bg-primary bg-opacity-10 shadow-sm">
                                <i class="fas fa-user-plus text-primary fs-4"></i>
                            </div>
                        </div>
                        <div class="mt-4 text-start">
                            <span class="btn btn-primary rounded-pill px-4 py-1 fw-bold text-white shadow-sm small" style="font-size: 0.85rem;">ابدأ التسجيل <i class="fas fa-arrow-left ms-1"></i></span>
                        </div>
                    </div>
                </a>
            </div>

            <!-- Card 2: Patient Index -->
            <div class="col-12 col-md-6 col-xl-3">
                <a href="{{ url_for('patient_index.patient_index') }}" class="text-decoration-none">
                    <div class="premium-card interactive-card d-flex flex-column p-4 shadow-sm rounded-4 bg-white h-100" style="min-height: 140px;">
                        <div class="d-flex justify-content-between align-items-start mb-auto">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.1rem;">فهرس المرضى</h5>
                                <small class="text-muted d-block">قاعدة البيانات الشاملة</small>
                            </div>
                            <div class="icon-circle bg-success bg-opacity-10 shadow-sm">
                                <i class="fas fa-address-book text-success fs-4"></i>
                            </div>
                        </div>
                        <div class="mt-4 text-start">
                            <span class="btn btn-success rounded-pill px-4 py-1 fw-bold text-white shadow-sm small" style="font-size: 0.85rem;">فتح السجل <i class="fas fa-folder-open ms-1"></i></span>
                        </div>
                    </div>
                </a>
            </div>

            <!-- Card 3: Billing -->
            <div class="col-12 col-md-6 col-xl-3">
                <a href="{{ url_for('billing.billing') }}" class="text-decoration-none">
                    <div class="premium-card interactive-card d-flex flex-column p-4 shadow-sm rounded-4 bg-white h-100 position-relative" style="min-height: 140px;">
                        {% if unpaid_count > 0 %}
                        <div class="position-absolute d-flex align-items-center justify-content-center fw-bold text-white shadow" 
                             style="top:-10px; right:-10px; width:32px; height:32px; border-radius:50%; background:#ef4444; font-size:0.85rem; border:2.5px solid #fff; z-index:10; box-shadow:0 3px 10px rgba(239,68,68,0.45);">{{ unpaid_count }}</div>
                        {% endif %}
                        <div class="d-flex justify-content-between align-items-start mb-auto">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.1rem;">المحاسبة</h5>
                                <small class="text-muted d-block">نظام الفواتير والدفع</small>
                            </div>
                            <div class="icon-circle bg-danger bg-opacity-10 shadow-sm">
                                <i class="fas fa-file-invoice-dollar text-danger fs-4"></i>
                            </div>
                        </div>
                        <div class="mt-4 text-start">
                            <span class="btn btn-danger rounded-pill px-4 py-1 fw-bold text-white shadow-sm small" style="font-size: 0.85rem;">دخول المحاسبة <i class="fas fa-cash-register ms-1"></i></span>
                        </div>
                    </div>
                </a>
            </div>

            <!-- Card 4: Reservations Mini-Board -->
            <div class="col-12 col-md-6 col-xl-3">
                <a href="{{ url_for('reservations.reservations') }}" class="text-decoration-none">
                    <div class="premium-card interactive-card d-flex flex-column p-4 shadow-sm rounded-4 bg-white h-100 position-relative" style="min-height: 140px;">
                        {% if s_today > 0 %}
                        <div class="position-absolute d-flex align-items-center justify-content-center fw-bold text-white shadow"
                             style="top:-10px; right:-10px; width:32px; height:32px; border-radius:50%; background:#7c3aed; font-size:0.85rem; border:2.5px solid #fff; z-index:10; box-shadow:0 3px 10px rgba(124,58,237,0.45);">{{ s_today }}</div>
                        {% endif %}
                        <div class="d-flex justify-content-between align-items-start mb-auto">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.1rem;">إدارة الحجوزات</h5>
                                <small class="text-muted d-block">متابعة مواعيد اليوم</small>
                            </div>
                            <div class="icon-circle shadow-sm border border-light" style="background-color: #f3e8ff;">
                                <i class="fas fa-calendar-check fs-4" style="color: #7c3aed;"></i>
                            </div>
                        </div>
                        <div class="mt-4 text-start">
                            <span class="btn rounded-pill px-4 py-1 fw-bold text-white shadow-sm small" style="background: #7c3aed; font-size: 0.85rem;">جدول الحجوزات <i class="fas fa-calendar-alt ms-1"></i></span>
                        </div>
                    </div>
                </a>
            </div>
            
            <!-- Card 5: WhatsApp Notifications -->
            <div class="col-12 col-md-6 col-xl-3">
                <a href="{{ url_for('reservations.whatsapp_reminders') }}" class="text-decoration-none">
                    <div class="premium-card interactive-card d-flex flex-column p-4 shadow-sm rounded-4 bg-white h-100 position-relative" style="min-height: 140px;">
                        {% if s_tom > 0 %}
                        <div class="position-absolute d-flex align-items-center justify-content-center fw-bold text-white shadow"
                             style="top:-10px; right:-10px; width:32px; height:32px; border-radius:50%; background:#25d366; font-size:0.85rem; border:2.5px solid #fff; z-index:10; box-shadow:0 3px 10px rgba(37,211,102,0.45);">{{ s_tom }}</div>
                        {% endif %}
                        <div class="d-flex justify-content-between align-items-start mb-auto">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.1rem;">إشعارات الواتساب</h5>
                                <small class="text-muted d-block">تبليغ مراجعي الغد</small>
                            </div>
                            <div class="icon-circle shadow-sm border border-light" style="background-color: #e8f5e9;">
                                <i class="fab fa-whatsapp fs-4" style="color: #25d366;"></i>
                            </div>
                        </div>
                        <div class="mt-4 text-start">
                            <span class="btn rounded-pill px-4 py-1 fw-bold text-white shadow-sm small" style="background: #25d366; font-size: 0.85rem;">إرسال تبليغات <i class="fas fa-paper-plane ms-1"></i></span>
                        </div>
                    </div>
                </a>
            </div>
        </div>




        <!-- Section 2: Patients List -->
        {% if result %}
        <div class="section-container mb-5">
            <div class="glass-card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="table-responsive">
                    <table class="table table-borderless table-hover align-middle mb-0">
                        <tbody>
                            {% for row in result %}
                                <tr>
                                    <td class="ps-4">
                                        <div class="d-flex align-items-center">
                                            <div class="avatar-sm bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 45px; height: 45px;">
                                                <i class="fas fa-user"></i>
                                            </div>
                                            <div>
                                                <a href="{{ url_for('patient_file.patient_file') }}?id={{ row.patient_id }}" class="fw-bold text-dark text-decoration-none stretched-link">{{ row.full_name_ar }}</a>
                                                <div class="small text-muted">هوية: {{ row.national_id or '---' }}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td><span class="badge bg-light text-dark border rounded-pill px-3">{{ row.file_number }}</span></td>
                                    <td><i class="fas fa-phone text-muted me-1"></i> {{ row.phone1 }}</td>
                                    <td class="text-center"><span class="badge bg-white text-primary border border-primary px-3 rounded-pill">{{ row.visit_count }}</span></td>
                                    <td class="text-end pe-4">
                                         <div class="d-flex justify-content-end gap-2">
                                             <a href="{{ url_for('book.book') }}?id={{ row.patient_id }}&type=followup" class="btn btn-sm btn-success rounded-pill px-3 shadow-sm">
                                                 <i class="fas fa-calendar-check me-1"></i> مراجعة
                                             </a>
                                             <a href="{{ url_for('book.book') }}?id={{ row.patient_id }}" class="btn btn-sm btn-primary rounded-pill px-3 shadow-sm">
                                                 <i class="fas fa-plus-circle me-1"></i> حجز كشفية
                                             </a>
                                         </div>
                                     </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
    <script>
    function cancelAppt(apptId, btn) {
        if(confirm('هل أنت متأكد من إلغاء هذا الحجز؟')) {
            window.location.href = '?cancel_appt=' + apptId;
        }
    }
    </script>
    """ + footer_html
    
    return render_template_string(html_template, 
                                  search=search, 
                                  result=result, 
                                  confirmed_today=confirmed_today, 
                                  s_today=s_today, 
                                  s_tom=s_tom, 
                                  s_week=s_week, 
                                  s_month=s_month, 
                                  today_apps=today_apps,
                                  unpaid_count=unpaid_count)
