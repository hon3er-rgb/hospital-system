import os, sys
# Ensure local imports are picked up from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access, local_now_naive, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
import datetime
import json

consultation_bp = Blueprint('consultation', __name__)

@consultation_bp.route('/consultation', methods=['GET', 'POST'])
def consultation():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    appt_id = request.args.get('id')
    if not appt_id:
        return redirect(url_for('doctor_clinic.doctor_clinic'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)

    sql = """
        SELECT a.*, p.*, t.blood_pressure, t.temperature, t.pulse, t.weight, t.height, t.oxygen, t.nurse_notes as triage_notes
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        LEFT JOIN triage t ON a.appointment_id = t.appointment_id
        WHERE a.appointment_id = %s
    """
    cursor.execute(sql, (appt_id,))
    data = cursor.fetchone()

    if not data:
        conn.close()
        return redirect(url_for('doctor_clinic.doctor_clinic'))

    # Calculate Age
    data['age'] = 'غير محدد'
    if data.get('date_of_birth'):
        try:
            dob = data['date_of_birth']
            if isinstance(dob, (datetime.date, datetime.datetime)):
                today = local_now_naive().date()
                data['age'] = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except: pass

    p_name = data.get('full_name_ar', 'مريض')
    cursor.execute("UPDATE users SET current_task = 'معاينة طبية جارية', active_patient_name = %s WHERE user_id = %s",
                   (p_name, session['user_id']))
    
    # Update status to 'in_progress' so the Monitor knows the patient is with the doctor
    if data['status'] == 'waiting_doctor':
        cursor.execute("UPDATE appointments SET status = 'in_progress' WHERE appointment_id = %s", (appt_id,))
    
    conn.commit()

    patient_id = data['patient_id']
    doctor_id  = session['user_id']

    cursor.execute("SELECT * FROM system_settings WHERE setting_key LIKE 'price_%'")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}

    lab_price = float(prices.get('price_lab_default', 15000))
    rad_price = float(prices.get('price_rad_default', 30000))
    rx_price  = float(prices.get('price_rx_default',  5000))
    if lab_price <= 0: lab_price = 15000
    if rad_price <= 0: rad_price = 30000
    if rx_price  <= 0: rx_price  = 5000

    if request.method == 'POST':
        if 'send_labs' in request.form:
            selected_tests = request.form.getlist('selected_tests[]')
            if selected_tests:
                for test in selected_tests:
                    cursor.execute("SELECT price FROM lab_tests WHERE test_name = %s", (test,))
                    p_row = cursor.fetchone()
                    this_price = p_row['price'] if p_row else lab_price
                    cursor.execute("""
                        INSERT INTO lab_requests (appointment_id, patient_id, doctor_id, test_type, price, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'pending_payment', %s)
                    """, (appt_id, patient_id, doctor_id, test, this_price, local_now_naive()))
                conn.commit()
                flash("تم إرسال التحاليل بنجاح للمحاسبة", "info")

        elif 'send_rads' in request.form:
            selected_scans = request.form.getlist('selected_scans[]')
            if selected_scans:
                for scan in selected_scans:
                    cursor.execute("SELECT price FROM radiology_tests WHERE test_name = %s", (scan,))
                    r_p_row = cursor.fetchone()
                    this_rad_price = r_p_row['price'] if r_p_row else rad_price
                    cursor.execute("""
                        INSERT INTO radiology_requests (appointment_id, patient_id, doctor_id, scan_type, price, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'pending_payment', %s)
                    """, (appt_id, patient_id, doctor_id, scan, this_rad_price, local_now_naive()))
                conn.commit()
                flash("تم إرسال طلبات الأشعة للمحاسبة", "info")

        elif 'send_ref' in request.form:
            to_dept = request.form.get('to_dept')
            reason  = request.form.get('reason')
            if to_dept:
                cursor.execute("""
                    INSERT INTO referrals (appointment_id, patient_id, from_doctor_id, to_department_id, reason)
                    VALUES (%s, %s, %s, %s, %s)
                """, (appt_id, patient_id, doctor_id, to_dept, reason))
                conn.commit()
                flash("تم إحالة المريض بنجاح", "warning")

        elif 'finish_visit' in request.form:
            ass  = request.form.get('assessment', '')
            sub  = request.form.get('notes', '')
            meds = request.form.get('rx', '')
            cursor.execute("""
                INSERT INTO consultations (patient_id, doctor_id, appointment_id, subjective, assessment, plan)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (patient_id, doctor_id, appt_id, sub, ass, meds))

            new_prescription_id = None
            if meds:
                cursor.execute("""
                    INSERT INTO prescriptions (appointment_id, patient_id, doctor_id, medicine_name, price, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending_payment')
                """, (appt_id, patient_id, doctor_id, meds, rx_price))
                new_prescription_id = cursor.lastrowid

            cursor.execute("UPDATE appointments SET status = 'completed', completed_at = %s WHERE appointment_id = %s", (local_now_naive(), appt_id))
            conn.commit()
            flash("تم إنهاء الزيارة وحفظ الملف الطبي", "success")
            conn.close()

            # إذا كانت توجد وصفة → اذهب لصفحة الطباعة
            if new_prescription_id:
                return redirect(url_for('print_rx.print_rx', prescription_id=new_prescription_id))
            return redirect(url_for('doctor_clinic.doctor_clinic'))


        elif 'book_followup' in request.form:
            followup_date = request.form.get('followup_date')
            if followup_date:
                try:
                    f_date   = datetime.datetime.strptime(followup_date, '%Y-%m-%d').date()
                    now_date = local_now_naive().date()
                    diff     = (f_date - now_date).days
                    is_free  = 1 if 0 <= diff <= 7 else 0
                    appt_followup_dt = f"{followup_date} {local_now_naive().strftime('%H:%M:%S')}"
                    
                    # ── Free follow-up goes directly to triage (no billing) ──
                    # Paid follow-ups (beyond 7 days) still go to billing (scheduled)
                    init_status = 'pending_triage' if is_free else 'scheduled'
                    
                    cursor.execute("""
                        INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status, is_free)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (patient_id, doctor_id, data['department_id'], appt_followup_dt, init_status, is_free))
                    conn.commit()
                    if is_free:
                        msg = f"✅ تم حجز مراجعة {followup_date} — مجانية، سيتوجه المريض للترياج مباشرةً بدون محاسبة"
                        flash(msg, "success")
                    else:
                        msg = f"تم حجز موعد {followup_date} (استشارة عادية — سيمر بالمحاسبة)"
                        flash(msg, "info")
                except Exception as e:
                    flash(f"خطأ في التاريخ: {str(e)}", "danger")

        # ─── CANCELLATION HANDLERS (NEW) ───
        elif 'cancel_lab' in request.form:
            lab_id = int(request.form.get('lab_id', 0))
            if lab_id > 0:
                # Check if session is paid to trigger refund
                cursor.execute("SELECT status FROM invoices WHERE appointment_id = %s AND status = 'paid'", (appt_id,))
                is_paid = cursor.fetchone() is not None
                ref_status = 'refund_needed' if is_paid else None
                
                cursor.execute("""
                    UPDATE lab_requests 
                    SET status = 'cancelled', refund_status = %s, cancelled_at = %s 
                    WHERE request_id = %s
                """, (ref_status, local_now_naive(), lab_id))
                conn.commit()
                flash("تم إلغاء طلب المختبر" + (" وإرسال طلب استرداد للمحاسبة" if is_paid else ""), "warning")

        elif 'cancel_rad' in request.form:
            rad_id = int(request.form.get('rad_id', 0))
            if rad_id > 0:
                cursor.execute("SELECT status FROM invoices WHERE appointment_id = %s AND status = 'paid'", (appt_id,))
                is_paid = cursor.fetchone() is not None
                ref_status = 'refund_needed' if is_paid else None
                
                cursor.execute("""
                    UPDATE radiology_requests 
                    SET status = 'cancelled', refund_status = %s, cancelled_at = %s 
                    WHERE request_id = %s
                """, (ref_status, local_now_naive(), rad_id))
                conn.commit()
                flash("تم إلغاء طلب الأشعة" + (" وإرسال طلب استرداد للمحاسبة" if is_paid else ""), "warning")

        elif 'cancel_visit_now' in request.form:
            cursor.execute("SELECT status FROM invoices WHERE appointment_id = %s AND status = 'paid'", (appt_id,))
            is_paid = cursor.fetchone() is not None
            ref_status = 'refund_needed' if is_paid else None
            
            cursor.execute("""
                UPDATE appointments 
                SET status = 'cancelled', refund_status = %s, cancelled_at = %s 
                WHERE appointment_id = %s
            """, (ref_status, local_now_naive(), appt_id))
            conn.commit()
            flash("تم إلغاء الزيارة" + (" وسيتم إشعار الحسابات برد المبلغ" if is_paid else ""), "danger")
            return redirect(url_for('doctor_clinic.doctor_clinic'))

    # ── Master data lists ──
    def safe_decode(text):
        if not text: return ""
        if isinstance(text, bytes):
            try:    text = text.decode('utf-8')
            except:
                try: text = text.decode('cp1256')
                except: text = str(text)
        else:
            text = str(text)
        return text.replace('\ufffd', '').replace('\u0000', '').strip()

    cursor.execute("SELECT test_name FROM lab_tests WHERE is_active = 1 ORDER BY test_name ASC")
    lab_list = [safe_decode(r['test_name']) for r in cursor.fetchall()]
    for dl in ['CBC','FBS','HBA1C','Urea','Creatinine','SGOT','SGPT','Lipid Profile','TSH','Vitamin D','CRP','Urine R/E','Stool R/E','H. Pylori','PSA']:
        if dl not in lab_list: lab_list.append(dl)

    cursor.execute("SELECT test_name FROM radiology_tests WHERE is_active = 1 ORDER BY test_name ASC")
    rad_list = [safe_decode(r['test_name']) for r in cursor.fetchall()]
    for dr in ['X-Ray Chest','U/S Abdomen','CT Brain','MRI Brain','X-Ray Knee','U/S Pelvis']:
        if dr not in rad_list: rad_list.append(dr)

    cursor.execute("SELECT * FROM lab_requests       WHERE appointment_id = %s", (appt_id,))
    curr_labs = cursor.fetchall()
    cursor.execute("SELECT * FROM radiology_requests WHERE appointment_id = %s", (appt_id,))
    curr_rads = cursor.fetchall()
    cursor.execute("SELECT * FROM departments WHERE department_type = 'medical'")
    depts = cursor.fetchall()
    cursor.execute("""
        SELECT c.*, u.full_name_ar as doc_name
        FROM consultations c
        JOIN users u ON c.doctor_id = u.user_id
        WHERE c.patient_id = %s ORDER BY c.created_at DESC
    """, (patient_id,))
    history = cursor.fetchall()
    
    # ── Active requests for easy cancellation ──
    cursor.execute("""
        SELECT * FROM lab_requests 
        WHERE appointment_id = %s AND status != 'cancelled' AND (result IS NULL OR result = '')
    """, (appt_id,))
    active_labs = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM radiology_requests 
        WHERE appointment_id = %s AND status != 'cancelled' AND (report IS NULL OR report = '')
    """, (appt_id,))
    active_rads = cursor.fetchall()

    diag_list = ['Influenza','Acute Pharyngitis','Gastroenteritis','Hypertension','Diabetes Mellitus Type 2',
                 'Bronchial Asthma','Urinary Tract Infection (UTI)','Migraine','Tension Headache','Back Pain',
                 'Upper Respiratory Tract Infection','Anemia','Allergic Rhinitis','Otitis Media','Acute Sinusitis']
    med_list  = ['Paracetamol 500mg','Amoxicillin 500mg','Ibuprofen 400mg','Omeprazole 20mg','Metformin 500mg',
                 'Loratadine 10mg','Salbutamol Inhaler','Azithromycin 250mg','Ciprofloxacin 500mg','Augmentin 625mg',
                 'Buscopan 10mg','Panadol Extra','Cough Syrup','Vitamin C 1000mg','Diclofenac 50mg']

    cursor.execute("""
        SELECT lr.*, u.full_name_ar as doc_name 
        FROM lab_requests lr 
        LEFT JOIN users u ON lr.doctor_id = u.user_id 
        WHERE lr.patient_id = %s AND lr.result IS NOT NULL AND lr.result != ''
        ORDER BY lr.created_at DESC
    """, (patient_id,))
    lab_history = cursor.fetchall()

    cursor.execute("""
        SELECT rr.*, u.full_name_ar as doc_name 
        FROM radiology_requests rr 
        LEFT JOIN users u ON rr.doctor_id = u.user_id 
        WHERE rr.patient_id = %s AND rr.report IS NOT NULL AND rr.report != ''
        ORDER BY rr.created_at DESC
    """, (patient_id,))
    rad_history = cursor.fetchall()


    html = header_html + """

    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        body { background:#f0f2f5; font-family:'Inter',sans-serif; }

        /* Sidebar */
        .hp-sidebar {
            background: linear-gradient(160deg, #0f2027, #203a43, #2c5364);
            border-radius: 22px; color:#fff; position: sticky; top: 76px; overflow: hidden;
        }
        .hp-sidebar::before {
            content:''; position:absolute; width:200px; height:200px;
            background:rgba(255,255,255,0.04); border-radius:50%;
            top:-50px; right:-50px; pointer-events:none;
        }
        .avatar-circle {
            width:78px; height:78px; border-radius:50%; margin:0 auto 14px;
            background: linear-gradient(135deg,#43e97b,#38f9d7);
            display:flex; align-items:center; justify-content:center;
            font-size:2rem; color:#fff;
            box-shadow: 0 8px 24px rgba(67,233,123,0.35);
        }
        .vital-row {
            background:rgba(255,255,255,0.09); border-radius:12px;
            padding:10px 14px; margin-bottom:8px;
            display:flex; align-items:center; gap:10px;
        }
        .vital-icon {
            width:34px; height:34px; border-radius:9px;
            display:flex; align-items:center; justify-content:center; font-size:0.88rem;
        }
        .vital-label { font-size:0.68rem; opacity:0.55; }
        .vital-val   { font-size:0.95rem; font-weight:700; }

        /* Tabs - Professional High-Density Single Row */
        .hp-tabs {
            background: #fff;
            border-radius: 18px;
            padding: 4px;
            display: flex;
            flex-wrap: nowrap;
            gap: 2px; /* Smaller gap to fit more items */
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            margin-bottom: 22px;
            overflow-x: auto;
            scrollbar-width: none;
            -ms-overflow-style: none;
            width: 100%;
        }
        .hp-tabs::-webkit-scrollbar { display: none; }

        .hp-tab {
            border: none;
            border-radius: 13px;
            padding: 8px 12px; /* Reduced horizontal padding (was 18px) */
            font-size: 0.82rem; /* Slightly smaller for better fit */
            font-weight: 700;
            color: #636e72;
            background: transparent;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
            flex-shrink: 0;
        }

        .hp-tab i { font-size: 0.9rem; } /* Consistent icon sizing */

        .hp-tab .cnt {
            background: #dfe6e9;
            color: #2d3436;
            border-radius: 20px;
            padding: 1px 6px;
            font-size: 0.7rem;
            font-weight: 800;
            transition: all 0.2s;
        }

        .hp-tab:hover {
            background: rgba(102, 126, 234, 0.05);
            color: #667eea;
        }

        .hp-tab.active {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        .hp-tab.active .cnt { background: rgba(255, 255, 255, 0.3); color: #fff; }

        /* Cards */
        .hp-card {
            background:#fff; border-radius:18px; padding:24px;
            box-shadow:0 2px 14px rgba(0,0,0,0.045); margin-bottom:18px;
        }
        .hp-card-title {
            font-size:0.92rem; font-weight:700; color:#1c1c1e;
            margin-bottom:14px; display:flex; align-items:center; gap:10px;
        }
        .title-icon {
            width:32px; height:32px; border-radius:9px;
            display:flex; align-items:center; justify-content:center; font-size:0.82rem;
        }

        /* Inputs */
        .hp-field {
            width:100%; border:2px solid #eef0f5; border-radius:13px;
            padding:12px 16px; font-size:0.93rem; background:#fafbff;
            transition:border-color .2s; color:#1c1c1e;
            font-family:'Inter',sans-serif;
        }
        .hp-field:focus { outline:none; border-color:#667eea; background:#fff; }
        textarea.hp-field { resize:vertical; }

        /* Search wrapper */
        .search-wrap { position:relative; }
        .search-wrap .s-icon {
            position:absolute; right:14px; top:50%; transform:translateY(-50%);
            color:#bbb; font-size:0.9rem; pointer-events:none;
        }
        .search-wrap .hp-field { padding-right:40px; }

        /* Grid */
        .items-grid {
            display:grid;
            grid-template-columns:repeat(auto-fill, minmax(148px,1fr));
            gap:7px; max-height:220px; overflow-y:auto; padding:2px;
        }
        .g-item {
            background:#f7f8ff; border:1.5px solid #e6e8f5; border-radius:11px;
            padding:9px 10px; cursor:pointer; font-size:0.8rem; font-weight:600;
            color:#555; text-align:center; transition:all .18s; user-select:none;
        }
        .g-item:hover {
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:#fff; border-color:transparent;
            transform:translateY(-2px); box-shadow:0 5px 14px rgba(102,126,234,.28);
        }

        /* Tags */
        .tags-area {
            min-height:68px; background:#f8f9ff; border-radius:13px;
            padding:10px; display:flex; flex-wrap:wrap; gap:7px;
            align-content:flex-start; border:2px dashed #dde0f5; margin:14px 0;
        }
        .tags-area .empty-hint {
            width:100%; text-align:center; color:#c5c7d8; font-size:0.82rem; padding:8px 0;
        }
        .hp-tag {
            background:linear-gradient(135deg,#eef0ff,#f0eaff);
            color:#667eea; border:1.5px solid #cdd0f5;
            border-radius:20px; padding:5px 13px;
            font-size:0.8rem; font-weight:700;
            display:inline-flex; align-items:center; gap:7px;
        }
        .hp-tag .x { cursor:pointer; color:#e74c3c; font-size:0.72rem; transition:.15s; }
        .hp-tag .x:hover { transform:scale(1.4); }

        /* Buttons */
        .hp-btn {
            display:block; width:100%; padding:13px; border:none;
            border-radius:13px; font-size:0.97rem; font-weight:700;
            cursor:pointer; transition:all .2s; letter-spacing:.3px;
        }
        .hp-btn-primary {
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:#fff; box-shadow:0 6px 18px rgba(102,126,234,.3);
        }
        .hp-btn-primary:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(102,126,234,.42); }
        .hp-btn-labs  { background:linear-gradient(135deg,#007aff,#5856d6); color:#fff; }
        .hp-btn-rads  { background:linear-gradient(135deg,#5ac8fa,#007aff); color:#fff; }
        .hp-btn-ref   { background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; }
        .hp-btn-fup   { background:linear-gradient(135deg,#27ae60,#2ecc71); color:#fff; }
        .hp-btn:disabled { background:#e5e5ea; color:#aaa; cursor:not-allowed; box-shadow:none; transform:none; }
        .hp-btn:not(:disabled):hover { filter:brightness(1.06); }

        /* Sidebar btn */
        .sidebar-btn {
            display:block; width:100%; padding:11px; border-radius:12px; border:none;
            font-size:0.88rem; font-weight:700; cursor:pointer; text-align:center;
            transition:all .2s; text-decoration:none;
        }

        /* Modal */
        .hist-item {
            background:#fff; border-radius:14px; border:1.5px solid #f0f0f8;
            padding:16px; margin-bottom:10px; transition:border-color .2s;
        }
        .hist-item:hover { border-color:#667eea; }
    </style>

    <div class="container-fluid px-3 px-md-4 py-4" style="max-width:1500px;margin:0 auto;">
        <div class="row g-4">

            <!-- ══════ MAIN AREA (FULL WIDTH) ══════ -->
            <div class="col-lg-12">
                
                <!-- ══════ DOCTOR'S CLINICAL BANNER ══════ -->
                <div class="hp-card d-flex align-items-center gap-3 py-2 px-4 mb-4" style="background: linear-gradient(135deg, #0f2027, #203a43); color: #fff; border:none; border-radius: 15px; box-shadow: 0 5px 25px rgba(0,0,0,0.1);">
                    <div class="avatar-circle m-0" style="width: 48px; height: 48px; font-size: 1.1rem; background: rgba(255,255,255,0.1);">
                        <i class="fas fa-user-md"></i>
                    </div>
                    <div class="me-auto">
                        <h4 class="fw-bold mb-0" style="font-size: 1.1rem;">{{ data.full_name_ar }}</h4>
                        <div class="d-flex gap-2 mt-0 opacity-50 x-small" style="font-size: 0.7rem;">
                            <span><i class="fas fa-id-card me-1"></i>{{ data.file_number }}</span>
                            <span><i class="fas fa-venus-mars me-1"></i>{{ data.gender or 'عير محدد' }}</span>
                            <span><i class="fas fa-child me-1"></i>{{ data.age }} عاماً</span>
                        </div>
                    </div>

                    <!-- Clinical Vitals Row -->
                    <div class="d-flex align-items-center gap-2">
                        <div class="mini-vital px-3 py-1 text-center animate-in" style="background: rgba(255,80,80,0.12); border-radius: 10px; border: 1px solid rgba(255,80,80,0.2);">
                            <div style="font-size: 0.6rem; opacity: 0.5; font-weight: 700;">B.P</div>
                            <div class="fw-bold" style="font-size: 0.95rem; color: #ff6b6b;">{{ data.blood_pressure or '--' }}</div>
                        </div>
                        <div class="mini-vital px-3 py-1 text-center animate-in" style="background: rgba(255,180,0,0.12); border-radius: 10px; border: 1px solid rgba(255,180,0,0.2);">
                            <div style="font-size: 0.6rem; opacity: 0.5; font-weight: 700;">TEMP</div>
                            <div class="fw-bold" style="font-size: 0.95rem; color: #ffd93d;">{{ data.temperature or '--' }}°</div>
                        </div>
                        <div class="mini-vital px-3 py-1 text-center animate-in" style="background: rgba(76,217,100,0.12); border-radius: 10px; border: 1px solid rgba(76,217,100,0.2);">
                            <div style="font-size: 0.6rem; opacity: 0.5; font-weight: 700;">PULSE</div>
                            <div class="fw-bold" style="font-size: 0.95rem; color: #4cd964;">{{ data.pulse or '--' }}</div>
                        </div>
                        <div class="mini-vital px-3 py-1 text-center animate-in" style="background: rgba(90,200,250,0.12); border-radius: 10px; border: 1px solid rgba(90,200,250,0.2);">
                            <div style="font-size: 0.6rem; opacity: 0.5; font-weight: 700;">SPO2</div>
                            <div class="fw-bold" style="font-size: 0.95rem; color: #5ac8fa;">{{ data.oxygen or '--' }}%</div>
                        </div>
                    </div>

                    <div class="d-flex gap-1 ms-3">
                        <a href="/patient_file?id={{ data.patient_id }}" target="_blank" class="btn btn-sm btn-outline-light rounded-pill border-0" title="السجل الكامل"><i class="fas fa-folder-open"></i></a>
                        <a href="{{ url_for('consultation.consultation', id=data.appointment_id) }}" class="btn btn-sm btn-outline-light rounded-pill border-0" title="تحديث"><i class="fas fa-sync-alt"></i></a>
                    </div>
                </div>



                <!-- Tabs -->
                <div class="hp-tabs">
                    <button type="button" class="hp-tab active" data-hp-target="t-exam"><i class="fas fa-stethoscope"></i> المعاينة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-history-full"><i class="fas fa-file-medical"></i> السجل الطبي</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-labs"><i class="fas fa-flask"></i> المختبر <span class="cnt" id="labBadge">0</span></button>
                    <button type="button" class="hp-tab"        data-hp-target="t-rads"><i class="fas fa-radiation"></i> الأشعة <span class="cnt" id="radBadge">0</span></button>
                    <button type="button" class="hp-tab"        data-hp-target="t-rx"><i class="fas fa-pills"></i> الأدوية</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-res"><i class="fas fa-microscope"></i> نتائج الفحوصات</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-ref"><i class="fas fa-share-alt"></i> إحالة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-fup"><i class="fas fa-calendar-check"></i> مراجعة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-notes"><i class="fas fa-edit"></i> ملاحظات</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-manage" style="background:#fffdec;color:#856404;"><i class="fas fa-tasks"></i> إدارة وإلغاء</button>
                </div>

                <!-- ─── EXAM ─── -->
                <div id="t-exam" class="hp-tab-pane">
                    <form method="POST">

                        <div class="hp-card">
                            <div class="hp-card-title">
                                <span class="title-icon" style="background:#eef0ff;color:#667eea;"><i class="fas fa-file-medical-alt"></i></span>
                                الشكوى والملاحظات السريرية
                                <button type="button" class="btn btn-sm rounded-pill ms-auto px-3 border-0 shadow-sm hp-mic-btn" 
                                        style="background: #fdfdfd; color: #667eea; font-size: 0.8rem; height: 32px;"
                                        onclick="hpStartSpeech('notes', this)">
                                    <i class="fas fa-microphone me-1"></i> إملاء صوتي
                                </button>
                            </div>
                            <textarea name="notes" id="notes-area" class="hp-field" rows="5"
                                      placeholder="اكتب الأعراض، المدة، الشدة..." required></textarea>
                        </div>

                        <div class="hp-card">
                            <div class="hp-card-title">
                                <span class="title-icon" style="background:#fff0f0;color:#e74c3c;"><i class="fas fa-stethoscope"></i></span>
                                التشخيص النهائي (Assessment)
                                <button type="button" class="btn btn-sm rounded-pill ms-auto px-3 border-0 shadow-sm hp-mic-btn" 
                                        style="background: #fdfdfd; color: #e74c3c; font-size: 0.8rem; height: 32px;"
                                        onclick="hpStartSpeech('assessment', this)">
                                    <i class="fas fa-microphone me-1"></i> إملاء
                                </button>
                            </div>
                            <div class="search-wrap">
                                <input type="text" name="assessment"
                                       list="diagDatalist" class="hp-field"
                                       placeholder="اكتب أو ابحث عن التشخيص من أول حرف..."
                                       required autocomplete="on">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <datalist id="diagDatalist">
                                {% for d in diag_list %}<option value="{{ d }}">{% endfor %}
                            </datalist>
                        </div>

                        <div class="hp-card">
                            <div class="hp-card-title" style="flex-wrap:wrap;gap:8px;">
                                <span class="title-icon" style="background:#f0fff4;color:#27ae60;"><i class="fas fa-pills"></i></span>
                                الخطة العلاجية والوصفة الطبية (Rx)
                                <button type="button" class="btn btn-sm rounded-pill ms-auto px-3 border-0 shadow-sm hp-mic-btn" 
                                        style="background: #fdfdfd; color: #27ae60; font-size: 0.8rem; height: 32px;"
                                        onclick="hpStartSpeech('plan', this)">
                                    <i class="fas fa-microphone me-1"></i> إملاء الوصفة
                                </button>
                                <div class="dropdown">
                                    <button type="button" class="btn btn-sm rounded-pill fw-semibold"
                                            style="background:#f0fff4;color:#27ae60;font-size:0.8rem;"
                                            data-bs-toggle="dropdown">
                                        <i class="fas fa-magic me-1"></i>قوالب جاهزة
                                    </button>
                                    <ul class="dropdown-menu dropdown-menu-end shadow border-0 rounded-4 p-2">
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Paracetamol 500mg - 3x daily\\nAmoxicillin 500mg - every 8h\\nRest for 3 days')">
                                            🤒 Flu / Fever</button></li>
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Buscopan 10mg - 3x daily\\nAntacid - 10ml after meals\\nAvoid spicy food')">
                                            😣 Stomach Ache</button></li>
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Cough Syrup 5ml - 3x daily\\nVitamin C 1000mg once daily\\nSteam inhalation')">
                                            🤧 Cough / Cold</button></li>
                                    </ul>
                                </div>
                            </div>
                            <div class="search-wrap mb-3">
                                <input type="text" id="medInput" list="medDatalist" class="hp-field"
                                       placeholder="ابحث عن دواء واضغط Enter لإضافته للوصفة..."
                                       autocomplete="on">
                                <i class="fas fa-pills s-icon" style="color:#27ae60;"></i>
                            </div>
                            <datalist id="medDatalist">
                                {% for m in med_list %}<option value="{{ m }}">{% endfor %}
                            </datalist>
                            <textarea name="rx" id="rxArea" class="hp-field" rows="4"
                                      placeholder="الوصفة الطبية وتعليمات العلاج..."></textarea>
                        </div>

                        <button type="submit" name="finish_visit" class="hp-btn hp-btn-primary" style="font-size:1rem;">
                            <i class="fas fa-file-signature me-2"></i>إنهاء المعاينة وحفظ السجل الطبي
                        </button>
                    </form>
                </div>

                <!-- ─── HISTORY FULL ─── -->
                <div id="t-history-full" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title text-primary">
                            <span class="title-icon" style="background:#eef4ff;color:#007aff;"><i class="fas fa-book-medical"></i></span>
                            السجل التاريخي الشامل للزيارات
                        </div>
                        <div class="row">
                            <div class="col-12">
                                {% for h in history %}
                                <div class="hist-item mb-3 shadow-sm" style="border-right: 5px solid #667eea;">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <div class="d-flex align-items-center gap-2">
                                            <span class="badge bg-primary rounded-pill">زيارة طبية</span>
                                            <span class="fw-bold text-dark">{{ h.doc_name }}</span>
                                        </div>
                                        <span class="text-muted small">
                                            {{ dt(h.created_at, '%Y-%m-%d | %I:%M:%S %p') }}
                                        </span>
                                    </div>
                                    <div class="mb-2"><strong class="text-danger small">التشخيص:</strong> <span class="fw-bold">{{ h.assessment }}</span></div>
                                    <div class="p-3 bg-light rounded-3 mb-2 small text-muted" style="border: 1px dashed #ddd;">{{ h.subjective }}</div>
                                    {% if h.plan %}
                                    <div class="p-2 rounded-3 small" style="background:#f0fff4;color:#27ae60;border: 1px solid #dcfce7;">
                                        <i class="fas fa-pills me-1"></i> <strong class="small">العلاج:</strong> {{ h.plan }}
                                    </div>
                                    {% endif %}
                                </div>
                                {% else %}
                                <div class="text-center py-5 opacity-50">
                                    <i class="fas fa-folder-open fa-3x mb-3"></i>
                                    <h6>لا توجد زيارات سابقة مؤرشفة</h6>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
                <div id="t-labs" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#eef4ff;color:#007aff;"><i class="fas fa-flask"></i></span>
                            طلب فحوصات مخبرية
                            <span class="badge rounded-pill ms-auto px-3" style="background:#eef4ff;color:#007aff;">
                                <i class="fas fa-vials me-1"></i>اختر من الشبكة أو ابحث
                            </span>
                        </div>

                        <div class="search-wrap mb-3 d-flex gap-2">
                            <div class="position-relative flex-grow-1">
                                <input type="text" id="labSearch" class="hp-field w-100"
                                       placeholder="ابحث من أول حرف... (مثال: c أو CBC)"
                                       autocomplete="off">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <button type="button" id="labAddBtn" class="btn hp-btn-labs m-0" style="width:auto; padding:0 24px; border-radius:13px;"><i class="fas fa-plus me-1"></i>إضافة</button>
                        </div>

                        <div class="items-grid" id="labGrid">
                            {% for item in lab_list %}
                            <div class="g-item" data-val="{{ item }}">{{ item }}</div>
                            {% endfor %}
                        </div>

                        <div class="tags-area" id="selectedLabs">
                            <div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على فحص أو ابحث ثم Enter لإضافته</div>
                        </div>

                        <form method="POST">
                            <div id="labHidden"></div>
                            <button type="submit" name="send_labs" class="hp-btn hp-btn-labs" id="labSubmitBtn" disabled>
                                <i class="fas fa-paper-plane me-2"></i>إرسال طلبات المختبر (<span id="labCount">0</span> فحص)
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── RADS ─── -->
                <div id="t-rads" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#e8f9ff;color:#5ac8fa;"><i class="fas fa-x-ray"></i></span>
                            طلب فحوصات شعاعية
                            <span class="badge rounded-pill ms-auto px-3" style="background:#e8f9ff;color:#5ac8fa;">
                                <i class="fas fa-radiation me-1"></i>اختر من الشبكة أو ابحث
                            </span>
                        </div>

                        <div class="search-wrap mb-3 d-flex gap-2">
                            <div class="position-relative flex-grow-1">
                                <input type="text" id="radSearch" class="hp-field w-100"
                                       placeholder="ابحث من أول حرف... (مثال: x أو CT)"
                                       autocomplete="off">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <button type="button" id="radAddBtn" class="btn hp-btn-rads m-0" style="width:auto; padding:0 24px; border-radius:13px;"><i class="fas fa-plus me-1"></i>إضافة</button>
                        </div>

                        <div class="items-grid" id="radGrid">
                            {% for item in rad_list %}
                            <div class="g-item" data-val="{{ item }}">{{ item }}</div>
                            {% endfor %}
                        </div>

                        <div class="tags-area" id="selectedRads">
                            <div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على أشعة أو ابحث ثم Enter لإضافتها</div>
                        </div>

                        <form method="POST">
                            <div id="radHidden"></div>
                            <button type="submit" name="send_rads" class="hp-btn hp-btn-rads" id="radSubmitBtn" disabled>
                                <i class="fas fa-paper-plane me-2"></i>إرسال طلبات الأشعة (<span id="radCount">0</span> فحص)
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── RX ─── -->
                <div id="t-rx" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#fefce8;color:#ca8a04;"><i class="fas fa-pills"></i></span>
                            الوصفات الطبية والعلاجات المقترحة
                        </div>
                        <div class="p-4 text-center opacity-50">
                            <i class="fas fa-prescription fa-3x mb-3"></i>
                            <p>تتم كتابة العلاج في تبويب "المعاينة" وسيظهر ملخصه هنا بشكل تلقائي للمراجعة.</p>
                        </div>
                    </div>
                </div>

                <!-- ─── NOTES ─── -->
                <div id="t-notes" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#eefdf9;color:#0d9488;"><i class="fas fa-user-tag"></i></span>
                            ملاحظات الطبيب الداخلية
                        </div>
                        <textarea class="hp-field pt-3" rows="8" placeholder="هنا يمكنك كتابة ملاحظات خاصة لن يراها المريض..."></textarea>
                    </div>
                </div>

                <!-- ─── REFERRAL ─── -->
                <div id="t-ref" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#fff8e1;color:#f39c12;"><i class="fas fa-share-alt"></i></span>
                            تحويل المريض إلى عيادة أخرى
                        </div>
                        <form method="POST">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="fw-semibold small text-muted mb-1">العيادة المحول إليها</label>
                                    <select name="to_dept" class="hp-field">
                                        {% for d in depts %}
                                        <option value="{{ d.department_id }}">{{ d.department_name_ar }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-12">
                                    <label class="fw-semibold small text-muted mb-1">سبب التحويل</label>
                                    <textarea name="reason" class="hp-field" rows="3" placeholder="لماذا يتم تحويل المريض؟"></textarea>
                                </div>
                                <div class="col-12">
                                    <button type="submit" name="send_ref" class="hp-btn hp-btn-ref">
                                        <i class="fas fa-check-circle me-2"></i>تأكيد عملية الإحالة
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- ─── FOLLOW-UP ─── -->
                <div id="t-fup" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card text-center">
                        <div class="hp-card-title" style="justify-content:center;">
                            <span class="title-icon" style="background:#f0fff4;color:#27ae60;"><i class="fas fa-calendar-check"></i></span>
                            تحديد موعد مراجعة (Follow-up)
                        </div>
                        <form method="POST" style="max-width:360px;margin:0 auto;">
                            <div class="mb-4">
                                <label class="fw-semibold small text-muted mb-1 d-block">تاريخ المراجعة</label>
                                <input type="date" name="followup_date" class="hp-field text-center"
                                       value="{{ followup_date_val }}" min="{{ today_date }}">
                            </div>
                            <button type="submit" name="book_followup" class="hp-btn hp-btn-fup">
                                <i class="fas fa-calendar-plus me-2"></i>تأكيد حجز موعد المراجعة
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── RESULTS ─── -->
                <div id="t-res" class="hp-tab-pane" style="display:none;">
                    <div class="row g-4">
                        <!-- ══════ LABORATORY RESULTS (HIGH DENSITY) ══════ -->
                        <div class="col-12 mb-3">
                            <div class="d-flex align-items-center justify-content-between py-2 px-3 mb-3 rounded-4 shadow-sm" style="background: rgba(0, 122, 255, 0.04); border-right: 5px solid #007aff;">
                                <h6 class="fw-bold m-0 d-flex align-items-center gap-2" style="color:#1e293b; font-size: 0.95rem;">
                                    <i class="fas fa-flask text-primary"></i> نتائج المختبر والتحاليل (Lab Results)
                                </h6>
                                <button type="button" class="btn btn-sm rounded-pill px-3 fw-bold border-0 shadow-sm hp-toggle-btn" 
                                        style="background: #ffffff; color: #007aff; font-size: 0.8rem; height: 32px; transition: all 0.3s ease;" 
                                        onclick="hpToggleSection('lab-results-content', this)">
                                    <i class="fas fa-eye-slash me-1"></i> إخفاء الفحوصات
                                </button>
                            </div>
                            
                            <div id="lab-results-content" style="transition: all 0.4s ease-in-out;">
                                {% set ns_lab = namespace(last_date='') %}
                                
                                {# 1. Separate Labs into Regular and Profiles #}
                                {% set regular_labs = [] %}
                                {% set profile_labs = [] %}
                                {% for lr in lab_history %}
                                    {% if 'PROFILE' in lr.test_type|upper or 'بروفايل' in lr.test_type %}
                                        {% set _ = profile_labs.append(lr) %}
                                    {% else %}
                                        {% set _ = regular_labs.append(lr) %}
                                    {% endif %}
                                {% endfor %}

                                {# 2. Render Regular Labs in a Professional List #}
                                {% if regular_labs %}
                                    <div class="hp-card mb-4 p-0 overflow-hidden border-0 shadow-sm" style="border-radius: 12px; background: #fff;">
                                        <div class="bg-light p-3 border-bottom d-flex align-items-center gap-2" style="background: #f8fafc !important;">
                                            <i class="fas fa-list-ul text-primary small"></i>
                                            <span class="fw-bold text-dark small">التحاليل المباشرة (Individual Tests)</span>
                                        </div>
                                        <div class="table-responsive">
                                            <table class="table table-hover mb-0 align-middle" style="font-size: 0.95rem;" id="labResultsTable">
                                                <thead>
                                                    <tr class="text-muted small">
                                                        <th class="ps-4 py-3 border-0">نوع الفحص</th>
                                                        <th class="py-3 border-0">النتيجة</th>
                                                        <th class="py-3 border-0">المدى الطبيعي</th>
                                                        <th class="py-3 border-0 text-center">الحالة</th>
                                                        <th class="py-3 border-0">التاريخ</th>
                                                        <th class="pe-4 border-0 text-center">إجراء</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {% for lr in regular_labs %}
                                                    <tr style="border-bottom: 1px solid #f1f5f9;" 
                                                        data-test-name="{{ lr.test_type|upper }}" 
                                                        data-result-val="{{ lr.result }}">
                                                        <td class="ps-4 py-3 fw-bold text-dark">{{ lr.test_type }}</td>
                                                        <td class="py-3"><span class="result-display fw-bold">{{ lr.result }}</span></td>
                                                        <td class="py-3 text-muted small range-display">--</td>
                                                        <td class="py-3 text-center status-cell"><span class="badge bg-light text-muted rounded-pill px-3">جاري التحقق..</span></td>
                                                        <td class="py-3 text-muted small" style="font-size: 0.8rem;">
                                                            {{ dt(lr.created_at) }}
                                                        </td>
                                                        <td class="pe-4 text-center">
                                                            <button class="btn btn-sm btn-light border-0 rounded-circle" onclick="alert('تقرير المختبر: {{ lr.test_type }}\n\nالنتيجة: {{ lr.result|replace('\n', ' ') }}')"><i class="fas fa-search-plus text-primary"></i></button>
                                                        </td>
                                                    </tr>
                                                    {% endfor %}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                {% endif %}

                                {# 3. Render Profile Labs in the Original Card Format #}
                                {% if profile_labs %}
                                    <div class="mb-2 mt-4 small text-muted fw-bold ps-2"><i class="fas fa-clipboard-list me-1"></i> التقارير المتكاملة (Profile Reports)</div>
                                    {% for lr in profile_labs %}
                                        <div class="hp-card mb-3 p-4 border-0 shadow-sm" style="border-right: 8px solid #007aff; border-radius: 16px; background: #ffffff;">
                                            <div class="d-flex justify-content-between align-items-center mb-3">
                                                <div class="fw-bold fs-5 text-dark"><i class="fas fa-microscope text-primary me-2"></i> {{ lr.test_type }}</div>
                                                <span class="badge bg-light text-muted fw-normal" style="font-size: 0.75rem;"><i class="far fa-clock me-1"></i> {{ format_dt(lr.created_at, '%I:%M %p') }}</span>
                                            </div>
                                            <div class="p-3 mb-3 rounded-4 bg-light border-0" style="min-height: 50px; white-space: pre-wrap; color: #334155; font-size: 1.05rem; line-height: 1.6; border-right: 4px solid #cbd5e1;">{{ lr.result }}</div>
                                            <div class="d-flex justify-content-between align-items-center opacity-75">
                                                <span class="small fw-semibold text-muted"><i class="fas fa-user-md me-1"></i> د. {{ lr.doc_name }}</span>
                                                <button type="button" class="btn btn-sm btn-primary rounded-pill px-4" onclick="alert('تقرير المريض:\n\n{{ lr.result|replace("\'", "\\\'")|replace("\n", " ") }}')">عرض كامل</button>
                                            </div>
                                        </div>
                                    {% endfor %}
                                {% endif %}

                                {% if not lab_history %}
                                    <div class="text-center py-5 opacity-25"><h6>لا توجد سجلات مختبرية</h6></div>
                                {% endif %}
                            </div>
                        </div>

                        <!-- ══════ RADIOLOGY REPORTS (HIGH DENSITY) ══════ -->
                        <div class="col-12">
                            <div class="d-flex align-items-center justify-content-between py-2 px-3 mb-3 rounded-4 shadow-sm" style="background: rgba(255, 45, 85, 0.04); border-right: 5px solid #ff2d55;">
                                <h6 class="fw-bold m-0 d-flex align-items-center gap-2" style="color:#1e293b; font-size: 0.95rem;">
                                    <i class="fas fa-radiation text-danger"></i> تقارير الأشعة (Radiology Reports)
                                </h6>
                                <button type="button" class="btn btn-sm rounded-pill px-3 fw-bold border-0 shadow-sm hp-toggle-btn" 
                                        style="background: #ffffff; color: #ff2d55; font-size: 0.8rem; height: 32px; transition: all 0.3s ease;" 
                                        onclick="hpToggleSection('rad-results-content', this)">
                                    <i class="fas fa-eye-slash me-1"></i> إخفاء الأشعة
                                </button>
                            </div>

                            <div id="rad-results-content" style="transition: all 0.4s ease-in-out;">
                                {% set ns_rad = namespace(last_date='') %}
                                {% for rr in rad_history %}
                                    {% set cur_date = format_dt(rr.created_at, '%Y-%m-%d') %}
                                    {% if cur_date %}
                                        {% if cur_date != ns_rad.last_date %}
                                            <div class="text-center my-4"><span class="badge bg-white text-danger border shadow-sm rounded-pill px-4 py-2 small fw-bold" style="font-size: 0.85rem;"><i class="fas fa-calendar-day me-1"></i> {{ cur_date }}</span></div>
                                            {% set ns_rad.last_date = cur_date %}
                                        {% endif %}
                                    {% endif %}
                                    <div class="hp-card mb-3 p-4 border-0 shadow-sm" style="border-right: 8px solid #ff2d55; border-radius: 16px; background: #ffffff;">
                                        <div class="d-flex justify-content-between align-items-center mb-3">
                                            <div class="fw-bold fs-5 text-dark">{{ rr.scan_type }}</div>
                                            <span class="badge bg-light text-muted fw-normal" style="font-size: 0.75rem;"><i class="far fa-clock me-1"></i> {{ format_dt(rr.created_at, '%I:%M %p') }}</span>
                                        </div>
                                        <div class="p-3 mb-3 rounded-4 bg-light border-0" style="min-height: 50px; white-space: pre-wrap; color: #334155; font-size: 1.05rem; line-height: 1.6; border-right: 4px solid #cbd5e1;">{{ rr.report }}</div>
                                        <div class="d-flex justify-content-between align-items-center opacity-75">
                                            <span class="small fw-semibold text-muted"><i class="fas fa-user-md me-1"></i> د. {{ rr.doc_name }}</span>
                                            <div>
                                                {% if rr.image_path %}
                                                <a href="{{ url_for('uploaded_file', filename=rr.image_path.replace('uploads/', '', 1).lstrip('/')) }}" 
                                                   target="_blank" rel="noopener noreferrer"
                                                   class="btn btn-sm btn-danger rounded-pill px-4 shadow-sm no-pjax" 
                                                   onclick="event.stopPropagation();">
                                                    <i class="fas fa-image me-1"></i> عرض الصورة فَقَط
                                                </a>
                                                {% endif %}
                                                <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-4 ms-2" onclick="alert('تقرير الأشعة:\n\n{{ rr.report|replace("\'", "\\\'")|replace("\n", " ") }}')">التفاصيل</button>
                                            </div>
                                        </div>
                                    </div>
                                {% else %}
                                    <div class="text-center py-5 opacity-25"><h6>لا توجد سجلات أشعة</h6></div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ══════ IMAGE VIEW MODAL REMOVED (OPEN IN NEW TAB PER REQUEST) ══════ -->


                <!-- ─── MANAGE & CANCELLATIONS ─── -->
                <div id="t-manage" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#fff3cd;color:#856404;"><i class="fas fa-exclamation-triangle"></i></span>
                            إدارة وتحرير الطلبات الحالية
                        </div>
                        
                        <div class="row g-4">
                            <!-- Labs Cancellation -->
                            <div class="col-md-6">
                                <div class="p-3 rounded-4 border" style="background:#fcfcfc;">
                                    <h6 class="fw-bold mb-3 small text-muted">تحاليل المختبر المعلقة/المدفوعة</h6>
                                    {% if active_labs %}
                                        <div class="list-group list-group-flush">
                                        {% for al in active_labs %}
                                            <div class="list-group-item d-flex justify-content-between align-items-center bg-transparent px-0 border-dashed">
                                                <div>
                                                    <span class="fw-bold d-block">{{ al.test_type }}</span>
                                                    <span class="badge {% if al.status == 'pending_payment' %}bg-secondary{% else %}bg-success{% endif %} rounded-pill" style="font-size:0.6rem;">
                                                        {{ 'بانتظار الدفع' if al.status == 'pending_payment' else 'مدفوعة - قيد التنفيذ' }}
                                                    </span>
                                                </div>
                                                <form method="POST" onsubmit="return confirm('هل أنت متأكد من إلغاء هذا التحليل؟');">
                                                    <input type="hidden" name="lab_id" value="{{ al.request_id }}">
                                                    <button type="submit" name="cancel_lab" class="btn btn-sm btn-outline-danger border-0 rounded-circle">
                                                        <i class="fas fa-trash-alt"></i>
                                                    </button>
                                                </form>
                                            </div>
                                        {% endfor %}
                                        </div>
                                    {% else %}
                                        <div class="text-center py-3 opacity-50"><small>لا توجد تحاليل معلقة حالياً</small></div>
                                    {% endif %}
                                </div>
                            </div>

                            <!-- Rads Cancellation -->
                            <div class="col-md-6">
                                <div class="p-3 rounded-4 border" style="background:#fcfcfc;">
                                    <h6 class="fw-bold mb-3 small text-muted">طلبات الأشعة المعلقة/المدفوعة</h6>
                                    {% if active_rads %}
                                        <div class="list-group list-group-flush">
                                        {% for ar in active_rads %}
                                            <div class="list-group-item d-flex justify-content-between align-items-center bg-transparent px-0 border-dashed">
                                                <div>
                                                    <span class="fw-bold d-block">{{ ar.scan_type }}</span>
                                                    <span class="badge {% if ar.status == 'pending_payment' %}bg-secondary{% else %}bg-success{% endif %} rounded-pill" style="font-size:0.6rem;">
                                                        {{ 'بانتظار الدفع' if ar.status == 'pending_payment' else 'مدفوعة - قيد التنفيذ' }}
                                                    </span>
                                                </div>
                                                <form method="POST" onsubmit="return confirm('هل أنت متأكد من إلغاء طلب الأشعة هذا؟');">
                                                    <input type="hidden" name="rad_id" value="{{ ar.request_id }}">
                                                    <button type="submit" name="cancel_rad" class="btn btn-sm btn-outline-danger border-0 rounded-circle">
                                                        <i class="fas fa-trash-alt"></i>
                                                    </button>
                                                </form>
                                            </div>
                                        {% endfor %}
                                        </div>
                                    {% else %}
                                        <div class="text-center py-3 opacity-50"><small>لا توجد طلبات أشعة معلقة حالياً</small></div>
                                    {% endif %}
                                </div>
                            </div>

                            <!-- Global Visit Cancellation -->
                            <div class="col-12 mt-4 text-center">
                                <div class="p-4 rounded-4" style="background:#fff5f5; border: 1px dashed #feb2b2;">
                                    <h6 class="fw-bold text-danger mb-2">إلغاء الزيارة بالكامل</h6>
                                    <p class="text-muted small mb-3">سيؤدي هذا الإلغاء إلى إقفال الجلسة وإبلاغ الحسابات برد مبلغ الكشفية (إذا تم دفعها).</p>
                                    <form method="POST" onsubmit="return confirm('‼️ تنبيه: هل أنت متأكد من إلغاء الزيارة الطبية بالكامل؟');">
                                        <button type="submit" name="cancel_visit_now" class="btn btn-danger rounded-pill px-4 fw-bold">
                                            <i class="fas fa-user-times me-2"></i>إلغاء الزيارة وتحويلها للاسترداد
                                        </button>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </div><!-- col-lg-9 -->
        </div><!-- row -->
    </div><!-- container -->

    <script>
    /* ════════════════════════════════════
       HealthPro Consultation v4 - Event Delegation JS
       ════════════════════════════════════ */

    if (!window.hpConsultationBound) {
        window.hpConsultationBound = true;
        window.hpTagStore = { selectedLabs: [], selectedRads: [] };

        window.hpAddTag = function(val, areaId, hiddenId, countId, badgeId, btnId, paramName) {
            val = val.trim();
            if (!val) return;
            if (window.hpTagStore[areaId].indexOf(val) !== -1) return;
            window.hpTagStore[areaId].push(val);

            var area = document.getElementById(areaId);
            if (!area) return;
            var hint = area.querySelector('.empty-hint');
            if (hint) hint.remove();

            var tag = document.createElement('div');
            tag.className = 'hp-tag';
            tag.setAttribute('data-v', val);
            tag.innerHTML = '<span>' + val + '</span>'
                + '<input type="hidden" name="' + paramName + '" value="' + val + '">'
                + '<i class="fas fa-times-circle x" onclick="hpRemoveTag(\\'' + val.replace(/'/g,"\\\\'") + '\\',\\'' + areaId + '\\',\\'' + countId + '\\',\\'' + badgeId + '\\',\\'' + btnId + '\\')"></i>';
            area.appendChild(tag);

            var hiddenCont = document.getElementById(hiddenId);
            if (hiddenCont) {
                var h = document.createElement('input');
                h.type = 'hidden'; h.name = paramName; h.value = val; h.setAttribute('data-v', val);
                hiddenCont.appendChild(h);
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpRemoveTag = function(val, areaId, countId, badgeId, btnId) {
            window.hpTagStore[areaId] = window.hpTagStore[areaId].filter(function(v){ return v !== val; });
            var area = document.getElementById(areaId);
            if (!area) return;
            area.querySelectorAll('.hp-tag').forEach(function(t){
                if (t.getAttribute('data-v') === val) t.remove();
            });
            if (window.hpTagStore[areaId].length === 0) {
                area.innerHTML = '<div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على فحص أو ابحث ثم Enter لإضافته</div>';
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpUpdateCount = function(areaId, countId, badgeId, btnId) {
            var n = window.hpTagStore[areaId].length;
            var c = document.getElementById(countId);  if (c) c.textContent = n;
            var b = document.getElementById(badgeId);  if (b) b.textContent = n;
            var btn = document.getElementById(btnId);  if (btn) btn.disabled = (n === 0);
        };

        window.hpAppendMed = function(val) {
            var rxArea = document.getElementById('rxArea');
            var medInp = document.getElementById('medInput');
            val = val.trim();
            if (!val || !rxArea) return;
            var cur = rxArea.value.trim();
            rxArea.value = cur ? cur + '\\n' + val + ' - ' : val + ' - ';
            if(medInp) medInp.value = '';
            rxArea.focus();
        };

        window.hpUseTpl = function(text) {
            var rxArea = document.getElementById('rxArea');
            if (rxArea) rxArea.value = text;
        };

        window.hpToggleSection = function(id, btn) {
            var content = document.getElementById(id);
            if (!content) return;
            
            var isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'block' : 'none';
            
            var isLab = id.includes('lab');
            var txtShow = isLab ? 'إظهار الفحوصات' : 'إظهار الأشعة';
            var txtHide = isLab ? 'إخفاء الفحوصات' : 'إخفاء الأشعة';
            var color = isLab ? '#007aff' : '#ff2d55';

            if (isHidden) {
                btn.innerHTML = '<i class="fas fa-eye-slash me-1"></i> ' + txtHide;
                btn.style.background = '#ffffff';
                btn.style.color = color;
                btn.classList.remove('text-white');
            } else {
                btn.innerHTML = '<i class="fas fa-eye me-1"></i> ' + txtShow;
                btn.style.background = color;
                btn.style.color = '#ffffff';
                btn.classList.add('text-white');
            }
        };

        window.hpStartSpeech = function(targetName, btn) {
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert("عذراً، متصفحك لا يدعم التعرف على الصوت. يرجى استخدام متصفح Chrome.");
                return;
            }

            var recognition = new SpeechRecognition();
            recognition.lang = 'ar-SA';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            var originalHTML = btn.innerHTML;
            var originalColor = btn.style.color;

            recognition.onstart = function() {
                btn.innerHTML = '<i class="fas fa-rss animate-pulse me-1"></i> جاري الاستماع...';
                btn.style.background = '#ff2d55';
                btn.style.color = '#ffffff';
                btn.classList.add('shadow-lg');
            };

            recognition.onresult = function(event) {
                var transcript = event.results[0][0].transcript;
                var target = document.querySelector('[name="' + targetName + '"]');
                if (target) {
                    var currentVal = target.value.trim();
                    target.value = (currentVal ? currentVal + ' ' : '') + transcript;
                    target.focus();
                }
            };

            recognition.onend = function() {
                btn.innerHTML = originalHTML;
                btn.style.background = '#fdfdfd';
                btn.style.color = originalColor;
                btn.classList.remove('shadow-lg');
            };

            recognition.onerror = function(event) {
                console.error("Speech Error:", event.error);
                btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i> خطأ!';
                setTimeout(function() {
                    btn.innerHTML = originalHTML;
                    btn.style.background = '#fdfdfd';
                    btn.style.color = originalColor;
                }, 2000);
            };

            recognition.start();
        };

        // Advanced Lab Result Validation
        window.hpValidateLabs = function() {
            const ranges = {
                // --- Basic & Hematology ---
                'GLUCOSE': { min: 70, max: 110, range: '70 - 110 mg/dL' },
                'WBC': { min: 4, max: 11, range: '4.0 - 11.0 10³/uL' },
                'RBC': { min: 4.5, max: 5.9, range: '4.5 - 5.9 10⁶/uL' },
                'HGB': { min: 12, max: 17.5, range: '12.0 - 17.5 g/dL' },
                'HBA1C': { min: 4, max: 5.6, range: '4.0 - 5.6 %' },
                'PLT': { min: 150, max: 450, range: '150 - 450 10³/uL' },
                'ESR': { min: 0, max: 20, range: '0 - 20 mm/hr' },
                
                // --- Renal Profile (وظائف الكلى) ---
                'UREA': { min: 15, max: 45, range: '15 - 45 mg/dL' },
                'CREA': { min: 0.7, max: 1.3, range: '0.7 - 1.3 mg/dL' },
                'BUN': { min: 7, max: 20, range: '7 - 20 mg/dL' },
                'URIC': { min: 3.5, max: 7.2, range: '3.5 - 7.2 mg/dL' },
                
                // --- Liver Profile (وظائف الكبد) ---
                'ALT': { min: 0, max: 41, range: '< 41 U/L' },
                'AST': { min: 0, max: 40, range: '< 40 U/L' },
                'ALP': { min: 40, max: 129, range: '40 - 129 U/L' },
                'BILI': { min: 0.1, max: 1.2, range: '0.1 - 1.2 mg/dL' },
                'ALB': { min: 3.5, max: 5.2, range: '3.5 - 5.2 g/dL' },
                'GGT': { min: 8, max: 61, range: '8 - 61 U/L' },

                // --- Lipid Profile (الدهون) ---
                'CHOL': { min: 100, max: 200, range: '< 200 mg/dL' },
                'TRIG': { min: 0, max: 150, range: '< 150 mg/dL' },
                'LDL': { min: 0, max: 130, range: '< 130 mg/dL' },
                'HDL': { min: 40, max: 60, range: '> 40 mg/dL' },

                // --- Thyroid & Hormones (الغدد) ---
                'TSH': { min: 0.4, max: 4.0, range: '0.4 - 4.0 mIU/L' },
                'T4': { min: 5, max: 12, range: '5 - 12 ug/dL' },
                'T3': { min: 80, max: 200, range: '80 - 200 ng/dL' },

                // --- Cardiac & Inflammatory ---
                'CRP': { min: 0, max: 5, range: '< 5.0 mg/L' },
                'TROPONIN': { min: 0, max: 0.04, range: '< 0.04 ng/mL' },
                'CK': { min: 22, max: 198, range: '22 - 198 U/L' },
                'LDH': { min: 140, max: 280, range: '140 - 280 U/L' },

                // --- Electrolytes & Others ---
                'SODIUM': { min: 135, max: 145, range: '135 - 145 mmol/L' },
                'POTASSIUM': { min: 3.5, max: 5.1, range: '3.5 - 5.1 mmol/L' },
                'CALCIUM': { min: 8.5, max: 10.5, range: '8.5 - 10.5 mg/dL' },
                'OSMOL': { min: 50, max: 1200, range: '50 - 1200 mOsm/kg' },

                // --- Specialty (Immunology & Specific mentioned) ---
                'HLA': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'ANTHRAX': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'SPERM': { min: 0, max: 60, range: '< 60 U/mL', type: 'hybrid', normal: 'NEGATIVE' },
                'HBV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'HCV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'HIV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'PAP': { min: 0, max: 3.5, range: '< 3.5 ng/mL' },
                'HBS': { type: 'hybrid', min: 10, max: 999999, range: '> 10 mIU/mL', normal: 'POSITIVE' }
            };

            const rows = document.querySelectorAll('#labResultsTable tbody tr');
            rows.forEach(row => {
                const testName = row.getAttribute('data-test-name');
                const resultText = row.getAttribute('data-result-val');
                const resultVal = parseFloat(resultText.replace(/[^\\d.-]/g, ''));
                
                const rangeDisp = row.querySelector('.range-display');
                const statusCell = row.querySelector('.status-cell');
                const resDisp = row.querySelector('.result-display');

                // Advanced Matching
                let matchedKey = Object.keys(ranges).find(k => testName.includes(k));
                if (matchedKey) {
                    const r = ranges[matchedKey];
                    rangeDisp.innerHTML = r.range;
                    
                    let statusHtml = '';
                    let statusColor = '';

                    if (r.type === 'string' || (r.type === 'hybrid' && isNaN(resultVal))) {
                        // Handle String Results (Positive/Negative)
                        const resUpper = resultText.toUpperCase();
                        if (resUpper.includes('NEG') || resUpper.includes('طبيعي') || resUpper.includes('سالب')) {
                            statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-check me-1"></i> سليم</span>';
                            statusColor = '#10b981';
                        } else if (resUpper.includes('POS') || resUpper.includes('موجب') || resUpper.includes('+')) {
                            statusHtml = '<span class="badge bg-danger text-white rounded-pill px-3 shadow-sm"><i class="fas fa-exclamation-triangle me-1"></i> إيجابي</span>';
                            statusColor = '#ef4444';
                        }
                    } else if (!isNaN(resultVal)) {
                        // Handle Numerical Results
                        if (matchedKey === 'HBS') {
                            // Hepatitis B Immunity Logic (Antibodies)
                            if (resultVal >= 10) {
                                statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-shield-alt me-1"></i> محصن</span>';
                                statusColor = '#10b981';
                            } else {
                                statusHtml = '<span class="badge bg-warning text-dark rounded-pill px-3 shadow-sm"><i class="fas fa-times me-1"></i> غير محصن</span>';
                                statusColor = '#f59e0b';
                            }
                        } else if (resultVal < r.min) {
                            statusHtml = '<span class="badge bg-warning text-dark rounded-pill px-3 shadow-sm"><i class="fas fa-arrow-down me-1"></i> منخفضة</span>';
                            statusColor = '#f59e0b';
                        } else if (resultVal > r.max) {
                            statusHtml = '<span class="badge bg-danger text-white rounded-pill px-3 shadow-sm"><i class="fas fa-arrow-up me-1"></i> مرتفعة</span>';
                            statusColor = '#ef4444';
                        } else {
                            statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-check me-1"></i> طبيعية</span>';
                            statusColor = '#10b981';
                        }
                    }

                    statusCell.innerHTML = statusHtml || '<span class="badge bg-secondary text-white rounded-pill px-3">تحليل نصي</span>';
                    resDisp.style.color = statusColor || '#3b82f6';
                } else {
                    rangeDisp.innerHTML = '<span class="opacity-50">غير محدد</span>';
                    statusCell.innerHTML = '<span class="badge bg-light text-muted border px-3">مراجعة يدوية</span>';
                    resDisp.style.color = '#3b82f6';
                }
            });
        };

        // Initialize validations
        setTimeout(window.hpValidateLabs, 100);

        // Event delegation for clicks (Tabs, Add Buttons, Grid Items)
        document.addEventListener('click', function(e) {
            // Tab switching
            var tabBtn = e.target.closest('.hp-tab');
            if (tabBtn) {
                document.querySelectorAll('.hp-tab').forEach(function(b){ b.classList.remove('active'); });
                document.querySelectorAll('.hp-tab-pane').forEach(function(p){ p.style.display = 'none'; });
                tabBtn.classList.add('active');
                var target = document.getElementById(tabBtn.getAttribute('data-hp-target'));
                if (target) target.style.display = 'block';
                return;
            }

            // Grid Items
            var gItem = e.target.closest('.g-item');
            if (gItem) {
                var gridId = gItem.parentElement.id;
                if (gridId === 'labGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                } else if (gridId === 'radGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                }
                return;
            }

            // Add Actions
            if (e.target.closest('#labAddBtn')) {
                var labInp = document.getElementById('labSearch');
                if (labInp && labInp.value.trim()) {
                    window.hpAddTag(labInp.value.trim(), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                    labInp.value = '';
                    document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            } else if (e.target.closest('#radAddBtn')) {
                var radInp = document.getElementById('radSearch');
                if (radInp && radInp.value.trim()) {
                    window.hpAddTag(radInp.value.trim(), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                    radInp.value = '';
                    document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            }
        });

        // Search filtering logic
        document.addEventListener('input', function(e) {
            if (e.target.id === 'labSearch') {
                var q1 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#labGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q1) ? '' : 'none';
                });
            } else if (e.target.id === 'radSearch') {
                var q2 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#radGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q2) ? '' : 'none';
                });
            }
        });

        // Enter key to add tags and meds
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                if (e.target.id === 'labSearch') {
                    e.preventDefault();
                    var v1 = e.target.value.trim();
                    if (v1) {
                        window.hpAddTag(v1, 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                        e.target.value = '';
                        document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'radSearch') {
                    e.preventDefault();
                    var v2 = e.target.value.trim();
                    if (v2) {
                        window.hpAddTag(v2, 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                        e.target.value = '';
                        document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'medInput') {
                    e.preventDefault();
                    window.hpAppendMed(e.target.value);
                }
            }
        });

        document.addEventListener('change', function(e) {
            if (e.target.id === 'medInput') {
                window.hpAppendMed(e.target.value);
            }
        });
    } else {
        // Reset state on PJAX reload
        window.hpTagStore = { selectedLabs: [], selectedRads: [] };
    }
    </script>
    """ + footer_html

    today_date        = local_today_str()
    followup_date_val = (local_now_naive() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

    # Unified Clinical Results Merge
    unified_results = []
    for lr in lab_history:
        unified_results.append({
            'type': 'lab',
            'title': lr.get('test_type'),
            'result': lr.get('result'),
            'doc': lr.get('doc_name'),
            'date': lr.get('created_at'),
            'icon': 'flask',
            'color': '#007aff',
            'bg': '#eef4ff'
        })
    for rr in rad_history:
        unified_results.append({
            'type': 'rad',
            'title': rr.get('scan_type'),
            'result': rr.get('report'),
            'doc': rr.get('doc_name'),
            'date': rr.get('created_at'),
            'img': rr.get('image_path'),
            'icon': 'radiation',
            'color': '#ff2d55',
            'bg': '#fff0f3'
        })
    
    # Sort descending by date
    try:
        unified_results.sort(key=lambda x: x['date'] if x['date'] else datetime.datetime.min, reverse=True)
    except: pass

    try:
        return render_template_string(
            html, data=data, curr_labs=curr_labs, curr_rads=curr_rads,
            lab_list=lab_list, rad_list=rad_list, depts=depts, history=history,
            lab_history=lab_history, rad_history=rad_history,
            today_date=today_date, followup_date_val=followup_date_val,
            lab_json=json.dumps(lab_list), rad_json=json.dumps(rad_list),
            diag_json=json.dumps(diag_list), med_json=json.dumps(med_list),
            active_labs=active_labs, active_rads=active_rads
        )
    except Exception as e:
        return f"<pre>Error: {e}</pre>"
