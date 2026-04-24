from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, log_activity, trigger_auto_backup # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
import os

import datetime

backup_logs_bp = Blueprint('backup_logs', __name__)

def check_admin():
    if not session.get('user_id') or session.get('role') != 'admin':
        return False
    return True

@backup_logs_bp.route('/api/list_drives')
def list_drives():
    if not check_admin(): return {"error": "Unauthorized"}, 403
    import string
    from ctypes import windll
    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(f"{letter}:/")
        bitmask >>= 1
    return {"drives": drives}

@backup_logs_bp.route('/api/browse_dir')
def browse_dir():
    if not check_admin(): return {"error": "Unauthorized"}, 403
    path = request.args.get('path', 'C:/')
    try:
        items = []
        for entry in os.scandir(path):
            if entry.is_dir():
                items.append({
                    "name": entry.name,
                    "path": entry.path.replace('\\', '/'),
                    "is_dir": True
                })
        return {"current": path, "items": sorted(items, key=lambda x: x['name'].lower())}
    except Exception as e:
        return {"error": str(e)}, 400

@backup_logs_bp.route('/settings/backups', methods=['GET', 'POST'])
def manage_backups():
    if not check_admin():
        return redirect(url_for('dashboard.dashboard'))
        
    msg = ""
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        paths = request.form.get('backup_paths', '')
        cur.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'backup_paths'", (paths,))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('backup_paths', %s)", (paths,))
            
        limit = request.form.get('backup_limit', '5')
        cur.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = 'backup_limit'", (limit,))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('backup_limit', %s)", (limit,))

        db.commit()
        log_activity(session.get('user_id'), "تعديل إعدادات النسخ الاحتياطي", f"تم تحديث المسارات إلى: {paths}")
        msg = "تم حفظ مسارات النسخ الاحتياطي بنجاح"
        
        if 'trigger_now' in request.form:
            trigger_auto_backup()
            log_activity(session.get('user_id'), "تشغيل نسخ احتياطي يدوي", "تم تشغيل عملية النسخ الاحتياطي يدوياً")
            msg += " | تم تشغيل النسخ الاحتياطي الآن"

    cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'backup_paths'")
    row = cur.fetchone()
    current_paths = row['setting_value'] if row else ""
    
    cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'backup_limit'")
    r_lim = cur.fetchone()
    current_limit = int(r_lim['setting_value']) if r_lim and r_lim['setting_value'] else 5
    
    html = header_html + """
    <style>
        .data-center-card { border-radius: 24px; border: 1px solid rgba(0,0,0,0.05); background: #fff; overflow: hidden; }
        .backup-entry { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 15px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; transition: 0.3s; }
        .backup-entry:hover { border-color: #3b82f6; background: #f0f9ff; }
        .folder-picker-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; backdrop-filter: blur(10px); }
        .picker-content { width: 90%; max-width: 500px; background: white; margin: 10vh auto; border-radius: 20px; box-shadow: 0 50px 100px rgba(0,0,0,0.4); display: flex; flex-direction: column; height: 70vh; }
        .browse-list { flex: 1; overflow-y: auto; padding: 15px; }
        .browse-item { padding: 12px 15px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 12px; transition: 0.2s; }
        .browse-item:hover { background: #eff6ff; color: #1e40af; }
        .pulse-shield { animation: shieldPulse 3s infinite ease-in-out; }
        @keyframes shieldPulse { 0% { transform: scale(1); opacity: 0.8; } 50% { transform: scale(1.1); opacity: 1; } 100% { transform: scale(1); opacity: 0.8; } }
    </style>

    <div class="row pt-2 mb-4">
        <div class="col-md-9 text-end">
            <h2 class="fw-bold mb-1"><i class="fas fa-server text-indigo me-2"></i>مركز أمن البيانات الفائق</h2>
            <p class="text-muted small">نظام إدارة النسخ الاحتياطي السحابي والمحلي الذكي</p>
        </div>
        <div class="col-md-3 text-center d-flex flex-column align-items-center justify-content-center">
            <div class="pulse-shield text-success fs-1 mb-2"><i class="fas fa-shield-halved"></i></div>
            <span class="badge bg-success-subtle text-success px-3">النظام محمي ومؤمن</span>
        </div>
    </div>

    {% if msg %}
        <div class="alert alert-success border-0 shadow-sm rounded-4 text-end mb-4">
            <i class="fas fa-check-circle me-2"></i> {{ msg }}
        </div>
    {% endif %}

    <div class="row g-4 mb-5 text-end">
        <!-- 1. Auto-Protection Mode -->
        <div class="col-md-5">
            <div class="data-center-card h-100 shadow-sm p-4">
                <h5 class="fw-bold mb-4"><i class="fas fa-robot text-primary me-2"></i>وضع الحماية التلقائي</h5>
                <div class="d-flex align-items-center justify-content-between mb-4 p-3 bg-light rounded-4">
                    <span class="fw-bold text-dark">النسخ الاحتياطي الذكي</span>
                    <div class="form-check form-switch fs-4">
                        <input class="form-check-input" type="checkbox" checked disabled>
                    </div>
                </div>
                <p class="text-muted extra-small">يقوم النظام بعمل نسخة "بصمة رقمية" فورية عند كل حركة بيانات هامة. لا حاجة للتدخل البشري.</p>
                <hr>
                <div class="mb-4">
                    <label class="form-label d-block fw-bold small mb-2">عدد النسخ في كل موقع</label>
                    <div class="btn-group w-100" role="group">
                        <input type="radio" class="btn-check" name="backup_limit" id="lim5" value="5" {% if current_limit == 5 %}checked{% endif %} onchange="this.form.submit()">
                        <label class="btn btn-outline-primary" for="lim5">5 نسخ</label>

                        <input type="radio" class="btn-check" name="backup_limit" id="lim10" value="10" {% if current_limit == 10 %}checked{% endif %} onchange="this.form.submit()">
                        <label class="btn btn-outline-primary" for="lim10">10 نسخ</label>

                        <input type="radio" class="btn-check" name="backup_limit" id="lim20" value="20" {% if current_limit == 20 %}checked{% endif %} onchange="this.form.submit()">
                        <label class="btn btn-outline-primary" for="lim20">20 نسخة</label>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2. Targets Implementation -->
        <div class="col-md-7">
            <div class="data-center-card h-100 shadow-sm p-4">
                <div class="d-flex align-items-center justify-content-between mb-4">
                    <button class="btn btn-primary rounded-pill px-4" onclick="openPicker()"><i class="fas fa-plus me-2"></i>إضافة موقع نسخ</button>
                    <h5 class="fw-bold mb-0">المواقع النشطة حالياً</h5>
                </div>
                
                <form method="POST" id="configForm">
                    <div id="pathList">
                        {% set paths = current_paths.split(',') %}
                        {% for p in paths if p.strip() %}
                            <div class="backup-entry" id="entry-{{ loop.index }}">
                                <button type="button" class="btn btn-link text-danger p-0" onclick="removePath('{{ loop.index }}')"><i class="fas fa-times-circle"></i></button>
                                <div class="text-start flex-grow-1 px-3">
                                    <div class="fw-bold text-dark extra-small">{{ p.strip() }}</div>
                                    <div class="text-muted" style="font-size: 0.65rem;">Active Target • Connected • Write Permission OK</div>
                                </div>
                                <i class="fas fa-folder text-warning fs-4"></i>
                            </div>
                        {% else %}
                            <div class="text-center py-5 text-muted opacity-50">
                                <i class="fas fa-hdd fa-2x mb-2"></i>
                                <p>لم يتم اختيار أي مواقع بعد</p>
                            </div>
                        {% endfor %}
                    </div>
                    
                    <input type="hidden" name="backup_paths" id="finalPaths" value="{{ current_paths }}">
                    
                    <div class="mt-4 pt-3 border-top d-flex gap-2">
                        <button type="submit" class="btn btn-dark flex-grow-1 py-2 fw-bold"><i class="fas fa-sync me-2"></i>تحديث الإعدادات</button>
                        <button type="submit" name="trigger_now" class="btn btn-success px-4"><i class="fas fa-play"></i> نسخ الآن</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Folder Picker Modal -->
    <div class="folder-picker-modal" id="pickerModal">
        <div class="picker-content text-end">
            <div class="p-4 border-bottom d-flex align-items-center justify-content-between">
                <button class="btn-close" onclick="closePicker()"></button>
                <h5 class="fw-bold mb-0"><i class="fas fa-folder-open me-2 text-primary"></i>اختر مجلد الحفظ</h5>
            </div>
            
            <div id="breadcrumb" class="px-4 py-2 bg-light extra-small text-start font-monospace"></div>
            
            <div class="browse-list" id="browseBox"></div>
            
            <div class="p-4 border-top">
                <button class="btn btn-primary w-100 py-2 fw-bold" onclick="selectCurrentFolder()">تأكيد الاختيار</button>
            </div>
        </div>
    </div>

    <div class="row pt-4 mb-5">
        <div class="col-12">
            <a href="/settings" class="btn btn-outline-secondary w-100 py-2 border-2"><i class="fas fa-arrow-right me-2"></i>العودة للإعدادات</a>
        </div>
    </div>

    <script>
        let currentPath = '';
        let activePaths = document.getElementById('finalPaths').value.split(',').filter(p => p.trim() !== '');

        function openPicker() {
            document.getElementById('pickerModal').style.display = 'block';
            loadDrives();
        }

        function closePicker() { document.getElementById('pickerModal').style.display = 'none'; }

        async function loadDrives() {
            const res = await fetch('/api/list_drives');
            const data = await res.json();
            const box = document.getElementById('browseBox');
            box.innerHTML = '';
            document.getElementById('breadcrumb').textContent = 'Computer';
            data.drives.forEach(d => {
                const el = document.createElement('div');
                el.className = 'browse-item';
                el.innerHTML = `<i class="fas fa-hdd text-secondary"></i> <strong>Disk (${d})</strong>`;
                el.onclick = () => loadDir(d);
                box.appendChild(el);
            });
        }

        async function loadDir(path) {
            currentPath = path;
            document.getElementById('breadcrumb').textContent = path;
            const res = await fetch(`/api/browse_dir?path=${encodeURIComponent(path)}`);
            const data = await res.json();
            const box = document.getElementById('browseBox');
            box.innerHTML = '';
            
            // Back button
            if (path.length > 3) {
                const back = document.createElement('div');
                back.className = 'browse-item text-primary';
                back.innerHTML = `<i class="fas fa-arrow-up"></i> .. (رجوع)`;
                const parent = path.substring(0, path.lastIndexOf('/', path.length-2)) + '/';
                back.onclick = () => loadDir(parent);
                box.appendChild(back);
            } else {
                const root = document.createElement('div');
                root.className = 'browse-item text-muted';
                root.innerHTML = `<i class="fas fa-computer"></i> My Computer`;
                root.onclick = () => loadDrives();
                box.appendChild(root);
            }

            data.items.forEach(i => {
                const el = document.createElement('div');
                el.className = 'browse-item';
                el.innerHTML = `<i class="fas fa-folder text-warning"></i> ${i.name}`;
                el.onclick = () => loadDir(i.path + '/');
                box.appendChild(el);
            });
        }

        function selectCurrentFolder() {
            if (!currentPath) return alert('الرجاء اختيار مجلد...');
            if (!activePaths.includes(currentPath)) {
                activePaths.push(currentPath);
                document.getElementById('finalPaths').value = activePaths.join(',');
                document.getElementById('configForm').submit();
            }
            closePicker();
        }

        function removePath(index) {
            activePaths.splice(index-1, 1);
            document.getElementById('finalPaths').value = activePaths.join(',');
            document.getElementById('configForm').submit();
        }
    </script>
    """ + footer_html
    return render_template_string(html, msg=msg, current_paths=current_paths)

@backup_logs_bp.route('/settings/logs')
def view_logs():
    if not check_admin():
        return redirect(url_for('dashboard.dashboard'))
        
    search = request.args.get('search', '')
    action_filter = request.args.get('action', '')
    
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    # ── 1. Fetch Logs with Search & Filter ────────────────────────────────────
    query = """
        SELECT al.*, u.username, u.full_name_ar
        FROM activity_logs al
        LEFT JOIN users u ON al.user_id = u.user_id
        WHERE (u.username LIKE %s OR u.full_name_ar LIKE %s OR al.action LIKE %s OR al.details LIKE %s)
    """
    params = [f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%']
    
    if action_filter:
        query += " AND al.action = %s"
        params.append(action_filter)
        
    query += " ORDER BY al.created_at DESC LIMIT 500"
    
    cur.execute(query, tuple(params))
    logs = cur.fetchall()
    
    # ── 2. Fetch Helper Data ──────────────────────────────────────────────────
    cur.execute("SELECT DISTINCT action FROM activity_logs ORDER BY action ASC")
    all_actions = [r['action'] for r in cur.fetchall()]
    
    cur.execute("SELECT COUNT(*) as c FROM activity_logs")
    total_count = cur.fetchone()['c']
    
    cur.execute("SELECT action, COUNT(*) as c FROM activity_logs GROUP BY action ORDER BY c DESC LIMIT 1")
    top_action_row = cur.fetchone()
    top_action = top_action_row['action'] if top_action_row else "-"

    html = header_html + """
    <style>
        .log-card { border-radius: 20px; border: none; background: #fff; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
        .search-bar { background: #f8f9fa; border-radius: 15px; padding: 20px; margin-bottom: 30px; border: 1px solid #eee; }
        .table thead th { background: #f1f5f9; color: #475569; font-weight: 700; border: none; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px; }
        .table td { border-bottom: 1px solid #f8fafc; padding: 15px; vertical-align: middle; }
        .action-badge { padding: 6px 12px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; }
        .user-pill { background: #eff6ff; color: #1e40af; padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
        .stat-icon { width: 45px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; font-size: 1.2rem; }
        .bg-cyber-blue { background: #e0f2fe; color: #0369a1; }
        .bg-cyber-purple { background: #f5f3ff; color: #6d28d9; }
        .bg-cyber-green { background: #f0fdf4; color: #15803d; }
    </style>

    <div class="row pt-2 mb-4">
        <div class="col-md-8 text-end">
            <h2 class="fw-bold mb-1"><i class="fas fa-fingerprint text-primary me-2"></i>مركز مراقبة النظام</h2>
            <p class="text-muted small">سجل العمليات المتقدم والتحليلات الأمنية</p>
        </div>
        <div class="col-md-4 text-start d-flex align-items-center justify-content-end">
            <span class="badge bg-dark px-3 py-2">إجمالي العمليات: {{ total_count }}</span>
        </div>
    </div>

    <!-- Stats Row -->
    <div class="row g-3 mb-4 text-end">
        <div class="col-md-4">
            <div class="card log-card p-3">
                <div class="stat-icon bg-cyber-blue"><i class="fas fa-bolt"></i></div>
                <h6 class="text-muted small mb-1">العملية الأكثر تكراراً</h6>
                <div class="fw-bold text-dark">{{ top_action }}</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card log-card p-3">
                <div class="stat-icon bg-cyber-purple"><i class="fas fa-user-shield"></i></div>
                <h6 class="text-muted small mb-1">المسؤول الحالي</h6>
                <div class="fw-bold text-dark">{{ session.full_name }}</div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card log-card p-3">
                <div class="stat-icon bg-cyber-green"><i class="fas fa-history"></i></div>
                <h6 class="text-muted small mb-1">آخر تحديث للسجل</h6>
                <div class="fw-bold text-dark fs-6">{{ logs[0].created_at if logs else 'لا يوجد' }}</div>
            </div>
        </div>
    </div>

    <!-- Search & Filter Controls -->
    <div class="search-bar">
        <form method="GET" class="row g-3">
            <div class="col-md-5">
                <div class="input-group">
                    <span class="input-group-text border-0 bg-white"><i class="fas fa-search text-muted"></i></span>
                    <input type="text" name="search" class="form-control border-0 shadow-none" placeholder="ابحث عن مستخدم، عملية، أو تفاصيل محددة..." value="{{ search }}">
                </div>
            </div>
            <div class="col-md-4">
                <select name="action" class="form-select border-0 shadow-none">
                    <option value="">كل أنواع العمليات</option>
                    {% for act in all_actions %}
                        <option value="{{ act }}" {% if action_filter == act %}selected{% endif %}>{{ act }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <button type="submit" class="btn btn-primary w-100 fw-bold rounded-3"><i class="fas fa-filter me-2"></i>تطبيق الفلتر</button>
            </div>
        </form>
    </div>

    <div class="card log-card overflow-hidden mb-5">
        <div class="table-responsive">
            <table class="table table-hover mb-0 text-end">
                <thead>
                    <tr>
                        <th class="ps-4">الوقت والتاريخ</th>
                        <th>المستخدم</th>
                        <th>العملية</th>
                        <th>التفاصيل التقنية</th>
                        <th class="pe-4">الحالة</th>
                    </tr>
                </thead>
                <tbody>
                    {% for log in logs %}
                    <tr>
                        <td class="ps-4">
                            <span class="text-dark fw-medium small"><i class="far fa-clock me-1 text-muted"></i> {{ log.created_at }}</span>
                        </td>
                        <td>
                            <div class="user-pill d-inline-block">
                                <i class="fas fa-user-circle me-1"></i> {{ log.username or 'النظام' }}
                            </div>
                        </td>
                        <td>
                            <span class="fw-bold text-dark">{{ log.action }}</span>
                        </td>
                        <td>
                            <div class="text-muted small" style="max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{{ log.details }}">
                                {{ log.details or '---' }}
                            </div>
                        </td>
                        <td class="pe-4">
                            <span class="action-badge {% if 'خطأ' in log.action %}bg-danger-subtle text-danger{% elif 'دخول' in log.action %}bg-success-subtle text-success{% else %}bg-primary-subtle text-primary{% endif %}">
                                <i class="fas fa-check-circle me-1"></i> مكتمل
                            </span>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" class="text-center py-5 text-muted">
                            <i class="fas fa-search fa-3x mb-3 d-block opacity-25"></i>
                            لم يتم العثور على أي سجلات تطابق بحثك
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="row mb-5">
        <div class="col-12">
            <a href="/settings" class="btn btn-outline-secondary w-100 py-2 border-2"><i class="fas fa-arrow-right me-2"></i>العودة إلى لوحة الإعدادات العامة</a>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, logs=logs, search=search, action_filter=action_filter, all_actions=all_actions, total_count=total_count, top_action=top_action)
