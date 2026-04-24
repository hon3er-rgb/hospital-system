import json
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db
from header import header_html
from footer import footer_html

manage_departments_bp = Blueprint('manage_departments', __name__)

@manage_departments_bp.route('/manage_departments', methods=['GET', 'POST'])
def manage_departments():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        action = request.form.get('action')
        dept_id = request.form.get('department_id')
        name_ar = request.form.get('department_name_ar', '')
        name_en = request.form.get('department_name_en', '')
        dtype = request.form.get('department_type', 'medical')
        
        if action == 'add':
            cursor.execute("INSERT INTO departments (department_name_ar, department_name_en, department_type) VALUES (%s, %s, %s)", (name_ar, name_en, dtype))
            flash("تم إضافة القسم بنجاح.", "success")
        elif action == 'edit' and dept_id:
            cursor.execute("UPDATE departments SET department_name_ar=%s, department_name_en=%s, department_type=%s WHERE department_id=%s", (name_ar, name_en, dtype, dept_id))
            flash("تم تعديل القسم بنجاح.", "success")

        conn.commit()
        conn.close()
        return redirect(url_for('manage_departments.manage_departments'))
        
    del_id = request.args.get('del')
    if del_id:
        # Check if users exist in this dept
        cursor.execute("SELECT COUNT(*) as c FROM users WHERE department_id=%s", (del_id,))
        res = cursor.fetchone()
        count = res.get('c', 0) if res else 0
        
        if count > 0:
            flash("عذراً! لا يمكن حذف هذا القسم لتوفر موظفين مسجلين ضمنه. يمكنك نقل الموظفين أولاً.", "danger")
        else:
            cursor.execute("DELETE FROM departments WHERE department_id=%s", (del_id,))
            conn.commit()
            flash("تم حذف القسم بنجاح.", "success")
            
        conn.close()
        return redirect(url_for('manage_departments.manage_departments'))

    # Fetch Data
    cursor.execute("SELECT * FROM departments ORDER BY department_id DESC")
    departments = cursor.fetchall()
    conn.close()

    html = header_html + """
    <style>
        .dept-wrap { padding: 25px; animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .dept-card { background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); transition: 0.3s; overflow: hidden; }
        
        
        .table-dept thead th { background: rgba(0,0,0,0.02); border: none; border-bottom: 2px solid var(--border) !important; padding: 20px 15px; font-size: 0.85rem; color: var(--text); opacity: 0.7; font-weight: 800; }
        
        
        .table-dept tbody td { padding: 20px 15px; border-bottom: 1px solid var(--border); vertical-align: middle; color: var(--text); }
        

        .dept-icon { width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--input-bg); color: var(--text); border: 1px solid var(--border); }
        

        .action-btn-dept { width: 38px; height: 38px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; transition: 0.2s; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); opacity: 0.8; text-decoration: none; }
        
        .action-btn-dept:hover { opacity: 1; transform: translateY(-2px); }
        .action-btn-dept.btn-edit:hover { background: #5e5ce6 !important; color: #fff !important; border-color: #5e5ce6 !important; }
        .action-btn-dept.btn-del:hover { background: #ff3b30 !important; color: #fff !important; border-color: #ff3b30 !important; }

        .badge-dept { padding: 8px 14px; border-radius: 12px; font-weight: 800; font-size: 0.8rem; }

        /* General Dark Overrides */
        
        
        
        
        /* Modal dark styling */
        
        
        
    </style>

    <div class="container-fluid py-5 px-lg-5 dept-wrap" style="min-height: 80vh;">
        <!-- Header -->
        <div class="d-flex justify-content-between align-items-center mb-5 animate__animated animate__fadeInDown">
            <div class="d-flex align-items-center gap-3">
                <div class="bg-primary text-white d-flex align-items-center justify-content-center rounded-3 shadow-sm" style="width: 50px; height: 50px;">
                    <i class="fas fa-building fa-lg"></i>
                </div>
                <div>
                    <h3 class="fw-bold mb-0 text-dark">إدارة الأقسام والعيادات</h3>
                    <p class="text-muted small mb-0">إضافة أو تعديل الأقسام الطبية والإدارية</p>
                </div>
            </div>
            <button class="btn btn-primary fw-bold px-4 py-2 rounded-pill shadow-sm d-flex align-items-center gap-2" onclick="openDeptModal()">
                <i class="fas fa-plus"></i> إضافة قسم جديد
            </button>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="mb-4">
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show border-0 shadow-sm rounded-3">
                        <i class="fas fa-info-circle me-2"></i> {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Departments List -->
        <div class="dept-card animate__animated animate__fadeInUp">
            <div class="table-responsive">
                <table class="table table-dept align-middle mb-0 border-0">
                    <thead class="bg-light">
                        <tr>
                            <th class="ps-4 py-3 text-muted small fw-bold border-0">اسم القسم (عربي)</th>
                            <th class="py-3 text-muted small fw-bold border-0">الاسم البديل (إنجليزي)</th>
                            <th class="text-center py-3 text-muted small fw-bold border-0">نوع القسم</th>
                            <th class="pe-4 text-center py-3 text-muted small fw-bold border-0">الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody class="border-top-0">
                        {% for d in departments %}
                        <tr>
                            <td class="ps-4 py-3">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="dept-icon text-primary">
                                        <i class="fas fa-layer-group"></i>
                                    </div>
                                    <h6 class="fw-bold mb-0 text-dark">{{ d.department_name_ar }}</h6>
                                </div>
                            </td>
                            <td class="py-3">
                                <span class="text-muted">{{ d.department_name_en if d.department_name_en else '---' }}</span>
                            </td>
                            <td class="text-center py-3">
                                {% if d.department_type == 'medical' %}
                                    <span class="badge badge-dept bg-success bg-opacity-10 text-success w-75">قسم طبي / عيادة</span>
                                {% else %}
                                    <span class="badge badge-dept bg-secondary bg-opacity-10 text-secondary w-75">قسم إداري</span>
                                {% endif %}
                            </td>
                            <td class="pe-4 text-center py-3">
                                <button class="action-btn-dept btn-edit" onclick='openDeptModal({{ d|tojson|safe }})' title="تعديل">
                                    <i class="fas fa-pen"></i>
                                </button>
                                <a href="?del={{ d.department_id }}" class="action-btn-dept btn-del ms-2" onclick="return confirm('هل أنت متأكد من حذف هذا القسم نهائياً؟');" title="حذف">
                                    <i class="fas fa-trash"></i>
                                </a>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" class="text-center text-muted py-5">لا يوجد أقسام مسجلة.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>


    <!-- Department Modal -->
    <div class="modal fade" id="deptModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow-lg" style="border-radius: 20px;">
                <form method="POST">
                    <input type="hidden" name="action" id="d_action" value="add">
                    <input type="hidden" name="department_id" id="d_id">
                    <div class="modal-body p-4 p-md-5">
                        <h4 class="fw-bold mb-4 text-center text-dark" id="deptModalTitle">إضافة قسم جديد</h4>
                        
                        <div class="mb-4">
                            <label class="form-label fw-bold small text-muted">اسم القسم باللغة العربية *</label>
                            <input type="text" name="department_name_ar" id="d_name_ar" class="form-control form-control-lg bg-light border-0 rounded-3" required>
                        </div>
                        <div class="mb-4">
                            <label class="form-label fw-bold small text-muted">اسم القسم باللغة الإنجليزية (اختياري)</label>
                            <input type="text" name="department_name_en" id="d_name_en" class="form-control form-control-lg bg-light border-0 rounded-3">
                        </div>
                        <div class="mb-4">
                            <label class="form-label fw-bold small text-muted">نوع القسم</label>
                            <select name="department_type" id="d_type" class="form-select form-control-lg bg-light border-0 rounded-3">
                                <option value="medical">طبي / عيادة (يمكن حجز مواعيد له)</option>
                                <option value="administrative">إداري (موظفين فقط)</option>
                            </select>
                        </div>
                    </div>
                    <div class="modal-footer px-5 pb-5 border-0 pt-0">
                        <button type="submit" class="btn btn-primary w-100 py-3 rounded-pill shadow fw-bold">حفظ بيانات القسم</button>
                        <button type="button" class="btn btn-light w-100 py-3 rounded-pill border fw-bold text-muted mt-2" data-bs-dismiss="modal">إلغاء</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
    function openDeptModal(data = null) {
        const modal = new bootstrap.Modal(document.getElementById('deptModal'));
        if(data) {
            document.getElementById('deptModalTitle').innerText = 'تعديل قسم: ' + data.department_name_ar;
            document.getElementById('d_action').value = 'edit';
            document.getElementById('d_id').value = data.department_id;
            document.getElementById('d_name_ar').value = data.department_name_ar;
            document.getElementById('d_name_en').value = data.department_name_en || '';
            document.getElementById('d_type').value = data.department_type;
        } else {
            document.getElementById('deptModalTitle').innerText = 'إضافة قسم جديد';
            document.getElementById('d_action').value = 'add';
            document.getElementById('d_id').value = '';
            document.getElementById('d_name_ar').value = '';
            document.getElementById('d_name_en').value = '';
            document.getElementById('d_type').value = 'medical';
        }
        modal.show();
    }
    </script>
    """ + footer_html
    return render_template_string(html, departments=departments)
