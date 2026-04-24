from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

system_data_bp = Blueprint('system_data', __name__)

@system_data_bp.route('/system_data', methods=['GET', 'POST'])
def system_data():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('dashboard.dashboard'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    msg = ''
    msg_type = 'info'
    
    # --- Handle Actions ---
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'wipe_transactions':
            try:
                if conn.is_pg:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                    for tbl in ['appointments', 'triage', 'consultations', 'lab_requests', 'radiology_requests', 'prescriptions', 'invoices']:
                        cursor.execute(f"TRUNCATE TABLE {tbl} CASCADE")
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                else:
                    # SQLite path
                    cursor.execute("PRAGMA foreign_keys = OFF")
                    for tbl in ['appointments', 'triage', 'consultations', 'lab_requests', 'radiology_requests', 'prescriptions', 'invoices']:
                        cursor.execute(f"DELETE FROM {tbl}")
                        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{tbl}'") # Reset auto-increment
                    cursor.execute("PRAGMA foreign_keys = ON")
                
                conn.commit()
                msg = "تم مسح كافة البيانات الحركية (التحويلات، المعاينات، والمحاسبة) بنجاح."
                msg_type = "danger"
            except Exception as e:
                msg = f"حدث خطأ: {e}"
                msg_type = "danger"
                
        elif action == 'optimize':
            try:
                if conn.is_pg:
                    cursor.execute("VACUUM FULL") # Postgres equivalent or just ignore if it's MySQL
                else:
                    cursor.execute("VACUUM")
                msg = "تم تحسين قاعدة البيانات وضغط الملفات بنجاح."
                msg_type = "success"
            except Exception as e:
                msg = f"حدث خطأ: {e}"
                msg_type = "danger"
                
        elif action == 'update_system':
            msg = "النظام مُحدّث بالفعل إلى آخر إصدار (Premier OS v5.2). لا توجد تحديثات متاحة حالياً."
            msg_type = "info"

    # --- Fetch Detailed Stats ---
    stats = {}
    queries = {
        'المستفيدين': "SELECT COUNT(*) as c FROM patients",
        'إجمالي الحجوزات': "SELECT COUNT(*) as c FROM appointments",
        'معاينات طبية': "SELECT COUNT(*) as c FROM consultations",
        'طلبات المختبر': "SELECT COUNT(*) as c FROM lab_requests",
        'طلبات الأشعة': "SELECT COUNT(*) as c FROM radiology_requests",
        'وصفات كلية': "SELECT COUNT(*) as c FROM prescriptions",
        'فواتير صادرة': "SELECT COUNT(*) as c FROM invoices WHERE amount > 0",
        'صافي الوارد المالي': "SELECT SUM(amount) as s FROM invoices",
        'المستخدمين': "SELECT COUNT(*) as c FROM users"
    }
    
    for label, query in queries.items():
        cursor.execute(query)
        result = cursor.fetchone()
        if 's' in result:
            stats[label] = result['s'] if result['s'] is not None else 0
        else:
            stats[label] = result['c']
            
    # Fetch Table Status
    table_names = ['patients', 'appointments', 'triage', 'consultations', 'users', 'invoices']
    table_statuses = []
    
    for tbl in table_names:
        if conn.is_pg:
            cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{tbl}'")
            status = cursor.fetchone()
            if status:
                table_statuses.append({
                    'name': tbl,
                    'Collation': 'Default',
                    'Engine': 'PostgreSQL'
                })
        else:
            # SQLite specific info
            cursor.execute(f"PRAGMA table_info({tbl})")
            res = cursor.fetchone()
            if res:
                table_statuses.append({
                    'name': tbl,
                    'Collation': 'Binary',
                    'Engine': 'SQLite'
                })
            
    conn.close()

    html = header_html + """
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="fw-bold text-dark"><i class="fas fa-database text-danger me-2"></i> أداة البيانات المركزية (Admin Tool)</h2>
        <span class="badge bg-danger rounded-pill px-3 py-2">وضع الأدمين المتقدم</span>
    </div>

    {% if msg %}
        <div class="alert alert-{{ msg_type }} shadow-sm border-0 rounded-4 mb-4 animate__animated animate__shakeX">
            <i class="fas fa-info-circle me-2"></i> {{ msg }}
        </div>
    {% endif %}

    <div class="row g-4">
        <!-- Detailed Metrics -->
        <div class="col-lg-8">
            <div class="apple-card p-4">
                <h5 class="fw-bold mb-4">إحصائيات النظام التفصيلية</h5>
                <div class="row row-cols-2 row-cols-md-3 g-3">
                    {% for label, val in stats.items() %}
                        <div class="col">
                            <div class="p-3 rounded-4 bg-light border text-center">
                                <div class="text-muted small mb-1">{{ label }}</div>
                                <div class="h4 fw-bold mb-0">
                                    {% if val is number %}
                                        {{ "{:,.0f}".format(val) if val % 1 == 0 else "{:,.2f}".format(val) }}
                                    {% else %}
                                        {{ val }}
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- System Actions -->
        <div class="col-lg-4">
            <div class="apple-card p-4 bg-dark text-white border-0 shadow-lg">
                <h5 class="fw-bold mb-4"><i class="fas fa-tools me-2"></i> عمليات النظام</h5>
                
                <form method="POST" onsubmit="return confirm('تحذير: هذا الإجراء سيمسح كافة السجلات الحركية. هل أنت متأكد؟')">
                    <input type="hidden" name="action" value="wipe_transactions">
                    <button type="submit" class="btn btn-outline-danger w-100 mb-3 rounded-pill py-2">
                        <i class="fas fa-trash-alt me-2"></i> مسح سجلات الحركة (Reset)
                    </button>
                </form>

                <form method="POST">
                    <input type="hidden" name="action" value="optimize">
                    <button type="submit" class="btn btn-outline-success w-100 mb-3 rounded-pill py-2">
                        <i class="fas fa-broom me-2"></i> تحسين قاعدة البيانات
                    </button>
                </form>

                <form method="POST">
                    <input type="hidden" name="action" value="update_system">
                    <button type="submit" class="btn btn-outline-info w-100 mb-3 rounded-pill py-2">
                        <i class="fas fa-sync-alt me-2"></i> تحديث النظام (V5.2)
                    </button>
                </form>

                <a href="data_cleanup" class="btn fw-bold w-100 mb-3 rounded-pill py-2 shadow-sm d-flex align-items-center justify-content-center" style="background: linear-gradient(135deg, #ff3b30, #d70015); color: white; transition: 0.3s; box-shadow: 0 4px 15px rgba(255, 59, 48, 0.4);">
                    <i class="fas fa-skull-crossbones ms-2 me-2"></i> مركز تنظيف البيانات المتقدم
                </a>
                
                <hr class="border-secondary my-4">
                <p class="small text-white-50 text-center">
                    تستخدم هذه الأداة للتحكم الكامل في بنية البيانات. يرجى الحذر عند استخدام خيار المسح.
                </p>
            </div>
        </div>
    </div>

    <div class="mt-4">
        <div class="apple-card p-4">
            <h5 class="fw-bold mb-4">سلامة الجداول والاتصال</h5>
            <div class="table-responsive">
                <table class="table table-sm small align-middle">
                    <thead>
                        <tr>
                            <th>الجدول</th>
                            <th>الحالة</th>
                            <th>الترميز</th>
                            <th>المحرك</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for info in table_statuses %}
                        <tr>
                            <td><strong>{{ info.name }}</strong></td>
                            <td><span class="badge bg-success-subtle text-success">Active</span></td>
                            <td>{{ info.Collation }}</td>
                            <td>{{ info.Engine }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, msg=msg, msg_type=msg_type, stats=stats, table_statuses=table_statuses)
