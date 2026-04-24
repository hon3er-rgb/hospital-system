from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access, local_now_naive, local_today_str
from header import header_html
from footer import footer_html
import datetime

book_bp = Blueprint('book', __name__)

@book_bp.route('/book', methods=['GET', 'POST'])
def book():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    patient_id = request.args.get('id')
    if not patient_id:
        return redirect(url_for('patients.patients'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()

    if not patient:
        return redirect(url_for('patients.patients'))

    if request.method == 'POST':
        visit_type  = request.form.get('visit_type', 'standard')
        # is_free_auto comes from hidden input set by JS when doctor is eligible
        is_free_auto = request.form.get('is_free_auto', '0') == '1'
        is_free     = 1 if (visit_type in ['lab_only', 'rad_only'] or is_free_auto) else 0
        date        = request.form.get('date')
        appt_time   = (request.form.get('appt_time') or '').strip()
        
        # If it's today's date, we use the actual current server time (with seconds) 
        # to ensure there's no delay from the time the page was opened.
        if date == local_today_str():
            appointment_dt = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        else:
            if len(appt_time) == 5 and appt_time.count(':') == 1:
                appt_time = appt_time + ':00'
            elif not appt_time or appt_time.count(':') < 1:
                appt_time = local_now_naive().strftime('%H:%M:%S')
            appointment_dt = f"{date} {appt_time}"

        try:
            # Note: doctor_id and dept_id might be empty if Direct Lab/Rad was selected via JS skip
            f_doctor_id = request.form.get('doctor_id') or '1' # System/Admin as dummy
            f_dept_id   = request.form.get('dept_id') or '2'   # Default to General Clinic if none

            # Specific Overrides for Direct Lab/Rad
            if visit_type == 'lab_only': f_dept_id = '3'
            elif visit_type == 'rad_only': f_dept_id = '4'

            # ── Determine initial status ──
            if visit_type == 'lab_only':
                init_status = 'pending_lab_selection'
            elif visit_type == 'rad_only':
                init_status = 'pending_rad_selection'
            elif is_free_auto:
                # Free follow-up: bypass billing, go straight to triage
                init_status = 'pending_triage'
            else:
                init_status = 'scheduled'

            cursor.execute(
                "INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status, is_free) VALUES (%s, %s, %s, %s, %s, %s)",
                (patient_id, f_doctor_id, f_dept_id, appointment_dt, init_status, is_free)
            )

            conn.commit()
            
            if visit_type == 'lab_only':
                label = 'حجز مختبر (بدون كشفية)'
                flash(f"✅ تم حجز {label} بنجاح — المريض ظاهر عند المختبر لاختيار التحاليل.", "success")
                conn.close()
                return redirect(url_for('patients.patients'))
            elif visit_type == 'rad_only':
                label = 'حجز أشعة (بدون كشفية)'
                flash(f"✅ تم حجز {label} بنجاح — المريض ظاهر عند الأشعة.", "success")
                conn.close()
                return redirect(url_for('patients.patients'))
            elif is_free_auto:
                # Free follow-up — skip billing, name goes straight to triage queue
                flash(f"✅ تم حجز مراجعة مجانية — المريض توجّه مباشرةً للترياج (بدون محاسبة).", "success")
                conn.close()
                return redirect(url_for('patients.patients'))
            else:
                flash(f"✅ تم حجز موعد جديد بنجاح — المريض في قائمة انتظار المحاسبة.", "success")
                conn.close()
                return redirect(url_for('billing.billing'))
        except Exception as e:
            try: conn.rollback()
            except: pass
            flash(f"❌ خطأ أثناء الحجز: {str(e)}", "danger")


    cursor.execute("SELECT user_id, full_name_ar, department_id FROM users WHERE role='doctor'")
    doctors = cursor.fetchall()
    
    # ── Auto-fill Logic for Follow-ups ──
    cursor.execute("""
        SELECT doctor_id, department_id 
        FROM appointments 
        WHERE patient_id = %s AND status != 'cancelled' 
        ORDER BY appointment_date DESC, created_at DESC LIMIT 1
    """, (patient_id,))
    last_visit = cursor.fetchone()
    
    pre_doctor = last_visit['doctor_id'] if last_visit else None
    pre_dept   = last_visit['department_id'] if last_visit else None
    pre_type   = request.args.get('type', 'standard')

    cursor.execute("SELECT * FROM departments WHERE department_type = 'medical'")
    depts = cursor.fetchall()

    # ── 7-Day Free Follow-up Detection (Doctor-Specific) ──
    # Fetch a list of doctors this patient has paid for in the last 7 days
    seven_days_ago = (local_now_naive() - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        SELECT a.doctor_id, MAX(i.created_at) as last_paid
        FROM invoices i
        JOIN appointments a ON i.appointment_id = a.appointment_id
        WHERE i.patient_id = %s 
          AND i.status = 'paid' 
          AND i.created_at >= %s
          AND a.is_free = 0
        GROUP BY a.doctor_id
    """, (patient_id, seven_days_ago))
    paid_doctors_rows = cursor.fetchall()
    paid_doctors_ids = [row['doctor_id'] for row in paid_doctors_rows]
    
    # Pre-select based on the very last visit if eligible
    eligible_for_free_followup = len(paid_doctors_ids) > 0
    
    if not request.args.get('type'):
        if last_visit and last_visit['doctor_id'] in paid_doctors_ids:
            pre_type = 'followup'
        else:
            pre_type = 'standard'
    else:
        pre_type = request.args.get('type')

    # ── Auto-Cleanup for this patient ──
    # If they have a 'scheduled' appt that is > 5 mins late, cancel it now
    cutoff = (local_now_naive() - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE appointments SET status = 'cancelled' 
        WHERE patient_id = %s AND status = 'scheduled' 
          AND appointment_date < %s AND (is_free = 0 OR is_free IS NULL)
    """, (patient_id, cutoff))
    if cursor.rowcount > 0:
        conn.commit()

    # فحص الحجز المفتوح للمريض (أي حالة غير "مكتمل" أو "ملغي")
    cursor.execute("""
        SELECT a.*, u.full_name_ar as doc_name, d.department_name_ar
        FROM appointments a
        LEFT JOIN users u ON a.doctor_id = u.user_id
        LEFT JOIN departments d ON a.department_id = d.department_id
        WHERE a.patient_id = %s AND a.status NOT IN ('completed', 'cancelled')
        ORDER BY a.appointment_date DESC LIMIT 1
    """, (patient_id,))
    active_appt = cursor.fetchone()

    # آخر مواعيد المريض
    cursor.execute("""
        SELECT a.*, u.full_name_ar as doc_name, d.department_name_ar
        FROM appointments a
        LEFT JOIN users u ON a.doctor_id = u.user_id
        LEFT JOIN departments d ON a.department_id = d.department_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC LIMIT 5
    """, (patient_id,))
    recent_appts = cursor.fetchall()

    conn.close()

    today = local_today_str()
    default_appt_time = local_now_naive().strftime('%H:%M')
    patient_age = ''
    if patient.get('date_of_birth'):
        try:
            dob = patient['date_of_birth']
            if isinstance(dob, (datetime.date, datetime.datetime)):
                today_d = local_now_naive().date()
                patient_age = today_d.year - dob.year - ((today_d.month, today_d.day) < (dob.month, dob.day))
        except: pass

    html = header_html + """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;800&display=swap');
        /* SweetAlert Custom Styles */
        .swal2-popup { font-family: 'Cairo', sans-serif !important; border-radius: 20px !important; }

        .bk-wrap { max-width: 1000px; margin: 0 auto; padding: 28px 16px 60px; }

        /* ── Clock Banner ── */
        .bk-clock-bar {
            display: flex; align-items: center; justify-content: space-between;
            background: var(--pf-card, #fff);
            border: 1px solid var(--pf-border, #e8e4f0);
            border-radius: 16px; padding: 12px 24px; margin-bottom: 18px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        }
        
        .bk-clock-time { font-size: 1.5rem; font-weight: 800; color: #007aff; letter-spacing: 2px; font-variant-numeric: tabular-nums; }
        .bk-clock-date { font-size: 0.82rem; font-weight: 700; opacity: 0.8; }
        .bk-clock-sub  { font-size: 0.65rem; opacity: 0.4; letter-spacing: 0.3px; }

        /* ── Patient Banner ── */
        .bk-patient-bar {
            background: linear-gradient(135deg, #1e3a5f 0%, #0f2027 100%);
            border-radius: 16px; padding: 16px 22px; margin-bottom: 20px;
            color: white; display: flex; align-items: center; gap: 16px;
            box-shadow: 0 8px 28px rgba(30,58,95,0.25);
        }
        .bk-avatar {
            width: 52px; height: 52px; border-radius: 14px;
            background: rgba(255,255,255,0.12);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem; flex-shrink: 0;
            border: 1px solid rgba(255,255,255,0.15);
        }
        .bk-chip {
            display: inline-flex; align-items: center; gap: 5px;
            padding: 3px 10px; border-radius: 20px;
            font-size: 0.68rem; font-weight: 700;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.15);
        }

        /* ── Form Card ── */
        .bk-card {
            background: var(--pf-card, #fff);
            border: 1px solid var(--pf-border, #e8e4f0);
            border-radius: 20px; padding: 28px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            margin-bottom: 18px;
        }
        

        .bk-section-title {
            font-size: 0.78rem; font-weight: 800; color: #007aff;
            text-transform: uppercase; letter-spacing: 0.8px;
            margin-bottom: 16px; display: flex; align-items: center; gap: 8px;
        }
        .bk-section-title::after { content: ''; flex: 1; height: 1px; background: var(--pf-border, #e8e4f0); }
        

        /* ── Fields ── */
        .bk-field {
            width: 100%; border: 1.5px solid var(--pf-border, #e8e4f0);
            border-radius: 12px; padding: 11px 16px;
            font-size: 0.9rem; font-family: 'Cairo', sans-serif;
            background: var(--pf-bg, #fafbff); color: var(--pf-text, #1e293b);
            transition: border-color 0.2s, box-shadow 0.2s;
            appearance: none;
        }
        .bk-field:focus { outline: none; border-color: #007aff; box-shadow: 0 0 0 3px rgba(0,122,255,0.1); }
        
        
        .bk-label { font-size: 0.75rem; font-weight: 700; margin-bottom: 6px; opacity: 0.6; display: flex; align-items: center; gap: 5px; }

        /* ── Visit Type Pills ── */
        /* Updated Visit Types Grid: Handles more items elegantly */
        .visit-types { display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 12px; margin-bottom: 5px; }
        .vt-pill { display: none; }
        .vt-label {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 6px; padding: 14px 10px;
            border: 1.5px solid var(--pf-border, #e8e4f0);
            border-radius: 14px; cursor: pointer; font-size: 0.78rem; font-weight: 700;
            transition: all 0.2s; text-align: center;
            background: var(--pf-bg, #fafbff);
        }
        
        
        .vt-label i { font-size: 1.3rem; margin-bottom: 2px; }
        .vt-pill:checked + .vt-label { border-color: #007aff; background: rgba(0,122,255,0.08); color: #007aff; }
        

        /* Priority */
        .prio-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; }
        .prio-pill { display: none; }
        .prio-label {
            display: flex; align-items: center; justify-content: center; gap: 7px;
            padding: 10px; border-radius: 12px; cursor: pointer;
            font-size: 0.78rem; font-weight: 700;
            border: 1.5px solid var(--pf-border, #e8e4f0);
            background: var(--pf-bg, #fafbff); transition: all 0.2s;
        }
        .prio-pill.p-normal:checked + .prio-label  { border-color: #34c759; background: rgba(52,199,89,0.08);   color: #28a745; }
        .prio-pill.p-urgent:checked + .prio-label  { border-color: #ff9f0a; background: rgba(255,159,10,0.08);  color: #e67e00; }
        .prio-pill.p-critical:checked + .prio-label{ border-color: #ff3b30; background: rgba(255,59,48,0.08);   color: #ff3b30; }

        /* Submit */
        .bk-submit {
            width: 100%; padding: 15px; border: none; border-radius: 14px;
            font-size: 1rem; font-weight: 800; font-family: 'Cairo', sans-serif;
            cursor: pointer; transition: all 0.3s;
            background: linear-gradient(135deg, #007aff, #5856d6);
            color: white; letter-spacing: 0.3px;
            box-shadow: 0 8px 24px rgba(0,122,255,0.3);
        }
        .bk-submit:hover { transform: translateY(-3px); box-shadow: 0 14px 36px rgba(0,122,255,0.4); }
        .bk-submit:disabled { background: #ccc; color: #999; cursor: not-allowed; box-shadow: none; transform: none; }

        /* Recent Appointments */
        .recent-appt-row {
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px 14px; border-radius: 12px; margin-bottom: 8px;
            background: var(--pf-bg, #f8faff);
            border: 1px solid var(--pf-border, #e8e4f0);
            font-size: 0.8rem;
        }
        
        .appt-status-badge {
            font-size: 0.65rem; font-weight: 700; padding: 3px 10px;
            border-radius: 20px; white-space: nowrap;
        }
    </style>

    <div class="bk-wrap">

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} border-0 rounded-4 shadow-sm mb-3">
                    {{ message }}
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- ── Live Clock (hidden) ──
        <div class="bk-clock-bar">
            <div class="d-flex align-items-center gap-3">
                <div>
                    <div class="bk-clock-time" id="bkClock">--:--:--</div>
                    <div class="bk-clock-sub">التوقيت المحلي الحالي</div>
                </div>
                <div>
                    <div class="bk-clock-date" id="bkDate"></div>
                    <div class="bk-clock-sub">Book Appointment System</div>
                </div>
            </div>
            <div class="d-flex align-items-center gap-2">
                <a href="/patient_file?id={{ patient.patient_id }}" class="btn btn-sm btn-outline-secondary rounded-pill px-3">
                    <i class="fas fa-folder-open me-1"></i> ملف المريض
                </a>
                <a href="{{ url_for('patients.patients') }}" class="btn btn-sm btn-light border rounded-pill px-3">
                    <i class="fas fa-times me-1"></i> إلغاء
                </a>
            </div>
        </div -->

        <!-- ── Patient Banner ── -->
        <div class="bk-patient-bar">
            <div class="bk-avatar"><i class="fas fa-user-injured"></i></div>
            <div class="flex-grow-1">
                <div style="font-size:1.1rem;font-weight:800;">{{ patient.full_name_ar }}</div>
                <div class="d-flex flex-wrap gap-2 mt-1">
                    <span class="bk-chip"><i class="fas fa-id-card"></i> {{ patient.file_number }}</span>
                    {% if patient.gender %}
                    <span class="bk-chip"><i class="fas fa-venus-mars"></i> {{ 'ذكر' if patient.gender == 'male' else 'أنثى' }}</span>
                    {% endif %}
                    {% if patient_age %}
                    <span class="bk-chip"><i class="fas fa-birthday-cake"></i> {{ patient_age }} عاماً</span>
                    {% endif %}
                    {% if patient.phone %}
                    <span class="bk-chip"><i class="fas fa-phone"></i> {{ patient.phone }}</span>
                    {% endif %}
                </div>
            </div>
            <div style="font-size:1.8rem;opacity:0.06;font-weight:900;">BOOK</div>
        </div>

        <div class="row g-3">
            <!-- ── Main Form ── -->
            <div class="col-lg-7">

                {% if active_appt %}
                <!-- ══ Active Booking BLOCKER ══ -->
                <div style="background:linear-gradient(135deg,rgba(255,59,48,0.08),rgba(255,59,48,0.04));border:2px solid rgba(255,59,48,0.35);border-radius:18px;padding:22px 24px;margin-bottom:18px;">
                    <div class="d-flex align-items-start gap-3">
                        <div style="width:48px;height:48px;border-radius:13px;background:rgba(255,59,48,0.12);display:flex;align-items:center;justify-content:center;font-size:1.3rem;color:#ff3b30;flex-shrink:0;">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="flex-grow-1">
                            <div style="font-size:0.95rem;font-weight:800;color:#ff3b30;margin-bottom:6px;">
                                ⛔ يوجد حجز مفتوح — لا يمكن إنشاء موعد جديد
                            </div>
                            <div style="font-size:0.8rem;opacity:0.7;margin-bottom:14px;">
                                المريض لديه موعد حالته الحاليّة <b>({{ 'بانتظار الطبيب' if active_appt.status == 'waiting_doctor' else ('قيد التنفيذ' if active_appt.status == 'in_progress' else 'مجدول') }})</b>. يمكنك تحويل الموعد الحالي بدلاً من إنشاء موعد جديد.
                            </div>
                            <!-- Active appt details -->
                            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px;">
                                <div style="background:rgba(255,59,48,0.07);border-radius:10px;padding:8px 12px;border:1px solid rgba(255,59,48,0.15);">
                                    <div style="font-size:0.65rem;font-weight:700;opacity:0.5;margin-bottom:2px;">الطبيب</div>
                                    <div style="font-weight:800;font-size:0.82rem;">{{ active_appt.doc_name or '—' }}</div>
                                </div>
                                <div style="background:rgba(255,59,48,0.07);border-radius:10px;padding:8px 12px;border:1px solid rgba(255,59,48,0.15);">
                                    <div style="font-size:0.65rem;font-weight:700;opacity:0.5;margin-bottom:2px;">القسم</div>
                                    <div style="font-weight:800;font-size:0.82rem;">{{ active_appt.department_name_ar or '—' }}</div>
                                </div>
                                <div style="background:rgba(255,59,48,0.07);border-radius:10px;padding:8px 12px;border:1px solid rgba(255,59,48,0.15);">
                                    <div style="font-size:0.65rem;font-weight:700;opacity:0.5;margin-bottom:2px;">التاريخ</div>
                                    <div style="font-weight:800;font-size:0.82rem;" dir="ltr">
                                        {{ format_dt(active_appt.appointment_date, '%Y-%m-%d %H:%M') }}
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex gap-2 flex-wrap">
                                <button type="button" id="transferBtnUI" onclick="enableTransferMode()"
                                   style="display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:10px;font-size:0.82rem;font-weight:800;background:#007aff;color:white;text-decoration:none;transition:all 0.2s;border:none;box-shadow: 0 4px 12px rgba(0,122,255,0.25);">
                                    <i class="fas fa-exchange-alt"></i> تحويل لطبيب / قسم آخر
                                </button>
                                <button type="button" onclick="cancelActiveAppt({{ active_appt.appointment_id }})"
                                   style="display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:10px;font-size:0.82rem;font-weight:800;background:#ff3b30;color:white;text-decoration:none;transition:all 0.2s;border:none;box-shadow: 0 4px 12px rgba(255,59,48,0.2);">
                                    <i class="fas fa-trash-alt"></i> إلغاء الحجز
                                </button>
                                <a href="/patients"
                                   style="display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:10px;font-size:0.82rem;font-weight:700;border:1.5px solid rgba(0,0,0,0.1);color:inherit;text-decoration:none;background:transparent;">
                                    <i class="fas fa-arrow-right"></i> الرجوع
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                {% endif %}

                <!-- Disabled Form Wrapper -->
                <div id="formWrapper" {% if active_appt %}style="opacity:0.35;pointer-events:none;user-select:none;" title="لا يمكن الحجز يوجد موعد مفتوح"{% endif %}>

                <form method="POST" id="bookForm">
                    <input type="hidden" id="activeApptId" value="{{ active_appt.appointment_id if active_appt else '' }}">
                    <input type="hidden" id="isTransferMode" value="0">
                    <input type="hidden" id="isFreeAuto" name="is_free_auto" value="0">

                    <!-- Section 1: Date & Time (Moved to top) -->
                    <div class="bk-card">
                        <div class="bk-section-title"><i class="fas fa-calendar-alt"></i> التاريخ والوقت</div>
                        <div class="row g-3">
                            <div class="col-7">
                                <div class="bk-label"><i class="far fa-calendar-alt"></i> تاريخ الموعد</div>
                                <input type="date" name="date" id="dateField" class="bk-field" value="{{ today }}" min="{{ today }}" required onchange="updateSubmitButtonState()">
                            </div>
                            <div class="col-5">
                                <div class="bk-label"><i class="far fa-clock"></i> وقت الموعد</div>
                                <input type="time" name="appt_time" class="bk-field" value="{{ default_appt_time }}" required step="60">
                            </div>
                        </div>
                        <!-- Quick date pills -->
                        <div class="d-flex gap-2 mt-3 flex-wrap">
                            <span class="bk-chip" style="cursor:pointer;padding:5px 12px;" onclick="setDate(0)">اليوم</span>
                            <span class="bk-chip" style="cursor:pointer;padding:5px 12px;" onclick="setDate(1)">غداً</span>
                            <span class="bk-chip" style="cursor:pointer;padding:5px 12px;" onclick="setDate(3)">بعد 3 أيام</span>
                            <span class="bk-chip" style="cursor:pointer;padding:5px 12px;" onclick="setDate(7)">بعد أسبوع</span>
                        </div>
                    </div>

                    <!-- Section 2: Visit Type -->
                    <div class="bk-card">
                        <div class="bk-section-title"><i class="fas fa-stethoscope"></i> نوع الزيارة</div>
                        <div class="visit-types">
                            <div>
                                <input type="radio" name="visit_type" value="standard" id="vt1" class="vt-pill" {{ 'checked' if pre_type == 'standard' }} onclick="handleVisitTypeChange('standard')">
                                <label for="vt1" class="vt-label">
                                    <i class="fas fa-user-plus" style="color:#007aff;"></i>
                                    زيارة جديدة<br><small style="opacity:.6;font-weight:400;">New Visit</small>
                                </label>
                            </div>
                            {# المراجعة المجانية مخفية — يكشفها النظام تلقائياً عبر الطبيب المختار #}
                            <div>
                                <input type="radio" name="visit_type" value="lab_only" id="vt4" class="vt-pill" {{ 'checked' if pre_type == 'lab_only' }} onclick="handleVisitTypeChange('lab_only')">
                                <label for="vt4" class="vt-label">
                                    <i class="fas fa-vial-circle-check" style="color:#0ea5e9;"></i>
                                    تحليل مختبر<br><small style="opacity:.6;font-weight:400;">Direct Lab</small>
                                </label>
                            </div>
                            <div>
                                <input type="radio" name="visit_type" value="rad_only" id="vt5" class="vt-pill" {{ 'checked' if pre_type == 'rad_only' }} onclick="handleVisitTypeChange('rad_only')">
                                <label for="vt5" class="vt-label">
                                    <i class="fas fa-x-ray" style="color:#8b5cf6;"></i>
                                    فحص أشعة<br><small style="opacity:.6;font-weight:400;">Radiology</small>
                                </label>
                            </div>
                        </div>
                    </div>

                    <!-- Section 3: Department & Doctor -->
                    <div class="bk-card" id="deptDoctorCard">
                        <div class="bk-section-title"><i class="fas fa-hospital"></i> القسم والطبيب</div>
                        <div class="mb-3">
                            <div class="bk-label"><i class="fas fa-layer-group"></i> القسم / العيادة</div>
                            <select name="dept_id" id="deptFilter" class="bk-field" required onchange="filterDoctors()">
                                <option value="" disabled selected>— اختر القسم الطبي أولاً —</option>
                                {% for d in depts %}
                                <option value="{{ d.department_id }}" {{ 'selected' if pre_dept == d.department_id }}>🏥 {{ d.department_name_ar }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <div class="bk-label"><i class="fas fa-user-md"></i> الطبيب المعالج</div>
                            <select name="doctor_id" id="doctorSelect" class="bk-field" required>
                                <option value="" disabled selected>— اختر القسم أولاً —</option>
                                {% for doc in doctors %}
                                <option value="{{ doc.user_id }}" data-dept="{{ doc.department_id }}" {{ 'selected' if pre_doctor == doc.user_id }}>
                                    👨‍⚕️ د. {{ doc.full_name_ar }}
                                </option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <button type="submit" id="submitBtn" class="bk-submit">
                        <i class="fas fa-check-circle me-2"></i> تأكيد الحجز والتحويل للمحاسبة
                    </button>
                </form>
                </div><!-- end wrapper div -->
            </div>

            <!-- ── Sidebar: Recent Appointments ── -->
            <div class="col-lg-5">
                <div class="bk-card" style="position:sticky;top:80px;">
                    <div class="bk-section-title"><i class="fas fa-history"></i> آخر المواعيد</div>
                    {% if recent_appts %}
                        {% for a in recent_appts %}
                        <div class="recent-appt-row">
                            <div>
                                <div style="font-weight:700;font-size:0.82rem;">{{ a.doc_name or '—' }}</div>
                                <div style="opacity:0.5;font-size:0.7rem;">{{ a.department_name_ar or '—' }}</div>
                                <div style="opacity:0.45;font-size:0.68rem;margin-top:2px;">
                                    <i class="fas fa-calendar-alt me-1"></i>
                                    {{ format_dt(a.appointment_date, '%Y-%m-%d %H:%M') }}
                                </div>
                            </div>
                            {% set sc = {'scheduled':'#007aff','in_progress':'#ff9f0a','completed':'#34c759','cancelled':'#ff3b30'} %}
                            {% set sl = {'scheduled':'مجدول','in_progress':'جارٍ','completed':'مكتمل','cancelled':'ملغي'} %}
                            <span class="appt-status-badge" style="background:{{ sc.get(a.status,'#ccc') }}22;color:{{ sc.get(a.status,'#888') }};border:1px solid {{ sc.get(a.status,'#ccc') }}44;">
                                {{ sl.get(a.status, a.status) }}
                            </span>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="text-center py-4" style="opacity:.4;">
                            <i class="fas fa-calendar-times fa-2x mb-2"></i>
                            <p style="font-size:0.8rem;">لا توجد مواعيد سابقة</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>

    <script>
    // ── Live Clock ──
    (function() {
        var days = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
        var months = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
        function tick() {
            var clockEl = document.getElementById('bkClock');
            var dateEl = document.getElementById('bkDate');
            if(!clockEl || !dateEl) return;
            var n = new Date();
            clockEl.textContent =
                String(n.getHours()).padStart(2,'0') + ':' +
                String(n.getMinutes()).padStart(2,'0') + ':' +
                String(n.getSeconds()).padStart(2,'0');
            dateEl.textContent =
                days[n.getDay()] + ' ' + n.getDate() + ' ' + months[n.getMonth()] + ' ' + n.getFullYear();
        }
        tick(); setInterval(tick, 1000);
    })();

    // ── Quick Date Setter ──
    function setDate(days) {
        var d = new Date();
        d.setDate(d.getDate() + days);
        var y = d.getFullYear();
        var m = String(d.getMonth()+1).padStart(2,'0');
        var dd = String(d.getDate()).padStart(2,'0');
        document.getElementById('dateField').value = y + '-' + m + '-' + dd;
        updateSubmitButtonState();
    }

    // ── Update Submit Button State ──
    function updateSubmitButtonState() {
        const type = document.querySelector('input[name="visit_type"]:checked')?.value;
        const drSelect = document.getElementById('doctorSelect');
        const submitBtn = document.getElementById('submitBtn');
        const dateVal = document.getElementById('dateField').value;
        
        if (!submitBtn) return;
        
        let isValid = dateVal !== "";
        
        if (type === 'lab_only' || type === 'rad_only') {
            // Lab/Rad don't require doctor selection here (handled via skip logic)
        } else {
            isValid = isValid && drSelect.value !== "";
        }
        
        submitBtn.disabled = !isValid;
    }

    // ── Department Filter ──
    function filterDoctors() {
        var deptSel = document.getElementById('deptFilter');
        var docSel  = document.getElementById('doctorSelect');
        var selectedDept = deptSel.value;
        
        if (!docSel) return;
        
        docSel.disabled = !selectedDept;
        var opts = Array.from(docSel.options).slice(1);
        
        // Save current selection to restore if it's still valid
        const prevValue = docSel.value;
        let prevValid = false;
        
        var hasDoctors = false;
        opts.forEach(function(opt) {
            if (opt.getAttribute('data-dept') === selectedDept) {
                opt.style.display = 'block'; 
                hasDoctors = true;
                if (opt.value === prevValue) prevValid = true;
            } else {
                opt.style.display = 'none';
            }
        });
        
        if (!prevValid) docSel.value = '';
        
        if (!hasDoctors && selectedDept) {
            docSel.options[0].text = '— لا يوجد أطباء في هذا القسم —';
            docSel.disabled = true;
        } else if (selectedDept) {
            docSel.options[0].text = '— اختر الطبيب المتاح —';
            docSel.disabled = false;
        }
        
        updateSubmitButtonState();
        checkDoctorFollowup();
    }

    const eligibleDoctors = {{ eligible_doctors | tojson }};

    // -- Banner element for free follow-up notification --
    const freeFollowupBanner = document.createElement('div');
    freeFollowupBanner.id = 'freeFollowupBanner';
    freeFollowupBanner.style.cssText = 'display:none;background:linear-gradient(135deg,rgba(52,199,89,0.15),rgba(52,199,89,0.05));border:2px solid rgba(52,199,89,0.5);border-radius:14px;padding:14px 18px;margin-bottom:16px;font-size:0.88rem;font-weight:700;color:#28a745;animation:fadeIn .3s ease;';
    freeFollowupBanner.innerHTML = '<i class="fas fa-check-circle me-2"></i>مراجعة مجانية — سيتوجه المريض مباشرةً للترياج بدون محاسبة لأنه دفع الكشفية خلال 7 أيام.';

    function checkDoctorFollowup() {
        const docId = parseInt(document.getElementById('doctorSelect').value);
        const isFreeAutoInput = document.getElementById('isFreeAuto');
        const bookForm = document.getElementById('bookForm');

        if (eligibleDoctors.includes(docId)) {
            // Mark as free follow-up silently
            isFreeAutoInput.value = '1';

            // Show the green banner inside the form if not already there
            if (!document.getElementById('freeFollowupBanner')) {
                bookForm.insertBefore(freeFollowupBanner, bookForm.firstChild);
            }
            freeFollowupBanner.style.display = 'block';
        } else {
            // Not eligible — reset
            isFreeAutoInput.value = '0';
            freeFollowupBanner.style.display = 'none';
        }
    }

    document.getElementById('doctorSelect').addEventListener('change', checkDoctorFollowup);

    function handleVisitTypeChange(type) {
        const deptBlock = document.getElementById('deptDoctorCard');
        const drSelect = document.getElementById('doctorSelect');
        const deptFilter = document.getElementById('deptFilter');

        if (type === 'lab_only' || type === 'rad_only') {
            if(deptBlock) {
                deptBlock.style.display = 'none';
                deptBlock.style.opacity = '0';
            }
            if(drSelect) drSelect.required = false;
            if(deptFilter) deptFilter.required = false;
        } else {
            if(deptBlock) {
                deptBlock.style.display = 'block';
                deptBlock.style.opacity = '1';
                deptBlock.style.pointerEvents = 'auto';
            }
            if(drSelect) drSelect.required = true;
            if(deptFilter) deptFilter.required = true;
        }
        updateSubmitButtonState();
    }

    document.getElementById('doctorSelect').addEventListener('change', updateSubmitButtonState);

    document.addEventListener('DOMContentLoaded', function() {
        // First, filter doctors based on any pre-selected department
        if (document.getElementById('deptFilter').value) {
            filterDoctors();
        }
        
        // Then, handle the visit type state
        const initialType = document.querySelector('input[name="visit_type"]:checked')?.value;
        if(initialType) {
            handleVisitTypeChange(initialType);
        } else {
            // Default to standard if none selected
            handleVisitTypeChange('standard');
        }
        
        // Finally, ensure button state is correct
        updateSubmitButtonState();
    });

    // ── Direct Cancel Logic ──
    async function cancelActiveAppt(apptId) {
        const result = await Swal.fire({
            title: 'هل أنت متأكد؟',
            text: "سيتم إلغاء هذا الحجز نهائياً!",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ff3b30',
            cancelButtonColor: '#8e8e93',
            confirmButtonText: 'نعم، إلغاء الحجز',
            cancelButtonText: 'تراجع',
            reverseButtons: true
        });

        if (result.isConfirmed) {
            Swal.fire({
                title: 'جاري الإلغاء...',
                didOpen: () => { Swal.showLoading(); }
            });

            const fd = new FormData();
            fd.append('id', apptId);

            try {
                const res = await fetch("{{ url_for('api.api_cancel_appointment') }}", {
                    method: 'POST',
                    body: fd
                });
                const data = await res.json();
                if (data.success) {
                    await Swal.fire({
                        icon: 'success',
                        title: 'تم الإلغاء',
                        text: 'تم إلغاء الحجز بنجاح، يمكنك الآن حجز موعد جديد.',
                        timer: 1500,
                        showConfirmButton: false
                    });
                    window.location.reload();
                } else {
                    Swal.fire('خطأ', data.message || 'حدث خطأ أثناء الإلغاء', 'error');
                }
            } catch (e) {
                Swal.fire('خطأ', 'فشل الاتصال بالسيرفر', 'error');
            }
        }
    }

    // ── Transfer Logic ──
    function enableTransferMode() {
        const wrapper = document.getElementById('formWrapper');
        const submitBtn = document.getElementById('submitBtn');
        const isTransferInput = document.getElementById('isTransferMode');
        
        if (wrapper) {
            wrapper.style.opacity = '1';
            wrapper.style.pointerEvents = 'auto';
            wrapper.style.userSelect = 'auto';
            wrapper.title = '';
        }

        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-exchange-alt me-2"></i> تأكيد تحويل المريض للطبيب المختار';
            submitBtn.style.background = 'linear-gradient(135deg, #007aff, #34c759)';
        }

        if (isTransferInput) {
            isTransferInput.value = '1';
        }

        // Focus on dept selection
        document.getElementById('deptFilter').focus();
        
        // Scroll to the selection
        document.getElementById('deptDoctorCard').scrollIntoView({ behavior: 'smooth' });

        // Hide non-relevant sections for transfer (optional but cleaner)
        // document.querySelectorAll('.bk-card').forEach((card, idx) => {
        //    if (idx < 2) card.style.display = 'none'; 
        // });
    }

    // Intercept form submission
    document.getElementById('bookForm').addEventListener('submit', async function(e) {
        const isTransfer = document.getElementById('isTransferMode').value === '1';
        if (!isTransfer) return; // Allow normal POST

        e.preventDefault();
        
        const apptId = document.getElementById('activeApptId').value;
        const deptId = document.getElementById('deptFilter').value;
        const docId  = document.getElementById('doctorSelect').value;

        if (!deptId || !docId) {
            Swal.fire('تنبيه', 'يرجى اختيار القسم والطبيب أولاً', 'warning');
            return;
        }

        Swal.fire({
            title: 'جاري التحويل...',
            didOpen: () => { Swal.showLoading(); }
        });

        const fd = new FormData();
        fd.append('id', apptId);
        fd.append('dept_id', deptId);
        fd.append('doctor_id', docId);

        try {
            const res = await fetch("{{ url_for('api.api_transfer_appointment') }}", {
                method: 'POST',
                body: fd
            });
            const data = await res.json();
            if (data.success) {
                await Swal.fire({
                    icon: 'success',
                    title: 'تم التحويل',
                    text: 'تم تحويل المريض بنجاح إلى الطبيب/القسم المختار.',
                    timer: 1500,
                    showConfirmButton: false
                });
                window.location.reload();
            } else {
                Swal.fire('خطأ', data.message || 'حدث خطأ أثناء التحويل', 'error');
            }
        } catch (e) {
            Swal.fire('خطأ', 'فشل الاتصال بالسيرفر', 'error');
        }
    });
    </script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    """ + footer_html


    return render_template_string(html, patient=patient, doctors=doctors,
                                  depts=depts, today=today,
                                  default_appt_time=default_appt_time,
                                  patient_age=patient_age,
                                  recent_appts=recent_appts,
                                  active_appt=active_appt,
                                  eligible_doctors=paid_doctors_ids,
                                  eligible_for_free_followup=eligible_for_free_followup,
                                  pre_type=pre_type)


