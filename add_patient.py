from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, log_activity # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
import os
import time
import random
import base64

add_patient_bp = Blueprint('add_patient', __name__)

@add_patient_bp.route('/capture_photo')
def capture_photo_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>التقاط صورة المريض</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { background: #000; color: white; display: flex; flex-direction: column; height: 100vh; margin: 0; overflow: hidden; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            .cam-container { flex: 1; position: relative; display: flex; align-items: center; justify-content: center; }
            #video { width: 100%; height: 100%; object-fit: cover; }
            .controls { background: rgba(0,0,0,0.8); padding: 20px; display: flex; justify-content: center; gap: 15px; border-top: 1px solid #333; }
            .btn-capture { width: 80px; height: 80px; border-radius: 50%; border: 5px solid white; background: #ff3b30; transition: all 0.2s; cursor: pointer; }
            .btn-capture:active { transform: scale(0.9); background: #cc2f26; }
            .preview-container { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: #000; display: none; flex-direction: column; }
            #previewImg { flex: 1; object-fit: contain; }
            .title-bar { position: absolute; top: 20px; right: 20px; background: rgba(0,0,0,0.5); padding: 5px 15_px; border-radius: 20px; backdrop-filter: blur(10px); z-index: 10; }
        </style>
    </head>
    <body>
        <div class="title-bar"><i class="fas fa-camera me-2"></i> التقاط صورة المريض</div>
        <div class="cam-container">
            <video id="video" autoplay playsinline></video>
            <div class="preview-container" id="previewBox">
                <img id="previewImg">
                <div class="controls">
                    <button class="btn btn-lg btn-light rounded-pill px-5 fw-bold" onclick="savePhoto()">
                        <i class="fas fa-check me-2"></i> حفظ واستمرار
                    </button>
                    <button class="btn btn-lg btn-outline-light rounded-pill px-5 fw-bold" onclick="retake()">
                        <i class="fas fa-redo me-2"></i> إعادة التقاط
                    </button>
                </div>
            </div>
        </div>
        <div class="controls" id="mainControls">
            <button class="btn-capture" onclick="takeSnapshot()"></button>
        </div>
        <canvas id="canvas" class="d-none"></canvas>
        <script>
            let stream = null;
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const previewBox = document.getElementById('previewBox');
            const previewImg = document.getElementById('previewImg');
            let capturedData = null;

            async function startCam() {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 1280, height: 720 } });
                    video.srcObject = stream;
                } catch(e) { alert("تعذر الوصول للكاميرا"); window.close(); }
            }

            function takeSnapshot() {
                canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                capturedData = canvas.toDataURL('image/jpeg', 0.6);
                previewImg.src = capturedData;
                previewBox.style.display = 'flex';
                document.getElementById('mainControls').style.display = 'none';
            }

            function retake() { previewBox.style.display = 'none'; document.getElementById('mainControls').style.display = 'flex'; }

            function savePhoto() {
                if(window.opener) {
                    window.opener.postMessage({ type: 'PATIENT_PHOTO', data: capturedData }, '*');
                    window.close();
                }
            }
            startCam();
            window.onbeforeunload = () => { if(stream) stream.getTracks().forEach(t => t.stop()); };
        </script>
    </body>
    </html>
    """)

@add_patient_bp.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"
    
    cursor = conn.cursor(dictionary=True)
    
    # --- Optimized: Schema is already updated in Migration ---

    error = None

    if request.method == 'POST':
        file_num = "P-" + str(random.randint(10000, 99999))
        name = request.form.get('full_name', '')
        name_en = request.form.get('full_name_en', '')
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        
        # Handle Photo Upload
        photo_path = None
        upload_dir_name = 'uploads/patients/'
        target_dir = os.path.join(os.path.dirname(__file__), upload_dir_name)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, mode=0o777, exist_ok=True)
            
        if 'photo' in request.files and request.files['photo'].filename != '':
            photo_file = request.files['photo']
            ext = os.path.splitext(photo_file.filename)[1]
            file_name = f"photo_{int(time.time())}{ext}"
            target_file = os.path.join(target_dir, file_name)
            db_path = upload_dir_name + file_name
            
            try:
                photo_file.save(target_file)
                photo_path = db_path
            except:
                pass 
                
        elif request.form.get('photo_base64'):
            data = request.form.get('photo_base64')
            import re
            match = re.search(r'^data:image/(\w+);base64,', data)
            if match:
                type_ext = match.group(1).lower()
                if type_ext not in ['jpg', 'jpeg', 'gif', 'png']:
                    type_ext = 'jpeg'
                data = data[match.end():]
            else:
                type_ext = 'jpeg'
                data = data.replace('data:image/jpeg;base64,', '').replace('data:image/png;base64,', '').replace(' ', '+')
                
            try:
                decoded_data = base64.b64decode(data)
                file_name = f"cam_{int(time.time())}.{type_ext}"
                target_file = os.path.join(target_dir, file_name)
                db_path = upload_dir_name + file_name
                
                with open(target_file, 'wb') as f:
                    f.write(decoded_data)
                
                photo_path = db_path
            except:
                pass 

        # Check for duplicate Name
        cursor.execute("SELECT patient_id FROM patients WHERE full_name_ar = %s", (name,))
        res = cursor.fetchone()
        
        if res:
            error = f"عذراً، الاسم ( {name} ) مسجل مسبقاً في النظام."
        
        if not error:
            from config import local_now_naive
            now_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
            sql = "INSERT INTO patients (file_number, full_name_ar, full_name_en, date_of_birth, gender, phone1, address, photo, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            if conn.is_pg: sql += " RETURNING patient_id"

            try:
                cursor.execute(sql, (file_num, name, name_en, dob, gender, phone, address, photo_path, now_ts))
                new_id = cursor.lastrowid
                conn.commit()
                log_activity(session.get('user_id'), "تسجيل مريض جديد", f"تم إضافة المريض: {name} برقم ملف: {file_num}")
                return redirect(url_for('add_patient.add_patient', success_id=new_id))
            except Exception as e:
                error = "خطأ في التسجيل: " + str(e)

    success_id = request.args.get('success_id')
    new_patient = None
    if success_id:
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (success_id,))
        new_patient = cursor.fetchone()

    html = header_html + """
    <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
    <style>
        .reg-wrapper { display: flex; height: calc(100vh - 100px); gap: 15px; padding: 15px; animation: fadeIn 0.4s ease-out; overflow: hidden; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .reg-photo-panel { flex: 0 0 260px; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 18px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
        
        .photo-preview-box { width: 150px; height: 150px; border-radius: 50%; border: 3px solid var(--border); background: var(--input-bg); display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative; margin-bottom: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
        .photo-preview-box img { width: 100%; height: 100%; object-fit: cover; }
        .photo-preview-box i { font-size: 3.5rem; color: var(--text); opacity: 0.15; }
        .cam-btn-group { display: flex; gap: 8px; width: 100%; }
        .btn-cam-action { flex: 1; padding: 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--border); background: var(--card); color: var(--text); }
        .btn-cam-action.primary { background: linear-gradient(135deg, #007aff 0%, #0056b3 100%); color: white !important; border: none; }
        
        .reg-form-panel { flex: 1; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 25px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); display: flex; flex-direction: column; overflow: hidden; }
        

        .form-row { display: grid; gap: 15px; margin-bottom: 15px; }
        .row-large { grid-template-columns: 1fr 1fr; }
        .row-compact { grid-template-columns: 1.2fr 1fr 1fr; }
        
        .field-wrap { position: relative; }
        .field-label { font-size: 0.75rem; font-weight: 800; color: var(--text); opacity: 0.6; margin-bottom: 4px; display: block; padding-right: 5px; }
        .reg-input { width: 100%; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); font-weight: 600; font-size: 0.9rem; transition: all 0.2s; }
        .reg-input:focus { outline: none; border-color: #5e5ce6; box-shadow: 0 0 0 3px rgba(94, 92, 230, 0.1); }
        
        .gender-toggle { display: flex; background: var(--input-bg); border-radius: 12px; padding: 3px; border: 1px solid var(--border); }
        .gender-opt { flex: 1; text-align: center; }
        .gender-opt input { display: none; }
        .gender-opt label { display: block; padding: 8px; border-radius: 9px; cursor: pointer; font-weight: 700; font-size: 0.8rem; margin: 0; opacity: 0.5; color: var(--text); }
        .gender-opt input:checked + label { background: #5e5ce6; color: white !important; opacity: 1; }
        
        .btn-submit-reg { background: #007aff; color: white; border: none; padding: 12px; border-radius: 12px; font-weight: 700; font-size: 1rem; width: 100%; margin-top: 10px; box-shadow: 0 4px 12px rgba(0,122,255,0.2); cursor: pointer; transition: all 0.2s; }
        .btn-submit-reg:hover { background: #0056b3; transform: translateY(-1px); }
        
        .age-dob-card { display: flex; align-items: center; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 2px 5px; transition: all 0.2s; }
        .age-dob-card:focus-within { border-color: #5e5ce6; box-shadow: 0 0 0 3px rgba(94, 92, 230, 0.1); }
        .age-dob-card .reg-input { border: none !important; background: transparent !important; box-shadow: none !important; padding: 10px 8px; }
        .age-dob-card .sep { width: 1px; height: 20px; background: var(--border); margin: 0 5px; opacity: 0.5; }
        
        .barcode-wrap { margin-top: 15px; width: 100%; display: flex; justify-content: center; background: white; border-radius: 10px; padding: 5px; min-height: 60px; border: 1px solid var(--border); opacity: 0; transition: opacity 0.3s; }
        .barcode-wrap.active { opacity: 1; }
        #barcode { max-width: 100%; height: auto; }

        /* Reverted Professional Landscape identity Card */
        .success-card { background: var(--card); backdrop-filter: blur(30px); border: 1px solid var(--border); border-radius: 32px; padding: 25px 35px; box-shadow: 0 40px 100px -30px rgba(0, 0, 0, 0.3); max-width: 680px; width: 95%; position: relative; overflow: hidden; animation: zoomIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; margin-top: -60px; }
        @keyframes zoomIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
        .success-check { width: 42px; height: 42px; background: rgba(40, 199, 111, 0.12); color: #28c76f; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; margin: 0 auto 12px; border: 1px solid rgba(40, 199, 111, 0.2); }
        .patient-id-card-horiz { background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: 20px; padding: 15px; margin-bottom: 20px; text-align: right; display: flex; align-items: center; gap: 20px; box-shadow: inset 0 0 40px rgba(0,0,0,0.015); }
        .id-details-box { flex: 1.5; border-left: 1px solid var(--border); padding-left: 15px; }
        .id-barcode-box-horiz { flex: 1; background: white; padding: 8px; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; border: 1px solid var(--border); }
        .id-photo-horiz { width: 85px; height: 85px; border-radius: 16px; object-fit: cover; border: 2px solid var(--border); }
        .id-label { font-size: 0.6rem; font-weight: 800; color: #5e5ce6; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 2px; display: block; opacity: 0.8; }
        
        /* Colored Actions */
        .btn-act-blue { background: linear-gradient(135deg, #007aff 0%, #0056b3 100%); color: white !important; box-shadow: 0 8px 18px rgba(0,122,255,0.3); }
        .btn-act-green { background: linear-gradient(135deg, #30d158 0%, #248a3d 100%); color: white !important; box-shadow: 0 8px 18px rgba(48,209,88,0.3); }
        .btn-act-indigo { background: linear-gradient(135deg, #5e5ce6 0%, #4a49c9 100%); color: white !important; box-shadow: 0 8px 18px rgba(94,92,230,0.3); }
        
        .action-btn-styled { padding: 12px; border-radius: 16px; width: 100%; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 6px; font-weight: 700; font-size: 0.85rem; flex-direction: column; border: none; }
        .action-btn-styled:hover { transform: translateY(-3px); opacity: 0.95; }
        .container-no-scroll { display: flex; align-items: center; justify-content: center; height: 100vh; width: 100%; overflow: hidden; padding: 10px; }
    </style>

    {% if success_id and new_patient %}
        <div class="container-no-scroll">
            <div class="success-card shadow-lg text-center">
                <div class="success-check animate__animated animate__bounceIn">
                    <i class="fas fa-check"></i>
                </div>
                <h4 class="fw-bold mb-1">تمت الإضافة بنجاح</h4>
                <p class="text-muted extra-small mb-3">تم إنشاء ملف المريض الرقمي بنجاح</p>

                <div class="patient-id-card-horiz">
                    {% if new_patient.photo %}
                        <img src="/{{ new_patient.photo }}" class="id-photo-horiz">
                    {% else %}
                        <div class="id-photo-horiz d-flex align-items-center justify-content-center bg-light">
                            <i class="fas fa-user-circle text-muted fa-2x" style="opacity:0.2"></i>
                        </div>
                    {% endif %}
                    
                    <div class="id-details-box">
                        <span class="id-label">بطاقة المريض الرقمية</span>
                        <h5 class="fw-bold mb-1 text-primary" style="font-size: 1.15rem;">{{ new_patient.full_name_ar }}</h5>
                        <p class="text-muted mb-2 extra-small">{{ new_patient.full_name_en }}</p>
                        <div class="badge bg-primary-subtle text-primary rounded-pill px-3 py-1 fw-bold" style="font-size: 0.8rem;">{{ new_patient.file_number }}</div>
                    </div>

                    <div class="id-barcode-box-horiz">
                        <canvas id="successBarcode" style="width: 100%;"></canvas>
                        <div class="extra-small fw-bold opacity-50">{{ format_dt(now, '%Y-%m-%d %H:%M') }}</div>
                    </div>
                </div>

                <div class="action-group">
                    <div class="row g-2">
                        <div class="col-4">
                            <a href="{{ url_for('book.book') }}?id={{ success_id }}" class="action-btn-styled btn-act-blue text-decoration-none">
                                <i class="fas fa-calendar-plus mb-1"></i>
                                <span>حجز موعد</span>
                            </a>
                        </div>
                        <div class="col-4">
                            <a href="{{ url_for('patient_file.patient_file') }}?id={{ success_id }}" class="action-btn-styled btn-act-green text-decoration-none">
                                <i class="fas fa-file-invoice mb-1"></i>
                                <span>عرض ملف</span>
                            </a>
                        </div>
                        <div class="col-4">
                            <a href="{{ url_for('add_patient.add_patient') }}" class="action-btn-styled btn-act-indigo text-decoration-none">
                                <i class="fas fa-user-plus mb-1"></i>
                                <span>تسجيل جديد</span>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            window.onload = function() {
                try {
                    JsBarcode("#successBarcode", "{{ new_patient.file_number }}", {
                        format: "CODE128",
                        width: 1.5,
                        height: 35,
                        displayValue: false,
                        margin: 0
                    });
                } catch(e) { console.error(e); }
            };
        </script>
{% else %}
        <form method="POST" enctype="multipart/form-data" class="container-fluid">
            <div class="reg-wrapper">
                <div class="reg-photo-panel shadow-sm">
                    <h6 class="fw-bold mb-3 w-100 text-center"><i class="fas fa-camera me-2"></i> صورة المريض</h6>
                    <div class="photo-preview-box" id="pPreview">
                        <i class="fas fa-user-circle"></i>
                        <img id="captured_image" class="d-none">
                    </div>
                    <input type="hidden" name="photo_base64" id="photo_base64">
                    <div class="cam-btn-group">
                        <button type="button" class="btn-cam-action primary" onclick="openCameraWindow()">
                            <i class="fas fa-camera"></i> تسجيل
                        </button>
                        <button type="button" class="btn-cam-action" onclick="document.getElementById('fileInput').click()">
                            <i class="fas fa-upload"></i> رفع
                        </button>
                    </div>
                    <input type="file" id="fileInput" name="photo" class="d-none" accept="image/*" onchange="previewFile(this)">
                    <div id="clearBtnWrap" class="mt-2 d-none">
                        <button type="button" class="btn btn-link text-danger text-decoration-none extra-small fw-bold" onclick="clearPhoto()">حذف الصورة</button>
                    </div>
                    
                    <div class="barcode-wrap" id="barcodeBox">
                        <svg id="barcode"></svg>
                    </div>
                </div>

                <div class="reg-form-panel">
                    <div class="d-flex align-items-center justify-content-between mb-4 pb-2 border-bottom">
                        <h5 class="fw-bold mb-0 text-primary"><i class="fas fa-id-card me-2"></i> استمارة تسجيل مريض جديد</h5>
                    </div>

                    {% if error %}
                        <div class="alert bg-danger-subtle text-danger border-0 extra-small pt-2 pb-2 rounded-3 mb-3">
                            <i class="fas fa-exclamation-circle me-1"></i> {{ error }}
                        </div>
                    {% endif %}

                    <!-- Row 1: Names -->
                    <div class="form-row row-large">
                        <div class="field-wrap">
                            <label class="field-label">اسم المريض (عربي)</label>
                            <input type="text" name="full_name" id="nameAr" class="reg-input" placeholder="الاسم الرباعي..." required oninput="transliterateName(); detectGender()">
                        </div>
                        <div class="field-wrap">
                            <label class="field-label">Patient Name (English)</label>
                            <input type="text" name="full_name_en" id="nameEn" class="reg-input" placeholder="Auto-translated name">
                        </div>
                    </div>

                    <!-- Row 2: Phone, Age, Gender -->
                    <div class="form-row row-compact">
                        <div class="field-wrap">
                            <label class="field-label">رقم الهاتف</label>
                            <input type="text" name="phone" id="phoneInput" class="reg-input" placeholder="07XXXXXXXXX" required>
                        </div>
                        <div class="field-wrap">
                            <label class="field-label">العمر / المواليد</label>
                            <div class="age-dob-card">
                                <input type="number" id="ageInput" class="reg-input" style="width: 65px;" placeholder="سنة" oninput="calculateBirthYear(this.value)">
                                <div class="sep"></div>
                                <input type="date" name="dob" id="dobInput" class="reg-input" style="flex: 1;" required oninput="calculateAge(this.value)">
                            </div>
                        </div>
                        <div class="field-wrap">
                            <label class="field-label">الجنس</label>
                            <div class="gender-toggle">
                                <div class="gender-opt">
                                    <input type="radio" name="gender" value="male" id="g1" checked>
                                    <label for="g1">ذكر</label>
                                </div>
                                <div class="gender-opt">
                                    <input type="radio" name="gender" value="female" id="g2">
                                    <label for="g2">أنثى</label>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Row 3: Address -->
                    <div class="form-row row-large">
                        <div class="field-wrap">
                            <label class="field-label">المحافظة</label>
                            <select id="govSelect" class="reg-input" onchange="updateDistricts()">
                                <option value="">اختر المحافظة...</option>
                            </select>
                        </div>
                        <div class="field-wrap">
                            <label class="field-label">المنطقة</label>
                            <select id="distSelect" class="reg-input" onchange="updateAddress()">
                                <option value="">اختر المنطقة...</option>
                            </select>
                        </div>
                        <input type="hidden" name="address" id="fullAddress">
                    </div>

                    <button type="submit" class="btn-submit-reg">
                        <i class="fas fa-user-plus me-2"></i> إتمام التسجيل والحفظ
                    </button>
                    
                    <div class="text-center mt-3">
                        <a href="{{ url_for('patients.patients') }}" class="text-muted extra-small text-decoration-none">إلغاء والعودة للقائمة</a>
                    </div>
                </div>
            </div>
        </form>
    {% endif %}

    <script>
        const photoB64 = document.getElementById('photo_base64');
        const imgEl = document.getElementById('captured_image');
        const pPreview = document.getElementById('pPreview');
        const clearBtn = document.getElementById('clearBtnWrap');

        function openCameraWindow() {
            const w = 800; const h = 600;
            const left = (screen.width/2)-(w/2); const top = (screen.height/2)-(h/2);
            window.open("{{ url_for('add_patient.capture_photo_page') }}", "CapturePhoto", `width=${w},height=${h},top=${top},left=${left},toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no`);
        }

        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'PATIENT_PHOTO') {
                const data = event.data.data;
                photoB64.value = data; imgEl.src = data;
                imgEl.classList.remove('d-none'); pPreview.querySelector('i').classList.add('d-none');
                clearBtn.classList.remove('d-none');
            }
        });

        function previewFile(input) {
            if(input.files && input.files[0]) {
                let r = new FileReader(); r.onload = e => {
                    imgEl.src = e.target.result; imgEl.classList.remove('d-none');
                    pPreview.querySelector('i').classList.add('d-none'); clearBtn.classList.remove('d-none');
                    photoB64.value = ''; 
                };
                r.readAsDataURL(input.files[0]);
            }
        }

        function clearPhoto() {
            photoB64.value = ''; imgEl.src = ''; imgEl.classList.add('d-none');
            pPreview.querySelector('i').classList.remove('d-none'); clearBtn.classList.add('d-none');
            document.getElementById('fileInput').value = '';
        }

        const iraqLocs = {
            "ذي قار": ["الناصرية", "الرفاعي", "الشطرة", "الغراف", "سوق الشيوخ", "الجبايش", "قلعة سكر", "الدواية", "الإصلاح", "سيد دخيل", "البطحاء", "الفضليـة", "العكيكة", "كرمة بني سعيد", "الطار", "المنار", "الفجر", "أور", "النصر", "الفهود", "الحمار", "الخميسية"],
            "بغداد": ["الكرخ", "رصافة", "الكاظمية", "الأعظمية", "المنصور", "الكرادة", "الدورة", "مدينة الصدر", "الغزالية", "العامرية", "الزعفرانية", "ببغداد الجديدة", "الشعلة", "حي العامل"],
            "البصرة": ["البصرة (المركز)", "الزبير", "القرنة", "شط العرب", "أبو الخصيب", "الفاو", "المدينة"],
            "النجف": ["النجف (المركز)", "الكوفة", "المناذرة", "المشخاب"],
            "كربلاء": ["كربلاء (المركز)", "الهندية (طويريج)", "عين التمر", "الحسينية"],
            "ميسان": ["العمارة", "الميمونة", "المجر الكبير", "علي الغربي", "الكحلاء"]
        };

        const govSelect = document.getElementById('govSelect');
        const distSelect = document.getElementById('distSelect');
        const fullAddr = document.getElementById('fullAddress');

        if(govSelect) {
            Object.keys(iraqLocs).sort().forEach(gov => {
                let opt = new Option(gov, gov); govSelect.add(opt);
            });
        }

        function updateDistricts() {
            distSelect.innerHTML = '<option value="">المنطقة...</option>';
            if (govSelect.value && iraqLocs[govSelect.value]) {
                iraqLocs[govSelect.value].sort().forEach(d => distSelect.add(new Option(d, d)));
            }
            updateAddress();
        }

        const transDict = {
            'علي': 'Ali', 'على': 'Ali', 'محمد': 'Mohamed', 'محمود': 'Mahmoud', 'احمد': 'Ahmed', 'أحمد': 'Ahmed',
            'حسين': 'Hussein', 'كريم': 'Kareem', 'سجاد': 'Sajjad', 'حيدر': 'Haider', 'مصطفى': 'Mustafa', 
            'مرتضى': 'Murtadha', 'كاظم': 'Kadhim', 'عباس': 'Abbas', 'جاسم': 'Jassim', 'فاطمة': 'Fatima', 
            'زينب': 'Zainab', 'مريم': 'Maryam', 'نور': 'Noor', 'زهراء': 'Zahraa', 'رقية': 'Ruqayya', 
            'سارة': 'Sara', 'ساره': 'Sara', 'ابراهيم': 'Ibrahim', 'إبراهيم': 'Ibrahim', 'يوسف': 'Yousif',
            'ياسين': 'Yaseen', 'طه': 'Taha', 'عمر': 'Omar', 'زيد': 'Zaid', 'امير': 'Amir', 'أمير': 'Amir',
            'ليث': 'Laith', 'حسن': 'Hassan', 'عبد': 'Abd'
        };

        const charMap = {
           'ا':'a','أ':'a','إ':'a','ب':'b','ت':'t','ث':'th','ج':'j','ح':'h','خ':'kh','د':'d','ذ':'dh','ر':'r','ز':'z','س':'s','ش':'sh','ص':'s','ض':'d','ط':'t','ظ':'z','ع':'a','غ':'gh','ف':'f','ق':'q','ك':'k','ل':'l','م':'m','ن':'n','ه':'h','و':'w','ي':'y','ى':'y','ة':'h','ء':'a','آ':'a','ؤ':'u','ئ':'e',' ':' '
        };

        function fallbackTrans(word) {
            let res = '';
            for(let char of word) {
                res += charMap[char] || '';
            }
            return res.charAt(0).toUpperCase() + res.slice(1);
        }

        function transliterateName() {
            const arName = document.getElementById('nameAr').value.trim();
            const nameEn = document.getElementById('nameEn');
            if(!arName) {
                nameEn.value = '';
                document.getElementById('barcodeBox').classList.remove('active');
                return;
            }
            let result = [];
            arName.split(' ').forEach(part => {
                if(part.trim() == "") return;
                let cleanPart = part.replace(/[ًٌٍَُِّْ]/g, ""); // strip tashkeel
                if(transDict[cleanPart]) {
                    result.push(transDict[cleanPart]);
                } else {
                    result.push(fallbackTrans(cleanPart));
                }
            });
            const finalEn = result.join(' ');
            nameEn.value = finalEn;
            
            // Barcode Generation
            document.getElementById('barcodeBox').classList.add('active');
            try {
                JsBarcode("#barcode", finalEn || "PT-" + Date.now(), {
                    format: "CODE128", lineColor: "#000", width: 1.5, height: 40, displayValue: false
                });
            } catch(e) {}
        }

        function detectGender() {
            const name = document.getElementById('nameAr').value.trim().split(' ')[0];
            const females = ['زينب','مريم','هند','سعاد','نور','هدى','منى','ضحى','سجى','تقى','فاطمة','خديجة','عائشة','سارة','نورا','ليلى'];
            const isF = females.includes(name) || (name.endsWith('ة') && !['حمزة','طلحة','عبيدة','أسامة','معاوية'].includes(name));
            if(document.getElementById(isF ? 'g2' : 'g1')) document.getElementById(isF ? 'g2' : 'g1').checked = true;
        }

        function calculateBirthYear(age) {
            if(age > 0) document.getElementById('dobInput').value = (new Date().getFullYear() - age) + "-01-01";
        }

        function calculateAge(dob) {
            if(!dob) return;
            let age = new Date().getFullYear() - new Date(dob).getFullYear();
            if(document.getElementById('ageInput')) document.getElementById('ageInput').value = age;
        }
    </script>
    """ + footer_html

    return render_template_string(html, success_id=success_id, new_patient=new_patient, error=error)
