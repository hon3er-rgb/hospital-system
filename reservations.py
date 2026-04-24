from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from datetime import timedelta
from config import get_db, can_access, local_now_naive, local_today_str # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

reservations_bp = Blueprint('reservations', __name__)

@reservations_bp.route('/reservations', methods=['GET'])
def reservations():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    filter_date = request.args.get('date', '')
    search_q = request.args.get('q', '')
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    sql = """
        SELECT a.*, p.full_name_ar, p.file_number, p.phone1, d.department_name_ar, u.full_name_ar as doctor_name 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        JOIN departments d ON a.department_id = d.department_id 
        LEFT JOIN users u ON a.doctor_id = u.user_id 
        WHERE a.status != 'cancelled_hidden'
    """
    params = []
    
    ln = local_now_naive()
    today_str = local_today_str()
    tomorrow_str = (ln + timedelta(days=1)).strftime('%Y-%m-%d')
    week_str = ln.strftime('%Y-%W')
    month_str = ln.strftime('%Y-%m')

    if filter_date == 'today':
        sql += " AND DATE(a.appointment_date) = %s"
        params.append(today_str)
    elif filter_date == 'tomorrow':
        sql += " AND DATE(a.appointment_date) = %s"
        params.append(tomorrow_str)
    elif filter_date == 'week':
        sql += " AND strftime('%Y-%W', a.appointment_date) = %s"
        params.append(week_str)
    elif filter_date == 'month':
        sql += " AND strftime('%Y-%m', a.appointment_date) = %s"
        params.append(month_str)
    elif filter_date == 'upcoming':
        sql += " AND a.appointment_date >= %s"
        params.append(today_str)

    elif filter_date:
        sql += " AND DATE(a.appointment_date) = %s"
        params.append(filter_date)
        
    if search_q:
        sql += " AND (p.full_name_ar LIKE %s OR p.file_number LIKE %s)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])
        
    sql += " ORDER BY a.appointment_date DESC, a.created_at DESC LIMIT 100"
    
    cursor.execute(sql, params)
    result = cursor.fetchall()
    
    html = header_html + """
    <div class="container-fluid py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="fw-bold text-primary"><i class="fas fa-calendar-alt me-2"></i> إدارة الحجوزات</h3>
                <p class="text-muted small mb-0">لوحة تحكم شاملة لكافة المواعيد والحجوزات</p>
            </div>
        </div>

        <!-- Controls -->
        <style>
            :root {
                --res-bg: #f5f6f8;
                --res-card: #ffffff;
                --res-text: #2c3e50;
                --res-border: #e1e4e8;
                --res-input: #ffffff;
            }

            

            .res-body { background: var(--res-bg); color: var(--res-text); min-height: 100vh; transition: background 0.3s; }
            
            .glass-card {
                background: var(--res-card);
                border: 1px solid var(--res-border);
                border-radius: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.03);
                margin-bottom: 2rem;
                overflow: hidden;
            }

            .form-control { 
                background-color: var(--res-input) !important; 
                color: var(--res-text) !important; 
                border: 1px solid var(--res-border) !important;
                border-radius: 50px !important;
                padding: 12px 20px !important;
            }
            .form-control::placeholder { color: var(--res-text); opacity: 0.5; }
            
            .date-picker-box {
                background: var(--res-input);
                border: 1px solid var(--res-border);
                border-radius: 50px;
                padding: 10px 20px;
                display: flex;
                align-items: center;
                gap: 10px;
                position: relative;
                cursor: pointer;
            }

            .table { color: var(--res-text) !important; background: transparent !important; }
            
            .table thead th { 
                background: rgba(0,0,0,0.02); 
                border-bottom: 2px solid var(--res-border); 
                color: var(--res-text); 
                opacity: 0.7; 
            }
            
            
            .btn-pill { border-radius: 50px; padding: 6px 18px; font-weight: 600; transition: all 0.3s; }
            
            /* Force disable blurs */
            * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }

            /* Print Styles */
            @media print {
                .no-print, .btn, .apple-nav, .glass-card form, .navbar, .footer, footer, header, .no-pjax {
                    display: none !important;
                }
                .badge { background: none !important; color: black !important; padding: 0 !important; border: none !important; }
                body { background: white !important; color: black !important; padding: 0 !important; margin: 0 !important; }
                .container-fluid { width: 100% !important; padding: 0 !important; margin: 0 !important; max-width: none !important; }
                .glass-card { 
                    border: none !important; 
                    box-shadow: none !important; 
                    margin: 0 !important; 
                    border-radius: 0 !important;
                    background: white !important;
                }
                .table { width: 100% !important; border-collapse: collapse !important; font-size: 12pt !important; }
                .table th, .table td { border: 1px solid #000 !important; padding: 8px !important; text-align: center !important; }
                .table thead th { background-color: #f2f2f2 !important; color: black !important; -webkit-print-color-adjust: exact; }
                .fw-bold { font-weight: bold !important; }
                .text-primary { color: black !important; }
                .print-header { display: block !important; text-align: center; margin-bottom: 20px; }
                @page { margin: 1cm; }
            }
            .print-header { display: none; }
        </style>

        <div class="glass-card p-3 p-md-4">
            <form method="GET" class="row g-3" action="{{ url_for('reservations.reservations') }}">
                <!-- Search Input -->
                <div class="col-md-5">
                    <div class="position-relative">
                        <i class="fas fa-search text-muted position-absolute" style="top: 18px; right: 20px; z-index: 5;"></i>
                        <input type="text" name="q" class="form-control ps-5"
                            placeholder="بحث باسم المريض أو رقم الملف..."
                            value="{{ search_q|e }}">
                    </div>
                </div>

                <!-- Date Input -->
                <div class="col-md-5">
                    <div class="date-picker-box">
                        <i class="fas fa-calendar-alt text-primary"></i>
                        <span class="fw-bold flex-grow-1 text-center">
                            {% if filter_date and filter_date not in ['today', 'tomorrow', 'week', 'month', 'upcoming'] %}
                                {{ filter_date }}
                            {% else %}
                                تحديد التاريخ
                            {% endif %}
                        </span>
                        <i class="fas fa-chevron-down text-muted small"></i>
                        <input type="date" name="date" class="position-absolute top-0 start-0 w-100 h-100"
                            style="opacity: 0; cursor: pointer; z-index: 10;"
                            value="{{ filter_date if filter_date not in ['today', 'tomorrow', 'week', 'month', 'upcoming'] else '' }}" onchange="this.form.submit()"
                            onclick="try{this.showPicker()}catch(e){}">
                    </div>
                </div>

                <!-- Filter Button -->
                <div class="col-md-1">
                    <button type="submit" class="btn btn-primary w-100 btn-pill shadow-sm fw-bold h-100 py-2 no-print">
                        <i class="fas fa-filter"></i>
                    </button>
                </div>

                <!-- Print Button -->
                <div class="col-md-1">
                    <button type="button" onclick="window.print()" class="btn btn-success w-100 btn-pill shadow-sm fw-bold h-100 py-2 no-print">
                        <i class="fas fa-print"></i>
                    </button>
                </div>
            </form>
        </div>

        <!-- Hidden Header for Printing -->
        <div class="print-header text-center mb-4">
            <h2 class="fw-bold">{{ system_name }}</h2>
            <h4 class="mb-1">قائمة الحجوزات والمواعيد</h4>
            <div class="text-muted">
                تاريخ الاستخراج: {{ now.strftime('%Y-%m-%d %I:%M %p') }}
                {% if filter_date %}
                    | تاريخ البحث: {{ filter_date }}
                {% endif %}
            </div>
            <hr>
        </div>

        <!-- Appointments Table -->
        <div class="glass-card p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0 text-center">
                    <thead>
                        <tr>
                            <th class="ps-4 text-start">المريض</th>
                            <th>القسم / الطبيب</th>
                            <th>الموعد</th>
                            <th>الحالة</th>
                            <th class="pe-4 no-print">تحكم</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if result %}
                            {% for row in result %}
                                {% set status_color = 'warning' if row.status == 'scheduled' else 'success' if row.status == 'completed' else 'danger' if row.status == 'cancelled' else 'secondary' %}
                                {% set status_text = 'مجدول' if row.status == 'scheduled' else 'مكتمل' if row.status == 'completed' else 'ملغى' if row.status == 'cancelled' else 'انتظار طبيب' if row.status == 'waiting_doctor' else 'انتظار فرز' if row.status == 'pending_triage' else row.status %}
                                <tr id="appt-{{ row.appointment_id }}">
                                    <td class="text-start ps-4">
                                        <div class="fw-bold">{{ row.full_name_ar }}</div>
                                        <div class="small text-muted">ملف: {{ row.file_number }} | ت: {{ row.phone1 }}</div>
                                    </td>
                                    <td>
                                        <div class="fw-bold text-primary">{{ row.department_name_ar }}</div>
                                        <div class="small text-muted">{{ 'د. ' ~ row.doctor_name if row.doctor_name else '---' }}</div>
                                    </td>
                                    <td>
                                        <div class="fw-bold">
                                            {{ format_dt(row.appointment_date, '%Y-%m-%d %H:%M') }}
                                        </div>
                                        <div class="small text-muted">
                                            {% if row.created_at %}
                                                {{ format_dt(row.created_at, '%I:%M %p') }}
                                            {% else %}
                                                ---
                                            {% endif %}
                                        </div>
                                    </td>
                                    <td>
                                        <span class="badge bg-{{ status_color }} bg-opacity-10 text-{{ status_color }} px-3 py-2 rounded-pill">
                                            {{ status_text }}
                                        </span>
                                    </td>
                                    <td class="no-print">
                                        <div class="d-flex justify-content-center gap-2">
                                            <a href="{{ url_for('reservations.edit_reservation', id=row.appointment_id) }}" class="btn btn-sm btn-outline-primary rounded-pill px-3">
                                                <i class="fas fa-pen me-1"></i> تعديل
                                            </a>
                                            {% if row.status != 'completed' and row.status != 'cancelled' %}
                                                <button onclick="cancelApptFull({{ row.appointment_id }})" class="btn btn-sm btn-outline-danger rounded-pill px-3">
                                                    <i class="fas fa-times me-1"></i> حذف
                                                </button>
                                            {% endif %}
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="5" class="py-5 text-muted">لا توجد حجوزات مطابقة للبحث</td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function cancelApptFull(id) {
            if (!confirm('هل أنت متأكد من حذف وإلغاء هذا الحجز نهائياً؟')) return;

            const row = document.getElementById('appt-' + id);
            row.style.opacity = '0.5';

            const formData = new FormData();
            formData.append('id', id);

            fetch("{{ url_for('api.api_cancel_appointment') }}", {
                method: 'POST',
                body: formData
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('خطأ: ' + data.message);
                        row.style.opacity = '1';
                    }
                })
                .catch(e => {
                    alert('خطأ في الاتصال');
                    row.style.opacity = '1';
                });
        }
    </script>
    """ + footer_html
    

    return render_template_string(html, filter_date=filter_date, search_q=search_q, result=result)


@reservations_bp.route('/edit_reservation/<int:id>', methods=['GET', 'POST'])
def edit_reservation(id):
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        new_date = request.form.get('date')
        new_status = request.form.get('status')
        cursor.execute("UPDATE appointments SET appointment_date=%s, status=%s WHERE appointment_id=%s", (new_date, new_status, id))
        conn.commit()
        return redirect(url_for('reservations.reservations'))

        
    cursor.execute("""
        SELECT a.*, p.full_name_ar, p.file_number, p.phone1 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.appointment_id = %s
    """, (id,))
    appt = cursor.fetchone()
    
    if not appt:
        return redirect(url_for('reservations.reservations'))

        
    html = header_html + """
    <style>
        :root {
            --edit-bg: #f5f6f8;
            --edit-card: #ffffff;
            --edit-text: #2c3e50;
            --edit-border: #e1e4e8;
            --edit-input: #ffffff;
        }

        

        .edit-body { background: var(--edit-bg); color: var(--edit-text); min-height: 100vh; transition: background 0.3s; padding: 3rem 0; }
        
        .glass-card {
            background: var(--edit-card);
            border: 1px solid var(--edit-border);
            border-radius: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.03);
            overflow: hidden;
            margin-bottom: 2rem;
        }

        .form-control, .form-select { 
            background-color: var(--edit-input) !important; 
            color: var(--edit-text) !important; 
            border: 1px solid var(--edit-border) !important;
            border-radius: 12px !important;
            padding: 12px !important;
        }

        .btn-pill { border-radius: 50px; padding: 12px 30px; font-weight: 600; transition: all 0.3s; }
        .btn-primary { 
            background: linear-gradient(135deg, #bf5af2 0%, #5e5ce6 100%) !important; 
            border: none !important;
            box-shadow: 0 4px 15px rgba(191, 90, 242, 0.3);
        }
    </style>

    <div class="edit-body">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="glass-card shadow-lg">
                        <div class="p-4 text-center border-bottom" style="background: rgba(191, 90, 242, 0.05);">
                            <h4 class="fw-bold mb-0 text-primary"><i class="fas fa-edit me-2"></i> تعديل بيانات الحجز</h4>
                        </div>
                        <div class="p-4 p-lg-5">
                            <div class="text-center mb-4 pb-3 border-bottom">
                                <div class="fw-bold fs-4 mb-1">""" + str(appt['full_name_ar']) + """</div>
                                <div class="badge bg-light text-dark border px-3 py-2 rounded-pill" style="background: var(--edit-input) !important; color: var(--edit-text) !important;">
                                    ملف رقم: """ + str(appt['file_number']) + """
                                </div>
                            </div>
                            
                            <form method="POST">
                                <div class="mb-4">
                                    <label class="form-label fw-bold small opacity-75"><i class="fas fa-calendar-day me-1"></i> تاريخ الموعد</label>
                                    <input type="date" name="date" class="form-control" 
                                           value='""" + (str(appt['appointment_date']).split(' ')[0] if appt['appointment_date'] else '') + """' required>
                                </div>
                                
                                <div class="mb-4">
                                    <label class="form-label fw-bold small opacity-75"><i class="fas fa-info-circle me-1"></i> حالة الموعد</label>
                                    <select name="status" class="form-select">
                                        <option value="scheduled" """ + ('selected' if appt['status'] == 'scheduled' else '') + """>مجدول</option>
                                        <option value="waiting_doctor" """ + ('selected' if appt['status'] == 'waiting_doctor' else '') + """>انتظار طبيب</option>
                                        <option value="pending_triage" """ + ('selected' if appt['status'] == 'pending_triage' else '') + """>انتظار فرز</option>
                                        <option value="completed" """ + ('selected' if appt['status'] == 'completed' else '') + """>مكتمل</option>
                                        <option value="cancelled" """ + ('selected' if appt['status'] == 'cancelled' else '') + """>ملغى</option>
                                    </select>
                                </div>
                                
                                <div class="d-grid gap-3 pt-3">
                                    <button type="submit" class="btn btn-primary btn-pill shadow-sm">
                                        <i class="fas fa-check-circle me-1"></i> حفظ التعديلات
                                    </button>
                                    <a href='""" + url_for('reservations.reservations') + """' class="btn btn-light btn-pill border">
                                        إلغاء والعودة
                                    </a>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    

    return render_template_string(html)


@reservations_bp.route('/whatsapp_reminders')
def whatsapp_reminders():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get tomorrow's appointments
    sql = """
        SELECT a.appointment_id, a.appointment_date, p.full_name_ar, p.file_number, p.phone1, d.department_name_ar, u.full_name_ar as doctor_name 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        JOIN departments d ON a.department_id = d.department_id 
        LEFT JOIN users u ON a.doctor_id = u.user_id 
        WHERE a.status != 'cancelled' AND a.status != 'cancelled_hidden' AND a.status != 'completed'
          AND DATE(a.appointment_date) = date('now', '+1 day')
        ORDER BY a.appointment_date ASC
    """
    cursor.execute(sql)
    appointments = cursor.fetchall()
    
    html = header_html + """
    <style>
        :root {
            --wa-bg: #f5f6f8;
            --wa-card: #ffffff;
            --wa-text: #2c3e50;
            --wa-border: #e1e4e8;
            --wa-green: #25d366;
            --wa-hover: #128c7e;
        }

        

        .glass-card {
            background: var(--wa-card);
            border: 1px solid var(--wa-border);
            border-radius: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.03);
            margin-bottom: 2rem;
            overflow: hidden;
        }

        .btn-wa { 
            background: var(--wa-green) !important; 
            color: white !important;
            border: none;
            border-radius: 50px;
            padding: 8px 20px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .btn-wa:hover {
            background: var(--wa-hover) !important;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(37, 211, 102, 0.3);
        }
        
        .table { color: var(--wa-text) !important; background: transparent !important; }
        
    </style>

    <div class="container-fluid py-4" style="color: var(--wa-text)">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h3 class="fw-bold text-success"><i class="fab fa-whatsapp me-2"></i> إشعارات مراجعي الغد</h3>
                <p class="text-muted small mb-0">تبليغ المراجعين بمواعيدهم ليوم غد والتأكيد عليهم</p>
            </div>
            <div>
                <a href=""" + "'" + url_for('patients.patients') + "'" + """ class="btn btn-outline-secondary rounded-pill px-4">عودة للتسجيل</a>
            </div>
        </div>

        <div class="glass-card p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0 text-center">
                    <thead>
                        <tr>
                            <th class="ps-4 text-start">المريض</th>
                            <th>الموعد والتفاصيل</th>
                            <th>القسم والطبيب</th>
                            <th>رقم الهاتف</th>
                            <th class="pe-4">إرسال عبر الواتساب</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if appointments %}
                            {% for row in appointments %}
                                <tr>
                                    <td class="text-start ps-4">
                                        <div class="fw-bold">{{ row.full_name_ar }}</div>
                                        <div class="small text-muted">ملف: {{ row.file_number }}</div>
                                    </td>
                                    <td>
                                        <div class="fw-bold text-primary">غداً</div>
                                        <div class="small text-muted">
                                            {{ format_dt(row.appointment_date, '%Y-%m-%d %H:%M') }}
                                        </div>
                                    </td>
                                    <td>
                                        <div class="fw-bold">{{ row.department_name_ar }}</div>
                                        <div class="small text-muted">{{ 'د. ' ~ row.doctor_name if row.doctor_name else '---' }}</div>
                                    </td>
                                    <td>
                                        <div class="fw-bold" dir="ltr">{{ row.phone1 }}</div>
                                    </td>
                                    <td>
                                        <button onclick="sendWA('{{ row.phone1 }}', '{{ row.full_name_ar }}', '{{ row.appointment_date|string }}', '{{ row.department_name_ar }}', '{{ row.doctor_name or '' }}')" class="btn btn-wa shadow-sm px-4">
                                            <i class="fab fa-whatsapp me-1 ms-1"></i> إرسال رسالة
                                        </button>
                                    </td>
                                </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="5" class="py-5 text-muted">
                                    <div class="text-center py-4">
                                        <i class="fas fa-calendar-check fa-3x text-success mb-3 opacity-50"></i>
                                        <h5>لا توجد مواعيد مسجلة ليوم غد</h5>
                                    </div>
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function sendWA(phone, name, dateObj, dept, doctor) {
            if (!phone || phone === 'None' || phone.trim() === '') {
                alert('عذراً، رقم الهاتف غير متوفر لهذا المريض.');
                return;
            }
            let p = phone.trim();
            p = p.replace(/\\D/g,''); // remove non-numeric
            if (p.startsWith('0')) p = '964' + p.substring(1);
            else if (!p.startsWith('964')) p = '964' + p;

            let docText = doctor && doctor !== 'None' ? ('مع د. ' + doctor) : '';
            // Just take the date part
            let dateText = dateObj.substring(0, 10);
            
            let message = `مرحباً ${name}،\\nنود تذكيرك بموعد مراجعتك غداً بتاريخ ${dateText} في ${dept} ${docText} في عيادتنا.\\n\\nمع تمنياتنا لك بالشفاء العاجل!`;
            
            let url = `https://wa.me/${p}?text=${encodeURIComponent(message)}`;
            window.open(url, '_blank');
        }
    </script>
    """ + footer_html
    
    return render_template_string(html, appointments=appointments, str=str)
