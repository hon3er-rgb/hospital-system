from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

price_control_bp = Blueprint('price_control', __name__)

@price_control_bp.route('/price_control', methods=['GET', 'POST'])
def price_control():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST' and 'update_prices' in request.form:
        for key, value in request.form.items():
            if key.startswith('settings['):
                # Extra settings[key]
                clean_key = key[9:-1] # Remove 'settings[' and ']'
                cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = %s", (value, clean_key))
                
        conn.commit()
        flash("تم تحديث الأسعار وإعدادات العملة بنجاح", "success")
        conn.close()
        return redirect(url_for('price_control.price_control'))

    cursor.execute("SELECT * FROM system_settings")
    settings_res = cursor.fetchall()
    sys_settings = {row['setting_key']: row['setting_value'] for row in settings_res}
    
    conn.close()

    html = header_html + """
    <div class="container py-5" style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); min-height: 100vh;">
        <div class="row justify-content-center">
            <div class="col-xl-7">
                <!-- Main Card -->
                <div class="card border-0 rounded-5 shadow-lg overflow-hidden" 
                     style="background: rgba(255,255,255,0.8); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.4) !important;">
                    
                    <div class="card-header bg-white py-4 px-5 border-bottom border-light d-flex justify-content-between align-items-center">
                        <div>
                            <h2 class="fw-black mb-1 text-primary" style="letter-spacing: -1px;">إدارة الكشفية والخصومات</h2>
                            <p class="text-muted mb-0 small fw-bold"><i class="fas fa-tags me-1 text-success"></i> التحكم المباشر بأسعار العيادة ونسب التخفيض</p>
                        </div>
                        <a href="{{ url_for('settings.view_settings') }}" class="btn btn-light rounded-pill px-4 fw-bold shadow-sm border">رجوع</a>
                    </div>

                    <div class="card-body p-5">
                        <form method="POST">
                            <input type="hidden" name="update_prices" value="1">
                            
                            <div class="row g-4">
                                <!-- MAIN CLINIC PRICE -->
                                <div class="col-12 mb-2">
                                    <div class="p-4 rounded-5 border bg-white shadow-soft text-center" style="border: 2px solid #007aff !important;">
                                        <label class="d-block mb-3 small fw-bold text-muted">سعر كشفية العيادة (Examination Fee)</label>
                                        <div class="d-flex align-items-center justify-content-center gap-2">
                                            <input type="number" name="settings[price_consultation]" class="form-control border-0 bg-light rounded-4 text-center fw-black fs-2 py-3" 
                                                   value="{{ sys_settings.price_consultation or 25000 }}" style="max-width: 250px;">
                                            <span class="fs-4 fw-bold text-primary">د.ع</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- CATEGORY DISCOUNTS -->
                                <div class="col-12">
                                    <h6 class="fw-bold text-muted mb-3"><i class="fas fa-percent me-2 text-warning"></i> نسب التخفيض المئوية (%)</h6>
                                    <div class="bg-light p-4 rounded-5 border">
                                        <div class="row g-3 text-center">
                                            <div class="col-md-6">
                                                <div class="bg-white p-3 rounded-4 border-light shadow-sm">
                                                    <label class="small fw-bold mb-2 d-block">تسعير (عادي)</label>
                                                    <div class="input-group">
                                                        <input type="number" name="settings[discount_normal]" class="form-control rounded-4-start py-3 text-center fw-bold" value="{{ sys_settings.discount_normal or 0 }}">
                                                        <span class="input-group-text bg-white border-0 py-3">%</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="bg-white p-3 rounded-4 border-light shadow-sm">
                                                    <label class="small fw-bold mb-2 d-block text-info">خصم (كبار السن)</label>
                                                    <div class="input-group">
                                                        <input type="number" name="settings[discount_senior]" class="form-control rounded-4-start py-3 text-center fw-bold text-info" value="{{ sys_settings.discount_senior or 20 }}">
                                                        <span class="input-group-text bg-white border-0 py-3">%</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="bg-white p-3 rounded-4 border-light shadow-sm">
                                                    <label class="small fw-bold mb-2 d-block text-danger">خصم (عائلات الشهداء)</label>
                                                    <div class="input-group">
                                                        <input type="number" name="settings[discount_martyr]" class="form-control rounded-4-start py-3 text-center fw-bold text-danger" value="{{ sys_settings.discount_martyr or 25 }}">
                                                        <span class="input-group-text bg-white border-0 py-3">%</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="bg-white p-3 rounded-4 border-light shadow-sm">
                                                    <label class="small fw-bold mb-2 d-block text-purple">خصم (احتياجات خاصة)</label>
                                                    <div class="input-group">
                                                        <input type="number" name="settings[discount_special]" class="form-control rounded-4-start py-3 text-center fw-bold text-purple" value="{{ sys_settings.discount_special or 30 }}">
                                                        <span class="input-group-text bg-white border-0 py-3">%</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="mt-5 text-center">
                                <button type="submit" class="btn btn-primary btn-lg rounded-pill px-5 py-3 fw-bold shadow-lg border-0 bg-gradient" 
                                        style="background: linear-gradient(45deg, #007aff, #00c6ff) !important;">
                                    <i class="fas fa-check-circle me-2"></i> حفظ الإعدادات المالية الحالية
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <style>
        .fw-black { font-weight: 900; }
        .shadow-soft { box-shadow: 0 10px 20px rgba(0,0,0,0.02) !important; }
        .rounded-4-start { border-radius: 12px 0 0 12px !important; }
        [dir="rtl"] .rounded-4-start { border-radius: 0 12px 12px 0 !important; }
        .text-purple { color: #8e44ad !important; }
    </style>
    """ + footer_html
    
    return render_template_string(html, sys_settings=sys_settings)
