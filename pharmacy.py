from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from datetime import timedelta
from config import get_db, can_access, local_now_naive, local_today_str  # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

pharmacy_bp = Blueprint('pharmacy', __name__)

@pharmacy_bp.route('/pharmacy', methods=['GET', 'POST'])
def pharmacy():
    if not session.get('user_id') or not can_access('pharmacy'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Dynamic Currency
    cursor.execute("SELECT * FROM system_settings")
    settings_res = cursor.fetchall()
    sys_settings = {row['setting_key']: row['setting_value'] for row in settings_res}
    currency = sys_settings.get('currency_label', 'د.ع')
    
    # 3. Handle Dispense & Payment
    if request.method == 'POST' and 'dispense_now' in request.form:
        id = int(request.form.get('prescription_id', 0))
        amount = float(request.form.get('price', 0))
        pid = int(request.form.get('patient_id', 0))
        aid = int(request.form.get('appointment_id', 0))
        
        cursor.execute("UPDATE prescriptions SET status = 'dispensed' WHERE prescription_id = %s", (id,))
        inv_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            """
            INSERT INTO invoices (appointment_id, patient_id, amount, status, created_at)
            VALUES (%s, %s, %s, 'paid_pharmacy', %s)
            """,
            (aid, pid, amount, inv_ts),
        )
        conn.commit()
        
        flash("تم استلام المبلغ وصرف العلاج بنجاح", "success")
        return redirect(url_for('pharmacy.pharmacy'))

        
    # 2. Fetch Pending Prescriptions
    today_str = local_today_str()

    sql = """
        SELECT pr.*, p.full_name_ar as p_name, p.file_number, a.appointment_date, u.full_name_ar as doc_name
        FROM prescriptions pr
        JOIN patients p ON pr.patient_id = p.patient_id
        JOIN appointments a ON pr.appointment_id = a.appointment_id
        LEFT JOIN users u ON pr.doctor_id = u.user_id
        WHERE pr.status IN ('pending', 'pending_payment')
        ORDER BY pr.created_at ASC
    """
    cursor.execute(sql)
    prescriptions = cursor.fetchall()

    filter_type = request.args.get('history_filter', 'today')
    date_params = []
    
    if filter_type == 'yesterday':
        target_date = (local_now_naive() - timedelta(days=1)).strftime('%Y-%m-%d')
        date_condition = "AND pr.created_at >= %s AND pr.created_at <= %s"
        date_params.extend([target_date + " 00:00:00", target_date + " 23:59:59"])
    elif filter_type == 'today':
        target_date = local_today_str()
        date_condition = "AND pr.created_at >= %s AND pr.created_at <= %s"
        date_params.extend([target_date + " 00:00:00", target_date + " 23:59:59"])
    else:
        date_condition = ""

    sql_history = f"""
        SELECT pr.*, p.full_name_ar as p_name, p.file_number, a.appointment_date, u.full_name_ar as doc_name
        FROM prescriptions pr
        JOIN patients p ON pr.patient_id = p.patient_id
        JOIN appointments a ON pr.appointment_id = a.appointment_id
        LEFT JOIN users u ON pr.doctor_id = u.user_id
        WHERE pr.status = 'dispensed' {date_condition}
        ORDER BY pr.created_at DESC LIMIT 100
    """
    if date_params:
        cursor.execute(sql_history, tuple(date_params))
    else:
        cursor.execute(sql_history)
        
    history_prescriptions = cursor.fetchall()

    html = header_html + """
    <style>
        .pharma-wrapper { display: flex; height: calc(100vh - 100px); gap: 15px; padding: 15px; animation: fadeIn 0.4s ease-out; overflow: hidden; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .pharma-history-panel { flex: 0 0 320px; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 18px; display: flex; flex-direction: column; box-shadow: 0 10px 30px rgba(0,0,0,0.05); overflow-y: auto; }
        
        
        .pharma-main-panel { flex: 1; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 20px; padding: 25px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); display: flex; flex-direction: column; overflow: hidden; }
        

        .history-card { background: var(--input-bg); border-radius: 12px; padding: 12px; margin-bottom: 15px; border: 1px solid var(--border); transition: all 0.2s; position: relative; overflow: hidden; }
        
        .history-card::before { content:''; position: absolute; top:0; right:0; width: 4px; height: 100%; background: #007aff; opacity: 0.7;}
        .history-card:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-color: #007aff; }
        
        .pharma-table-wrap { overflow-y: auto; flex: 1; padding-right: 5px; }
        
        /* Minimal sleek table */
        .sleek-table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
        .sleek-table th { color: var(--text); opacity: 0.5; font-size: 0.75rem; font-weight: 700; padding: 0 15px 5px; text-align: right; text-transform: uppercase; letter-spacing: 0.5px;}
        .sleek-table tbody tr { background: var(--input-bg); transition: all 0.2s; position: relative;}
        
        .sleek-table tbody tr:hover { transform: scale(1.01); box-shadow: 0 5px 15px rgba(0,0,0,0.05); z-index: 2;}
        .sleek-table td { padding: 15px; border: none; vertical-align: middle; color: var(--text); }
        .sleek-table td:first-child { border-top-right-radius: 16px; border-bottom-right-radius: 16px; border-right: 4px solid #30d158; }
        .sleek-table td:last-child { border-top-left-radius: 16px; border-bottom-left-radius: 16px; }

        .btn-dispense { background: linear-gradient(135deg, #30d158 0%, #248a3d 100%); color: white !important; border: none; padding: 10px 20px; border-radius: 12px; font-weight: 700; transition: all 0.2s; box-shadow: 0 4px 12px rgba(48,209,88,0.3); font-size: 0.85rem;}
        .btn-dispense:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(48,209,88,0.4); opacity: 0.95;}

        .btn-print { background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 10px 14px; border-radius: 12px; transition: all 0.2s; }
        .btn-print:hover { background: #007aff; color: white; border-color: #007aff; }
        
        /* Custom scrollbar for panels */
        .pharma-table-wrap::-webkit-scrollbar { width: 6px; }
        .pharma-table-wrap::-webkit-scrollbar-track { background: transparent; }
        .pharma-table-wrap::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 10px; }
        
        
        /* Medicine Tag */
        .med-tag { background: rgba(48,209,88,0.08); border-right: 3px solid #30d158; padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; line-height: 1.6; color: var(--text);}
        
    </style>

    <div class="pharma-wrapper container-fluid">
        <!-- History Sidebar -->
        <div class="pharma-history-panel">
            <h6 class="fw-bold mb-3 text-primary d-flex align-items-center justify-content-between pb-2 border-bottom">
                <span><i class="fas fa-history me-2"></i> الطلبات السابقة</span>
                <span class="badge bg-primary-subtle text-primary rounded-pill py-1 px-2 shadow-sm" style="font-size:0.65rem;">ارشيف الصيدلية</span>
            </h6>
            
            <!-- Date Filter Buttons -->
            <div class="d-flex gap-2 mb-3">
                <a href="?history_filter=today" class="btn btn-sm w-100 fw-bold rounded-pill {{ 'btn-primary shadow-sm' if filter_type == 'today' else 'btn-outline-primary bg-white text-primary border-primary' }}" style="font-size: 0.75rem;">اليوم</a>
                <a href="?history_filter=yesterday" class="btn btn-sm w-100 fw-bold rounded-pill {{ 'btn-primary shadow-sm' if filter_type == 'yesterday' else 'btn-outline-primary bg-white text-primary border-primary' }}" style="font-size: 0.75rem;">الأمس</a>
                <a href="?history_filter=all" class="btn btn-sm w-100 fw-bold rounded-pill {{ 'btn-primary shadow-sm' if filter_type == 'all' else 'btn-outline-primary bg-white text-primary border-primary' }}" style="font-size: 0.75rem;">الكل</a>
            </div>
            
            <div class="pharma-table-wrap pe-2">
                {% for h in history_prescriptions %}
                    <div class="history-card">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="fw-bold" style="font-size: 0.9rem; color: var(--text);">{{ h.p_name }}</span>
                            <span class="badge bg-success" style="font-size: 0.7rem; box-shadow: 0 2px 5px rgba(48,209,88,0.3);">
                                {{ "{:,.0f}".format(h.price) }} {{ currency }}
                            </span>
                        </div>
                        <div class="text-muted mb-2 d-flex justify-content-between align-items-center" style="font-size: 0.7rem;">
                            <span><i class="fas fa-user-md me-1 text-primary"></i> د. {{ h.doc_name }}</span>
                            <span style="opacity:0.7"><i class="fas fa-clock me-1"></i>{{ dt(h.created_at, '%Y-%m-%d %I:%M %p') }}</span>
                        </div>
                        <div class="bg-card rounded small text-dark p-2" style="font-size: 0.75rem; max-height: 45px; overflow: hidden; text-overflow: ellipsis; border: 1px solid var(--border); background: var(--card); color: var(--text) !important;">
                            {{ h.medicine_name | replace('\\n', ' ') | safe }}
                        </div>
                    </div>
                {% endfor %}
                {% if not history_prescriptions %}
                    <div class="text-center text-muted mt-5 opacity-50">
                        <i class="fas fa-box-open fa-3x mb-3 text-primary" style="opacity: 0.5;"></i>
                        <p class="small fw-bold">لا توجد طلبات سابقة في الأرشيف</p>
                    </div>
                {% endif %}
            </div>
        </div>

        <!-- Main Pending Panel -->
        <div class="pharma-main-panel">
            <div class="d-flex justify-content-between align-items-center pb-3 border-bottom mb-3">
                <div class="d-flex align-items-center gap-3">
                    <div class="bg-success-subtle text-success p-3 rounded-circle d-flex align-items-center justify-content-center" style="width: 50px; height: 50px;">
                        <i class="fas fa-pills fa-lg"></i>
                    </div>
                    <div>
                        <h4 class="fw-bold mb-1" style="color: var(--text);">نظام الصيدلية المركزي</h4>
                        <p class="text-muted extra-small mb-0">لوحة التحكم السريعة بصرف العلاجات والدفع</p>
                    </div>
                </div>
                <div class="badge bg-light text-dark border px-3 py-2 rounded-pill shadow-sm fw-bold">
                    <i class="fas fa-hourglass-half text-warning me-1"></i>
                    قيد الانتظار: <span class="text-primary">{{ prescriptions|length }}</span>
                </div>
            </div>
            
            <div class="pharma-table-wrap">
                {% if prescriptions %}
                    <table class="sleek-table">
                        <thead>
                            <tr>
                                <th>تفاصيل المريض</th>
                                <th>الوصفة بواسطة</th>
                                <th width="35%">العلاج المطلوب</th>
                                <th>التكلفة</th>
                                <th class="text-end">الإجراءات</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in prescriptions %}
                            <tr>
                                <td>
                                    <div class="fw-bold" style="font-size: 0.95rem;">{{ r.p_name }}</div>
                                    <div class="text-muted mt-1" style="font-size: 0.75rem;"><span class="badge bg-secondary-subtle text-secondary px-2 py-1"><i class="fas fa-hashtag me-1"></i>{{ r.file_number }}</span></div>
                                </td>
                                <td>
                                    <div class="fw-bold" style="font-size: 0.85rem;"><i class="fas fa-user-md text-primary me-1"></i> د. {{ r.doc_name }}</div>
                                    <div class="text-muted mt-1" style="font-size: 0.7rem;"><i class="fas fa-clock me-1 text-warning"></i>{{ dt(r.created_at, '%Y-%m-%d %I:%M %p') }}</div>
                                </td>
                                <td>
                                    <div class="med-tag">
                                        {{ r.medicine_name | replace('\\n', '<br>') | safe }}
                                    </div>
                                </td>
                                <td>
                                    <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2 shadow-sm fw-bold" style="font-size: 0.9rem;">
                                        {{ "{:,.0f}".format(r.price) }} {{ currency }}
                                    </span>
                                </td>
                                <td class="text-end pe-3">
                                    <form method="POST" class="d-inline-block m-0">
                                        <input type="hidden" name="prescription_id" value="{{ r.prescription_id }}">
                                        <input type="hidden" name="patient_id" value="{{ r.patient_id }}">
                                        <input type="hidden" name="appointment_id" value="{{ r.appointment_id }}">
                                        <input type="hidden" name="price" value="{{ r.price }}">
                                        <button type="submit" name="dispense_now" class="btn-dispense me-2">
                                            <i class="fas fa-check-circle me-1"></i> استلام وصرف
                                        </button>
                                    </form>
                                    <a href="print_rx?id={{ r.prescription_id }}" class="btn-print" title="طباعة">
                                        <i class="fas fa-print"></i>
                                    </a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% else %}
                    <div class="d-flex flex-column align-items-center justify-content-center h-100 opacity-75">
                        <div class="mb-3 p-4 bg-success-subtle rounded-circle d-flex align-items-center justify-content-center" style="width: 100px; height: 100px;">
                            <i class="fas fa-check fa-3x text-success"></i>
                        </div>
                        <h4 class="fw-bold" style="color: var(--text);">لا توجد وصفات قيد الانتظار</h4>
                        <p class="text-muted small">تم إنجاز وتسليم جميع طلبات قسم الصيدلية.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, prescriptions=prescriptions, history_prescriptions=history_prescriptions, currency=currency, filter_type=filter_type)
