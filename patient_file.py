import os
import time
from werkzeug.utils import secure_filename # type: ignore
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

patient_file_bp = Blueprint('patient_file', __name__)

@patient_file_bp.route('/patient_file', methods=['GET', 'POST'])
def patient_file():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    patient_id = request.args.get('id')
    if not patient_id:
        return redirect(url_for('patients.patients'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # --- Handle Archive Upload ---
    if request.method == 'POST' and 'upload_archive' in request.form:
        file_desc = request.form.get('file_name', '')
        
        target_file_path = None
        if 'archive_file' in request.files:
            file = request.files['archive_file']
            if file and file.filename != '':
                upload_dir = 'uploads/archive/'
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir, exist_ok=True)
                    
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                new_name = secure_filename(f"arch_{int(time.time())}.{file_ext}") # simple unique name
                target_file_path = os.path.join(upload_dir, new_name)
                file.save(target_file_path)
                target_file_path = target_file_path.replace("\\", "/")
                
        doc_id = session.get('user_id', 1)
        
        if target_file_path:
            cursor.execute("""
                INSERT INTO radiology_requests (patient_id, doctor_id, scan_type, image_path, status, created_at) 
                VALUES (%s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP)
            """, (patient_id, doc_id, file_desc, target_file_path))
            conn.commit()
            
            flash("تم أرشفة الملف بنجاح", "success")
        else:
            flash("حدث خطأ أثناء رفع الملف", "danger")
            
        return redirect(url_for('patient_file.patient_file', id=patient_id))

        
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    p = cursor.fetchone()
    
    if not p:
        return redirect(url_for('patients.patients'))

        
    cursor.execute("""
        SELECT c.*, u.full_name_ar as doc_name 
        FROM consultations c 
        JOIN users u ON c.doctor_id = u.user_id 
        WHERE c.patient_id = %s 
        ORDER BY c.created_at DESC
    """, (patient_id,))
    history = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM prescriptions 
        WHERE patient_id = %s 
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id,))
    prescs = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM lab_requests 
        WHERE patient_id = %s 
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id,))
    labs = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM radiology_requests 
        WHERE patient_id = %s 
        ORDER BY created_at DESC
    """, (patient_id,))
    rads = cursor.fetchall()
    
    
    def file_exists(path):
        if not path: return False
        try:
             return os.path.exists(path)
        except:
             return False

    html = header_html + """
    <!-- Include Barcode Library -->
    <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>

    <style>
        :root {
            --pf-bg: #f5f6f8;
            --pf-card: #ffffff;
            --pf-text: #2c3e50;
            --pf-border: #e1e4e8;
            --pf-input-bg: #ffffff;
        }

        

        .pf-body { background: transparent; color: var(--pf-text); min-height: 100vh; font-family: 'Outfit', sans-serif; transition: background 0.3s; }

        
        .glass-card {
            background: var(--pf-card) !important;
            border: 1px solid var(--pf-border) !important;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
            overflow: hidden;
            backdrop-filter: blur(15px);
        }

        

        .hover-scale { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
        .hover-scale:hover { transform: translateY(-8px); box-shadow: 0 15px 40px rgba(0,0,0,0.15); }

        .barcode-v { 
            background: #ffffff; 
            padding: 8px 12px; 
            border-radius: 12px; 
            display: inline-block; 
            border: 1px solid var(--pf-border);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transform: scale(0.9);
            transform-origin: left center;
        }
        
        


        
        .section-header-line { border-right: 4px solid var(--bs-primary); padding-right: 15px; margin-bottom: 1.5rem; }
        
        /* Form & Table Adaptation */
        .form-control { 
            background-color: var(--pf-input-bg) !important; 
            color: var(--pf-text) !important; 
            border: 1px solid var(--pf-border) !important;
            border-radius: 12px !important;
            padding: 12px !important;
        }
        .form-control::placeholder { color: var(--pf-text); opacity: 0.5; }
        
        /* File Input Button Styling */
        .form-control::file-selector-button {
            background: rgba(191, 90, 242, 0.1);
            color: var(--pf-text);
            border: none;
            border-left: 1px solid var(--pf-border);
            margin-left: 15px;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        
        .form-control::file-selector-button:hover {
            background: rgba(191, 90, 242, 0.2);
        }
        
        .table { color: var(--pf-text) !important; background: transparent !important; }
        
        
        .table thead th { background: rgba(0,0,0,0.02); border-bottom: 2px solid var(--pf-border); color: var(--pf-text); opacity: 0.7; }
        
        .table td { border-bottom: 1px solid var(--pf-border); vertical-align: middle; }
        
        

        .btn-primary { 
            background: linear-gradient(135deg, #bf5af2 0%, #5e5ce6 100%) !important; 
            border: none !important;
            box-shadow: 0 4px 15px rgba(191, 90, 242, 0.3);
            transition: all 0.3s;
        }
        .btn-primary:hover { transform: scale(1.02); box-shadow: 0 6px 20px rgba(191, 90, 242, 0.4); }
        
        .btn-round { border-radius: 12px; padding: 10px 20px; font-weight: 600; transition: all 0.3s; }
        .action-icon { font-size: 2rem; margin-bottom: 0.5rem; display: block; }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade { animation: fadeInUp 0.4s ease-out forwards; }
        
        .archive-form-box {
            background: rgba(191, 90, 242, 0.05);
            border: 1px dashed var(--pf-border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .text-themed { color: var(--pf-text); opacity: 0.85; }
    </style>


    <div class="pf-body pt-4">
        <div class="container-fluid px-lg-5">
            <!-- Compact Patient Header -->
            <div class="d-flex justify-content-center mb-4">
                <div class="glass-card p-2 animate-fade shadow-sm" style="max-width: 900px; width: 100%;">
                    <div class="row align-items-center g-2">
                        <div class="col-md-12">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="avatar-box rounded-circle overflow-hidden shadow-sm" style="width: 60px; height: 60px; background: var(--pf-input-bg); border: 2px solid var(--pf-border);">
                                        {% if p.photo and file_exists(p.photo) %}
                                            <img src="/{{ p.photo }}" class="w-100 h-100" style="object-fit: cover;">
                                        {% else %}
                                            <div class="w-100 h-100 d-flex align-items-center justify-content-center text-muted" style="font-size: 1.8rem; background: var(--pf-input-bg);">
                                                <i class="fas fa-user-circle"></i>
                                            </div>
                                        {% endif %}
                                    </div>
                                    <div class="flex-grow-1">
                                        <h4 class="fw-bold mb-0" style="font-size: 1.15rem;">{{ p.full_name_ar }}</h4>
                                        <div class="d-flex flex-wrap gap-2 align-items-center mt-1">
                                            <span class="badge bg-primary px-2 py-1 rounded-pill" style="font-size: 0.75rem;">{{ p.file_number }}</span>
                                            <span class="text-themed fw-bold" style="font-size: 0.8rem;"><i class="fas fa-venus-mars me-1"></i> {{ 'ذكر' if p.gender == 'male' else 'أنثى' }}</span>
                                            <span class="text-themed small" style="font-size: 0.75rem;"><i class="fas fa-calendar-alt me-1"></i> 
                                                {% if p.date_of_birth and p.date_of_birth.__class__.__name__ == 'datetime' %}
                                                    {{ p.date_of_birth.strftime('%Y-%m-%d') }}
                                                {% elif p.date_of_birth %}
                                                    {{ p.date_of_birth|string|replace('00:00:00', '')|trim }}
                                                {% endif %}
                                            </span>
                                            <span class="text-themed small" style="font-size: 0.75rem;"><i class="fas fa-phone-alt me-1"></i> {{ p.phone1 }}</span>
                                        </div>
                                    </div>
                                </div>

                        </div>
                    </div>
                </div>
            </div>



            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} rounded-4 border-0 shadow-sm animate-fade">
                            <i class="fas fa-info-circle me-2"></i> {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- ══════ ACTION TILES — Unified Professional Design ══════ -->
            <style>
                .ptile-row {
                    display: grid;
                    grid-template-columns: repeat(5, 1fr);
                    gap: 10px;
                    margin-bottom: 1.8rem;
                }
                .ptile {
                    background: var(--pf-card);
                    border: 1px solid var(--pf-border);
                    border-radius: 16px;
                    padding: 16px 12px 14px;
                    cursor: pointer;
                    text-decoration: none;
                    color: var(--pf-text);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
                    position: relative;
                    overflow: hidden;
                    min-height: 100px;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
                }
                .ptile:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 12px 32px rgba(0,0,0,0.12);
                    border-color: transparent;
                    color: var(--pf-text);
                    text-decoration: none;
                }
                
                

                /* Colored accent top bar */
                .ptile::before {
                    content: '';
                    position: absolute;
                    top: 0; left: 0; right: 0;
                    height: 3px;
                    border-radius: 16px 16px 0 0;
                    opacity: 0;
                    transition: opacity 0.3s;
                }
                .ptile:hover::before { opacity: 1; }
                .ptile.c-blue::before   { background: linear-gradient(90deg,#007aff,#5856d6); }
                .ptile.c-green::before  { background: linear-gradient(90deg,#34c759,#30d158); }
                .ptile.c-orange::before { background: linear-gradient(90deg,#ff9f0a,#ff6b00); }
                .ptile.c-red::before    { background: linear-gradient(90deg,#ff3b30,#ff6b6b); }
                .ptile.c-purple::before { background: linear-gradient(90deg,#bf5af2,#5e5ce6); }

                .ptile-icon-wrap {
                    width: 44px; height: 44px;
                    border-radius: 12px;
                    display: flex; align-items: center; justify-content: center;
                    font-size: 1.15rem;
                    flex-shrink: 0;
                    transition: transform 0.3s;
                }
                .ptile:hover .ptile-icon-wrap { transform: scale(1.1); }

                .ptile.c-blue   .ptile-icon-wrap { background: rgba(0,122,255,0.12);   color: #007aff; }
                .ptile.c-green  .ptile-icon-wrap { background: rgba(52,199,89,0.12);   color: #28a745; }
                .ptile.c-orange .ptile-icon-wrap { background: rgba(255,159,10,0.12);  color: #e67e00; }
                .ptile.c-red    .ptile-icon-wrap { background: rgba(255,59,48,0.12);   color: #ff3b30; }
                .ptile.c-purple .ptile-icon-wrap { background: rgba(191,90,242,0.12);  color: #bf5af2; }

                
                
                
                
                

                .ptile-label {
                    font-size: 0.78rem;
                    font-weight: 700;
                    text-align: center;
                    line-height: 1.2;
                }
                .ptile-sublabel {
                    font-size: 0.65rem;
                    opacity: 0.45;
                    text-align: center;
                    margin-top: -4px;
                    letter-spacing: 0.3px;
                }
                .ptile-badge {
                    position: absolute;
                    top: 8px; left: 8px;
                    font-size: 0.6rem;
                    font-weight: 700;
                    padding: 2px 7px;
                    border-radius: 20px;
                    letter-spacing: 0.3px;
                }

                /* Live clock bar */
                .pf-clock-bar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    background: var(--pf-card);
                    border: 1px solid var(--pf-border);
                    border-radius: 14px;
                    padding: 10px 20px;
                    margin-bottom: 14px;
                    font-size: 0.78rem;
                }
                
                .pf-clock-time {
                    font-size: 1.2rem;
                    font-weight: 800;
                    letter-spacing: 1px;
                    font-variant-numeric: tabular-nums;
                }
                .pf-stat-chip {
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.72rem;
                    font-weight: 700;
                    border: 1px solid;
                }
            </style>


            <!-- Real-Time Clock & Date Bar -->
            <div class="d-flex justify-content-center mb-1">
                <div class="pf-clock-bar animate-fade shadow-sm" style="max-width: 900px; width: 100%; border-color: rgba(191,90,242,0.15); background: white;">
                    <div class="d-flex align-items-center gap-3">
                        <span class="pf-stat-chip text-primary" style="background: rgba(0,122,255,0.08); border-color: rgba(0,122,255,0.2);">
                            <i class="fas fa-calendar-alt me-1"></i> <span id="pf-live-date">{{ now.strftime('%Y-%m-%d') }}</span>
                        </span>
                        <span class="pf-stat-chip text-purple" style="background: rgba(191,90,242,0.08); border-color: rgba(191,90,242,0.2);">
                            <i class="fas fa-history me-1"></i> التوقيت المباشر
                        </span>
                    </div>
                    <div class="pf-clock-time text-primary d-flex align-items-center gap-2" id="pf-live-clock" style="font-size: 1.1rem;">
                        <i class="far fa-clock opacity-50"></i>
                        <span>{{ now.strftime('%I:%M:%S %p') }}</span>
                    </div>
                </div>
            </div>

            <script>
                function updateLiveClock() {
                    const now = new Date();
                    
                    // Time format
                    const timeOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true };
                    const timeString = now.toLocaleTimeString('en-US', timeOptions);
                    
                    // Date format
                    const year = now.getFullYear();
                    const month = String(now.getMonth() + 1).padStart(2, '0');
                    const day = String(now.getDate()).padStart(2, '0');
                    const dateString = `${year}-${month}-${day}`;
                    
                    document.getElementById('pf-live-clock').querySelector('span').innerText = timeString;
                    document.getElementById('pf-live-date').innerText = dateString;
                }
                setInterval(updateLiveClock, 1000);
            </script>

            <!-- Unified Action Tiles -->
            <div class="ptile-row animate-fade" style="animation-delay:0.1s; grid-template-columns: repeat(6, 1fr);">

                <!-- 1. المعلومات -->
                <a href="{{ url_for('edit_patient.edit_patient') }}?id={{ p.patient_id }}" class="ptile c-blue">
                    <div class="ptile-icon-wrap"><i class="fas fa-user-edit"></i></div>
                    <div class="ptile-label">المعلومات</div>
                    <div class="ptile-sublabel">Patient Info</div>
                </a>

                <!-- 2. السجل الطبي -->
                <div onclick="showSection('history-section')" class="ptile c-green">
                    <span class="ptile-badge" style="background:rgba(52,199,89,0.15);color:#28a745;">{{ history|length }}</span>
                    <div class="ptile-icon-wrap"><i class="fas fa-notes-medical"></i></div>
                    <div class="ptile-label">السجل الطبي</div>
                    <div class="ptile-sublabel">Medical History</div>
                </div>

                <!-- 3. التقارير (Medication & Prescription Record) -->
                <div onclick="showSection('reports-section')" class="ptile c-purple">
                    <span class="ptile-badge" style="background:rgba(191,90,242,0.15);color:#bf5af2;">{{ (prescs|length) + (labs|length) }}</span>
                    <div class="ptile-icon-wrap"><i class="fas fa-file-medical-alt"></i></div>
                    <div class="ptile-label" style="font-size: 0.65rem;">Medication & Prescription Record</div>
                    <div class="ptile-sublabel">Treatment History</div>
                </div>

                <!-- 4. الأرشيف -->
                <div onclick="showSection('archive-section')" class="ptile c-orange">
                    <span class="ptile-badge" style="background:rgba(255,159,10,0.15);color:#e67e00;">{{ rads|length }}</span>
                    <div class="ptile-icon-wrap"><i class="fas fa-archive"></i></div>
                    <div class="ptile-label">الأرشيف</div>
                    <div class="ptile-sublabel">Archive</div>
                </div>

                <!-- 5. تقرير طبي -->
                <a href="/medical_report?id={{ p.patient_id }}" target="_blank" class="ptile c-blue" style="--pf-accent: #007aff;">
                    <div class="ptile-icon-wrap" style="background: rgba(0,122,255,0.1); color: #007aff;"><i class="fas fa-file-prescription"></i></div>
                    <div class="ptile-label">تقرير طبي</div>
                    <div class="ptile-sublabel">Medical Report</div>
                </a>

                <!-- 6. حجز موعد -->
                <a href="{{ url_for('book.book') }}?id={{ p.patient_id }}" class="ptile c-red">
                    <div class="ptile-icon-wrap"><i class="fas fa-calendar-plus"></i></div>
                    <div class="ptile-label">حجز موعد</div>
                    <div class="ptile-sublabel">Book Appointment</div>
                </a>

            </div>

        
    <script>
        // PDF & WhatsApp Share System (Local-Safe)
        async function robustShare(url, filename, phone) {
            const btn = event.currentTarget || this; 
            const original = btn.innerHTML;
            
            try {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ...';
                btn.style.pointerEvents = 'none';

                const iframe = document.createElement('iframe');
                iframe.style.cssText = 'position:fixed; top:-10000px; left:-10000px; width:850px; height:1200px;';
                document.body.appendChild(iframe);
                iframe.src = window.location.origin + url;
                
                iframe.onload = async function() {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        const el = doc.querySelector('.rx-card, .lab-report, .report-box, body');
                        
                        // Copy image to clipboard
                        if (window.html2canvas) {
                             const canvas = await html2canvas(el, { scale: 1.5, useCORS: true });
                             canvas.toBlob(b => {
                                 if (navigator.clipboard && window.ClipboardItem) {
                                     navigator.clipboard.write([new ClipboardItem({ "image/png": b })]).catch(e => console.warn(e));
                                 }
                             });
                        }

                        // Download PDF
                        if (window.html2pdf) {
                             await html2pdf().set({ margin: 10, filename: filename + '.pdf' }).from(el).save();
                        }

                        const msg = "مرحباً، إليك ملف " + filename + " الخاص بك. التقرير متاح الآن كملف PDF في جهازك، وصوره منسوخة للذاكرة.";
                        const waUrl = "https://wa.me/" + phone.replace(/\\D/g, '') + "?text=" + encodeURIComponent(msg);
                        window.open(waUrl, '_blank');
                        
                        setTimeout(() => alert("✅ جاهز! الملف في التنزيلات، والصورة منسوخة للذاكرة لإرسالها بالضغط على (Ctrl+V) في الواتساب."), 300);
                    } catch (e) {
                         console.error(e);
                         window.open("https://wa.me/" + phone.replace(/\\D/g, ''), '_blank');
                    } finally {
                        btn.innerHTML = original;
                        btn.style.pointerEvents = 'auto';
                        if (iframe.parentNode) document.body.removeChild(iframe);
                    }
                };
            } catch (err) {
                btn.innerHTML = original;
                btn.style.pointerEvents = 'auto';
            }
        }
    </script>



            <!-- Content Area -->
            <div class="animate-fade" style="animation-delay: 0.2s;">
                <!-- History Section (Visible by default) -->
                <div class="section-content" id="history-section" style="display: block;">
                    <div class="glass-card p-4">
                        <div class="section-header-line">
                            <h3 class="fw-bold m-0"><i class="fas fa-notes-medical me-2"></i> السجل الطبي والتاريخ المرضي</h3>
                        </div>
                        <div class="row g-4 mt-1">
                            {% for h in history %}
                                <div class="col-12 border-bottom pb-4 mb-4" style="border-color: var(--pf-border) !important;">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <span class="badge bg-light text-dark border px-3" style="background: var(--pf-input-bg) !important; color: var(--pf-text) !important; font-size: 0.8rem;">
                                            <i class="far fa-clock me-1 text-primary"></i>
                                            {{ dt(h.created_at, '%Y-%m-%d | %I:%M %p') }}
                                        </span>
                                        <span class="fw-bold text-primary">د. {{ h.doc_name }}</span>
                                    </div>
                                    <h5 class="fw-bold text-danger mb-3">التشخيص: {{ h.assessment }}</h5>
                                    <p class="opacity-75 mb-3">{{ h.subjective }}</p>
                                    <div class="bg-light p-4 rounded-4 small border" style="background: var(--pf-input-bg) !important; border-color: var(--pf-border) !important;">
                                        <strong class="d-block text-dark mb-2" style="color: var(--pf-text) !important;">الخطة والعلاج:</strong>
                                        {{ h.plan }}
                                    </div>
                                </div>
                            {% else %}
                                <div class="text-center py-5 opacity-50">
                                    <i class="fas fa-folder-open fa-3x mb-3"></i>
                                    <h5>لا توجد سجلات طبية مسجلة بعد</h5>
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>

                <!-- Reports Section — Professional Premium Design -->
                <div class="section-content" id="reports-section" style="display: none;">

                    <style>
                        /* ===== PROFESSIONAL REPORTS STYLES ===== */
                        .rep-header {
                            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                            border-radius: 20px;
                            padding: 2rem;
                            margin-bottom: 2rem;
                            position: relative;
                            overflow: hidden;
                            border: 1px solid rgba(255,255,255,0.08);
                        }
                        .rep-header::before {
                            content: '';
                            position: absolute;
                            top: -50%;
                            right: -20%;
                            width: 300px;
                            height: 300px;
                            background: radial-gradient(circle, rgba(94,92,230,0.3) 0%, transparent 70%);
                            border-radius: 50%;
                        }
                        .rep-header::after {
                            content: '';
                            position: absolute;
                            bottom: -40%;
                            left: 10%;
                            width: 200px;
                            height: 200px;
                            background: radial-gradient(circle, rgba(52,199,89,0.2) 0%, transparent 70%);
                            border-radius: 50%;
                        }
                        .rep-stat-card {
                            background: rgba(255,255,255,0.07);
                            border: 1px solid rgba(255,255,255,0.12);
                            border-radius: 16px;
                            padding: 1.2rem 1.5rem;
                            backdrop-filter: blur(10px);
                            transition: all 0.3s;
                            position: relative;
                            z-index: 1;
                        }
                        .rep-stat-card:hover { background: rgba(255,255,255,0.12); transform: translateY(-3px); }
                        .rep-stat-num { font-size: 2rem; font-weight: 800; line-height: 1; }
                        .rep-stat-label { font-size: 0.78rem; opacity: 0.7; margin-top: 4px; letter-spacing: 0.5px; text-transform: uppercase; }

                        .rep-section-card {
                            background: var(--pf-card);
                            border: 1px solid var(--pf-border);
                            border-radius: 20px;
                            overflow: hidden;
                            box-shadow: 0 8px 30px rgba(0,0,0,0.06);
                            margin-bottom: 1.5rem;
                            transition: box-shadow 0.3s;
                        }
                        .rep-section-card:hover { box-shadow: 0 12px 40px rgba(0,0,0,0.1); }
                        

                        .rep-card-header {
                            padding: 1.2rem 1.5rem;
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            border-bottom: 1px solid var(--pf-border);
                        }
                        

                        .rep-card-header.rx-header {
                            background: linear-gradient(135deg, rgba(52,199,89,0.12) 0%, rgba(52,199,89,0.04) 100%);
                        }
                        .rep-card-header.lab-header {
                            background: linear-gradient(135deg, rgba(0,122,255,0.12) 0%, rgba(0,122,255,0.04) 100%);
                        }

                        .rep-icon-badge {
                            width: 46px;
                            height: 46px;
                            border-radius: 14px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: 1.2rem;
                            flex-shrink: 0;
                        }
                        .rep-icon-badge.rx { background: linear-gradient(135deg, #34c759, #30d158); color: white; box-shadow: 0 4px 15px rgba(52,199,89,0.4); }
                        .rep-icon-badge.lab { background: linear-gradient(135deg, #007aff, #0a84ff); color: white; box-shadow: 0 4px 15px rgba(0,122,255,0.4); }

                        .rep-title { font-size: 1.05rem; font-weight: 700; color: var(--pf-text); }
                        .rep-subtitle { font-size: 0.75rem; opacity: 0.55; letter-spacing: 0.5px; text-transform: uppercase; margin-top: 2px; }

                        .rep-count-pill {
                            font-size: 0.75rem;
                            font-weight: 700;
                            padding: 5px 14px;
                            border-radius: 20px;
                        }
                        .rep-count-pill.rx { background: rgba(52,199,89,0.15); color: #28a745; border: 1px solid rgba(52,199,89,0.3); }
                        .rep-count-pill.lab { background: rgba(0,122,255,0.15); color: #007aff; border: 1px solid rgba(0,122,255,0.3); }
                        
                        

                        /* Pro Table */
                        .pro-table { width: 100%; border-collapse: separate; border-spacing: 0; }
                        .pro-table thead th {
                            background: rgba(0,0,0,0.02);
                            padding: 12px 18px;
                            font-size: 0.72rem;
                            font-weight: 700;
                            letter-spacing: 0.8px;
                            text-transform: uppercase;
                            color: var(--pf-text);
                            opacity: 0.5;
                            border-bottom: 1px solid var(--pf-border);
                        }
                        

                        .pro-table tbody tr {
                            transition: background 0.2s;
                            border-bottom: 1px solid var(--pf-border);
                        }
                        
                        .pro-table tbody tr:last-child { border-bottom: none; }
                        .pro-table tbody tr:hover { background: rgba(0,0,0,0.015); }
                        
                        .pro-table td { padding: 14px 18px; vertical-align: middle; color: var(--pf-text); font-size: 0.9rem; }

                        .date-badge {
                            display: inline-flex;
                            align-items: center;
                            gap: 6px;
                            background: var(--pf-input-bg);
                            border: 1px solid var(--pf-border);
                            border-radius: 10px;
                            padding: 5px 12px;
                            font-size: 0.8rem;
                            font-weight: 600;
                            color: var(--pf-text);
                        }
                        .date-badge i { opacity: 0.5; font-size: 0.7rem; }

                        .med-name-cell {
                            max-width: 280px;
                            font-size: 0.88rem;
                            line-height: 1.5;
                        }
                        .med-name-cell .med-main { font-weight: 600; color: var(--pf-text); }
                        .med-name-cell .med-sub { font-size: 0.75rem; opacity: 0.55; margin-top: 2px; }

                        .count-bubble {
                            display: inline-flex;
                            align-items: center;
                            gap: 6px;
                            background: linear-gradient(135deg, rgba(0,122,255,0.1), rgba(0,122,255,0.05));
                            border: 1px solid rgba(0,122,255,0.2);
                            border-radius: 12px;
                            padding: 6px 14px;
                            font-size: 0.85rem;
                            font-weight: 700;
                            color: #007aff;
                        }
                        

                        .btn-action-rx {
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 6px;
                            width: 90px;
                            height: 36px;
                            border-radius: 10px;
                            font-size: 0.78rem;
                            font-weight: 700;
                            border: 1.5px solid rgba(52,199,89,0.4);
                            color: #28a745;
                            background: rgba(52,199,89,0.08);
                            text-decoration: none;
                            transition: all 0.25s;
                            white-space: nowrap;
                        }
                        .btn-action-rx:hover {
                            background: rgba(52,199,89,0.18);
                            border-color: rgba(52,199,89,0.7);
                            color: #1e7e34;
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(52,199,89,0.25);
                        }
                        
                        

                        .btn-action-lab {
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 6px;
                            width: 90px;
                            height: 36px;
                            border-radius: 10px;
                            font-size: 0.78rem;
                            font-weight: 700;
                            border: 1.5px solid rgba(0,122,255,0.4);
                            color: #007aff;
                            background: rgba(0,122,255,0.08);
                            text-decoration: none;
                            transition: all 0.25s;
                            white-space: nowrap;
                        }
                        .btn-action-lab:hover {
                            background: rgba(0,122,255,0.18);
                            border-color: rgba(0,122,255,0.7);
                            color: #0056b3;
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(0,122,255,0.25);
                        }
                        
                        

                        /* زر العرض - موحد لكلا الجدولين */
                        .btn-action-view {
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 6px;
                            width: 90px;
                            height: 36px;
                            border-radius: 10px;
                            font-size: 0.78rem;
                            font-weight: 700;
                            border: 1.5px solid rgba(94,92,230,0.4);
                            color: #5e5ce6;
                            background: rgba(94,92,230,0.08);
                            text-decoration: none;
                            transition: all 0.25s;
                            white-space: nowrap;
                            cursor: pointer;
                        }
                        .btn-action-view:hover {
                            background: rgba(94,92,230,0.18);
                            border-color: rgba(94,92,230,0.7);
                            color: #4340c4;
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(94,92,230,0.25);
                        }
                        

                        /* زر التقرير الطبي */
                        .btn-action-report {
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 6px;
                            width: 90px;
                            height: 36px;
                            border-radius: 10px;
                            font-size: 0.78rem;
                            font-weight: 700;
                            border: 1.5px solid rgba(37, 99, 235, 0.4);
                            color: #2563eb;
                            background: rgba(37, 99, 235, 0.08);
                            text-decoration: none;
                            transition: all 0.25s;
                            white-space: nowrap;
                            cursor: pointer;
                        }
                        .btn-action-report:hover {
                            background: rgba(37, 99, 235, 0.18);
                            border-color: rgba(37, 99, 235, 0.7);
                            color: #1d4ed8;
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
                        }

                        .btn-action-whatsapp {
                            display: inline-flex;
                            align-items: center;
                            justify-content: center;
                            gap: 6px;
                            width: 90px;
                            height: 36px;
                            border-radius: 10px;
                            font-size: 0.78rem;
                            font-weight: 700;
                            border: 1.5px solid rgba(37, 211, 102, 0.4);
                            color: #25d366;
                            background: rgba(37, 211, 102, 0.08);
                            text-decoration: none;
                            transition: all 0.25s;
                            white-space: nowrap;
                        }
                        .btn-action-whatsapp:hover {
                            background: rgba(37, 211, 102, 0.18);
                            border-color: rgba(37, 211, 102, 0.7);
                            color: #128c7e;
                            transform: translateY(-2px);
                            box-shadow: 0 4px 12px rgba(37, 211, 102, 0.25);
                        }
                        

                        .empty-state-pro {
                            text-align: center;
                            padding: 3rem 2rem;
                            opacity: 0.4;
                        }
                        .empty-state-pro .empty-icon { font-size: 3rem; margin-bottom: 1rem; display: block; }
                        .empty-state-pro p { font-size: 0.9rem; margin: 0; }

                        @keyframes slideUp {
                            from { opacity: 0; transform: translateY(16px); }
                            to { opacity: 1; transform: translateY(0); }
                        }
                        .rep-section-card { animation: slideUp 0.35s ease-out both; }
                        .rep-section-card:nth-child(2) { animation-delay: 0.1s; }
                    </style>

                    <!-- ===== Summary Stats Bar (Hidden) ===== -->
                    <div class="rep-header text-white mb-4" style="display:none;"></div>

                    <!-- ===== Prescriptions Card ===== -->
                    <div class="rep-section-card">
                        <div class="rep-card-header rx-header">
                            <div class="d-flex align-items-center gap-3">
                                <div class="rep-icon-badge rx">
                                    <i class="fas fa-prescription-bottle-alt"></i>
                                </div>
                                <div>
                                    <div class="rep-title">سجل الأدوية والوصفات</div>
                                    <div class="rep-subtitle">Prescription Records</div>
                                </div>
                            </div>
                            <span class="rep-count-pill rx">
                                <i class="fas fa-layer-group me-1"></i>
                                {{ prescs|length }} وصفة
                            </span>
                        </div>

                        {% if prescs %}
                        <div class="table-responsive">
                            <table class="pro-table">
                                <thead>
                                    <tr>
                                        <th style="width:40px;">#</th>
                                        <th>التاريخ والوقت</th>
                                        <th>الأدوية المصروفة</th>
                                        <th style="text-align:center;min-width:220px;">الإجراءات</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for pr in prescs %}
                                    <tr>
                                        <td>
                                            <span style="font-size:0.75rem;font-weight:700;color:var(--pf-text);opacity:0.35;">{{ loop.index }}</span>
                                        </td>
                                        <td>
                                            <div class="date-badge" style="color: #bf5af2; border-color: rgba(191,90,242,0.2);">
                                                <i class="far fa-clock"></i>
                                                {{ dt(pr.created_at, '%Y-%m-%d | %I:%M %p') }}
                                            </div>
                                        </td>
                                        <td>
                                            <div class="med-name-cell" style="max-width: 400px;">
                                                <div class="med-main" style="font-weight: 700; color: #bf5af2; line-height: 1.4;">
                                                    <i class="fas fa-prescription-bottle-alt me-2"></i> الوصفة الطبية
                                                </div>
                                            </div>
                                        </td>
                                        <td style="text-align:center;">
                                            <div class="d-flex gap-2 justify-content-center flex-wrap">
                                                <a href="{{ url_for('medical_report.medical_report', id=p.patient_id, appointment_id=pr.appointment_id) if pr.appointment_id else url_for('medical_report.medical_report', id=p.patient_id) }}" target="_blank" class="btn-action-report" title="التقرير الطبي">
                                                    <i class="fas fa-file-invoice"></i> التقرير
                                                </a>
                                                 <a href="javascript:void(0)" onclick="robustShare('{{ url_for('medical_report.medical_report', id=p.patient_id) }}', 'التقرير الطبي - {{ p.full_name_ar }}', '{{ p.phone1 }}')" class="btn-action-whatsapp" title="إرسال التقرير عبر واتساب">
                                                     <i class="fab fa-whatsapp"></i> واتساب
                                                 </a>
                                            </div>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                        {% else %}
                        <div class="empty-state-pro">
                            <span class="empty-icon">💊</span>
                            <p>لا توجد وصفات طبية مسجلة لهذا المريض</p>
                        </div>
                        {% endif %}
                    </div>

                    <!-- ===== Lab Results Card ===== -->
                    <div class="rep-section-card">
                        <div class="rep-card-header lab-header">
                            <div class="d-flex align-items-center gap-3">
                                <div class="rep-icon-badge lab">
                                    <i class="fas fa-flask"></i>
                                </div>
                                <div>
                                    <div class="rep-title">سجل التحاليل والمختبر</div>
                                    <div class="rep-subtitle">Laboratory Results — Grouped by Date</div>
                                </div>
                            </div>
                            <span class="rep-count-pill lab">
                                <i class="fas fa-layer-group me-1"></i>
                                {{ labs|length }} تحليل
                            </span>
                        </div>

                        {% set grouped_labs = {} %}
                        {% for l in labs %}
                            {% set d = format_dt(l.created_at, '%Y-%m-%d') %}
                            {% if d not in grouped_labs %}
                                {% set _ = grouped_labs.update({d: 1}) %}
                            {% else %}
                                {% set _ = grouped_labs.update({d: grouped_labs[d] + 1}) %}
                            {% endif %}
                        {% endfor %}

                        {% if grouped_labs %}
                        <div class="table-responsive">
                            <table class="pro-table">
                                <thead>
                                    <tr>
                                        <th style="width:40px;">#</th>
                                        <th>تاريخ جلسة الفحص</th>
                                        <th>عدد التحاليل المطلوبة</th>
                                        <th style="text-align:center;min-width:220px;">الإجراءات</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for d_str, count in grouped_labs.items() %}
                                    <tr>
                                        <td>
                                            <span style="font-size:0.75rem;font-weight:700;color:var(--pf-text);opacity:0.35;">{{ loop.index }}</span>
                                        </td>
                                        <td>
                                            <div class="date-badge">
                                                <i class="fas fa-calendar-check"></i>
                                                {{ d_str }}
                                            </div>
                                        </td>
                                        <td>
                                            <div class="count-bubble">
                                                <i class="fas fa-vials" style="font-size:0.8rem;"></i>
                                                {{ count }} تحليل مخبري
                                            </div>
                                        </td>
                                        <td style="text-align:center;">
                                            <div class="d-flex gap-2 justify-content-center flex-wrap">
                                                <a href="{{ url_for('print_lab.print_lab', patient_id=p.patient_id, date=d_str) }}" target="_blank" class="btn-action-lab" title="طباعة نتائج التحاليل">
                                                    <i class="fas fa-print"></i> طباعة
                                                </a>
                                                <a href="{{ url_for('print_lab.print_lab', patient_id=p.patient_id, date=d_str) }}" target="_blank" class="btn-action-view" title="عرض نتائج التحاليل">
                                                    <i class="fas fa-eye"></i> عرض
                                                </a>
                                                 <a href="javascript:void(0)" onclick="robustShare('{{ url_for('print_lab.print_lab', patient_id=p.patient_id, date=d_str) }}', 'نتائج تحاليل - {{ d_str }} - {{ p.full_name_ar }}', '{{ p.phone1 }}')" class="btn-action-whatsapp" title="إرسال ملف PDF عبر واتساب">
                                                     <i class="fab fa-whatsapp"></i> واتساب
                                                 </a>
                                            </div>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                        {% else %}
                        <div class="empty-state-pro">
                            <span class="empty-icon">🔬</span>
                            <p>لا توجد نتائج تحاليل مسجلة لهذا المريض</p>
                        </div>
                        {% endif %}
                    </div>

                    <!-- ===== Radiology Card ===== -->
                    <div class="rep-section-card" style="animation-delay:0.2s;">
                        <div class="rep-card-header" style="background:linear-gradient(135deg,rgba(255,159,10,0.12) 0%,rgba(255,159,10,0.04) 100%);">
                            <div class="d-flex align-items-center gap-3">
                                <div class="rep-icon-badge" style="background:linear-gradient(135deg,#ff9f0a,#ff6b00);color:white;box-shadow:0 4px 15px rgba(255,159,10,0.4);">
                                    <i class="fas fa-x-ray"></i>
                                </div>
                                <div>
                                    <div class="rep-title">سجل الأشعة والتصوير</div>
                                    <div class="rep-subtitle">Radiology & Imaging Records</div>
                                </div>
                            </div>
                            <span class="rep-count-pill" style="background:rgba(255,159,10,0.15);color:#e67e00;border:1px solid rgba(255,159,10,0.3);">
                                <i class="fas fa-layer-group me-1"></i>
                                {{ rads|length }} أشعة
                            </span>
                        </div>

                        {% if rads %}
                        <div class="table-responsive">
                            <table class="pro-table">
                                <thead>
                                    <tr>
                                        <th style="width:40px;">#</th>
                                        <th>التاريخ والوقت</th>
                                        <th>نوع الأشعة / الفحص</th>
                                        <th>الحالة</th>
                                        <th style="text-align:center;min-width:180px;">الإجراءات</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for r in rads %}
                                    <tr>
                                        <td>
                                            <span style="font-size:0.75rem;font-weight:700;color:var(--pf-text);opacity:0.35;">{{ loop.index }}</span>
                                        </td>
                                        <td>
                                            <div class="date-badge" style="color: #e67e00; border-color: rgba(255,159,10,0.2);">
                                                <i class="far fa-clock"></i>
                                                {{ dt(r.created_at, '%Y-%m-%d | %I:%M %p') }}
                                            </div>
                                        </td>
                                        <td>
                                            <div style="font-weight:700;font-size:0.9rem;color:var(--pf-text);">{{ r.scan_type }}</div>
                                        </td>
                                        <td>
                                            {% if r.status == 'completed' %}
                                                <span style="display:inline-flex;align-items:center;gap:5px;background:rgba(52,199,89,0.1);color:#28a745;border:1px solid rgba(52,199,89,0.3);border-radius:20px;padding:4px 12px;font-size:0.75rem;font-weight:700;">
                                                    <i class="fas fa-check-circle"></i> مكتمل
                                                </span>
                                            {% else %}
                                                <span style="display:inline-flex;align-items:center;gap:5px;background:rgba(255,159,10,0.1);color:#e67e00;border:1px solid rgba(255,159,10,0.3);border-radius:20px;padding:4px 12px;font-size:0.75rem;font-weight:700;">
                                                    <i class="fas fa-hourglass-half"></i> {{ r.status or 'قيد الانتظار' }}
                                                </span>
                                            {% endif %}
                                        </td>
                                        <td style="text-align:center;">
                                            <div class="d-flex gap-2 justify-content-center flex-wrap">
                                                {% if r.image_path %}
                                                <a href="/{{ r.image_path }}" target="_blank"
                                                   style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:12px;font-size:0.8rem;font-weight:700;border:1.5px solid rgba(255,159,10,0.4);color:#e67e00;background:rgba(255,159,10,0.08);text-decoration:none;transition:all 0.25s;"
                                                   onmouseover="this.style.background='rgba(255,159,10,0.18)';this.style.transform='translateY(-1px)'"
                                                   onmouseout="this.style.background='rgba(255,159,10,0.08)';this.style.transform=''">
                                                    <i class="fas fa-eye"></i> عرض
                                                </a>
                                                 <a href="/{{ r.image_path }}" download="{{ r.scan_type }}" class="btn-action-whatsapp" title="تحميل الملف لإرساله" onclick="window.open('https://wa.me/{{ p.phone1|string|replace('+', '')|replace(' ', '') }}', '_blank'); alert('سيتم تحميل الصورة الآن. يرجى سحبها إلى نافذة الواتساب التي فُتحت.');">
                                                     <i class="fab fa-whatsapp"></i> واتساب
                                                 </a>
                                                {% else %}
                                                <span style="font-size:0.78rem;opacity:0.4;">لا يوجد ملف</span>
                                                {% endif %}
                                            </div>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                        {% else %}
                        <div class="empty-state-pro">
                            <span class="empty-icon">🩻</span>
                            <p>لا توجد سجلات أشعة مسجلة لهذا المريض</p>
                        </div>
                        {% endif %}
                    </div>

                </div>

                <!-- Archive Section -->
                <div class="section-content" id="archive-section" style="display: none;">
                    <div class="glass-card p-0">
                        <div class="bg-secondary text-white p-3 fw-bold"><i class="fas fa-file-archive me-2"></i> أرشيف الملفات والأشعة</div>
                        <div class="p-4">
                            <form method="POST" enctype="multipart/form-data" class="archive-form-box">
                                <h6 class="fw-bold mb-3"><i class="fas fa-cloud-upload-alt me-2 text-primary"></i> رفع ملف جديد</h6>
                                <div class="row g-3">
                                    <div class="col-md-5"><input type="text" name="file_name" class="form-control" placeholder="وصف الملف (مثال: أشعة صدر)..." required></div>
                                    <div class="col-md-5"><input type="file" name="archive_file" class="form-control" required></div>
                                    <div class="col-md-2"><button type="submit" name="upload_archive" class="btn btn-primary w-100 btn-round shadow-sm"><i class="fas fa-save me-1"></i> حفظ</button></div>
                                </div>
                            </form>
                            <table class="table table-hover align-middle">
                                <thead><tr><th class="text-center">التاريخ</th><th class="text-center">الوصف</th><th class="text-center">عرض</th></tr></thead>
                                <tbody>
                                    {% for r in rads %}
                                        <tr>
                                            <td class="text-center"><small class="text-muted">{{ dt(r.created_at, '%Y-%m-%d %I:%M %p') }}</small></td>
                                            <td class="fw-bold text-center">{{ r.scan_type }}</td>
                                            <td class="text-center"><a href="/{{ r.image_path }}" target="_blank" class="btn btn-sm btn-outline-primary btn-round px-3"><i class="fas fa-external-link-alt me-1"></i> فتح الملف</a>
                                                 <a href="/{{ r.image_path }}" download="{{ r.scan_type }}" class="btn-action-whatsapp" title="تحميل الملف لإرساله" onclick="window.open('https://wa.me/{{ p.phone1|string|replace('+', '')|replace(' ', '') }}', '_blank'); alert('سيتم تحميل الصورة الآن. يرجى سحبها إلى نافذة الواتساب التي فُتحت.');">
                                                     <i class="fab fa-whatsapp"></i> واتساب
                                                 </a></td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>



    <script>
        // PDF & WhatsApp Share System (Local-Safe)
        async function robustShare(url, filename, phone) {
            const btn = event.currentTarget || this; 
            const original = btn.innerHTML;
            
            try {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ...';
                btn.style.pointerEvents = 'none';

                const iframe = document.createElement('iframe');
                iframe.style.cssText = 'position:fixed; top:-10000px; left:-10000px; width:850px; height:1200px;';
                document.body.appendChild(iframe);
                iframe.src = window.location.origin + url;
                
                iframe.onload = async function() {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        const el = doc.querySelector('.rx-card, .lab-report, .report-box, body');
                        
                        // Copy image to clipboard
                        if (window.html2canvas) {
                             const canvas = await html2canvas(el, { scale: 1.5, useCORS: true });
                             canvas.toBlob(b => {
                                 if (navigator.clipboard && window.ClipboardItem) {
                                     navigator.clipboard.write([new ClipboardItem({ "image/png": b })]).catch(e => console.warn(e));
                                 }
                             });
                        }

                        // Download PDF
                        if (window.html2pdf) {
                             await html2pdf().set({ margin: 10, filename: filename + '.pdf' }).from(el).save();
                        }

                        const msg = "مرحباً، إليك ملف " + filename + " الخاص بك. التقرير متاح الآن كملف PDF في جهازك، وصوره منسوخة للذاكرة.";
                        const waUrl = "https://wa.me/" + phone.replace(/\\D/g, '') + "?text=" + encodeURIComponent(msg);
                        window.open(waUrl, '_blank');
                        
                        setTimeout(() => alert("✅ جاهز! الملف في التنزيلات، والصورة منسوخة للذاكرة لإرسالها بالضغط على (Ctrl+V) في الواتساب."), 300);
                    } catch (e) {
                         console.error(e);
                         window.open("https://wa.me/" + phone.replace(/\\D/g, ''), '_blank');
                    } finally {
                        btn.innerHTML = original;
                        btn.style.pointerEvents = 'auto';
                        if (iframe.parentNode) document.body.removeChild(iframe);
                    }
                };
            } catch (err) {
                btn.innerHTML = original;
                btn.style.pointerEvents = 'auto';
            }
        }
    </script>




    """ + footer_html
    
    def parse_rx(text):
        if not text: return ""
        import re
        # Split by common delimiters like newlines, full stops followed by space, dashes, or long dashes
        items = re.split(r'\n|(?<=\.)\s+|(?<=\!)\s+|(?<=\?)\s+|—|- |\*/', text)
        items = [i.strip() for i in items if i.strip()]
        if not items: return text
        
        # Build a neat bulleted list with RX symbol
        html_out = '<ul style="list-style: none; padding: 0; margin: 0;">'
        for item in items:
            # Clean up leading dashes or numbers if any
            clean_item = re.sub(r'^[\d\.\-\—\*\s]+', '', item).strip()
            if clean_item:
                html_out += f'<li style="margin-bottom: 6px; display: flex; gap: 8px; font-size: 0.85rem; line-height: 1.4;"><span style="color: #bf5af2; font-weight: 800;">•</span> <span>{clean_item}</span></li>'
        html_out += '</ul>'
        return html_out

    from config import format_datetime, local_now_naive
    
    html = html.replace('{{ dt(pr.created_at) }}', '{{ dt(pr.created_at, "%Y-%m-%d %I:%M %p") }}')
    # Update prescription cell
    html = html.replace('{{ pr.medicine_name|replace(\'\\\\n\', \' — \')|safe }}', '{{ parse_rx(pr.medicine_name)|safe }}')
    # Update medical history plan cell
    html = html.replace('{{ h.plan }}', '{{ parse_rx(h.plan)|safe }}')

    return render_template_string(html, p=p, history=history, prescs=prescs, labs=labs, rads=rads, file_exists=file_exists, dt=format_datetime, format_dt=format_datetime, now=local_now_naive(), parse_rx=parse_rx)
