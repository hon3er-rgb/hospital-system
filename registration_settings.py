from flask import Blueprint, session, redirect, url_for, request, render_template_string
from header import header_html
from footer import footer_html

registration_settings_bp = Blueprint('registration_settings', __name__)

@registration_settings_bp.route('/registration_settings', methods=['GET', 'POST'])
def registration_settings():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    # Toggle Patient Classification
    if request.method == 'POST':
        if 'toggle_classification' in request.form:
            session['patient_classification_enabled'] = not session.get('patient_classification_enabled', True)
        elif 'toggle_discount' in request.form:
            session['discount_enabled'] = not session.get('discount_enabled', True)
        return redirect(url_for('registration_settings.registration_settings'))

    classification_enabled = session.get('patient_classification_enabled', True)
    discount_enabled = session.get('discount_enabled', True)

    html = header_html + """
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card border-0 shadow-lg rounded-4 overflow-hidden">
                    <div class="card-header bg-info text-white py-3 border-0">
                        <h4 class="mb-0 fw-bold"><i class="fas fa-address-card me-2"></i> إعدادات التسجيل (Registration
                            Settings)</h4>
                    </div>
                    <div class="card-body p-4 bg-white">
                        <h5 class="fw-bold mb-4 text-primary border-bottom pb-2">التحكم في حقول التسجيل</h5>

                        <!-- Patient Classification Toggle -->
                        <div class="d-flex justify-content-between align-items-center p-3 rounded-4 bg-light mb-3">
                            <div>
                                <h6 class="fw-bold mb-1"><i class="fas fa-layer-group me-2 text-primary"></i> تصنيف المريض
                                    (Patient Classification)</h6>
                                <p class="small text-muted mb-0">إظهار حقل تصنيف المريض (VIP، موظف، عادي) للحصول على خصومات
                                    تلقائية.</p>
                            </div>
                            <form method="POST">
                                <input type="hidden" name="toggle_classification" value="1">
                                <button type="submit"
                                    class="btn btn-{{ 'success' if classification_enabled else 'secondary' }} rounded-pill px-4 shadow-sm fw-bold">
                                    {{ 'مفعـل (Enabled)' if classification_enabled else 'معطـل (Disabled)' }}
                                </button>
                            </form>
                        </div>

                        <!-- Discount System Toggle -->
                        <div class="d-flex justify-content-between align-items-center p-3 rounded-4 bg-light mb-3">
                            <div>
                                <h6 class="fw-bold mb-1"><i class="fas fa-percent me-2 text-success"></i> نظام التخفيض (Discount System)</h6>
                                <p class="small text-muted mb-0">تفعيل أو تعطيل إمكانية إجراء خصومات مالية في الصندوق للحالات المشمولة.</p>
                            </div>
                            <form method="POST">
                                <input type="hidden" name="toggle_discount" value="1">
                                <button type="submit"
                                    class="btn btn-{{ 'success' if discount_enabled else 'secondary' }} rounded-pill px-4 shadow-sm fw-bold">
                                    {{ 'مفعـل (Enabled)' if discount_enabled else 'معطـل (Disabled)' }}
                                </button>
                            </form>
                        </div>

                        <div class="mt-4 text-center">
                            <a href="{{ url_for('settings.view_settings') }}" class="btn btn-outline-primary rounded-pill px-5 fw-bold"><i
                                    class="fas fa-arrow-right me-2"></i> العودة للإعدادات</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, classification_enabled=classification_enabled, discount_enabled=discount_enabled)
