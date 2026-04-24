from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string, jsonify
from config import get_db
from header import header_html
from footer import footer_html

lab_maintenance_bp = Blueprint('lab_maintenance', __name__)

# --- 1. Main List View ---
@lab_maintenance_bp.route('/lab_maintenance')
def lab_maintenance():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    active_tab = request.args.get('tab', 'lab')
    
    # Ensure Lab Specimen Columns Exist
    try:
        cursor.execute("SELECT tube_type FROM lab_tests LIMIT 1")
    except Exception:
        # Columns missing, add them
        cols = [
            "ALTER TABLE lab_tests ADD COLUMN tube_type VARCHAR(100)",
            "ALTER TABLE lab_tests ADD COLUMN sample_type VARCHAR(100)",
            "ALTER TABLE lab_tests ADD COLUMN volume_ml REAL",
            "ALTER TABLE lab_tests ADD COLUMN instructions TEXT"
        ]
        for col in cols:
            try: cursor.execute(col)
            except: pass
        
        # Ensure Radiology Category Column
        try:
            cursor.execute("SELECT category FROM radiology_tests LIMIT 1")
        except:
            cursor.execute("ALTER TABLE radiology_tests ADD COLUMN category VARCHAR(100)")
            
        conn.commit()

    if active_tab == 'lab':
        cursor.execute("SELECT * FROM lab_tests WHERE is_active = 1 ORDER BY test_name ASC")
        tests = cursor.fetchall()
        title = "تحليلات المختبر"
        icon = "fa-flask-vial"
        color = "primary"
    else:
        cursor.execute("SELECT * FROM radiology_tests WHERE is_active = 1 ORDER BY test_name ASC")
        tests = cursor.fetchall()
        title = "فحوصات الأشعة"
        icon = "fa-x-ray"
        color = "info"
        
    conn.close()

    html = header_html + """
    <div class="container-fluid py-4 px-lg-5">
        <!-- Header Section with Glass Effect -->
        <div class="glass-header p-4 rounded-5 mb-5 d-flex justify-content-between align-items-center flex-wrap gap-4 shadow-gentle">
            <div class="d-flex align-items-center gap-4">
                <div class="icon-orb icon-orb-{{ color }} shadow-orb">
                    <i class="fas {{ icon }} fa-2x"></i>
                </div>
                <div>
                    <h1 class="fw-black mb-1 display-6 text-gradient-{{ color }}">{{ title }}</h1>
                    <p class="text-muted-modern mb-0 font-arabic">إدارة وتحديث قائمة الخدمات الطبية والأسعار بكل سهولة</p>
                </div>
            </div>
            
            <div class="d-flex align-items-center gap-3">
                <div class="tab-switcher shadow-sm">
                    <a href="?tab=lab" class="tab-btn {{ 'active' if active_tab == 'lab' else '' }}">المختبر</a>
                    <a href="?tab=rad" class="tab-btn {{ 'active' if active_tab == 'rad' else '' }}">الأشعة</a>
                </div>
                <a href="{{ url_for('lab_maintenance.lab_form', target=active_tab) }}" class="btn-action shadow-soft">
                    <i class="fas fa-plus-circle"></i>
                    <span>إضافة خدمة</span>
                </a>
            </div>
        </div>

        <!-- Main Listing Area -->
        <div class="content-card shadow-lg">
            <div class="panel-header">
                <div class="d-flex align-items-center gap-2">
                    <span class="status-indicator-live"></span>
                    <h5 class="fw-bold mb-0 text-dark">سجل الفحوصات المسجلة</h5>
                </div>
                <div class="search-container">
                    <input type="text" id="liveSearch" class="search-input" placeholder="ابحث عن أي فحص أو كود أو سعر...">
                    <i class="fas fa-search search-icon"></i>
                </div>
            </div>
            
            <div class="table-container">
                <table class="table-premium" id="data-table">
                    <thead>
                        <tr>
                            <th class="ps-5">تفاصيل الفحص</th>
                            <th class="text-center" style="white-space: nowrap;">المقياس / التصنيف</th>
                            <th class="text-center">التكلفة</th>
                            <th class="pe-5 text-center">العمليات</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for t in tests %}
                        <tr class="premium-row">
                            <td class="ps-5">
                                <div class="test-identity">
                                    <div class="test-symbol symbol-{{ color }}">
                                        <i class="fas {{ 'fa-vial' if active_tab == 'lab' else 'fa-radiation' }}"></i>
                                    </div>
                                    <div class="test-details">
                                        <div class="test-name">{{ t.test_name }}</div>
                                        <div class="test-code">#{{ t.test_id or 0 }}</div>
                                    </div>
                                </div>
                            </td>
                            <td class="text-center" style="vertical-align: middle;">
                                {% if active_tab == 'lab' %}
                                    {% if t.is_profile %}
                                        <div class="badge-premium badge-purple">
                                            <i class="fas fa-folder-open me-2"></i> بروفايل كامل
                                        </div>
                                    {% else %}
                                        <div class="badge-premium badge-light">
                                            <i class="fas fa-flask-vial me-2"></i> {{ t.unit if (t.unit and t.unit.strip()) else 'عادي' }}
                                        </div>
                                    {% endif %}
                                {% else %}
                                    <div class="badge-premium badge-info">
                                        <i class="fas fa-dot-circle me-1"></i> فحص إشعاعي (Rad)
                                    </div>
                                {% endif %}
                            </td>
                            <td class="text-center">
                                <div class="price-val price-val-container px-3 py-2 rounded-3" style="display: inline-flex; align-items: baseline; gap: 6px; margin: 0 auto;">
                                    <span>{{ "{:,.0f}".format(t.price|int) }}</span>
                                    <span class="currency">د.ع</span>
                                </div>
                            </td>
                            <td class="pe-5 text-center" style="vertical-align: middle;">
                                <div class="actions-wrapper">
                                    {% if active_tab == 'lab' %}
                                        {% if t.is_profile %}
                                            <a href="{{ url_for('lab_maintenance.lab_profile', id=t.test_id) }}" class="btn-icon-struct" title="إدارة الهيكلية">
                                                <i class="fas fa-cogs"></i>
                                            </a>
                                        {% else %}
                                            <div class="btn-icon-struct" style="visibility: hidden; pointer-events: none;">
                                                <i class="fas fa-cogs"></i>
                                            </div>
                                        {% endif %}
                                    {% endif %}
                                    <a href="{{ url_for('lab_maintenance.lab_form', id=t.test_id, target=active_tab) }}" class="btn-icon-edit" title="تعديل">
                                        <i class="fas fa-pen"></i>
                                    </a>
                                    <a href="{{ url_for('lab_maintenance.lab_delete', id=t.test_id, target=active_tab) }}" class="btn-icon-del" onclick="return confirm('حذف هذا الفحص نهائياً؟')" title="حذف">
                                        <i class="fas fa-trash-alt"></i>
                                    </a>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" class="empty-state">
                                <div class="empty-anim">
                                    <i class="fas fa-box-open fa-4x mb-4"></i>
                                    <h4 class="fw-bold">القائمة فارغة تماماً</h4>
                                    <p class="text-muted">لم يتم إضافة أي بيانات لهذا القسم بعد. ابدأ بإضافة فحص جديد من الزر العلوي.</p>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <style>
        :root {
            --primary-g: linear-gradient(135deg, #007aff, #0051a8);
            --info-g: linear-gradient(135deg, #58ccff, #0099cc);
            --purple-g: linear-gradient(135deg, #8e44ad, #6c3483);
        }

        .glass-header {
            background: var(--card);
            border: 1px solid var(--border);
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        }
        

        .fw-black { font-weight: 900; }
        .text-muted-modern { color: #6e6e73; font-size: 1.1rem; }
        
        .icon-orb {
            width: 70px; height: 70px;
            border-radius: 20px;
            display: flex; align-items: center; justify-content: center;
            color: #fff;
            transition: 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            background: var(--primary);
            box-shadow: 0 15px 35px rgba(var(--primary-rgb), 0.2);
        }
        .icon-orb-primary { background: var(--primary); }
        .icon-orb-info { background: #58ccff; }
        

        .tab-switcher {
            background: var(--section-bg);
            padding: 5px;
            border-radius: 50px;
            display: flex; gap: 5px;
            border: 1px solid var(--border);
        }
        .tab-btn {
            padding: 10px 30px;
            border-radius: 50px;
            text-decoration: none;
            color: var(--text);
            font-weight: 600;
            transition: 0.3s;
            opacity: 0.6;
        }
        .tab-btn.active {
            background: var(--card);
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            color: var(--primary);
            opacity: 1;
        }

        .btn-action {
            background: var(--primary);
            color: #fff;
            padding: 12px 25px;
            border-radius: 50px;
            text-decoration: none;
            display: flex; align-items: center; gap: 10px;
            font-weight: 600;
            transition: 0.3s;
            box-shadow: 0 5px 15px rgba(var(--primary-rgb), 0.2);
        }
        .btn-action:hover { transform: translateY(-2px); color: #fff; filter: brightness(1.1); }

        .content-card {
            background: var(--card);
            border-radius: 35px;
            overflow: hidden;
            border: 1px solid var(--border);
        }

        .panel-header {
            padding: 30px 40px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border);
            background: var(--section-bg);
        }

        .search-container { position: relative; width: 350px; }
        .search-input {
            width: 100%;
            padding: 12px 45px 12px 20px;
            border-radius: 15px;
            border: 1px solid var(--border);
            background: var(--card);
            color: var(--text);
            outline: none;
            transition: 0.3s;
        }
        .search-input:focus { border-color: var(--primary); box-shadow: 0 0 0 4px rgba(var(--primary-rgb),0.1); }
        .search-icon { position: absolute; left: 18px; top: 15px; color: var(--primary); opacity: 0.7; }

        .table-premium { width: 100%; border-collapse: collapse; }
        .table-premium th { padding: 20px; font-weight: 700; color: #86868b; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 0.5px; }
        
        .premium-row { border-bottom: 1px solid var(--border); transition: 0.3s; cursor: pointer; }
        .premium-row:hover { background: rgba(var(--primary-rgb), 0.05) !important; }
        

        .test-identity { display: flex; align-items: center; gap: 15px; }
        .test-symbol {
            width: 45px; height: 45px;
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
            background: rgba(var(--primary-rgb), 0.1);
            color: var(--primary);
        }

        .test-name { font-weight: 800; color: #1d1d1f; font-size: 0.95rem; }
        
        .test-code { font-size: 0.85rem; color: var(--text); opacity: 0.5; margin-top: 2px; }

        .badge-premium {
            display: inline-flex; align-items: center;
            justify-content: center;
            padding: 6px 15px;
            border-radius: 50px;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid transparent;
            min-width: 140px; /* Fixed width for uniformity */
            transition: 0.3s;
        }
        .badge-purple { 
            background: rgba(142, 68, 173, 0.1); 
            color: #8e44ad; 
            border-color: rgba(142, 68, 173, 0.1);
        }
        .badge-light { 
            background: var(--section-bg); 
            color: var(--text); 
            border-color: var(--border); 
        }
        
        .badge-info { background: rgba(0, 153, 204, 0.1); color: #0099cc; }

        .price-val { font-size: 14px; font-weight: 900; letter-spacing: -0.5px; }
        .currency { font-size: 10px; font-weight: 700; opacity: 0.8; }
        
        /* Unified Price Colors */
        [data-theme="light"] .price-val { color: #28a745; }
        [data-theme="light"] .currency { color: #28a745; }
        [data-theme="light"] .price-val-container {
            background: rgba(40, 167, 69, 0.05);
            border: 1px solid rgba(40, 167, 69, 0.1);
        }
        
        
        
        

        .actions-wrapper { 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            gap: 6px; 
            width: 100px; /* Adjusted fixed width for smallest buttons to keep them centered */
            margin: 0 auto;
        }
        
        .btn-icon-struct, .btn-icon-edit, .btn-icon-del {
            width: 28px; height: 28px;
            border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            text-decoration: none;
            font-size: 12px;
            transition: all 0.3s ease;
        }

        .btn-icon-struct { background: rgba(142, 68, 173, 0.1); border: 1px solid rgba(142,68,173,0.1); color: #8e44ad; }
        .btn-icon-struct:hover { background: #8e44ad; color: #fff; transform: translateY(-2px); }
        .btn-icon-edit { background: rgba(var(--primary-rgb), 0.1); border: 1px solid rgba(var(--primary-rgb), 0.1); color: var(--primary); }
        .btn-icon-edit:hover { background: var(--primary); color: #fff; transform: translateY(-2px); }
        
        .btn-icon-del { background: rgba(255, 59, 48, 0.1); border: 1px solid rgba(255,59,48,0.1); color: #ff3b30; }
        .btn-icon-del:hover { background: #ff3b30; color: #fff; transform: translateY(-2px); }

        .empty-state { text-align: center; padding: 100px 0; color: #86868b; }
        
        .status-indicator-live {
            width: 10px; height: 10px;
            background: #34c759;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 rgba(52, 199, 89, 0.4);
            animation: pulse-live 2s infinite;
        }
        
        @keyframes pulse-live {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 199, 89, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(52, 199, 89, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(52, 199, 89, 0); }
        }

        .font-arabic { font-family: 'Inter', 'Noto Sans Arabic', sans-serif; }
    </style>

    <script>
        document.getElementById('liveSearch').addEventListener('input', function() {
            let q = this.value.toLowerCase();
            document.querySelectorAll('.premium-row').forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        });
    </script>
    """ + footer_html
    return render_template_string(html, tests=tests, active_tab=active_tab, title=title, icon=icon, color=color)

# --- 2. Add/Edit Form Page ---
@lab_maintenance_bp.route('/lab_maintenance/form', methods=['GET', 'POST'])
def lab_form():
    if not session.get('user_id'): return redirect(url_for('login.login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    tid = request.args.get('id')
    target = request.args.get('target', 'lab')
    test_data = None
    
    if tid:
        table = "lab_tests" if target == 'lab' else "radiology_tests"
        cursor.execute(f"SELECT * FROM {table} WHERE test_id = %s", (tid,))
        test_data = cursor.fetchone()

    if request.method == 'POST':
        name = request.form.get('test_name')
        price = float(request.form.get('test_price', 0))
        is_prof = 1 if request.form.get('is_profile') == 'on' else 0
        unit = request.form.get('unit', '')
        min_v = request.form.get('min_value') if request.form.get('min_value') else None
        max_v = request.form.get('max_value') if request.form.get('max_value') else None
        
        # Specimen Collection info
        tube = request.form.get('tube_type', '')
        sample = request.form.get('sample_type', '')
        vol = request.form.get('volume_ml', 0)
        instr = request.form.get('instructions', '')

        if tid: # Update
            if target == 'lab':
                cursor.execute("""
                    UPDATE lab_tests SET 
                        test_name=%s, price=%s, unit=%s, min_value=%s, max_value=%s, 
                        is_profile=%s, tube_type=%s, sample_type=%s, volume_ml=%s, instructions=%s 
                    WHERE test_id=%s
                """, (name, price, unit, min_v, max_v, is_prof, tube, sample, vol, instr, tid))
            else:
                category = request.form.get('category', '')
                cursor.execute("UPDATE radiology_tests SET test_name=%s, price=%s, category=%s WHERE test_id=%s", (name, price, category, tid))
            flash("تم تحديث الفحص بنجاح", "success")
        else: # Add
            if target == 'lab':
                cursor.execute("""
                    INSERT INTO lab_tests (test_name, price, unit, min_value, max_value, is_profile, is_active, tube_type, sample_type, volume_ml, instructions) 
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s)
                """, (name, price, unit, min_v, max_v, is_prof, tube, sample, vol, instr))
            else:
                category = request.form.get('category', '')
                cursor.execute("INSERT INTO radiology_tests (test_name, price, category, is_active) VALUES (%s, %s, %s, 1)", (name, price, category))
            flash("تمت إضافة الفحص الجديد لقائمة البيانات", "success")
        
        conn.commit()
        conn.close()
        return redirect(url_for('lab_maintenance.lab_maintenance', tab=target))

    conn.close()
    
    title = f"{'تعديل' if test_data else 'إضافة'} {'فحص مختبري' if target == 'lab' else 'فحص أشعة'}"
    
    html = header_html + """
    <div class="container-fluid py-4 px-lg-5">
        <div class="row justify-content-center">
            <div class="col-xl-9">
                <div class="border-0 rounded-4 overflow-hidden shadow-sm shadow-apple" style="background: var(--card); border: 1px solid var(--border) !important;">
                    <!-- Pro Title Bar -->
                    <div class="px-4 py-3 border-bottom d-flex justify-content-between align-items-center" style="background: var(--card); border-color: var(--border) !important;">
                        <div class="d-flex align-items-center gap-2">
                            <div class="rounded-3 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px; background: var(--primary); color: white;">
                                 <i class="fas {{ 'fa-pen-nib' if test_data else 'fa-plus' }}" style="font-size: 0.8rem;"></i>
                            </div>
                            <h6 class="fw-bold mb-0" style="letter-spacing: -0.3px; color: var(--text);">{{ title }}</h6>
                        </div>
                        <div class="d-flex align-items-center gap-3">
                            <a href="{{ url_for('lab_maintenance.lab_maintenance', tab=target) }}" class="btn btn-link text-decoration-none text-muted p-0 small">إلغاء</a>
                        </div>
                    </div>

                    <!-- Compact Body -->
                    <div class="card-body p-4">
                        <form method="POST">
                            <div class="row g-4">
                                <div class="col-md-6">
                                    <label class="label-premium">الاسم الكامل للخدمة</label>
                                    <input type="text" name="test_name" class="input-premium" value="{{ test_data.test_name if test_data else '' }}" placeholder="مثال: CBC" required>
                                </div>
                                <div class="col-md-3">
                                    <label class="label-premium">السعر (د.ع)</label>
                                    <input type="number" name="test_price" class="input-premium" value="{{ test_data.price if test_data else '15000' }}" required>
                                </div>
                                <div class="col-md-3">
                                    {% if target == 'lab' %}
                                    <label class="label-premium">نوع التحليل</label>
                                    <div class="form-check form-switch input-premium d-flex align-items-center justify-content-between px-3" style="background: var(--section-bg); border-color: var(--border);">
                                        <label class="form-check-label small fw-bold mb-0" for="isProf" style="color: var(--text); opacity: 0.7;">بروفايل؟</label>
                                        <input class="form-check-input ms-0" type="checkbox" name="is_profile" id="isProf" {% if test_data and test_data.is_profile %}checked{% endif %} style="cursor: pointer; float: none;">
                                    </div>
                                    {% else %}
                                    <label class="label-premium">تصنيف الأشعة</label>
                                    <select name="category" class="form-select input-premium" required>
                                        <option value="">-- اختر التصنيف --</option>
                                        <option value="X-Ray" {% if test_data and test_data.category == 'X-Ray' %}selected{% endif %}>X-Ray (أشعة سينية)</option>
                                        <option value="MRI" {% if test_data and test_data.category == 'MRI' %}selected{% endif %}>MRI (رنين مغناطيسي)</option>
                                        <option value="CT Scan" {% if test_data and test_data.category == 'CT Scan' %}selected{% endif %}>CT Scan (مفراس)</option>
                                        <option value="Ultrasound" {% if test_data and test_data.category == 'Ultrasound' %}selected{% endif %}>Ultrasound (سونار)</option>
                                        <option value="Mammogram" {% if test_data and test_data.category == 'Mammogram' %}selected{% endif %}>Mammogram (أشعة الثدي)</option>
                                        <option value="Doppler" {% if test_data and test_data.category == 'Doppler' %}selected{% endif %}>Doppler (دوبلر)</option>
                                        <option value="ECHO" {% if test_data and test_data.category == 'ECHO' %}selected{% endif %}>ECHO (ايكو القلب)</option>
                                        <option value="ECG" {% if test_data and test_data.category == 'ECG' %}selected{% endif %}>ECG (تخطيط قلب)</option>
                                        <option value="Others" {% if test_data and test_data.category == 'Others' %}selected{% endif %}>أخرى</option>
                                    </select>
                                    {% endif %}
                                </div>
                                
                                {% if target == 'lab' %}
                                <div id="labDetails" class="mt-2" style="display: {{ 'none' if test_data and test_data.is_profile else 'block' }};">
                                    <div class="row g-3">
                                        <div class="col-md-4">
                                            <label class="label-premium small">الوحدة (Unit)</label>
                                            <input type="text" name="unit" class="input-premium py-2" value="{{ test_data.unit or '' }}" placeholder="mg/dL">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="label-premium small">أدنى قيمة (Min)</label>
                                            <input type="number" step="any" name="min_value" class="input-premium py-2" value="{% if test_data and test_data.min_value is not none %}{{ test_data.min_value }}{% endif %}">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="label-premium small">أقصى قيمة (Max)</label>
                                            <input type="number" step="any" name="max_value" class="input-premium py-2" value="{% if test_data and test_data.max_value is not none %}{{ test_data.max_value }}{% endif %}">
                                        </div>
                                    </div>
                                </div>

                                 <!-- Specimen Strip -->
                                 <div class="col-12 mt-3">
                                     <div class="px-4 py-3 rounded-4" style="background: var(--section-bg); border: 1px solid var(--border);">
                                         <div class="d-flex align-items-center gap-2 mb-3">
                                             <i class="fas fa-syringe text-primary" style="font-size: 0.8rem;"></i>
                                             <span class="fw-bold small" style="color: var(--text);">متطلبات العينة (Specimen)</span>
                                         </div>
                                         <div class="row g-3">
                                             <div class="col-md-4">
                                                <select name="tube_type" class="form-select input-premium py-2" style="font-size: 0.8rem;">
                                                    <option value="">-- الأنبوب --</option>
                                                    <option value="Lavender (EDTA)" {% if test_data and test_data.tube_type == 'Lavender (EDTA)' %}selected{% endif %}>البنفسجي (EDTA)</option>
                                                    <option value="Gold (SST/Serum)" {% if test_data and test_data.tube_type == 'Gold (SST/Serum)' %}selected{% endif %}>الذهبي (SST)</option>
                                                    <option value="Light Blue (Citrate)" {% if test_data and test_data.tube_type == 'Light Blue (Citrate)' %}selected{% endif %}>الأزرق (سيترات)</option>
                                                    <option value="Grey (Fluoride)" {% if test_data and test_data.tube_type == 'Grey (Fluoride)' %}selected{% endif %}>الرمادي (سكر)</option>
                                                    <option value="Red (Plain)" {% if test_data and test_data.tube_type == 'Red (Plain)' %}selected{% endif %}>الأحمر (سادة)</option>
                                                    <option value="Green (Heparin)" {% if test_data and test_data.tube_type == 'Green (Heparin)' %}selected{% endif %}>الأخضر (هيبارين)</option>
                                                    <option value="Urine Cup" {% if test_data and test_data.tube_type == 'Urine Cup' %}selected{% endif %}>علبة إدرار</option>
                                                    <option value="Stool Container" {% if test_data and test_data.tube_type == 'Stool Container' %}selected{% endif %}>علبة خروج</option>
                                                    <option value="Other" {% if test_data and test_data.tube_type == 'Other' %}selected{% endif %}>أخرى</option>
                                                </select>
                                             </div>
                                             <div class="col-md-4">
                                                <input type="text" name="sample_type" class="input-premium py-2" value="{{ test_data.sample_type or '' }}" placeholder="نوع العينة (مثلاً: دم كامل)" style="font-size: 0.8rem;">
                                             </div>
                                             <div class="col-md-4">
                                                <input type="number" step="any" name="volume_ml" class="input-premium py-2" value="{% if test_data and test_data.volume_ml is not none %}{{ test_data.volume_ml }}{% else %}3{% endif %}" placeholder="الكمية (ml)" style="font-size: 0.8rem;">
                                             </div>
                                             <div class="col-12 mt-1">
                                                <input type="text" name="instructions" class="input-premium py-2" value="{% if test_data and test_data.instructions is not none %}{{ test_data.instructions }}{% endif %}" placeholder="تعليمات السحب الخاصة... (اختياري)" style="font-size: 0.8rem;">
                                             </div>
                                         </div>
                                     </div>
                                 </div>
                                 {% endif %}
                            </div>

                            <div class="mt-4 pt-3 border-top">
                                <button type="submit" class="btn btn-primary w-100 py-2 rounded-3 shadow-sm fw-bold">
                                    <i class="fas fa-check-circle me-1"></i> حفظ البيانات
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const isProf = document.getElementById('isProf');
        if(isProf) {
            isProf.addEventListener('change', function() {
                document.getElementById('labDetails').style.display = this.checked ? 'none' : 'block';
            });
        }
    </script>
    <style>
        .label-premium { font-weight: 700; color: var(--text); opacity: 0.6; font-size: 0.65rem; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        .input-premium { 
            width: 100%; padding: 8px 14px; 
            border-radius: 8px; border: 1px solid var(--border); 
            background: var(--card); outline: none; transition: 0.2s;
            font-weight: 600; font-size: 0.9rem; color: var(--text);
        }
        .input-premium:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.1); }
        .form-check-input:checked { background-color: var(--primary); border-color: var(--primary); }
        .font-arabic { font-family: 'Cairo', sans-serif; }
        .shadow-apple { box-shadow: 0 10px 30px rgba(0,0,0,0.05) !important; }
        
    </style>
    """ + footer_html
    return render_template_string(html, test_data=test_data, target=target, title=title)

# --- 3. Profile Management Page ---
@lab_maintenance_bp.route('/lab_maintenance/profile', methods=['GET', 'POST'])
def lab_profile():
    if not session.get('user_id'): return redirect(url_for('login.login'))
    
    tid = request.args.get('id')
    if not tid: return redirect(url_for('lab_maintenance.lab_maintenance'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch Parent Info
    cursor.execute("SELECT * FROM lab_tests WHERE test_id = %s", (tid,))
    test_parent = cursor.fetchone()
    
    if not test_parent:
        conn.close()
        return redirect(url_for('lab_maintenance.lab_maintenance'))

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO lab_test_parameters (test_id, param_name, min_value, max_value, unit) 
            VALUES (%s, %s, %s, %s, %s)
        """, (
            tid,
            request.form.get('p_name'),
            request.form.get('p_min') if request.form.get('p_min') else None,
            request.form.get('p_max') if request.form.get('p_max') else None,
            request.form.get('p_unit', '')
        ))
        conn.commit()
        flash("تمت إضافة المكون الجديد للبروفايل بنجاح", "success")

    # Fetch Children
    cursor.execute("SELECT * FROM lab_test_parameters WHERE test_id = %s ORDER BY sort_order ASC", (tid,))
    params = cursor.fetchall()
    conn.close()

    html = header_html + """
    <div class="container-fluid py-5 px-lg-5" style="background: #f8f8fb; min-height: 100vh;">
        <!-- Glowing Ambient Orbs -->
        <div style="position:fixed; top:-10%; right:-5%; width:400px; height:400px; background:radial-gradient(circle, rgba(142,68,173,0.1) 0%, rgba(255,255,255,0) 70%); z-index:0; pointer-events:none;"></div>
        <div style="position:fixed; bottom:-10%; left:-5%; width:500px; height:500px; background:radial-gradient(circle, rgba(0,122,255,0.05) 0%, rgba(255,255,255,0) 70%); z-index:0; pointer-events:none;"></div>

        <div class="position-relative" style="z-index: 2;">
            <!-- Header Section -->
            <div class="glass-header p-4 rounded-4 mb-4 d-flex justify-content-between align-items-center shadow-sm" style="background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(255,255,255,0.5);">
                <div class="d-flex align-items-center gap-4">
                    <div class="icon-orb-premium">
                        <i class="fas fa-layer-group fa-lg"></i>
                    </div>
                    <div>
                        <nav aria-label="breadcrumb">
                          <ol class="breadcrumb mb-1">
                            <li class="breadcrumb-item small"><a href="{{ url_for('dashboard.dashboard') }}" class="text-decoration-none text-muted">الرئيسية</a></li>
                            <li class="breadcrumb-item small"><a href="{{ url_for('lab_maintenance.lab_maintenance', tab='lab') }}" class="text-decoration-none text-muted">المختبر</a></li>
                            <li class="breadcrumb-item active small text-purple fw-bold" aria-current="page">هيكلية الفحص</li>
                          </ol>
                        </nav>
                        <h2 class="fw-black mb-0 text-dark">{{ test_parent.test_name }}</h2>
                        <p class="text-muted mb-0" style="font-size: 0.9rem;">إدارة التكوين الداخلي (Parameters) لهذا البروفايل</p>
                    </div>
                </div>
                <a href="{{ url_for('lab_maintenance.lab_maintenance', tab='lab') }}" class="btn-back-premium">
                    <i class="fas fa-arrow-right me-2"></i> عودة للمختبر
                </a>
            </div>

            <!-- Main Content Area -->
            <div class="row g-4 align-items-start">
                
                <!-- Left Panel: Add Component -->
                <div class="col-xl-4 col-lg-5">
                    <div class="premium-card sticky-top" style="top: 20px;">
                        <div class="card-header-premium">
                            <div class="d-flex align-items-center gap-2">
                                <div class="mini-icon-box bg-purple-soft"><i class="fas fa-plus text-purple"></i></div>
                                <h5 class="fw-bold mb-0">إضافة مكون (Parameter)</h5>
                            </div>
                        </div>
                        <div class="card-body-premium">
                            <form method="POST">
                                <div class="form-floating-custom mb-3">
                                    <label>اسم التحليل الفرعي (Parameter Name)</label>
                                    <input type="text" name="p_name" class="form-control-premium" placeholder="مثال: WBC, RBC, Glucose..." required>
                                </div>
                                
                                <div class="form-floating-custom mb-3">
                                    <label>وحدة القياس (Unit)</label>
                                    <input type="text" name="p_unit" class="form-control-premium" placeholder="مثال: mg/dL, %, g/L...">
                                </div>

                                <div class="row g-2 mb-4">
                                    <div class="col-6 form-floating-custom">
                                        <label class="text-success">الحد الأدنى للمعدل</label>
                                        <input type="number" step="any" name="p_min" class="form-control-premium text-center" placeholder="Min">
                                    </div>
                                    <div class="col-6 form-floating-custom">
                                        <label class="text-danger">الحد الأقصى للمعدل</label>
                                        <input type="number" step="any" name="p_max" class="form-control-premium text-center" placeholder="Max">
                                    </div>
                                </div>

                                <button type="submit" class="btn-submit-pro w-100">
                                    <i class="fas fa-check-circle me-2"></i> حفظ المكون
                                </button>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: List of Components -->
                <div class="col-xl-8 col-lg-7">
                    <div class="premium-card">
                        <div class="card-header-premium d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center gap-2">
                                <div class="mini-icon-box bg-blue-soft"><i class="fas fa-list text-primary"></i></div>
                                <h5 class="fw-bold mb-0">الهيكلية الحالية للملف</h5>
                            </div>
                            <span class="badge-count">{{ params|length }} مكون</span>
                        </div>
                        
                        <div class="card-body-premium p-0">
                            {% if params %}
                            <div class="table-responsive">
                                <table class="table table-borderless table-hover premium-table mb-0">
                                    <thead>
                                        <tr>
                                            <th class="ps-4">اسم المكون (Parameter)</th>
                                            <th class="text-center">الوحدة</th>
                                            <th class="text-center">النطاق المرجعي (Range)</th>
                                            <th class="pe-4 text-center">الإجراء</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for p in params %}
                                        <tr>
                                            <td class="ps-4">
                                                <div class="d-flex align-items-center gap-3 py-1">
                                                    <div class="param-bullet"></div>
                                                    <span class="fw-bold fs-6 text-dark">{{ p.param_name }}</span>
                                                </div>
                                            </td>
                                            <td class="text-center">
                                                {% if p.unit %}
                                                    <span class="badge-unit">{{ p.unit }}</span>
                                                {% else %}
                                                    <span class="text-black-50 small">-</span>
                                                {% endif %}
                                            </td>
                                            <td class="text-center">
                                                {% if p.min_value is not none or p.max_value is not none %}
                                                    <div class="range-box">
                                                        <span class="range-val min">{{ p.min_value if p.min_value is not none else '--' }}</span>
                                                        <span class="range-divider">~</span>
                                                        <span class="range-val max">{{ p.max_value if p.max_value is not none else '--' }}</span>
                                                    </div>
                                                {% else %}
                                                    <span class="text-black-50 small">غير محدد</span>
                                                {% endif %}
                                            </td>
                                            <td class="pe-4 text-center">
                                                <a href="{{ url_for('lab_maintenance.delete_param', pid=p.param_id, tid=test_parent.test_id) }}" class="btn-del-mini" onclick="return confirm('هل أنت متأكد من حذف هذا المكون؟')">
                                                    <i class="fas fa-times"></i>
                                                </a>
                                            </td>
                                        </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                            {% else %}
                            <div class="empty-state-card text-center py-5">
                                <div class="empty-icon-wrap mb-3 mx-auto">
                                    <i class="fas fa-vials text-muted"></i>
                                </div>
                                <h5 class="fw-bold text-dark">لا توجد مكونات فرعية</h5>
                                <p class="text-muted mb-0">لم تقم بإضافة أي تحاليل دقيقة لهذا البروفايل حتى الآن.<br>أضف المكون الأول من لوحة التحكم الجانبية.</p>
                            </div>
                            {% endif %}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <style>
        /* Modern Apple-like Premium UI */
        .text-purple { color: #8e44ad; }
        .bg-purple-soft { background: rgba(142,68,173,0.1); }
        .bg-blue-soft { background: rgba(0,122,255,0.1); }
        
        .icon-orb-premium {
            width: 56px; height: 56px; border-radius: 16px;
            background: linear-gradient(135deg, #8e44ad, #6c3483);
            color: white; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 10px 20px rgba(142,68,173,0.3);
        }

        .btn-back-premium {
            background: #fff; border: 1px solid #e5e5ea; color: #1c1c1e;
            padding: 10px 20px; border-radius: 12px; font-weight: 700;
            text-decoration: none; display: flex; align-items: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 5px rgba(0,0,0,0.02);
        }
        .btn-back-premium:hover { background: #1c1c1e; color: #fff; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }

        .premium-card {
            background: #fff; border-radius: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.03), 0 1px 3px rgba(0,0,0,0.02);
            border: 1px solid rgba(0,0,0,0.04); overflow: hidden;
            transition: 0.3s;
        }
        .premium-card:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.06); }
        
        .card-header-premium { padding: 20px 24px; border-bottom: 1px solid #f2f2f7; background: #fafafc; }
        .card-body-premium { padding: 24px; }
        
        .mini-icon-box {
            width: 32px; height: 32px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
        }
        
        .badge-count {
            background: #1c1c1e; color: #fff; padding: 6px 14px; border-radius: 20px;
            font-size: 0.85rem; font-weight: 700;
        }

        .form-floating-custom { position: relative; }
        .form-floating-custom label {
            font-size: 0.85rem; font-weight: 700; color: #86868b;
            margin-bottom: 6px; display: block;
        }
        .form-control-premium {
            width: 100%; padding: 14px 16px; border-radius: 12px;
            border: 1px solid #e5e5ea; background: #fbfbfd;
            font-size: 0.95rem; font-weight: 600; color: #1d1d1f;
            transition: all 0.3s ease;
        }
        .form-control-premium:focus {
            background: #fff; border-color: #8e44ad; outline: none;
            box-shadow: 0 0 0 4px rgba(142,68,173,0.1);
        }

        .btn-submit-pro {
            background: #1c1c1e; color: #fff; border: none;
            padding: 14px 20px; border-radius: 14px; font-weight: 700; font-size: 1rem;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .btn-submit-pro:hover {
            background: #8e44ad; box-shadow: 0 8px 20px rgba(142,68,173,0.3); transform: translateY(-2px);
        }

        /* Table Design */
        .premium-table th {
            text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.5px;
            color: #86868b; font-weight: 700; border-bottom: 1px solid #f2f2f7;
            padding-top: 16px; padding-bottom: 16px; background: #fff;
        }
        .premium-table td { padding: 16px 8px; vertical-align: middle; border-bottom: 1px solid #f9f9f9; }
        .premium-table tr:hover td { background: #fafafc; }
        .premium-table tr:last-child td { border-bottom: none; }

        .param-bullet { width: 8px; height: 8px; border-radius: 50%; background: #007aff; }

        .badge-unit {
            background: #f2f2f7; color: #1c1c1e; padding: 6px 12px;
            border-radius: 8px; font-size: 0.85rem; font-weight: 600;
        }

        .range-box {
            display: inline-flex; align-items: center; background: #fdfdfd;
            border: 1px solid #e5e5ea; border-radius: 8px; overflow: hidden;
            font-family: monospace; font-size: 0.9rem; font-weight: 700;
        }
        .range-val { padding: 6px 12px; }
        .range-val.min { color: #34c759; background: rgba(52,199,89,0.05); }
        .range-val.max { color: #ff3b30; background: rgba(255,59,48,0.05); }
        .range-divider { color: #c7c7cc; padding: 0 4px; }

        .btn-del-mini {
            width: 32px; height: 32px; border-radius: 8px;
            background: #fff0f0; color: #ff3b30; border: none;
            display: inline-flex; align-items: center; justify-content: center;
            text-decoration: none; transition: 0.3s;
        }
        .btn-del-mini:hover { background: #ff3b30; color: #fff; transform: scale(1.1); }

        .empty-icon-wrap {
            width: 80px; height: 80px; border-radius: 50%;
            background: #f2f2f7; display: flex; align-items: center; justify-content: center;
            font-size: 2rem;
        }
    </style>
    """ + footer_html
    return render_template_string(html, test_parent=test_parent, params=params)

# --- 4. Utilities ---
@lab_maintenance_bp.route('/lab_maintenance/delete_p')
def delete_param():
    pid = request.args.get('pid')
    tid = request.args.get('tid')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lab_test_parameters WHERE param_id = %s", (pid,))
    conn.commit()
    conn.close()
    flash("تم حذف المكون بنجاح", "info")
    return redirect(url_for('lab_maintenance.lab_profile', id=tid))

@lab_maintenance_bp.route('/lab_maintenance/delete_t')
def lab_delete():
    tid = request.args.get('id')
    target = request.args.get('target', 'lab')
    table = "lab_tests" if target == 'lab' else "radiology_tests"
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE {table} SET is_active = 0 WHERE test_id = %s", (tid,))
        conn.commit()
        flash("تم حذف الفحص بالكامل بنجاح", "success")
    except:
        flash("فشلت عملية الحذف لارتباط الفحص بطلبات سابقة في السجل الطبي", "danger")
    conn.close()
    return redirect(url_for('lab_maintenance.lab_maintenance', tab=target))
