from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db
from header import header_html
from footer import footer_html
import os
import time

edit_patient_bp = Blueprint('edit_patient', __name__)

@edit_patient_bp.route('/edit_patient', methods=['GET', 'POST'])
def edit_patient():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    id = request.args.get('id', type=int)
    if not id:
        return redirect(url_for('patients.patients'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (id,))
    p = cursor.fetchone()
    
    if not p:
        conn.close()
        return redirect(url_for('patients.patients'))
        
    # Ensure date_of_birth is a string YYYY-MM-DD
    if p.get('date_of_birth'):
        try:
            # If it's a date/datetime object, convert to string
            if hasattr(p['date_of_birth'], 'strftime'):
                p['date_of_birth'] = p['date_of_birth'].strftime('%Y-%m-%d')
            else:
                p['date_of_birth'] = str(p['date_of_birth'])
        except:
            pass

    if request.method == 'POST' and 'update' in request.form:
        name = request.form.get('full_name_ar', '')
        name_en = request.form.get('full_name_en', '')
        phone = request.form.get('phone1', '')
        dob = request.form.get('date_of_birth')
        if not dob:
            flash("يرجى تحديد تاريخ الميلاد", "warning")
            return redirect(url_for('edit_patient.edit_patient', id=id))

        gender = request.form.get('gender', 'ذكر')
        province = request.form.get('province', '')
        area = request.form.get('area', '')
        address = (province + ' - ' + area).strip(' - ')
        
        # Handle Photo Upload
        photo_path = p.get('photo', '')
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
            except Exception:
                pass
                
        # Update data
        cursor.execute("""
            UPDATE patients 
            SET full_name_ar = %s, full_name_en = %s, phone1 = %s, address = %s, date_of_birth = %s, gender = %s, photo = %s 
            WHERE patient_id = %s
        """, (name, name_en, phone, address, dob, gender, photo_path, id))
        
        conn.commit()
        conn.close()
        flash("تم تحديث بيانات المريض بنجاح", "success")
        return redirect(url_for('patient_file.patient_file', id=id))

    # Parse address into province and area
    p_addr = p.get('address', '') if p.get('address') else ''
    p_province = ''
    p_area = ''
    if ' - ' in p_addr:
        parts = p_addr.split(' - ', 1)
        p_province = parts[0]
        p_area = parts[1]
    else:
        p_province = p_addr

    photo_url = ''
    if p.get('photo'):
        photo_url = '/' + p['photo'] if not '://' in p['photo'] else p['photo']

    html = header_html + """
    <style>
        .reg-wrapper { display: flex; height: calc(100vh - 100px); gap: 15px; padding: 15px; animation: fadeIn 0.4s ease-out; overflow: hidden; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .reg-photo-panel { flex: 0 0 250px; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 18px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
        .photo-preview-box { width: 140px; height: 140px; border-radius: 50%; border: 3px solid var(--border); background: var(--input-bg); display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative; margin-bottom: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
        .photo-preview-box img { width: 100%; height: 100%; object-fit: cover; }
        
        .reg-form-panel { flex: 1; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 25px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); display: flex; flex-direction: column; overflow: hidden; }
        
        .form-row { display: grid; gap: 15px; margin-bottom: 15px; }
        .row-large { grid-template-columns: 1fr 1fr; }
        .row-compact { grid-template-columns: 1.2fr 1fr 1fr; }
        
        .field-label { font-size: 0.75rem; font-weight: 800; color: var(--text); opacity: 0.6; margin-bottom: 4px; display: block; padding-right: 5px; }
        .reg-input { width: 100%; padding: 11px 14px; border-radius: 12px; border: 1px solid var(--border); background: var(--input-bg); color: var(--text); font-weight: 600; font-size: 0.9rem; transition: all 0.2s; }
        .reg-input:focus { outline: none; border-color: #007aff; box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1); }
        
        .gender-toggle { display: flex; background: var(--input-bg); border-radius: 12px; padding: 3px; border: 1px solid var(--border); }
        .gender-opt { flex: 1; text-align: center; }
        .gender-opt input { display: none; }
        .gender-opt label { display: block; padding: 8px; border-radius: 9px; cursor: pointer; font-weight: 700; font-size: 0.8rem; margin: 0; opacity: 0.5; color: var(--text); }
        .gender-opt input:checked + label { background: #5e5ce6; color: white !important; opacity: 1; }
        
        .btn-submit-reg { background: linear-gradient(135deg, #007aff 0%, #0056b3 100%); color: white; border: none; padding: 12px; border-radius: 12px; font-weight: 700; font-size: 1rem; width: 100%; margin-top: 10px; box-shadow: 0 4px 12px rgba(0,122,255,0.2); transition: all 0.2s; }
        .btn-submit-reg:hover { transform: translateY(-1px); box-shadow: 0 6px 15px rgba(0,122,255,0.3); }
        
        .age-dob-card { display: flex; align-items: center; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1px 5px; }
        .age-num { border: none; background: transparent; width: 50px; text-align: center; font-weight: 800; font-size: 1rem; padding: 8px 0; color: #007aff; outline: none; }
        .sep { width: 1px; height: 25px; background: var(--border); margin: 0 5px; }
    </style>

    <div class="reg-wrapper container-fluid">
        <!-- Photo Panel -->
        <div class="reg-photo-panel shadow-sm text-center">
            <div class="photo-preview-box" id="photoPreview">
                {% if photo_url %}
                    <img src="{{ photo_url }}" onerror="this.onerror=null; this.src='/{{ p.photo }}';">
                {% else %}
                    <i class="fas fa-user-circle text-muted fa-4x opacity-25"></i>
                {% endif %}
            </div>
            <label class="btn-submit-reg py-2" style="font-size: 0.8rem; background: var(--input-bg); color: var(--text); border: 1px solid var(--border); box-shadow: none; cursor: pointer;">
                <i class="fas fa-image me-1"></i> تغيير الصورة
                <input type="file" name="photo" style="display:none;" onchange="previewImg(this)">
            </label>
        </div>

        <!-- Form Panel -->
        <div class="reg-form-panel">
            <div class="d-flex justify-content-between align-items-center mb-3 border-bottom pb-2">
                <h5 class="fw-bold mb-0 text-primary"><i class="fas fa-user-edit me-2"></i> تعديل بيانات المريض</h5>
                <div class="badge bg-primary-subtle text-primary border px-3 py-2 fw-bold">رقم الملف: {{ p.file_number }}</div>
            </div>

            <form method="POST" enctype="multipart/form-data" class="text-end">
                <!-- Row 1: Names -->
                <div class="form-row row-large">
                    <div class="field-wrap">
                        <label class="field-label">اسم المريض الكامل (عربي)</label>
                        <input type="text" name="full_name_ar" id="nameAr" class="reg-input" value="{{ p.full_name_ar }}" onkeyup="transliterateName(this.value)" required>
                    </div>
                    <div class="field-wrap">
                        <label class="field-label">Patient Name (English)</label>
                        <input type="text" name="full_name_en" id="nameEn" class="reg-input text-start" value="{{ p.full_name_en }}" placeholder="Auto-translated name">
                    </div>
                </div>

                <!-- Row 2: Phone, DOB, Gender -->
                <div class="form-row row-compact">
                    <div class="field-wrap">
                        <label class="field-label">رقم الهاتف</label>
                        <input type="text" name="phone1" class="reg-input" value="{{ p.phone1 if p.phone1 else '' }}" placeholder="07XXXXXXXXX" required>
                    </div>
                    <div class="field-wrap">
                        <label class="field-label">العمر / المواليد</label>
                        <div class="age-dob-card">
                            <input type="number" id="pAge" class="age-num" placeholder="00" onchange="calculateDob(this.value)">
                            <div class="sep"></div>
                            <input type="date" name="date_of_birth" id="pDob" class="reg-input border-0 py-1" value="{{ p.date_of_birth or '' }}" onchange="calculateAge(this.value)" style="background:transparent;" required>
                        </div>
                    </div>
                    <div class="field-wrap">
                        <label class="field-label">الجنس</label>
                        <div class="gender-toggle">
                            <div class="gender-opt">
                                <input type="radio" name="gender" id="gMale" value="ذكر" {% if p.gender == 'ذكر' %}checked{% endif %}>
                                <label for="gMale">ذكر</label>
                            </div>
                            <div class="gender-opt">
                                <input type="radio" name="gender" id="gFemale" value="أنثى" {% if p.gender == 'أنثى' %}checked{% endif %}>
                                <label for="gFemale">أنثى</label>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Row 3: Address -->
                <div class="form-row row-large">
                    <div class="field-wrap">
                        <label class="field-label">المحافظة</label>
                        <select name="province" class="reg-input">
                            <option value="">اختر المحافظة...</option>
                            {% set provinces = ['بغداد', 'البصرة', 'نينوى', 'أربيل', 'النجف', 'كربلاء', 'ذي قار', 'بابل', 'الأنبار', 'ميسان', 'المثنى', 'ديالى', 'صلاح الدين', 'كركوك', 'السليمانية', 'دهوك', 'واسط', 'القادسية'] %}
                            {% for prov in provinces %}
                                <option value="{{ prov }}" {% if p_province == prov %}selected{% endif %}>{{ prov }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="field-wrap">
                        <label class="field-label">المنطقة</label>
                        <input type="text" name="area" class="reg-input" value="{{ p_area }}" placeholder="اسم المنطقة أو الحي...">
                    </div>
                </div>

                <div class="mt-2">
                    <button type="submit" name="update" class="btn-submit-reg">
                        <i class="fas fa-save me-1"></i> حفظ التعديلات وتحديث الملف
                    </button>
                    <div class="text-center mt-3">
                        <a href="{{ url_for('patient_file.patient_file', id=p.patient_id) }}" class="text-muted text-decoration-none extra-small">
                            إلغاء والعودة لملف المريض
                        </a>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <script>
        function previewImg(input) {
            if (input.files && input.files[0]) {
                var reader = new FileReader();
                reader.onload = function(e) { 
                    const preview = document.querySelector('#photoPreview img');
                    if(preview) preview.src = e.target.result;
                    else {
                        document.querySelector('#photoPreview').innerHTML = `<img src="${e.target.result}" style="width:100%; height:100%; object-fit:cover;">`;
                    }
                }
                reader.readAsDataURL(input.files[0]);
            }
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

        function transliterateName(arName) {
            const nameEn = document.getElementById('nameEn');
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
            nameEn.value = result.join(' ');
        }

        function calculateAge(dob) {
            if(!dob || dob === "") return;
            const birthDate = new Date(dob);
            if (isNaN(birthDate.getTime())) return;
            const age = new Date().getFullYear() - birthDate.getFullYear();
            document.getElementById('pAge').value = age;
        }

        function calculateDob(age) {
            if(!age || age === "" || age <= 0) return;
            const year = new Date().getFullYear() - parseInt(age);
            const currentDob = document.getElementById('pDob').value;
            // Only update if it's a significant change to avoid resetting day/month if not needed
            document.getElementById('pDob').value = `${year}-01-01`;
        }

        window.onload = function() {
            const dob = document.getElementById('pDob').value;
            if(dob) calculateAge(dob);
        }
    </script>
    """ + footer_html
    
    return render_template_string(html, p=p, photo_url=photo_url, p_province=p_province, p_area=p_area)
