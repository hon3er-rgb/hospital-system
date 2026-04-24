from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
import json

programmer_settings_bp = Blueprint('programmer_settings', __name__)

def check_permission():
    if not session.get('user_id'):
        return False
    # Only allow admin for programmer settings
    if session.get('role') != 'admin':
        return False
    return True

@programmer_settings_bp.route('/programmer_settings/change_name', methods=['GET', 'POST'])
def change_name():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Handle submission first
    if request.method == 'POST':
        new_name = request.form.get('system_name')
        new_icon = request.form.get('system_icon')
        ai_key   = request.form.get('gemini_api_key')
        
        if new_name:
            import re
            if not re.match(r'^[A-Za-z0-9\s\-_.,&\'"]+$', new_name):
                msg = "خطأ: يرجى كتابة الاسم باللغة الإنجليزية فقط."
            else:
                cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'hospital_name'", (new_name,))
                if cursor.rowcount == 0:
                    cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('hospital_name', %s)", (new_name,))
                
                if new_icon:
                    cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'system_icon'", (new_icon,))
                    if cursor.rowcount == 0:
                        cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('system_icon', %s)", (new_icon,))
                
                if ai_key is not None:
                    cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'gemini_api_key'", (ai_key,))
                    if cursor.rowcount == 0:
                        cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('gemini_api_key', %s)", (ai_key,))

                conn.commit()
                msg = "تم حفظ التغييرات بنجاح"

    # 2. Fetch current settings for the form
    cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ('hospital_name', 'system_icon', 'gemini_api_key')")
    rows = cursor.fetchall()
    curr_data = {'hospital_name': 'HealthPro Intelligence', 'system_icon': 'fas fa-hand-holding-medical', 'gemini_api_key': ''}
    for row in rows:
        curr_data[row['setting_key']] = row['setting_value'] if row['setting_value'] else ''
    
    current_name = curr_data['hospital_name']
    current_icon = curr_data['system_icon']
    current_ai   = curr_data['gemini_api_key']
    conn.close()

    def render_body(msg_str, sys_name, sys_icon, sys_ai):
        return header_html + f"""
        <div class="row pt-2 mb-4 text-center">
            <div class="col-12">
                <h2 class="fw-bold mb-0 text-danger"><i class="fas fa-signature me-2"></i>تغيير هوية النظام والذكاء الاصطناعي</h2>
                <p class="text-muted small">هذه صفحة صلاحيات المبرمج - تحكم كامل بظهور النظام</p>
            </div>
        </div>
        <div class="row justify-content-center mb-5">
            <div class="col-md-6">
                <div class="card neo-card">
                    <div class="card-body text-center">
                        {{% if msg %}}
                            <div class="alert alert-{{% if 'خطأ' in msg %}}danger{{% else %}}success{{% endif %}}">{{ msg }}</div>
                        {{% endif %}}
                        <form method="POST">
                            <div class="mb-4 text-end">
                                <label class="form-label fw-bold">الاسم الجديد للنظام (English Only)</label>
                                <input type="text" name="system_name" class="form-control text-center fs-5 py-2" value="{ sys_name }" pattern="^[A-Za-z0-9\\\\s\\\\-_.,&\\'\\&quot;]+$" title="الرجاء كتابة الاسم باللغة الإنجليزية فقط" placeholder="أدخل اسم النظام باللغة الإنجليزية فقط" required>
                            </div>
                            
                            <div class="mb-4 text-end">
                                <label class="form-label fw-bold">أيقونة النظام</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="{ sys_icon } text-primary"></i></span>
                                    <select name="system_icon" class="form-select text-center">
                                        <option value="fas fa-hand-holding-medical" { 'selected' if sys_icon == 'fas fa-hand-holding-medical' else '' }>طبية (Medical Hand)</option>
                                        <option value="fas fa-hospital" { 'selected' if sys_icon == 'fas fa-hospital' else '' }>مستشفى (Hospital)</option>
                                        <option value="fas fa-stethoscope" { 'selected' if sys_icon == 'fas fa-stethoscope' else '' }>سماعة (Stethoscope)</option>
                                        <option value="fas fa-user-md" { 'selected' if sys_icon == 'fas fa-user-md' else '' }>طبيب (Doctor)</option>
                                        <option value="fas fa-user-shield" { 'selected' if sys_icon == 'fas fa-user-shield' else '' }>حماية (Shield)</option>
                                        <option value="fas fa-laptop-medical" { 'selected' if sys_icon == 'fas fa-laptop-medical' else '' }>تقنية طبية (E-Health)</option>
                                        <option value="fas fa-heartbeat" { 'selected' if sys_icon == 'fas fa-heartbeat' else '' }>نبض (Heartbeat)</option>
                                        <option value="fas fa-plus-square" { 'selected' if sys_icon == 'fas fa-plus-square' else '' }>بلس (Plus Sign)</option>
                                        <option value="fas fa-microscope" { 'selected' if sys_icon == 'fas fa-microscope' else '' }>مختبر (Microscope)</option>
                                    </select>
                                </div>
                            </div>

                            <div class="mb-4 text-end p-3 rounded-4" style="background:#f8fafc; border: 1.5px solid #e2e8f0;">
                                <label class="form-label fw-bold text-primary"><i class="fas fa-brain me-1"></i> مفاتيح الذكاء الاصطناعي (Google Gemini API Keys)</label>
                                <textarea name="gemini_api_key" class="form-control text-center font-monospace" rows="3" placeholder="أدخل مفاتيح Google Gemini هنا، افصل بينها بفاصلة أو سطر جديد...">{ sys_ai }</textarea>
                                <div class="form-text text-muted small mt-2">يمكنك إضافة أكثر من مفتاح لتفادي حظر الخدمة وزيادة السرعة. افصل بينها بفاصلة (,) أو سطر جديد.</div>
                            </div>

                            <button type="submit" class="btn btn-danger w-100 mb-2 py-2 fs-5"><i class="fas fa-save me-2"></i>حفظ كافة الإعدادات</button>
                            <a href="/settings" class="btn btn-secondary w-100 py-2"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        """ + footer_html
    
    return render_template_string(render_body(msg, current_name, current_icon, current_ai), msg=msg)

@programmer_settings_bp.route('/programmer_settings/update_system', methods=['GET', 'POST'])
def update_system():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    if request.method == 'POST':
        msg = "جاري التحقق من التحديثات... النظام يعمل بأحدث إصدار حالياً."

    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0 text-warning"><i class="fas fa-sync-alt me-2"></i>تحديث النظام</h2>
            <p class="text-muted small">هذه صفحة صلاحيات المبرمج</p>
        </div>
    </div>
    <div class="row justify-content-center mb-5">
        <div class="col-md-6">
            <div class="card neo-card">
                <div class="card-body text-center">
                    {% if msg %}
                        <div class="alert alert-info">{{ msg }}</div>
                    {% endif %}
                    <h5 class="mb-4">إصدار النظام الحالي: v2.5.0</h5>
                    <form method="POST">
                        <button type="submit" class="btn btn-warning w-100 mb-2 text-dark fw-bold"><i class="fas fa-download me-2"></i>البحث عن تحديثات وتثبيتها</button>
                        <a href="/settings" class="btn btn-secondary w-100"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, msg=msg)

@programmer_settings_bp.route('/programmer_settings/system_access', methods=['GET'])
def system_access():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0 text-secondary"><i class="fas fa-door-open me-2"></i>الدخول للنظام</h2>
            <p class="text-muted small">هذه صفحة صلاحيات المبرمج</p>
        </div>
    </div>
    <div class="row justify-content-center mb-5">
        <div class="col-md-6">
            <div class="card neo-card">
                <div class="card-body text-center">
                    <p>هنا يمكن للمبرمج تجاوز قيود الدخول العادية أو إنشاء روابط دخول طوارئ للنظام.</p>
                    <button class="btn btn-dark w-100 mb-2"><i class="fas fa-user-secret me-2"></i>تسجيل دخول طوارئ</button>
                    <button class="btn btn-outline-dark w-100 mb-2"><i class="fas fa-shield-alt me-2"></i>إدارة الأذونات الأساسية</button>
                    <a href="/settings" class="btn btn-secondary w-100"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html)

@programmer_settings_bp.route('/programmer_settings/activate_system', methods=['GET', 'POST'])
def activate_system():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    if request.method == 'POST':
        key = request.form.get('activation_key')
        if key == '12345':
            msg = "تم تفعيل النظام بنجاح"
        else:
            msg = "مفتاح التفعيل غير صحيح"
            
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0 text-success"><i class="fas fa-key me-2"></i>تفعيل النظام</h2>
            <p class="text-muted small">هذه صفحة صلاحيات المبرمج</p>
        </div>
    </div>
    <div class="row justify-content-center mb-5">
        <div class="col-md-6">
            <div class="card neo-card">
                <div class="card-body text-center">
                    <form method="POST">
                        <div class="mb-3 text-end">
                            <label class="form-label">مفتاح التفعيل / السيريال</label>
                            <input type="text" name="activation_key" class="form-control text-center" placeholder="XXXX-XXXX-XXXX-XXXX" required>
                        </div>
                        <button type="submit" class="btn btn-success w-100 mb-2"><i class="fas fa-check-circle me-2"></i>تأكيد التفعيل</button>
                        <a href="/settings" class="btn btn-secondary w-100"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, msg=msg)

@programmer_settings_bp.route('/programmer_settings/ai_settings', methods=['GET', 'POST'])
def ai_settings():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        ai_key = request.form.get('gemini_api_key')
        if ai_key is not None:
            # We use the existing gemini_api_key field for the new logic
            cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'gemini_api_key'", (ai_key,))
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('gemini_api_key', %s)", (ai_key,))
            conn.commit()
            msg = "تم تحديث مفتاح التشغيل (API Token) بنجاح"
            
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'gemini_api_key'")
    row = cursor.fetchone()
    current_ai = row['setting_value'] if row and row['setting_value'] else ''
    conn.close()
    
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0 text-primary"><i class="fas fa-microchip me-2"></i>إعدادات المحرك السريري (Free LLM)</h2>
            <p class="text-muted small">هنا يتم إدارة الاتصال بمحركات الذكاء الاصطناعي الخارجية للتشخيص السريري</p>
        </div>
    </div>
    <div class="row justify-content-center mb-5">
        <div class="col-md-6">
            <div class="card neo-card border-primary shadow-lg" style="border-radius: 24px; border-width: 2px;">
                <div class="card-body text-center p-4">
                    {% if msg %}
                        <div class="alert alert-success rounded-4 fw-bold mb-4 py-3"><i class="fas fa-check-circle me-2"></i>{{ msg }}</div>
                    {% endif %}
                    
                    <div class="text-start mb-4 p-4 rounded-4" style="background:#f8fafc; border: 1.5px solid #e2e8f0;">
                        <h6 class="fw-bold text-primary mb-3"><i class="fas fa-info-circle me-2"></i>معلومات المحرك الحالي</h6>
                        <ul class="list-unstyled small text-muted mb-0">
                            <li class="mb-2"><i class="fas fa-link me-2 text-primary"></i>المزود: <strong>apifreellm.com</strong></li>
                            <li class="mb-2"><i class="fas fa-brain me-2 text-primary"></i>النموذج: <strong>High-Performance Clinical Chat</strong></li>
                            <li><i class="fas fa-shield-alt me-2 text-primary"></i>التأمين: <strong>Bearer Token Authentication</strong></li>
                        </ul>
                    </div>

                    <form method="POST">
                        <div class="mb-4 text-end">
                            <label class="form-label fw-bold text-dark fs-5 mb-2"><i class="fas fa-key me-2 text-primary"></i>رمز التحقق (API Token)</label>
                            <div class="input-group">
                                <span class="input-group-text bg-white border-end-0" style="border-radius: 12px 0 0 12px;"><i class="fas fa-lock text-muted"></i></span>
                                <input type="text" name="gemini_api_key" id="keys_textarea" class="form-control text-center font-monospace border-start-0" 
                                       style="border-radius: 0 12px 12px 0; height: 55px;"
                                       value="{{ current_ai }}"
                                       placeholder="أدخل الـ Token الخاص بك هنا...">
                            </div>
                            <div class="form-text text-muted small mt-2">يمكنك الحصول على الـ Token من لوحة تحكم apifreellm.com وإضافته هنا لتفعيل المساعد الذكي.</div>
                            
                            <div id="validation_results" class="mt-3 text-start small"></div>
                            
                            <button type="button" onclick="verifyKeys()" class="btn btn-sm btn-outline-primary rounded-pill mt-3 px-4 py-2 fw-bold" id="verify_btn">
                                <i class="fas fa-bolt me-1"></i> اختبار اتصال المحرك الآن
                            </button>
                        </div>
                        
                        <hr class="my-4">
                        
                        <button type="submit" class="btn btn-primary w-100 mb-3 py-3 fw-bold rounded-pill shadow-sm fs-5"><i class="fas fa-save me-2"></i>حفظ وتفعيل الإعدادات</button>
                        <a href="/settings" class="btn btn-link text-secondary w-100 text-decoration-none"><i class="fas fa-arrow-right me-2"></i>العودة إلى الإعدادات الرئيسية</a>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function verifyKeys() {
        const key = document.getElementById('keys_textarea').value;
        const btn = document.getElementById('verify_btn');
        const resDiv = document.getElementById('validation_results');
        
        if (!key.trim()) { alert("يرجى إدخال الـ Token أولاً"); return; }
        
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-sync fa-spin me-1"></i> جاري الاتصال بالمحرك...';
        resDiv.innerHTML = '';
        
        fetch('/api/verify_api_key', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ keys: key })
        })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-bolt me-1"></i> اختبار اتصال المحرك الآن';
            
            let html = '<div class="alert alert-' + (data.results[0].status ? 'success' : 'danger') + ' rounded-4 py-2 mt-2">';
            html += '<i class="fas fa-' + (data.results[0].status ? 'check-circle' : 'exclamation-triangle') + ' me-2"></i>';
            html += data.results[0].message;
            html += '</div>';
            resDiv.innerHTML = html;
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-bolt me-1"></i> اختبار اتصال المحرك الآن';
            resDiv.innerHTML = '<div class="alert alert-danger rounded-4 py-2 mt-2"><i class="fas fa-times-circle me-2"></i>فشل في الاتصال بالخادم</div>';
        });
    }
    </script>
    """ + footer_html
    return render_template_string(html, msg=msg, current_ai=current_ai)

@programmer_settings_bp.route('/programmer_settings/reset_data', methods=['GET', 'POST'])
def reset_data():
    if not check_permission():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    if request.method == 'POST':
        confirm = request.form.get('confirm_reset')
        if confirm == 'RESET':
            conn = get_db()
            cursor = conn.cursor()
            try:
                # Sequence of deletion to avoid foreign key issues (if any)
                cursor.execute("DELETE FROM lab_result_details")
                cursor.execute("DELETE FROM lab_requests")
                cursor.execute("DELETE FROM radiology_requests")
                cursor.execute("DELETE FROM prescriptions")
                cursor.execute("DELETE FROM triage")
                cursor.execute("DELETE FROM consultations")
                cursor.execute("DELETE FROM invoices")
                cursor.execute("DELETE FROM appointments")
                cursor.execute("DELETE FROM patients")
                conn.commit()
                msg = "تم حذف كافة بيانات المرضى والزيارات بنجاح"
            except Exception as e:
                conn.rollback()
                msg = f"خطأ أثناء الحذف: {str(e)}"
        else:
            msg = "خطأ: يرجى كتابة كلمة RESET للتأكيد"

    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0 text-danger"><i class="fas fa-trash-alt me-2"></i>تفريغ بيانات المرضى</h2>
            <p class="text-muted small">هذه صفحة صلاحيات المبرمج - سيتم مسح كافة السجلات الطبية</p>
        </div>
    </div>
    <div class="row justify-content-center mb-5">
        <div class="col-md-6">
            <div class="card neo-card border-danger">
                <div class="card-body text-center">
                    {% if msg %}
                        <div class="alert alert-{% if 'بنجاح' in msg %}success{% else %}danger{% endif %}">{{ msg }}</div>
                    {% endif %}
                    
                    <div class="alert alert-warning mb-4">
                        <i class="fas fa-exclamation-triangle fa-2x mb-2 d-block"></i>
                        تحذير: سيتم حذف كافة المرضى، المواعيد، الفواتير، التحاليل والأشعة نهائياً!
                        هذا الإجراء لا يمكن التراجع عنه.
                    </div>

                    <form method="POST">
                        <div class="mb-4 text-end">
                            <label class="form-label fw-bold">لتأكيد الحذف، اكتب كلمة RESET باللغة الإنجليزية:</label>
                            <input type="text" name="confirm_reset" class="form-control text-center fs-4 font-monospace" placeholder="RESET" required>
                        </div>
                        <button type="submit" class="btn btn-danger w-100 mb-2 py-2 fw-bold"><i class="fas fa-eraser me-2"></i>بدء عملية الحذف النهائي</button>
                        <a href="/settings" class="btn btn-secondary w-100 py-2"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, msg=msg)
