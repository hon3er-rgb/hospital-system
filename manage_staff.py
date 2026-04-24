import json
from werkzeug.security import generate_password_hash # type: ignore
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access
from header import header_html
from footer import footer_html

manage_staff_bp = Blueprint('manage_staff', __name__)

@manage_staff_bp.route('/manage_staff', methods=['GET', 'POST'])
def manage_staff():
    # --- Security Check ---
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Ensure columns
    try:
        cursor.execute("ALTER TABLE users MODIFY COLUMN permissions TEXT")
        cursor.execute("SHOW COLUMNS FROM users LIKE 'department_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD department_id INT DEFAULT 0")
        conn.commit()
    except Exception:
        pass # Ignore errors if columns already exist or syntax unsupported

    # --- Submit Logic & Delete Logic ---
    if request.method == 'POST':
        if 'save_employee' in request.form:
            uid = int(request.form.get('user_id') or 0)
            user = request.form.get('username', '')
            name = request.form.get('full_name', '')
            role = request.form.get('role', 'reception')
            dept = int(request.form.get('department_id', 0))
            
            # New fields
            phone = request.form.get('phone', '')
            gender = request.form.get('gender', 'male')
            nat_id = request.form.get('national_id', '')
            emp_no = request.form.get('employee_no', '')
            
            permissions = request.form.getlist('permissions[]')
            perms = json.dumps(permissions) if permissions else '[]'
            
            pwd = request.form.get('password', '')

            if uid > 0:
                sql = """UPDATE users SET 
                         username=%s, full_name_ar=%s, role=%s, department_id=%s, permissions=%s,
                         phone=%s, gender=%s, national_id=%s, employee_no=%s
                         WHERE user_id=%s"""
                cursor.execute(sql, (user, name, role, dept, perms, phone, gender, nat_id, emp_no, uid))
                if pwd:
                    hashed = generate_password_hash(pwd)
                    cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (hashed, uid))
                flash("تم تحديث بيانات الموظف بنجاح", "success")
            else:
                hashed = generate_password_hash(pwd) if pwd else generate_password_hash('123456')
                email = f"{user}@healthpro.local"
                sql = """INSERT INTO users 
                         (username, password_hash, email, full_name_ar, role, department_id, permissions, phone, gender, national_id, employee_no) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (user, hashed, email, name, role, dept, perms, phone, gender, nat_id, emp_no))
                flash("تم إضافة الموظف بنجاح", "success")
                
            conn.commit()
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))
            
    # Delete User
    del_user_id = request.args.get('del_user')
    if del_user_id:
        if int(del_user_id) != session.get('user_id'):
            cursor.execute("DELETE FROM users WHERE user_id = %s", (del_user_id,))
            conn.commit()
            flash("تم حذف الموظف بنجاح", "success")
        else:
            flash("لا يمكنك حذف حسابك الخاص", "danger")
        conn.close()
        return redirect(url_for('manage_staff.manage_staff'))
            
    # Fetch Data
    cursor.execute("""
        SELECT u.*, d.department_name_ar 
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.department_id 
        ORDER BY user_id DESC
    """)
    users = cursor.fetchall()
    conn.close()

    html = header_html + """
    <style>
        .staff-wrap { padding: 25px; animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .staff-card { background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); transition: 0.3s; overflow: hidden; }
        .staff-card:hover { transform: translateY(-5px); }
        
        
        .avatar-box { width: 50px; height: 50px; border-radius: 15px; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; font-weight: bold; background: var(--input-bg); color: var(--text); border: 1px solid var(--border); }
        
        .role-badge { font-size: 0.75rem; font-weight: 800; padding: 6px 14px; border-radius: 10px; text-transform: uppercase; }
        
        .table-pro thead th { background: rgba(0,0,0,0.02); border: none; border-bottom: 2px solid var(--border); padding: 20px 15px; font-size: 0.85rem; color: var(--text); opacity: 0.7; font-weight: 800; }
        
        .table-pro tbody td { padding: 20px 15px; border-bottom: 1px solid var(--border); vertical-align: middle; color: var(--text); }
        
        
        .action-btn { width: 40px; height: 40px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; transition: 0.2s; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); opacity: 0.8; }
        
        .action-btn:hover { background: #5e5ce6 !important; color: #fff !important; border-color: #5e5ce6 !important; opacity: 1; transform: translateY(-2px); }
        .action-btn.btn-del:hover { background: #ff3b30 !important; border-color: #ff3b30 !important; color: #fff !important; }

        /* Bootstrap overrides for theme */
        
        
        
        
    </style>

    <div class="container-fluid staff-wrap">
        <!-- Header -->
        <div class="row align-items-center mb-5 animate__animated animate__fadeIn">
            <div class="col-md-6">
                <div class="d-flex align-items-center gap-3">
                    <div class="bg-primary text-white rounded-4 shadow-sm d-flex align-items-center justify-content-center" style="width: 65px; height: 65px; font-size: 1.8rem;">
                        <i class="fas fa-user-shield"></i>
                    </div>
                    <div>
                        <h2 class="fw-black text-dark mb-0">دليل الموظفين</h2>
                        <p class="text-muted mb-0">إدارة الكادر الطبي، الصلاحيات، وهيكلية المركز</p>
                    </div>
                </div>
            </div>
            <div class="col-md-6 text-md-end mt-4 mt-md-0">
                <div class="d-inline-flex gap-2">
                    <a href="{{ url_for('manage_departments.manage_departments') }}" class="btn btn-light bg-white border-0 shadow-sm px-4 py-3 rounded-pill fw-bold text-muted">
                        <i class="fas fa-building me-2"></i> إدارة الأقسام
                    </a>
                    <a href="{{ url_for('manage_staff.add_employee') }}" class="btn btn-primary px-4 py-3 rounded-pill fw-bold shadow-sm d-flex align-items-center gap-2">
                        <i class="fas fa-plus"></i> إضافة موظف جديد
                    </a>
                </div>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="mb-5">
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} border-0 shadow-sm rounded-4 p-4 d-flex align-items-center gap-3">
                        <i class="fas fa-{% if category == 'success' %}check-circle{% else %}exclamation-triangle{% endif %} fs-4"></i>
                        <span class="fw-bold">{{ message }}</span>
                        <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Stats Overview -->
        <div class="row g-4 mb-5 animate__animated animate__fadeInUp">
            <div class="col-md-3">
                <div class="staff-card p-4 d-flex align-items-center gap-3">
                    <div class="bg-primary bg-opacity-10 text-primary rounded-4 avatar-box"><i class="fas fa-users"></i></div>
                    <div>
                        <h4 class="fw-black mb-0">{{ users|length }}</h4>
                        <p class="small text-muted mb-0">إجمالي الموظفين</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                {% set dr_count = users|selectattr('role', 'equalto', 'doctor')|list|length %}
                <div class="staff-card p-4 d-flex align-items-center gap-3">
                    <div class="bg-success bg-opacity-10 text-success rounded-4 avatar-box"><i class="fas fa-user-md"></i></div>
                    <div>
                        <h4 class="fw-black mb-0">{{ dr_count }}</h4>
                        <p class="small text-muted mb-0">أطباء مسجلين</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                {% set nurse_count = users|selectattr('role', 'equalto', 'nurse')|list|length %}
                <div class="staff-card p-4 d-flex align-items-center gap-3">
                    <div class="bg-info bg-opacity-10 text-info rounded-4 avatar-box"><i class="fas fa-user-nurse"></i></div>
                    <div>
                        <h4 class="fw-black mb-0">{{ nurse_count }}</h4>
                        <p class="small text-muted mb-0">تمريض ومساعدين</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                 <div class="staff-card p-4 d-flex align-items-center gap-3">
                    <div class="bg-warning bg-opacity-10 text-warning rounded-4 avatar-box"><i class="fas fa-id-badge"></i></div>
                    <div>
                        <h4 class="fw-black mb-0">نشط</h4>
                        <p class="small text-muted mb-0">حالة النظام الآن</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Staff List Table -->
        <div class="staff-card overflow-hidden animate__animated animate__fadeInUp" style="animation-delay: 0.1s;">
            <div class="table-responsive">
                <table class="table table-pro mb-0">
                    <thead>
                        <tr>
                            <th>الموظف والمعلومات الأساسية</th>
                            <th>بيانات الوصول الشخصية</th>
                            <th class="text-center">الدور الوظيفي</th>
                            <th>القسم / العيادة</th>
                            <th class="text-center">أدوات التحكم</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for u in users %}
                        <tr>
                            <td>
                                <div class="d-flex align-items-center gap-3">
                                    <div class="bg-light text-muted avatar-box" style="width: 45px; height: 45px; font-size: 1rem;">
                                        {{ u.full_name_ar[:1] if u.full_name_ar else '?' }}
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-1 text-dark">{{ u.full_name_ar if u.full_name_ar else u.username }}</h6>
                                        <p class="small text-muted mb-0"><i class="fas fa-phone-alt me-1"></i> {{ u.phone if u.phone else '--' }}</p>
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="d-flex flex-column">
                                    <span class="fw-bold" style="font-family: 'Courier New', Courier, monospace; letter-spacing: 1px;">@{{ u.username }}</span>
                                    <span class="small text-muted">ID: {{ u.employee_no if u.employee_no else 'N/A' }}</span>
                                </div>
                            </td>
                            <td class="text-center">
                                {% if u.role == 'admin' %}
                                    <span class="role-badge bg-danger bg-opacity-10 text-danger">مدير نظام</span>
                                {% elif u.role == 'doctor' %}
                                    <span class="role-badge bg-success bg-opacity-10 text-success">طبيب/أخصائي</span>
                                {% elif u.role == 'reception' %}
                                    <span class="role-badge bg-primary bg-opacity-10 text-primary">استقبال</span>
                                {% else %}
                                    <span class="role-badge bg-secondary bg-opacity-10 text-secondary">{{ u.role }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="d-flex align-items-center gap-2">
                                    <span class="p-2 bg-light rounded-3 small"><i class="fas fa-building text-muted"></i></span>
                                    <span class="fw-bold text-muted small">{{ u.department_name_ar if u.department_name_ar else 'الإدارة العامة' }}</span>
                                </div>
                            </td>
                            <td class="text-center">
                                <div class="d-flex justify-content-center gap-2">
                                    <a href="{{ url_for('manage_staff.edit_employee', uid=u.user_id) }}" class="action-btn" title="تعديل">
                                        <i class="fas fa-pen-nib"></i>
                                    </a>
                                    {% if u.user_id != session['user_id'] %}
                                    <a href="?del_user={{ u.user_id }}" class="action-btn btn-del" onclick="return confirm('تحذير: هل أنت متأكد من حذف حساب هذا الموظف نهائياً؟');" title="حذف">
                                        <i class="fas fa-trash-alt"></i>
                                    </a>
                                    {% endif %}
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="text-center py-5 text-muted">
                                <img src="https://cdn-icons-png.flaticon.com/512/7486/7486744.png" width="80" class="mb-3 opacity-25">
                                <p class="fw-bold">لا يوجد موظفين مسجلين حالياً</p>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, users=users)

@manage_staff_bp.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # ── Advanced Granular Permissions ───────────────────────────────────────
    permission_groups = {
        'وحدات النظام الأساسية': {
            'registration': 'قسم الاستقبال (Registration)', 
            'triage': 'قسم الفحص الأولي (Triage)', 
            'doctor': 'العيادة الطبية (Doctor Clinic)', 
            'lab': 'المختبر والنتائج (Laboratory)', 
            'radiology': 'الأشعة والسونار (Radiology)', 
            'pharmacy': 'الصيدلية والعلاجات (Pharmacy)',
        },
        'إدارة الحسابات والبيانات': {
            'invoices': 'عرض وإصدار الفواتير',
            'edit_invoice': 'تعديل أو حذف الفواتير',
            'reports': 'التقارير المالية والإحصائيات',
        },
        'الإشراف والتحكم': {
            'settings': 'إعدادات النظام العام',
            'manage_staff': 'إدارة الموظفين والصلاحيات',
            'nursing': 'سحب العينات (Nursing Lab)',
        }
    }
    
    # Flat mods for backward compatibility
    mods = {}
    for g, items in permission_groups.items():
        for k, v in items.items(): mods[k] = v

    if request.method == 'POST':
        user = request.form.get('username', '')
        name = request.form.get('full_name', '')
        role = request.form.get('role', 'reception')
        dept = int(request.form.get('department_id', 0))
        pwd = request.form.get('password', '')
        
        # New fields
        phone = request.form.get('phone', '')
        gender = request.form.get('gender', 'male')
        nat_id = request.form.get('national_id', '')
        emp_no = request.form.get('employee_no', '')
        
        permissions = request.form.getlist('permissions[]')
        perms = json.dumps(permissions) if permissions else '[]'
        
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (user,))
        if cursor.fetchone():
            flash("خطأ: اسم المستخدم موجود مسبقاً بجهاز آخر، الرجاء اختيار اسم مختلف.", "danger")
        else:
            hashed = generate_password_hash(pwd) if pwd else generate_password_hash('123456')
            email = f"{user}@healthpro.local"
            sql = """INSERT INTO users 
                     (username, password_hash, email, full_name_ar, role, department_id, permissions, phone, gender, national_id, employee_no) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (user, hashed, email, name, role, dept, perms, phone, gender, nat_id, emp_no))
            conn.commit()
            flash("تم إضافة الموظف بنجاح (مخزن بشكل آمن ومشفّر في قاعدة البيانات).", "success")
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    conn.close()

    html = header_html + """
    <style>
        .pro-card { border-radius: 24px; border: none; box-shadow: 0 20px 40px rgba(0,0,0,0.03); overflow: hidden; background: #fff; }
        .form-section-head { margin-bottom: 30px; border-bottom: 2px solid #f8f9fa; padding-bottom: 15px; display: flex; align-items: center; gap: 12px; }
        .form-section-head i { color: #0d6efd; font-size: 1.25rem; }
        .form-section-head h5 { margin-bottom: 0; font-weight: 800; color: #333; }
        .pro-input { border: 2px solid #f1f3f5; border-radius: 14px; padding: 14px 20px; transition: all 0.3s ease; background: #f8f9fa; color: #333; font-weight: 500; }
        .pro-input:focus { border-color: #0d6efd; background: #fff; box-shadow: 0 0 0 5px rgba(13, 110, 253, 0.08); outline: none; }
        .perm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; }
        .perm-box { cursor: pointer; border-radius: 18px; border: 2px solid #f1f3f5; padding: 25px 15px; text-align: center; transition: 0.3s; background: #fff; }
        .btn-check:checked + .perm-box { border-color: #0d6efd; background: #f0f7ff; transform: translateY(-5px); box-shadow: 0 10px 20px rgba(13, 110, 253, 0.1); }
        .perm-box i { font-size: 2rem; margin-bottom: 15px; color: #adb5bd; transition: 0.3s; }
        .btn-check:checked + .perm-box i { color: #0d6efd; }
        .section-label { font-size: 0.85rem; font-weight: 700; color: #6c757d; margin-bottom: 10px; display: block; }
    </style>

    <div class="container py-5" style="min-height: 85vh;">
        <div class="row justify-content-center">
            <div class="col-xl-11">
                <!-- Top Bar -->
                <div class="d-flex justify-content-between align-items-end mb-5 animate__animated animate__fadeIn">
                    <div>
                        <span class="badge bg-primary bg-opacity-10 text-primary px-3 py-2 rounded-pill fw-bold mb-2">الموارد البشرية (HR)</span>
                        <h1 class="fw-black text-dark mb-0" style="font-size: 2.5rem;">إضافة موظف جديد</h1>
                        <p class="text-muted mt-2">تسجيل بيانات الموظف، توزيع الأقسام، وتحديد صلاحيات النظام بدقة عالية</p>
                    </div>
                    <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-outline-dark px-4 py-2 rounded-pill fw-bold border-2">
                        <i class="fas fa-list-ul me-2"></i> عرض قائمة الموظفين
                    </a>
                </div>

                <form method="POST" class="animate__animated animate__fadeInUp">
                    <div class="row g-4">
                        <!-- Left Side: Basic & Personal Info -->
                        <div class="col-lg-8">
                            <div class="pro-card card mb-4">
                                <div class="card-body p-4 p-md-5">
                                    <div class="form-section-head">
                                        <i class="fas fa-id-card"></i>
                                        <h5>المعلومات الشخصية والوظيفية</h5>
                                    </div>
                                    
                                    <div class="row g-4">
                                        <div class="col-md-8">
                                            <label class="section-label">الاسم الكامل الرسمي (عربي)</label>
                                            <input type="text" name="full_name" class="form-control pro-input" placeholder="أدخل الاسم الرباعي كما في الهوية" required>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الرقم الوظيفي</label>
                                            <input type="text" name="employee_no" class="form-control pro-input" placeholder="HP-1000">
                                        </div>
                                        
                                        <div class="col-md-4">
                                            <label class="section-label">رقم الهاتف</label>
                                            <input type="tel" name="phone" class="form-control pro-input text-start" placeholder="07XXXXXXXX" dir="ltr">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الرقم الوطني / الهوية</label>
                                            <input type="text" name="national_id" class="form-control pro-input" placeholder="رقم الهوية الوطنية">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الجنس</label>
                                            <select name="gender" class="form-select pro-input">
                                                <option value="male">ذكر</option>
                                                <option value="female">أنثى</option>
                                            </select>
                                        </div>

                                        <div class="col-md-6">
                                            <label class="section-label">المسمى الوظيفي / الدور</label>
                                            <select name="role" class="form-select pro-input">
                                                <option value="doctor">طبيب / أخصائي</option>
                                                <option value="nurse">تمريض / مساعد طبي</option>
                                                <option value="lab_tech">فني مختبر / أشعة</option>
                                                <option value="reception" selected>موظف استقبال / إداري</option>
                                                <option value="admin">مدير نظام (Admin)</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="section-label">القسم الرئيسي</label>
                                            <div class="position-relative">
                                                <select name="department_id" class="form-select pro-input">
                                                    <option value="0">الإدارة العامة</option>
                                                    {% for d in departments %}
                                                        <option value="{{ d.department_id }}">{{ d.department_name_ar }}</option>
                                                    {% endfor %}
                                                </select>
                                                <a href="{{ url_for('manage_departments.manage_departments') }}" class="position-absolute translate-middle-y top-50 start-0 ms-3 text-muted" title="إدارة الأقسام">
                                                    <i class="fas fa-external-link-alt small"></i>
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Enhanced Permissions Section -->
                            <div class="pro-card card">
                                <div class="card-body p-4 p-md-5">
                                    <div class="form-section-head">
                                        <i class="fas fa-shield-alt"></i>
                                        <h5>مصفوفة الصلاحيات المتقدمة</h5>
                                    </div>
                                    <p class="text-muted small mb-4">قم بتحديد الصلاحيات الدقيقة لكل موظف. يمكنك تفعيل وحدات كاملة أو عمليات محددة.</p>
                                    
                                    {% for group_name, items in permission_groups.items() %}
                                    <div class="mb-5">
                                        <h6 class="fw-black text-primary mb-3"><i class="fas fa-layer-group me-2"></i> {{ group_name }}</h6>
                                        <div class="perm-grid">
                                            {% for k, v in items.items() %}
                                            <div class="position-relative">
                                                <input type="checkbox" name="permissions[]" value="{{ k }}" id="p_{{ k }}" class="btn-check">
                                                <label class="perm-box w-100 h-100 d-flex flex-column align-items-center justify-content-center" for="p_{{ k }}">
                                                    <div class="mb-2">
                                                        {% if k == 'registration' %}<i class="fas fa-user-plus"></i>
                                                        {% elif k == 'triage' %}<i class="fas fa-stethoscope"></i>
                                                        {% elif k == 'doctor' %}<i class="fas fa-user-md"></i>
                                                        {% elif k == 'lab' %}<i class="fas fa-microscope"></i>
                                                        {% elif k == 'radiology' %}<i class="fas fa-x-ray"></i>
                                                        {% elif k == 'pharmacy' %}<i class="fas fa-prescription-bottle-alt"></i>
                                                        {% elif k == 'invoices' %}<i class="fas fa-cash-register"></i>
                                                        {% elif k == 'edit_invoice' %}<i class="fas fa-file-invoice"></i>
                                                        {% elif k == 'reports' %}<i class="fas fa-chart-line"></i>
                                                        {% elif k == 'settings' %}<i class="fas fa-cogs"></i>
                                                        {% elif k == 'manage_staff' %}<i class="fas fa-users-cog"></i>
                                                        {% elif k == 'nursing' %}<i class="fas fa-vial"></i>
                                                        {% else %}<i class="fas fa-check-shield"></i>{% endif %}
                                                    </div>
                                                    <span class="fw-bold" style="font-size: 0.85rem;">{{ v.split('(')[0].strip() }}</span>
                                                </label>
                                            </div>
                                            {% endfor %}
                                        </div>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>

                        <!-- Right Side: Account & Credentials -->
                        <div class="col-lg-4">
                            <div class="pro-card card sticky-top" style="top: 20px;">
                                <div class="card-body p-4">
                                    <div class="form-section-head">
                                        <i class="fas fa-key"></i>
                                        <h5>بيانات الحساب</h5>
                                    </div>
                                    
                                    <div class="mb-4">
                                        <label class="section-label">اسم المستخدم (Username)</label>
                                        <input type="text" name="username" class="form-control pro-input text-start" dir="ltr" placeholder="john.doe" required>
                                        <div class="form-text mt-1 text-primary small"><i class="fas fa-info-circle me-1"></i> يُستخدم لتسجيل الدخول للنظام</div>
                                    </div>
                                    
                                    <div class="mb-4">
                                        <label class="section-label">كلمة المرور</label>
                                        <input type="password" name="password" class="form-control pro-input text-start" dir="ltr" placeholder="********" required>
                                    </div>

                                    <div class="bg-light p-3 rounded-4 mb-4 border-start border-primary border-4">
                                        <p class="small text-dark mb-0 fw-bold">تنبيه أمني:</p>
                                        <p class="small text-muted mb-0">تأكد من اختيار كلمة مرور قوية تحتوي على أحرف وأرقام لضمان حماية بيانات المرضى والمركز.</p>
                                    </div>

                                    <button type="submit" class="btn btn-primary w-100 py-3 rounded-pill fw-bold shadow-lg mb-3">
                                        <i class="fas fa-save me-2"></i> حفظ الموظف الجديد
                                    </button>
                                    <button type="reset" class="btn btn-light w-100 py-3 rounded-pill fw-bold text-muted">إلغاء العملية</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, departments=departments, mods=mods, permission_groups=permission_groups)

@manage_staff_bp.route('/edit_employee/<int:uid>', methods=['GET', 'POST'])
def edit_employee(uid):
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # ── Advanced Granular Permissions ───────────────────────────────────────
    permission_groups = {
        'وحدات النظام الأساسية': {
            'registration': 'قسم الاستقبال (Registration)', 
            'triage': 'قسم الفحص الأولي (Triage)', 
            'doctor': 'العيادة الطبية (Doctor Clinic)', 
            'lab': 'المختبر والنتائج (Laboratory)', 
            'radiology': 'الأشعة والسونار (Radiology)', 
            'pharmacy': 'الصيدلية والعلاجات (Pharmacy)',
        },
        'إدارة الحسابات والبيانات': {
            'invoices': 'عرض وإصدار الفواتير',
            'edit_invoice': 'تعديل أو حذف الفواتير',
            'reports': 'التقارير المالية والإحصائيات',
        },
        'الإشراف والتحكم': {
            'settings': 'إعدادات النظام العام',
            'manage_staff': 'إدارة الموظفين والصلاحيات',
            'nursing': 'سحب العينات (Nursing Lab)',
        }
    }
    
    # Flat mods for backward compatibility
    mods = {}
    for g, items in permission_groups.items():
        for k, v in items.items(): mods[k] = v

    if request.method == 'POST':
        user = request.form.get('username', '')
        name = request.form.get('full_name', '')
        role = request.form.get('role', 'reception')
        dept = int(request.form.get('department_id', 0))
        pwd = request.form.get('password', '')
        
        # New fields
        phone = request.form.get('phone', '')
        gender = request.form.get('gender', 'male')
        nat_id = request.form.get('national_id', '')
        emp_no = request.form.get('employee_no', '')
        
        permissions = request.form.getlist('permissions[]')
        perms = json.dumps(permissions) if permissions else '[]'
        
        cursor.execute("SELECT user_id FROM users WHERE username = %s AND user_id != %s", (user, uid))
        if cursor.fetchone():
            flash("خطأ: اسم المستخدم موجود مسبقاً، يرجى تغييره.", "danger")
        else:
            sql = """UPDATE users SET 
                     username=%s, full_name_ar=%s, role=%s, department_id=%s, permissions=%s,
                     phone=%s, gender=%s, national_id=%s, employee_no=%s
                     WHERE user_id=%s"""
            cursor.execute(sql, (user, name, role, dept, perms, phone, gender, nat_id, emp_no, uid))
            if pwd:
                hashed = generate_password_hash(pwd)
                cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (hashed, uid))
            
            conn.commit()
            flash("تم تحديث وحفظ بيانات الموظف والصلاحيات بنجاح.", "success")
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    employee = cursor.fetchone()
    if not employee:
        conn.close()
        return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    conn.close()

    emp_perms = []
    if employee['permissions']:
        try:
            emp_perms = json.loads(employee['permissions'])
        except:
            emp_perms = []

    html = header_html + """
    <style>
        .pro-card { border-radius: 24px; border: none; box-shadow: 0 20px 40px rgba(0,0,0,0.03); overflow: hidden; background: #fff; }
        .form-section-head { margin-bottom: 30px; border-bottom: 2px solid #f8f9fa; padding-bottom: 15px; display: flex; align-items: center; gap: 12px; }
        .form-section-head i { color: #0d6efd; font-size: 1.25rem; }
        .form-section-head h5 { margin-bottom: 0; font-weight: 800; color: #333; }
        .pro-input { border: 2px solid #f1f3f5; border-radius: 14px; padding: 14px 20px; transition: all 0.3s ease; background: #f8f9fa; color: #333; font-weight: 500; }
        .pro-input:focus { border-color: #0d6efd; background: #fff; box-shadow: 0 0 0 5px rgba(13, 110, 253, 0.08); outline: none; }
        .perm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; }
        .perm-box { cursor: pointer; border-radius: 18px; border: 2px solid #f1f3f5; padding: 25px 15px; text-align: center; transition: 0.3s; background: #fff; }
        .btn-check:checked + .perm-box { border-color: #0d6efd; background: #f0f7ff; transform: translateY(-5px); box-shadow: 0 10px 20px rgba(13, 110, 253, 0.1); }
        .perm-box i { font-size: 2rem; margin-bottom: 15px; color: #adb5bd; transition: 0.3s; }
        .btn-check:checked + .perm-box i { color: #0d6efd; }
        .section-label { font-size: 0.85rem; font-weight: 700; color: #6c757d; margin-bottom: 10px; display: block; }
    </style>

    <div class="container py-5" style="min-height: 85vh;">
        <div class="row justify-content-center">
            <div class="col-xl-11">
                <!-- Top Bar -->
                <div class="d-flex justify-content-between align-items-end mb-5 animate__animated animate__fadeIn">
                    <div>
                        <span class="badge bg-success bg-opacity-10 text-success px-3 py-2 rounded-pill fw-bold mb-2">تعديل الملف الشخصي</span>
                        <h1 class="fw-black text-dark mb-0" style="font-size: 2.5rem;">تعديل بيانات الموظف</h1>
                        <p class="text-muted mt-2">تحديث معلومات الموظف: {{ emp.full_name_ar }}</p>
                    </div>
                    <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-outline-dark px-4 py-2 rounded-pill fw-bold border-2">
                        <i class="fas fa-arrow-right me-2"></i> العودة للقائمة
                    </a>
                </div>

                <form method="POST" class="animate__animated animate__fadeInUp">
                    <div class="row g-4">
                        <!-- Left Side: Basic & Personal Info -->
                        <div class="col-lg-8">
                            <div class="pro-card card mb-4">
                                <div class="card-body p-4 p-md-5">
                                    <div class="form-section-head">
                                        <i class="fas fa-user-edit"></i>
                                        <h5>المعلومات الشخصية والوظيفية</h5>
                                    </div>
                                    
                                    <div class="row g-4">
                                        <div class="col-md-8">
                                            <label class="section-label">الاسم الكامل الرسمي (عربي)</label>
                                            <input type="text" name="full_name" class="form-control pro-input" value="{{ emp.full_name_ar }}" required>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الرقم الوظيفي</label>
                                            <input type="text" name="employee_no" class="form-control pro-input" value="{{ emp.employee_no or '' }}" placeholder="HP-1000">
                                        </div>
                                        
                                        <div class="col-md-4">
                                            <label class="section-label">رقم الهاتف</label>
                                            <input type="tel" name="phone" class="form-control pro-input text-start" value="{{ emp.phone or '' }}" placeholder="07XXXXXXXX" dir="ltr">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الرقم الوطني / الهوية</label>
                                            <input type="text" name="national_id" class="form-control pro-input" value="{{ emp.national_id or '' }}" placeholder="رقم الهوية الوطنية">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="section-label">الجنس</label>
                                            <select name="gender" class="form-select pro-input">
                                                <option value="male" {% if emp.gender == 'male' %}selected{% endif %}>ذكر</option>
                                                <option value="female" {% if emp.gender == 'female' %}selected{% endif %}>أنثى</option>
                                            </select>
                                        </div>

                                        <div class="col-md-6">
                                            <label class="section-label">المسمى الوظيفي / الدور</label>
                                            <select name="role" class="form-select pro-input">
                                                <option value="doctor" {% if emp.role == 'doctor' %}selected{% endif %}>طبيب / أخصائي</option>
                                                <option value="nurse" {% if emp.role == 'nurse' %}selected{% endif %}>تمريض / مساعد طبي</option>
                                                <option value="lab_tech" {% if emp.role == 'lab_tech' %}selected{% endif %}>فني مختبر / أشعة</option>
                                                <option value="reception" {% if emp.role == 'reception' %}selected{% endif %}>موظف استقبال / إداري</option>
                                                <option value="admin" {% if emp.role == 'admin' %}selected{% endif %}>مدير نظام (Admin)</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="section-label">القسم الرئيسي</label>
                                            <select name="department_id" class="form-select pro-input">
                                                <option value="0">الإدارة العامة</option>
                                                {% for d in departments %}
                                                    <option value="{{ d.department_id }}" {% if emp.department_id == d.department_id %}selected{% endif %}>{{ d.department_name_ar }}</option>
                                                {% endfor %}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Enhanced Permissions Section -->
                            <div class="pro-card card">
                                <div class="card-body p-4 p-md-5">
                                    <div class="form-section-head">
                                        <i class="fas fa-shield-alt"></i>
                                        <h5>مصفوفة الصلاحيات المتقدمة</h5>
                                    </div>
                                    <p class="text-muted small mb-4">قم بتعديل الصلاحيات الدقيقة للموظف الحالي. التعديرات تطبق فور تسجيل دخوله القادم.</p>
                                    
                                    {% for group_name, items in permission_groups.items() %}
                                    <div class="mb-5">
                                        <h6 class="fw-black text-primary mb-3"><i class="fas fa-layer-group me-2"></i> {{ group_name }}</h6>
                                        <div class="perm-grid">
                                            {% for k, v in items.items() %}
                                            <div class="position-relative">
                                                <input type="checkbox" name="permissions[]" value="{{ k }}" id="p_{{ k }}" class="btn-check" {% if k in emp_perms %}checked{% endif %}>
                                                <label class="perm-box w-100 h-100 d-flex flex-column align-items-center justify-content-center" for="p_{{ k }}">
                                                    <div class="mb-2">
                                                        {% if k == 'registration' %}<i class="fas fa-user-plus"></i>
                                                        {% elif k == 'triage' %}<i class="fas fa-stethoscope"></i>
                                                        {% elif k == 'doctor' %}<i class="fas fa-user-md"></i>
                                                        {% elif k == 'lab' %}<i class="fas fa-microscope"></i>
                                                        {% elif k == 'radiology' %}<i class="fas fa-x-ray"></i>
                                                        {% elif k == 'pharmacy' %}<i class="fas fa-prescription-bottle-alt"></i>
                                                        {% elif k == 'invoices' %}<i class="fas fa-cash-register"></i>
                                                        {% elif k == 'edit_invoice' %}<i class="fas fa-file-invoice"></i>
                                                        {% elif k == 'reports' %}<i class="fas fa-chart-line"></i>
                                                        {% elif k == 'settings' %}<i class="fas fa-cogs"></i>
                                                        {% elif k == 'manage_staff' %}<i class="fas fa-users-cog"></i>
                                                        {% elif k == 'nursing' %}<i class="fas fa-vial"></i>
                                                        {% else %}<i class="fas fa-check-shield"></i>{% endif %}
                                                    </div>
                                                    <span class="fw-bold" style="font-size: 0.85rem;">{{ v.split('(')[0].strip() }}</span>
                                                </label>
                                            </div>
                                            {% endfor %}
                                        </div>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>

                        <!-- Right Side: Account & Credentials -->
                        <div class="col-lg-4">
                            <div class="pro-card card sticky-top" style="top: 20px;">
                                <div class="card-body p-4">
                                    <div class="form-section-head">
                                        <i class="fas fa-key"></i>
                                        <h5>بيانات الحساب</h5>
                                    </div>
                                    
                                    <div class="mb-4">
                                        <label class="section-label">اسم المستخدم (Username)</label>
                                        <input type="text" name="username" class="form-control pro-input text-start" dir="ltr" value="{{ emp.username }}" required>
                                    </div>
                                    
                                    <div class="mb-4">
                                        <label class="section-label">كلمة المرور الجديدة</label>
                                        <input type="password" name="password" class="form-control pro-input text-start" dir="ltr" placeholder="اتركه فارغاً للحفاظ على الحالية">
                                    </div>

                                    <div class="bg-light p-3 rounded-4 mb-4 border-start border-warning border-4">
                                        <p class="small text-dark mb-0 fw-bold">ملاحظة:</p>
                                        <p class="small text-muted mb-0">عند تغيير كلمة المرور، سيتم تشفير القيمة الجديدة فوراً في قاعدة البيانات.</p>
                                    </div>

                                    <button type="submit" class="btn btn-primary w-100 py-3 rounded-pill fw-bold shadow-lg mb-3">
                                        <i class="fas fa-check-circle me-2"></i> تحديث بيانات الموظف
                                    </button>
                                    <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-light w-100 py-3 rounded-pill fw-bold text-muted d-block text-center text-decoration-none">إلغاء التعديل</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, emp=employee, departments=departments, mods=mods, emp_perms=emp_perms, permission_groups=permission_groups)
