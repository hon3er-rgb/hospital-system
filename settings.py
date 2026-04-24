from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
from datetime import datetime
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def view_settings():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    perms = session.get('permissions', [])
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except:
            perms = []
            
    if session.get('role') != 'admin' and 'settings' not in perms:
        return redirect(url_for('dashboard.dashboard'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # 3. Dynamic Daily Report Stats (High Accuracy SQL)
    today_str = local_today_str()
    
    # Today's Patients (Unique check-ins)
    cursor.execute("SELECT COUNT(DISTINCT patient_id) as c FROM appointments WHERE appointment_date LIKE ? AND status != 'cancelled'", (today_str + '%',))
    today_p_count = cursor.fetchone()['c'] or 0
    
    # Today's Revenue
    cursor.execute("SELECT SUM(amount) as s FROM invoices WHERE created_at LIKE ? AND status = 'paid'", (today_str + '%',))
    today_rev = cursor.fetchone()['s'] or 0
    
    # Today's Labs
    cursor.execute("SELECT COUNT(*) as c FROM lab_requests WHERE created_at LIKE ?", (today_str + '%',))
    today_lab_count = cursor.fetchone()['c'] or 0
    
    # Today's Radiology
    cursor.execute("SELECT COUNT(*) as c FROM radiology_requests WHERE created_at LIKE ?", (today_str + '%',))
    today_rad_count = cursor.fetchone()['c'] or 0
    
    # New Registrations Today
    cursor.execute("SELECT COUNT(*) as c FROM patients WHERE created_at LIKE ?", (today_str + '%',))
    new_reg_count = cursor.fetchone()['c'] or 0

    # Free Follow-ups Today
    cursor.execute("SELECT COUNT(*) as c FROM appointments WHERE is_free = 1 AND appointment_date LIKE ? AND status != 'cancelled'", (today_str + '%',))
    free_follow_ups = cursor.fetchone()['c'] or 0
    
    conn.close()
    
    html = header_html + """
    <style>
        .daily-card {
            background: #ffffff;
            border-radius: 20px;
            padding: 18px 12px;
            border: 1px solid rgba(226, 232, 240, 0.7);
            box-shadow: 0 4px 15px rgba(0,0,0,0.02);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .daily-card:hover { 
            transform: translateY(-5px); 
            box-shadow: 0 12px 25px rgba(0,0,0,0.06);
            border-color: rgba(59, 130, 246, 0.15);
        }
        .daily-card::after {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            opacity: 0.5;
        }
        
        .card-orange::after { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .card-blue::after { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        .card-teal::after { background: linear-gradient(90deg, #14b8a6, #2dd4bf); }
        .card-green::after { background: linear-gradient(90deg, #10b981, #34d399); }
        .card-cyan::after { background: linear-gradient(90deg, #06b6d4, #22d3ee); }
        .card-purple::after { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }

        .daily-icon {
            width: 44px; height: 44px;
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 18px; margin-bottom: 12px;
            transition: all 0.3s ease;
        }
        .daily-card:hover .daily-icon { transform: scale(1.1); }

        .stat-val { 
            font-size: 22px; 
            font-weight: 800; 
            color: #1e293b; 
            margin-bottom: 2px;
            font-family: 'Inter', sans-serif;
        }
        .stat-lbl { 
            font-size: 11px; 
            font-weight: 700; 
            color: #64748b; 
            letter-spacing: 0.1px; 
        }
        
        .bg-orange-light { background: #fff7ed; color: #ea580c; }
        .bg-blue-light { background: #eff6ff; color: #2563eb; }
        .bg-teal-light { background: #f0fdfa; color: #0d9488; }
        .bg-green-light { background: #f0fdf4; color: #16a34a; }
        .bg-cyan-light { background: #ecfeff; color: #0891b2; }
        .bg-purple-light { background: #f5f3ff; color: #7c3aed; }
    </style>

    <div class="row pt-2 mb-3 text-center">
        <div class="col-12">
            <h5 class="fw-bold mb-0" style="color: #1a237e; font-family: 'Cairo', sans-serif;"><i class="fas fa-chart-line me-2"></i>التقرير اليومي المباشر</h5>
        </div>
    </div>

    <!-- Daily Report Cards Grid -->
    <div class="row row-cols-2 row-cols-md-3 row-cols-lg-6 g-3 mb-5">
        <!-- New Patients -->
        <div class="col">
            <div class="daily-card card-orange">
                <div class="daily-icon bg-orange-light"><i class="fas fa-user-plus"></i></div>
                <div class="stat-val">{{ "{:,}".format(new_reg_count) }}</div>
                <div class="stat-lbl">مسجلين جدد</div>
            </div>
        </div>
        <!-- Today's Patients -->
        <div class="col">
            <div class="daily-card card-blue">
                <div class="daily-icon bg-blue-light"><i class="fas fa-hospital-user"></i></div>
                <div class="stat-val">{{ "{:,}".format(today_p_count) }}</div>
                <div class="stat-lbl">مرضى اليوم</div>
            </div>
        </div>
        <!-- Free Follow-ups -->
        <div class="col">
            <div class="daily-card card-teal">
                <div class="daily-icon bg-teal-light"><i class="fas fa-hand-holding-medical"></i></div>
                <div class="stat-val">{{ "{:,}".format(free_follow_ups) }}</div>
                <div class="stat-lbl">مراجعات مجانية</div>
            </div>
        </div>
        <!-- Revenue -->
        <div class="col">
            <div class="daily-card card-green">
                <div class="daily-icon bg-green-light"><i class="fas fa-wallet"></i></div>
                <div class="stat-val">{{ "{:,.0f}".format(today_rev|float) }}</div>
                <div class="stat-lbl">صافي الدخل</div>
            </div>
        </div>
        <!-- Labs -->
        <div class="col">
            <div class="daily-card card-cyan">
                <div class="daily-icon bg-cyan-light"><i class="fas fa-vials"></i></div>
                <div class="stat-val">{{ "{:,}".format(today_lab_count) }}</div>
                <div class="stat-lbl">تحاليل</div>
            </div>
        </div>
        <!-- Radiology -->
        <div class="col">
            <div class="daily-card card-purple">
                <div class="daily-icon bg-purple-light"><i class="fas fa-x-ray"></i></div>
                <div class="stat-val">{{ "{:,}".format(today_rad_count) }}</div>
                <div class="stat-lbl">أشعة</div>
            </div>
        </div>
    </div>

    <!-- Main Settings Tiles Grid -->
    <div class="row row-cols-2 row-cols-md-3 row-cols-lg-4 g-3 justify-content-center mb-5">

        <!-- 1. System Management Group -->
        <div class="col">
            <a href="javascript:void(0)" onclick="new bootstrap.Modal(document.getElementById('systemMgmtModal')).show()" class="neo-tile tile-blue">
                <i class="fas fa-shield-alt text-primary" style="color: #3b82f6 !important;"></i>
                <span style="font-weight: 800;">إدارة النظام</span>
            </a>
        </div>

        <!-- 8. Admin Reports Dashboard -->
        <div class="col">
            <a href="{{ url_for('admin_reports.admin_reports') }}" class="neo-tile tile-indigo">
                <i class="fas fa-chart-pie" style="color: #6366f1 !important;"></i>
                <span style="font-weight: 800;">تقارير المدير</span>
            </a>
        </div>

        <!-- 9. Developer Settings Consolidated -->
        <div class="col">
            <a href="javascript:void(0)" onclick="new bootstrap.Modal(document.getElementById('devModal')).show()" class="neo-tile tile-dark">
                <i class="fas fa-code text-secondary" style="color: #64748b !important;"></i>
                <span style="font-weight: 800;">إعدادات المطور</span>
            </a>
        </div>

    </div>

    <!-- System Management Modal -->
    <div class="modal fade" id="systemMgmtModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content border-0 shadow-lg rounded-5 overflow-hidden">
                <div class="modal-header border-0 bg-primary text-white p-4">
                    <h5 class="modal-title fw-bold"><i class="fas fa-shield-alt me-2"></i>لوحة إدارة النظام</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4 bg-light">
                    <div class="row row-cols-2 row-cols-md-3 g-3">
                        <!-- Price Control -->
                        <div class="col">
                            <a href="price_control" class="neo-tile tile-indigo shadow-sm h-100 py-4">
                                <i class="fas fa-tags text-primary mb-2"></i>
                                <span class="small fw-bold">ادارة الأسعار</span>
                            </a>
                        </div>
                        <!-- Staff Management -->
                        <div class="col">
                            <a href="{{ url_for('manage_staff.manage_staff') }}" class="neo-tile tile-blue shadow-sm h-100 py-4">
                                <i class="fas fa-user-tie text-info mb-2"></i>
                                <span class="small fw-bold">إدارة الموظفين</span>
                            </a>
                        </div>
                        <!-- Department Management -->
                        <div class="col">
                            <a href="{{ url_for('manage_departments.manage_departments') }}" class="neo-tile tile-teal shadow-sm h-100 py-4">
                                <i class="fas fa-building text-success mb-2"></i>
                                <span class="small fw-bold">إدارة الأقسام</span>
                            </a>
                        </div>
                        <!-- Data Protection -->
                        <div class="col">
                            <a href="{{ url_for('backup_logs.manage_backups') }}" class="neo-tile tile-blue shadow-sm h-100 py-4" style="border: 1px solid #0d6efd;">
                                <i class="fas fa-shield-alt text-primary mb-2"></i>
                                <span class="small fw-bold">حماية البيانات</span>
                            </a>
                        </div>
                        <!-- Activity Logs -->
                        <div class="col">
                            <a href="{{ url_for('backup_logs.view_logs') }}" class="neo-tile tile-dark shadow-sm h-100 py-4" style="border: 1px solid #6c757d;">
                                <i class="fas fa-history text-secondary mb-2"></i>
                                <span class="small fw-bold">سجل النشاط</span>
                            </a>
                        </div>
                        <!-- Radiology & Lab Management -->
                        <div class="col">
                            <a href="lab_maintenance" class="neo-tile tile-indigo shadow-sm h-100 py-4">
                                <i class="fas fa-microscope text-primary mb-2"></i>
                                <span class="small fw-bold">إدارة الأشعة والمختبر</span>
                            </a>
                        </div>
                    </div>
                </div>
                <div class="modal-footer border-0 p-3 bg-white text-center d-block">
                    <p class="text-muted small mb-0"><i class="fas fa-lock me-1"></i>صلاحيات الوصول مخصصة فقط لمدير النظام.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Developer Settings Modal -->
    <div class="modal fade" id="devModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content border-0 shadow-lg rounded-5 overflow-hidden">
                <div class="modal-header border-0 bg-dark text-white p-4">
                    <h5 class="modal-title fw-bold"><i class="fas fa-laptop-code me-2"></i>إحصائيات وصلاحيات المطور</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4 bg-light">
                    <div class="row row-cols-2 row-cols-md-3 g-3">
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.change_name') }}" class="neo-tile tile-red shadow-sm h-100 py-4">
                                <i class="fas fa-signature text-danger mb-2"></i>
                                <span class="small fw-bold">تغيير اسم النظام</span>
                            </a>
                        </div>
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.update_system') }}" class="neo-tile tile-orange shadow-sm h-100 py-4">
                                <i class="fas fa-sync-alt text-warning mb-2"></i>
                                <span class="small fw-bold">تحديث النظام</span>
                            </a>
                        </div>
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.system_access') }}" class="neo-tile tile-dark shadow-sm h-100 py-4">
                                <i class="fas fa-user-shield text-secondary mb-2"></i>
                                <span class="small fw-bold">الدخول للنظام</span>
                            </a>
                        </div>
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.activate_system') }}" class="neo-tile tile-green shadow-sm h-100 py-4">
                                <i class="fas fa-key text-success mb-2"></i>
                                <span class="small fw-bold">تفعيل النظام</span>
                            </a>
                        </div>
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.ai_settings') }}" class="neo-tile tile-blue shadow-sm h-100 py-4">
                                <i class="fas fa-brain text-primary mb-2"></i>
                                <span class="small fw-bold">إعدادات الذكاء</span>
                            </a>
                        </div>
                        <div class="col">
                            <a href="{{ url_for('programmer_settings.reset_data') }}" class="neo-tile tile-red shadow-sm h-100 py-4">
                                <i class="fas fa-eraser text-danger mb-2"></i>
                                <span class="small fw-bold">تفريغ البيانات</span>
                            </a>
                        </div>
                    </div>
                </div>
                <div class="modal-footer border-0 p-3 bg-white text-center d-block">
                    <p class="text-muted small mb-0"><i class="fas fa-info-circle me-1"></i>هذه الإعدادات مخصصة فقط للمهندسين والمطورين.</p>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, today_p_count=today_p_count, today_rev=today_rev, today_lab_count=today_lab_count, today_rad_count=today_rad_count, new_reg_count=new_reg_count, free_follow_ups=free_follow_ups)
