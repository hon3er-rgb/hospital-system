import os
import time
from werkzeug.utils import secure_filename
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

radiology_bp = Blueprint('radiology', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'dcm', 'dicom'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@radiology_bp.route('/radiology', methods=['GET', 'POST'])
def radiology():
    if not session.get('user_id') or not can_access('radiology'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # --- Actions ---
    if request.method == 'POST' and 'save_report' in request.form:
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = 'تصوير شعاعي' WHERE user_id = %s", (session['user_id'],))
            
        req_id = int(request.form.get('req_id', 0))
        rep = request.form.get('report', '')
        
        target_file_path = None
        if 'radiology_file' in request.files:
            file = request.files['radiology_file']
            if file and file.filename != '' and allowed_file(file.filename):
                target_dir = "uploads/radiology/"
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                    
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"rad_{req_id}_{int(time.time())}.{file_ext}")
                target_file_path = os.path.join(target_dir, filename)
                file.save(target_file_path)
                
                # Use forward slashes for URLs
                target_file_path = target_file_path.replace("\\", "/")

        cursor.execute("SELECT appointment_id FROM radiology_requests WHERE request_id = %s", (req_id,))
        req_info = cursor.fetchone()
        
        if req_info:
            appt_id = req_info['appointment_id']
            
            if target_file_path:
                cursor.execute("UPDATE radiology_requests SET report = %s, status = 'completed', image_path = %s WHERE request_id = %s", (rep, target_file_path, req_id))
            else:
                cursor.execute("UPDATE radiology_requests SET report = %s, status = 'completed' WHERE request_id = %s", (rep, req_id))
                
            cursor.execute("SELECT COUNT(*) as c FROM radiology_requests WHERE appointment_id = %s AND status = 'pending'", (appt_id,))
            rem = cursor.fetchone()['c']
            
            if rem == 0:
                # Check if this is a direct lab/rad appointment (Dept 3 or 4)
                cursor.execute("SELECT department_id FROM appointments WHERE appointment_id = %s", (appt_id,))
                appt_data = cursor.fetchone()
                if appt_data and appt_data['department_id'] in [3, 4]:
                    cursor.execute("UPDATE appointments SET status = 'completed' WHERE appointment_id = %s", (appt_id,))
                    flash("تم إكمال التقرير ورفع الملف بنجاح. تم إغلاق ملف المريض بنجاح.", "success")
                else:
                    cursor.execute("UPDATE appointments SET status = 'waiting_doctor' WHERE appointment_id = %s", (appt_id,))
                    flash("تم إكمال التقرير ورفع الملف بنجاح. المريض عاد لقائمة الطبيب للمراجعة.", "success")
            else:
                flash("تم حفظ التقرير والملف بنجاح", "success")
                
            conn.commit()

        return redirect(url_for('radiology.radiology'))

    # 1. Fetch Radiology Requests (Paid and Pending Payment)
    sql = """
        SELECT r.*, p.full_name_ar as p_name, p.file_number 
        FROM radiology_requests r 
        JOIN patients p ON r.patient_id = p.patient_id 
        WHERE r.status IN ('pending', 'pending_payment')
        ORDER BY r.status ASC, r.created_at DESC
    """
    cursor.execute(sql)
    requests = cursor.fetchall()

    html = header_html + """

    <div class="solid-mode">
        <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="fw-bold text-secondary"><i class="fas fa-x-ray"></i> قسم الأشعة (Radiology)</h2>
    </div>

    <!-- Main Radiology Requests Section -->
    <div class="row">
        <div class="col-12">
            <h5 class="fw-bold mb-4 px-2"><i class="fas fa-list-ul me-2"></i> قائمة الفحوصات الإشعاعية (المدفوعة)</h5>
            <div class="row">
                {% for r in requests %}
                    <div class="col-md-6 mb-4">
                        <div class="card border-0 shadow-sm border-top border-secondary border-4 {{ 'opacity-75' if r.status == 'pending_payment' else '' }}">
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <div>
                                        <h6 class="fw-bold mb-1">{{ r.p_name }}</h6>
                                        <small class="text-muted">{{ r.file_number }}</small>
                                    </div>
                                    <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-3 py-2 rounded-pill">{{ r.scan_type }}</span>
                                </div>
                                <div class="mb-3">
                                    {% if r.status == 'pending_payment' %}
                                        <span class="badge bg-warning text-dark"><i class="fas fa-clock me-1"></i> بانتظار الدفع في الحسابات</span>
                                    {% else %}
                                        <span class="badge bg-success text-white"><i class="fas fa-check-circle me-1"></i> تم الدفع - جاهز للتصوير</span>
                                    {% endif %}
                                </div>
                                <hr class="my-3 opacity-50">
                                <form method="POST" enctype="multipart/form-data">
                                    <input type="hidden" name="req_id" value="{{ r.request_id }}">
                                    <div class="mb-3">
                                        <label class="form-label small fw-bold">التقرير الشعاعي:</label>
                                        <textarea name="report" class="form-control form-control-sm border-0 bg-light" rows="3" 
                                            placeholder="{{ 'لا يمكن إدخال التقرير قبل تسديد المبلغ' if r.status == 'pending_payment' else 'اكتب وصف التقرير الشعاعي هنا..' }}" 
                                            {{ 'disabled' if r.status == 'pending_payment' else 'required' }}></textarea>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small fw-bold text-primary">رفع صور أو ملفات الأشعة (JPG, PDF, DICOM):</label>
                                        <div class="input-group input-group-sm">
                                            <input type="file" name="radiology_file" class="form-control border-dashed" accept=".jpg,.jpeg,.png,.pdf,.dcm,.dicom" {{ 'disabled' if r.status == 'pending_payment' else '' }}>
                                        </div>
                                    </div>
                                    <div class="d-grid gap-2">
                                        {% if r.status == 'pending' %}
                                            <button type="submit" name="save_report" class="btn btn-secondary text-white btn-sm fw-bold rounded-pill shadow-sm">
                                                <i class="fas fa-cloud-upload-alt me-1"></i> إرسال التقرير والملف للطبيب
                                            </button>
                                        {% else %}
                                            <button type="button" class="btn btn-dark btn-sm fw-bold rounded-pill shadow-sm" disabled>
                                                <i class="fas fa-lock me-1"></i> بانتظار المحاسبة
                                            </button>
                                        {% endif %}
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                {% endfor %}
                {% if not requests %}
                    <div class="col-12">
                        <div class="alert alert-light text-center py-5 border-dashed border-2 rounded-4">
                            <i class="fas fa-image fa-3x text-muted mb-3"></i>
                            <p class="text-muted mb-0 text-center">لا توجد طلبات أشعة بانتظار التنفيذ حالياً</p>
                        </div>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, requests=requests)
