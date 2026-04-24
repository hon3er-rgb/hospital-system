from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, can_access
from header import header_html
from footer import footer_html

archive_bp = Blueprint('archive', __name__)

@archive_bp.route('/archive', methods=['GET'])
def archive():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    search = request.args.get('search', '')
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    patients = []
    has_searched = False
    
    if search:
        has_searched = True
        sql = """
            SELECT p.*, 
            (
                SELECT COUNT(*) FROM appointments WHERE patient_id = p.patient_id AND status = 'scheduled'
            ) +
            (
                SELECT COUNT(*) FROM lab_requests WHERE patient_id = p.patient_id AND status = 'pending_payment'
            ) +
            (
                SELECT COUNT(*) FROM radiology_requests WHERE patient_id = p.patient_id AND status = 'pending_payment'
            ) +
            (
                SELECT COUNT(*) FROM prescriptions WHERE patient_id = p.patient_id AND status = 'pending_payment'
            ) as debt_count
            FROM patients p
            WHERE p.full_name_ar LIKE %s OR p.file_number LIKE %s OR p.national_id LIKE %s
            ORDER BY p.created_at DESC
        """
        search_term = f"%{search}%"
        cursor.execute(sql, (search_term, search_term, search_term))
        patients = cursor.fetchall()
        
    conn.close()

    html = header_html + """
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="fw-bold text-dark"><i class="fas fa-archive me-2"></i> أرشيف المرضى الإلكتروني</h2>
        <a href="patients" class="btn btn-primary"><i class="fas fa-user-plus me-1"></i> إدارة المرضى</a>
    </div>

    <div class="card border-0 shadow-sm mb-4">
        <div class="card-body">
            <form method="GET" class="row g-2" action="{{ url_for('archive.archive') }}">
                <div class="col-md-10">
                    <input type="text" name="search" class="form-control" placeholder="ابحث باسم المريض أو رقم الملف..."
                        value="{{ search|e }}">
                </div>
                <div class="col-md-2">
                    <button type="submit" class="btn btn-dark w-100">بحث بالأرشيف</button>
                </div>
            </form>
        </div>
    </div>

    <div class="row row-cols-1 row-cols-md-3 g-4">
        {% if has_searched and patients %}
            {% for p in patients %}
                {% set has_debt = p.debt_count > 0 %}
                <div class="col">
                    <div class="card h-100 border-0 shadow-sm transition-hover" style="background: var(--card);">
                        <div class="card-body text-center">
                            <div class="mb-3">
                                <i class="fas fa-file-medical fa-3x text-{{ 'danger' if has_debt else 'success' }}"></i>
                            </div>
                            <h5 class="fw-bold mb-1">{{ p.full_name_ar }}</h5>
                            <p class="text-muted small mb-3">{{ p.file_number }}</p>

                            <div class="p-2 rounded mb-3 {{ 'bg-danger-subtle text-danger' if has_debt else 'bg-success-subtle text-success' }}">
                                <small class="fw-bold">
                                    <i class="fas {{ 'fa-exclamation-triangle' if has_debt else 'fa-check-circle' }}"></i>
                                    {{ 'توجد ذمة مالية معلقة' if has_debt else 'لا توجد ذمة مالية - الحساب صافي' }}
                                </small>
                            </div>

                            <div class="d-grid gap-2">
                                {% if not has_debt %}
                                    <a href="patient_file?id={{ p.patient_id }}" class="btn btn-outline-dark btn-sm rounded-pill">عرض السجل الطبي</a>
                                    <!-- Edit disabled here because we don't have edit_patient route yet -->
                                    <a href="patients" class="btn btn-outline-primary btn-sm rounded-pill">إدارة المريض</a>
                                {% else %}
                                    <button class="btn btn-secondary btn-sm rounded-pill" disabled title="لا يمكن التعديل أو الفتح لوجود مطالبات مالية">مغلق (وجود ذمة مالية)</button>
                                    <a href="billing" class="btn btn-link btn-sm text-danger">انتقال لتسوية الحسابات</a>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
        {% elif has_searched and not patients %}
            <div class="col-12 text-center py-5">
                <i class="fas fa-search-minus fa-3x text-muted mb-3"></i>
                <h4>لم يتم العثور على مريض بهذا الاسم أو الرقم</h4>
                <p class="text-muted">تأكد من كتابة الاسم بشكل صحيح أو جرب رقم الملف</p>
            </div>
        {% else %}
            <div class="col-12 text-center py-5">
                <div class="p-5 apple-card shadow-none border-dashed" style="border: 2px dashed rgba(0,0,0,0.1);">
                    <i class="fas fa-search fa-3x text-primary mb-3"></i>
                    <h4>أرشيف المستشفى متاح للبحث الآن</h4>
                    <p class="text-muted">أدخل بيانات المريض في الخانة أعلاه للبدء في استعراض السجلات الطبية المؤرشفة</p>
                </div>
            </div>
        {% endif %}
    </div>

    <style>
        .transition-hover:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1) !important;
            transition: all 0.3s;
        }

        .bg-danger-subtle {
            background-color: #fceaea;
        }

        .bg-success-subtle {
            background-color: #eafaf1;
        }
    </style>
    """ + footer_html
    
    return render_template_string(html, patients=patients, search=search, has_searched=has_searched)
