import datetime
from flask import Blueprint, session, redirect, url_for, request, render_template_string, flash # type: ignore
from config import get_db, local_now_naive # type: ignore

data_cleanup_bp = Blueprint('data_cleanup', __name__)

def delete_patients_by_ids(cursor, conn, patient_ids):
    if not patient_ids:
        return 0
        
    ids_str = ",".join(map(str, patient_ids))
    
    # 1. Triage (using appointments)
    cursor.execute(f"DELETE FROM triage WHERE appointment_id IN (SELECT appointment_id FROM appointments WHERE patient_id IN ({ids_str}))")
    # 2. Invoices
    cursor.execute(f"DELETE FROM invoices WHERE patient_id IN ({ids_str})")
    # 3. Referrals
    cursor.execute(f"DELETE FROM referrals WHERE patient_id IN ({ids_str})")
    # 4. Prescriptions
    cursor.execute(f"DELETE FROM prescriptions WHERE patient_id IN ({ids_str})")
    # 5. Radiology
    cursor.execute(f"DELETE FROM radiology_requests WHERE patient_id IN ({ids_str})")
    # 6. Lab
    cursor.execute(f"DELETE FROM lab_requests WHERE patient_id IN ({ids_str})")
    # 7. Consultations
    cursor.execute(f"DELETE FROM consultations WHERE patient_id IN ({ids_str})")
    # 8. Appointments
    cursor.execute(f"DELETE FROM appointments WHERE patient_id IN ({ids_str})")
    # 9. Patients
    cursor.execute(f"DELETE FROM patients WHERE patient_id IN ({ids_str})")
    return len(patient_ids)

def delete_all_patients(cursor, conn):
    if conn.is_pg:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for tbl in ['triage', 'invoices', 'referrals', 'prescriptions', 'radiology_requests', 'lab_requests', 'consultations', 'appointments', 'patients']:
            cursor.execute(f"TRUNCATE TABLE {tbl} CASCADE")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    else:
        cursor.execute("PRAGMA foreign_keys = OFF")
        for tbl in ['triage', 'invoices', 'referrals', 'prescriptions', 'radiology_requests', 'lab_requests', 'consultations', 'appointments', 'patients']:
            cursor.execute(f"DELETE FROM {tbl}")
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{tbl}'") # Reset auto-increment
        cursor.execute("PRAGMA foreign_keys = ON")
        
    # Reset all caching counters to 0 to remove phantom numbers
    try:
        cursor.execute("UPDATE global_counters SET val = 0")
    except:
        pass


@data_cleanup_bp.route('/data_cleanup', methods=['GET', 'POST'])
def data_cleanup():
    # Only Admin should access this
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('dashboard.dashboard'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"
    
    cursor = conn.cursor(dictionary=True)
    msg = ""
    msg_type = ""

    # Stats for Preview
    cursor.execute("SELECT COUNT(*) as c FROM patients")
    total_patients = cursor.fetchone().get('c', 0)
    
    # Calculate available years
    try:
        if conn.is_pg:
            cursor.execute("SELECT DISTINCT EXTRACT(YEAR FROM created_at) as y FROM patients ORDER BY y DESC")
            years = [int(row['y']) for row in cursor.fetchall() if row['y']]
        else:
            cursor.execute("SELECT DISTINCT strftime('%Y', created_at) as y FROM patients WHERE created_at IS NOT NULL ORDER BY y DESC")
            years = [int(row['y']) for row in cursor.fetchall() if row['y']]
    except:
        years = []

    if request.method == 'POST':
        action = request.form.get('action')
        
        try:
            if action == 'delete_all':
                delete_all_patients(cursor, conn)
                conn.commit()
                msg = "تـم مـسح كــافة سـجلّات المرضـى ومعاملاتهـم المتـعلقة بنـجاح!"
                msg_type = "danger"
                
            elif action == 'delete_by_year':
                year = request.form.get('target_year')
                if year and year.isdigit():
                    if conn.is_pg:
                        cursor.execute("SELECT patient_id FROM patients WHERE EXTRACT(YEAR FROM created_at) = %s", (year,))
                    else:
                        cursor.execute("SELECT patient_id FROM patients WHERE strftime('%Y', created_at) = %s", (year,))
                    
                    rows = cursor.fetchall()
                    p_ids = [r['patient_id'] for r in rows]
                    
                    if p_ids:
                        deleted_count = delete_patients_by_ids(cursor, conn, p_ids)
                        conn.commit()
                        msg = f"تم حذف {deleted_count} مريض (وملفاتهم) لعام {year} بنجاح."
                        msg_type = "success"
                    else:
                        msg = f"لم يتم العثور على أي مرضى في عام {year}."
                        msg_type = "warning"
                
            elif action == 'delete_by_age':
                age = request.form.get('target_age')
                operator = request.form.get('age_operator')
                
                if age and age.isdigit():
                    target_dob_year = local_now_naive().year - int(age)
                    
                    if operator == 'older':
                        # DOB <= target_dob_year means older
                        cursor.execute("SELECT patient_id FROM patients WHERE CAST(SUBSTR(date_of_birth, 1, 4) AS INTEGER) <= %s", (target_dob_year,))
                    elif operator == 'younger':
                        # DOB > target_dob_year means younger
                        cursor.execute("SELECT patient_id FROM patients WHERE CAST(SUBSTR(date_of_birth, 1, 4) AS INTEGER) > %s", (target_dob_year,))
                    else: # exact
                        cursor.execute("SELECT patient_id FROM patients WHERE CAST(SUBSTR(date_of_birth, 1, 4) AS INTEGER) = %s", (target_dob_year,))
                        
                    rows = cursor.fetchall()
                    p_ids = [r['patient_id'] for r in rows]
                    
                    if p_ids:
                        deleted_count = delete_patients_by_ids(cursor, conn, p_ids)
                        conn.commit()
                        msg = f"تم حذف {deleted_count} مريض (وملفاتهم) حسب شرط العمر بنجاح."
                        msg_type = "success"
                    else:
                        msg = "لم يتم العثور على أي مرضى يطابقون شرط العمر."
                        msg_type = "warning"
                        
            # Refresh total count
            cursor.execute("SELECT COUNT(*) as c FROM patients")
            total_patients = cursor.fetchone().get('c', 0)
            
        except Exception as e:
            conn.rollback()
            msg = f"حدث خطأ أثناء تنفيذ الحذف: {str(e)}"
            msg_type = "danger"

    from header import header_html
    from footer import footer_html
    
    html = header_html + """
    <style>
        .cleanup-wrapper { display: flex; flex-direction: column; gap: 20px; animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .c-card { background: var(--card, #fff); backdrop-filter: blur(20px); border: 1px solid var(--border, rgba(0,0,0,0.05)); border-radius: 24px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.04); position: relative; overflow: hidden;}
        
        
        .danger-card { border: 1px solid rgba(255,59,48,0.2); }
        .danger-card::before { content: ''; position: absolute; top:0; left:0; width: 100%; height: 5px; background: linear-gradient(90deg, #ff3b30, #ff9500); }
        
        .feature-box { background: var(--input-bg, #f8f9fa); border-radius: 16px; padding: 20px; transition: all 0.3s; border: 1px solid transparent; }
        .feature-box:hover { border-color: rgba(0,122,255,0.3); transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.03); }
        
        .cleanup-input { border-radius: 12px; border: 1px solid var(--border); padding: 12px 15px; font-weight: 600; background: var(--card); color: var(--text); }
        .cleanup-input:focus { border-color: #007aff; outline: none; box-shadow: 0 0 0 3px rgba(0,122,255,0.1); }
        
        .btn-nuke { background: linear-gradient(135deg, #ff3b30 0%, #d70015 100%); border: none; padding: 15px 30px; border-radius: 14px; font-weight: 800; color: white !important; font-size: 1.1rem; box-shadow: 0 8px 25px rgba(255,59,48,0.3); transition: all 0.3s; width: 100%; }
        .btn-nuke:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 12px 30px rgba(255,59,48,0.4); opacity: 0.95; }
        
        .btn-action-safe { background: linear-gradient(135deg, #007aff 0%, #0056b3 100%); color: white !important; padding: 12px 25px; border-radius: 12px; font-weight: 700; border: none; box-shadow: 0 6px 20px rgba(0,122,255,0.25); transition: all 0.3s; width: 100%;}
        .btn-action-safe:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,122,255,0.35); opacity: 0.95;}
        
        .stat-badge { font-size: 1.5rem; font-weight: 900; color: #ff3b30; background: rgba(255,59,48,0.1); padding: 5px 15px; border-radius: 12px; border: 1px solid rgba(255,59,48,0.2);}
        
    </style>

    <div class="cleanup-wrapper container-fluid mb-5">
        <div class="d-flex align-items-center justify-content-between mb-2">
            <div class="d-flex align-items-center gap-3">
                <div class="bg-danger-subtle text-danger p-3 rounded-circle d-flex align-items-center justify-content-center shadow-sm" style="width: 55px; height: 55px;">
                    <i class="fas fa-radiation fa-lg"></i>
                </div>
                <div>
                    <h3 class="fw-bold mb-1" style="color: var(--text);">مركز تنظيف البيانات المتقدم</h3>
                    <p class="text-muted small mb-0">أداة احترافية لحذف قيود المرضى بشكل آمن وبشروط وتفضيلات مخصصة (Admin Only)</p>
                </div>
            </div>
            <a href="system_data" class="btn btn-light rounded-pill border fw-bold shadow-sm px-4">
                <i class="fas fa-arrow-right me-2"></i> رجوع للإعدادات
            </a>
        </div>

        {% if msg %}
            <div class="alert alert-{{ msg_type }} border-0 shadow-sm rounded-4 animate__animated animate__shakeX fw-bold px-4 py-3">
                {% if msg_type == 'danger' %}<i class="fas fa-exclamation-triangle me-2 fa-lg"></i>{% else %}<i class="fas fa-check-circle me-2 fa-lg"></i>{% endif %}
                {{ msg }}
            </div>
        {% endif %}

        <div class="row g-4">
            <!-- Global Stats -->
            <div class="col-lg-4">
                <div class="c-card text-center h-100 d-flex flex-column justify-content-center">
                    <i class="fas fa-users fa-3x text-primary mb-3 opacity-75"></i>
                    <h5 class="fw-bold mb-2">إجمالي المرضى في النظام</h5>
                    <div class="stat-badge d-inline-block mx-auto mb-2">{{ "{:,.0f}".format(total_patients) }}</div>
                    <p class="text-muted extra-small">كل ملف مريض يرتبط بحجوزات وأرشفة</p>
                </div>
            </div>

            <!-- Delete by Year / Preferences -->
            <div class="col-lg-8">
                <div class="c-card h-100">
                    <h5 class="fw-bold mb-4 text-primary"><i class="fas fa-sliders-h me-2"></i> تصفية الحذف المتقدمة (تفضيلات)</h5>
                    
                    <div class="row g-3">
                        <!-- By Year -->
                        <div class="col-md-6">
                            <form method="POST" class="feature-box h-100" onsubmit="return confirm('هل أنت متأكد من حذف جميع المرضى لهذه السنة بملفاتهم؟')">
                                <input type="hidden" name="action" value="delete_by_year">
                                <h6 class="fw-bold mb-3"><i class="fas fa-calendar-alt text-muted me-2"></i> حذف مرضى لسنة محددة</h6>
                                
                                <label class="small text-muted fw-bold mb-2">اختر سنة التسجيل (تاريخ فتح الملف):</label>
                                <select name="target_year" class="cleanup-input w-100 mb-4" required>
                                    <option value="">-- اختر السنة --</option>
                                    {% for y in years %}
                                        <option value="{{ y }}">{{ y }}</option>
                                    {% endfor %}
                                    {% if not years %}
                                        <option value="">لا توجد إحصائيات</option>
                                    {% endif %}
                                </select>
                                
                                <button type="submit" class="btn-action-safe mt-auto">
                                    <i class="fas fa-trash me-2"></i> تنفيذ الحذف بذكاء
                                </button>
                            </form>
                        </div>
                        
                        <!-- By Age -->
                        <div class="col-md-6">
                            <form method="POST" class="feature-box h-100" onsubmit="return confirm('هل أنت متأكد من حذف كافة المرضى المطابقين لشرط العمر؟')">
                                <input type="hidden" name="action" value="delete_by_age">
                                <h6 class="fw-bold mb-3"><i class="fas fa-user-clock text-muted me-2"></i> تصفية الحذف بواسطة العمر</h6>
                                    
                                <div class="row g-2 mb-4">
                                    <div class="col-7">
                                        <label class="small text-muted fw-bold mb-2">العمر (سنوات):</label>
                                        <input type="number" name="target_age" class="cleanup-input w-100" placeholder="مثلاً: 60" required min="1" max="150">
                                    </div>
                                    <div class="col-5">
                                        <label class="small text-muted fw-bold mb-2">الشرط:</label>
                                        <select name="age_operator" class="cleanup-input w-100">
                                            <option value="older">أكبر من</option>
                                            <option value="younger">أصغر من</option>
                                            <option value="exact">يساوي</option>
                                        </select>
                                    </div>
                                </div>
                                
                                <button type="submit" class="btn-action-safe mt-auto">
                                    <i class="fas fa-filter me-2"></i> حذف المرضى مطابقين للشرط
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Absolute Global Delete -->
            <div class="col-12 mt-4">
                <div class="c-card danger-card text-center p-5">
                    <div class="mx-auto bg-danger-subtle text-danger rounded-circle d-flex align-items-center justify-content-center mb-4" style="width: 80px; height: 80px;">
                        <i class="fas fa-skull-crossbones fa-2x"></i>
                    </div>
                    <h3 class="fw-bold text-danger mb-2">حذف جميع المرضى بالكامل (النظام كاملاً)</h3>
                    <p class="text-muted mx-auto mb-4" style="max-width: 600px;">
                        انتباه: هذا الإجراء الأخطر في النظام! بضغطة واحدة ستقوم بمسح <b class="text-dark">{{ total_patients }}</b> ملف مريض بالإضافة لجميع الحجوزات، الفواتير، الاستشارات الطبية ووصفات العلاج المرتبطة بهم نهائياً دون تراجع. (سيتم استخدام TRUNCATE لضمان القضاء التام على البيانات الحركية).
                    </p>
                    
                    <form method="POST" onsubmit="return confirm('إجراء لا يمكن التراجع عنه مطلقاً! هل توافق على مسح كافة مرضى النظام ومعاملاتهم نهائياً؟')">
                        <input type="hidden" name="action" value="delete_all">
                        <button type="submit" class="btn-nuke mx-auto" style="max-width: 400px;">
                            <i class="fas fa-bomb me-2"></i> مسح سجل النظام بالكامل والجداول
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, total_patients=total_patients, years=years, msg=msg, msg_type=msg_type)
