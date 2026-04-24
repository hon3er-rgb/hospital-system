from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access, local_now_naive, local_today_str # type: ignore


def _is_corrupt_timestamp(val):
    if val is None:
        return True
    s = str(val).strip().upper()
    if not s or s in ('NULL', 'NONE'):
        return True
    return 'CURRENT' in s


def _heal_statement_timestamps(cursor, conn, statement_data):
    """Fix legacy rows where created_at was stored as literal CURRENT_DATETIME."""
    for item in statement_data:
        if not _is_corrupt_timestamp(item.get('created_at')):
            item['is_frozen'] = True
            continue

        fixed = None
        apid = item.get('appointment_id')
        if apid:
            cursor.execute(
                "SELECT created_at, appointment_date FROM appointments WHERE appointment_id = %s",
                (apid,),
            )
            row = cursor.fetchone()
            if row:
                for key in ('created_at', 'appointment_date'):
                    v = row.get(key)
                    if v is not None and not _is_corrupt_timestamp(v):
                        fixed = v
                        break
        if fixed is None:
            fixed = local_now_naive()
        item['created_at'] = fixed
        ts = fixed.strftime('%Y-%m-%d %H:%M:%S') if hasattr(fixed, 'strftime') else str(fixed)
        
        # 1. Update Invoices
        inv_id = item.get('invoice_id')
        if inv_id not in (None, '-', ''):
            try:
                # Force update by ID regardless of previous content to ensure permanent freezing
                cursor.execute("UPDATE invoices SET created_at = %s WHERE invoice_id = %s", (ts, inv_id))
                conn.commit()
            except Exception: pass
            
        # 2. Update Appointments
        if apid:
            try:
                # Force update both potential timestamp fields in appointments
                cursor.execute("UPDATE appointments SET created_at = %s WHERE appointment_id = %s", (ts, apid))
                cursor.execute("UPDATE appointments SET appointment_date = %s WHERE appointment_id = %s", (ts, apid))
                conn.commit()
            except Exception: pass
        
        item['is_frozen'] = True # Once we heal and save, it's frozen




from header import header_html # type: ignore
from footer import footer_html # type: ignore
import datetime

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing', methods=['GET', 'POST'])
def billing():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Update current task
    cursor.execute("UPDATE users SET current_task = 'إدارة الصندوق المالي' WHERE user_id = %s", (session['user_id'],))
    
    
    
    # --- Handle Multi-Payment & Discount ---
    if request.method == 'POST' and 'process_payment' in request.form:
        patient_id = int(request.form.get('patient_id', 0))
        appt_id = int(request.form.get('appointment_id', 0))
        discount = float(request.form.get('discount_amount') or 0)
        total_original = float(request.form.get('total_original', 0))
        final_amount = total_original - discount
        
        if request.form.get('pay_appt'):
            cursor.execute("SELECT department_id FROM appointments WHERE appointment_id = %s", (appt_id,))
            appt_info = cursor.fetchone()
            if appt_info and appt_info['department_id'] in [3, 4]:
                # For direct Lab/Rad, stay in scheduled or set to something else that's not triage
                cursor.execute("UPDATE appointments SET status = 'scheduled' WHERE appointment_id = %s", (appt_id,))
            else:
                cursor.execute("UPDATE appointments SET status = 'pending_triage' WHERE appointment_id = %s", (appt_id,))
            
        pay_labs = request.form.getlist('pay_labs[]')
        for lid in pay_labs:
            cursor.execute("UPDATE lab_requests SET status = 'pending' WHERE request_id = %s", (int(lid),))
            
        pay_rads = request.form.getlist('pay_rads[]')
        for rid in pay_rads:
            cursor.execute("UPDATE radiology_requests SET status = 'pending' WHERE request_id = %s", (int(rid),))
            
        pay_prescs = request.form.getlist('pay_prescs[]')
        for pxid in pay_prescs:
            cursor.execute("UPDATE prescriptions SET status = 'pending' WHERE prescription_id = %s", (int(pxid),))
            
        paid_ts = local_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO invoices (appointment_id, patient_id, amount, status, created_at) VALUES (%s, %s, %s, 'paid', %s)",
            (appt_id, patient_id, final_amount, paid_ts),
        )
        
        conn.commit()
        flash(f"تم استلام المبلغ بنجاح: {final_amount:,.0f}", "success")
        return redirect(url_for('billing.billing'))

    # --- Handle Refund Confirmation (NEW) ---
    if request.method == 'POST' and 'confirm_refund' in request.form:
        item_id = int(request.form.get('item_id', 0))
        item_type = request.form.get('item_type', '')
        if item_type == 'lab':
            # Get price and IDs first
            cursor.execute("SELECT price, patient_id, appointment_id FROM lab_requests WHERE request_id = %s", (item_id,))
            row = cursor.fetchone()
            if row:
                amount = -float(row['price'] or 0)
                cursor.execute("INSERT INTO invoices (patient_id, appointment_id, amount, status, created_at) VALUES (%s, %s, %s, 'paid', CURRENT_TIMESTAMP)", (row['patient_id'], row['appointment_id'], amount))
            cursor.execute("UPDATE lab_requests SET refund_status = 'refunded' WHERE request_id = %s", (item_id,))
        elif item_type == 'rad':
            cursor.execute("SELECT price, patient_id, appointment_id FROM radiology_requests WHERE request_id = %s", (item_id,))
            row = cursor.fetchone()
            if row:
                amount = -float(row['price'] or 0)
                cursor.execute("INSERT INTO invoices (patient_id, appointment_id, amount, status, created_at) VALUES (%s, %s, %s, 'paid', CURRENT_TIMESTAMP)", (row['patient_id'], row['appointment_id'], amount))
            cursor.execute("UPDATE radiology_requests SET refund_status = 'refunded' WHERE request_id = %s", (item_id,))
        elif item_type == 'appt':
            cursor.execute("SELECT patient_id FROM appointments WHERE appointment_id = %s", (item_id,))
            row = cursor.fetchone()
            if row:
                prices_res = cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'price_consult_default'").fetchone()
                price_val = float(prices_res['setting_value'] if prices_res else 15000)
                cursor.execute("INSERT INTO invoices (patient_id, appointment_id, amount, status, created_at) VALUES (%s, %s, %s, 'paid', CURRENT_TIMESTAMP)", (row['patient_id'], item_id, -price_val))
            cursor.execute("UPDATE appointments SET refund_status = 'refunded' WHERE appointment_id = %s", (item_id,))
        conn.commit()
        flash("تم تأكيد إرجاع المبلغ بنجاح ✅", "success")
        return redirect(url_for('billing.billing'))



    # Local calendar date for filters (APP_TIMEZONE)
    today_str = local_today_str()

    # Fetch total paid today
    cursor.execute("SELECT SUM(amount) as total FROM invoices WHERE DATE(created_at) = %s AND status = 'paid'", (today_str,))
    res_tot = cursor.fetchone()
    total_paid_today = float(res_tot['total']) if res_tot and res_tot['total'] else 0.0

    # Fetch patients with pending payments
    sql_patients = """
        SELECT DISTINCT p.patient_id, p.full_name_ar, p.file_number, p.category, a.appointment_id, a.is_free, a.appointment_date 
        FROM patients p 
        JOIN appointments a ON p.patient_id = a.patient_id
        LEFT JOIN lab_requests l ON a.appointment_id = l.appointment_id AND l.status = 'pending_payment'
        LEFT JOIN radiology_requests r ON a.appointment_id = r.appointment_id AND r.status = 'pending_payment'
        LEFT JOIN prescriptions pr ON a.appointment_id = pr.appointment_id AND pr.status = 'pending_payment'
        WHERE DATE(a.appointment_date) = %s

           AND (
               (a.status = 'scheduled')
               OR (l.status = 'pending_payment')
               OR (r.status = 'pending_payment')
               OR (pr.status = 'pending_payment')
           )
        ORDER BY a.appointment_date DESC
    """
    cursor.execute(sql_patients, (today_str,))
    patients_res = cursor.fetchall()
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    
    price_consult = float(prices.get('price_consultation', 25000))
    currency = prices.get('currency_label', 'د.ع')
    
    discount_rates = {
        'normal': float(prices.get('discount_normal', 0)),
        'senior': float(prices.get('discount_senior', 20)),
        'martyr': float(prices.get('discount_martyr', 25)),
        'special': float(prices.get('discount_special', 30))
    }
    category_names = {'normal': 'عادي', 'senior': 'كبار السن', 'martyr': 'عائلات الشهداء', 'special': 'ذوي الاحتياجات الخاصة'}
    
    patients_data = []
    
    for p in patients_res:
        pid = p['patient_id']
        aid = p['appointment_id']
        is_free = int(p['is_free']) == 1 if p.get('is_free') is not None else False
        items = []
        total = 0
        
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s AND status = 'scheduled'", (aid,))
        chk_appt = cursor.fetchone()
        if chk_appt:
            actual_price = 0 if is_free else price_consult
            items.append({'type': 'مراجعة مجانية' if is_free else 'كشف طبي للعيادة', 'id': aid, 'price': actual_price, 'db_type': 'appt'})
            total += actual_price
            
        cursor.execute("SELECT * FROM lab_requests WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for l in cursor.fetchall():
            price = float(l['price']) if l['price'] is not None else 0
            items.append({'type': f"مختبر: {l['test_type']}", 'id': l['request_id'], 'price': price, 'db_type': 'lab'})
            total += price
            
        cursor.execute("SELECT * FROM radiology_requests WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for r in cursor.fetchall():
            price = float(r['price']) if r['price'] is not None else 0
            items.append({'type': f"أشعة: {r['scan_type']}", 'id': r['request_id'], 'price': price, 'db_type': 'rad'})
            total += price
            
        cursor.execute("SELECT * FROM prescriptions WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for px in cursor.fetchall():
            price = float(px['price']) if px['price'] is not None else 0
            items.append({'type': f"صيدلية: {px['medicine_name']}", 'id': px['prescription_id'], 'price': price, 'db_type': 'px'})
            total += price
            
        p_category = p.get('category') or 'normal'
        rate = discount_rates.get(p_category, 0)
        auto_discount = (total * rate) / 100
        
        is_delayed = False
        delay_msg = ""
        appt_date_str = ""
        appt_val = p.get('appointment_date')
        if appt_val:
            if isinstance(appt_val, str):
                try:
                    # Parse by splitting by dot for potential microseconds
                    dt_part = appt_val.split('.')[0]
                    # Further ensure precisely 19 chars for standard YYYY-MM-DD HH:MM:SS
                    appt_date_str = str(dt_part)[0:19] # type: ignore
                    appt_dt_obj = datetime.datetime.strptime(appt_date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    appt_dt_obj = None
            else:
                appt_dt_obj = appt_val
                appt_date_str = appt_val.strftime('%Y-%m-%d %H:%M:%S')

            if appt_dt_obj:
                diff_minutes = (local_now_naive() - appt_dt_obj).total_seconds() / 60
                if diff_minutes >= 7:
                    is_delayed = True
                    delay_msg = f"تأخر ({int(diff_minutes)} دقيقة)"

        # Generate dynamic summary label
        parts = []
        types_count = {}
        for it in items:
            t = it['db_type']
            types_count[t] = types_count.get(t, 0) + 1
            
        if types_count.get('appt'): 
            parts.append("كشفية" if types_count['appt'] == 1 else f"{types_count['appt']} كشفيات")
        if types_count.get('lab'):  
            parts.append("تحاليل" if types_count['lab'] > 1 else "تحليل مختبر")
        if types_count.get('rad'):  
            parts.append("أشعة" if types_count['rad'] > 1 else "أشعة")
        if types_count.get('px'):   
            parts.append("صيدلية" if types_count['px'] == 1 else f"{types_count['px']} علاجات")
            
        summary_label = " + ".join(parts) if parts else "بدون تفاصيل"

        patients_data.append({
            'patient_id': pid,
            'appointment_id': aid,
            'full_name_ar': p['full_name_ar'],
            'file_number': p['file_number'],
            'total': total,
            'auto_discount': auto_discount,
            'billing_items': items,
            'summary_label': summary_label,
            'category_name': category_names.get(p_category, 'عادي'),
            'is_delayed': is_delayed,
            'delay_msg': delay_msg,
            'appt_date_str': appt_date_str
        })

    # --- Fetch Pending Refunds (NEW) ---
    cursor.execute("""
        SELECT 'lab' as type, lr.request_id as id, lr.test_type as name, lr.price, lr.cancelled_at, p.full_name_ar, lr.patient_id, lr.appointment_id
        FROM lab_requests lr JOIN patients p ON lr.patient_id = p.patient_id 
        WHERE lr.refund_status = 'refund_needed'
        UNION ALL
        SELECT 'rad' as type, rr.request_id as id, rr.scan_type as name, rr.price, rr.cancelled_at, p.full_name_ar, rr.patient_id, rr.appointment_id
        FROM radiology_requests rr JOIN patients p ON rr.patient_id = p.patient_id 
        WHERE rr.refund_status = 'refund_needed'
        UNION ALL
        SELECT 'appt' as type, a.appointment_id as id, 'كشفية عيادة' as name, %s as price, a.cancelled_at, p.full_name_ar, a.patient_id, a.appointment_id
        FROM appointments a JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.refund_status = 'refund_needed'
        ORDER BY cancelled_at DESC
    """, (price_consult,))
    refunds_data = cursor.fetchall()
    refund_count = len(refunds_data)


    html = header_html + """
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --success-gradient: linear-gradient(135deg, #10b981 0%, #34d399 100%);
            --card-bg: rgba(255, 255, 255, 0.82);
            --glass-border: rgba(255, 255, 255, 0.5);
            --text-col: #1e293b;
            --text-muted: #64748b;
            --inp-bg: rgba(0, 0, 0, 0.02);
            --shadow-sm: 0 2px 8px -2px rgba(0, 0, 0, 0.05);
            --shadow-lg: 0 15px 30px -10px rgba(0, 0, 0, 0.1);
            --radius-md: 0.85rem;
            --radius-sm: 0.6rem;
        }

        

        .billing-redesign {
            font-family: 'Tajawal', sans-serif;
            color: var(--text-col);
        }

        .header-title {
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 1.75rem;
        }
        
        .refund-badge {
            background: #ef4444; 
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            padding: 4px 14px; border-radius: 20px;
            font-size: 0.85rem; font-weight: 800;
            margin-right: 12px; vertical-align: middle;
            display: inline-flex; align-items: center; gap: 4px;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
            animation: pulse-red 2s infinite;
        }
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .refund-section {
            background: rgba(239, 68, 68, 0.04);
            border: 1px solid #fecaca;
            border-radius: var(--radius-md);
            padding: 20px;
            box-shadow: var(--shadow-sm);
        }
        .refund-toggle-btn {
            background: none; border: none; padding: 0;
            transition: transform 0.2s;
        }
        .refund-toggle-btn:hover { transform: scale(1.05); }
        .refund-toggle-btn:active { transform: scale(0.95); }

        .patient-billing-card {
            background: var(--card-bg) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border) !important;
            border-radius: var(--radius-md) !important;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            margin-bottom: 0.75rem !important;
            border-right: 4px solid transparent !important;
        }

        .patient-billing-card:hover {
            transform: translateX(-4px);
            box-shadow: var(--shadow-lg);
            border-right-color: #818cf8 !important;
        }

        .icon-circle {
            width: 42px;
            height: 42px;
            border-radius: 10px;
            background: var(--inp-bg);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            font-size: 1.1rem;
            border: 1px solid var(--glass-border);
        }

        .badge-compact {
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 6px;
            background: var(--inp-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-muted);
        }

        .price-display {
            font-weight: 800;
            font-size: 1.4rem;
            color: var(--text-col);
            letter-spacing: -0.5px;
        }

        .expand-btn {
            width: 34px;
            height: 34px;
            border-radius: 8px;
            border: 1px solid var(--glass-border);
            background: var(--inp-bg);
            color: var(--text-muted);
            transition: all 0.2s;
        }
        .expand-btn:hover { background: var(--primary-gradient); color: white; border-color: transparent; }

        .btn-action-sm {
            padding: 8px 16px;
            font-size: 0.85rem;
            font-weight: 700;
            border-radius: 8px;
            background: var(--card-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-col);
            backdrop-filter: blur(5px);
            transition: 0.2s;
        }
        .btn-action-sm:hover { background: var(--inp-bg); transform: translateY(-1px); }

        .form-control-compact {
            background: var(--inp-bg) !important;
            border: 1px solid var(--glass-border) !important;
            color: var(--text-col) !important;
            border-radius: 8px;
            padding: 8px 12px;
            font-weight: 600;
        }

        .btn-pay-compact {
            background: var(--primary-gradient);
            border: none;
            color: white;
            font-weight: 700;
            border-radius: 10px;
            padding: 12px;
            width: 100%;
            transition: 0.3s;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
        }
        .btn-pay-compact:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3); }

        .delayed-card { border-right-color: #ef4444 !important; background: rgba(239, 68, 68, 0.03) !important; }

        .service-row {
            padding: 8px 0;
            border-bottom: 1px dashed var(--glass-border);
        }
        .service-row:last-child { border-bottom: none; }
    </style>

    <div class="billing-redesign py-4 container-fluid" style="max-width: 1200px;">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center mb-4 gap-3">
            <div>
                <h1 class="header-title m-0">صندوق المحاسبة
                    {% if refund_count > 0 %}
                    <button class="refund-toggle-btn" type="button" data-bs-toggle="collapse" data-bs-target="#refundQueueCollapse" title="عرض طلبات الاسترداد">
                        <span class="refund-badge"><i class="fas fa-undo me-1"></i>{{ refund_count }} مبالغ مستردة</span>
                    </button>
                    {% endif %}
                </h1>
                <p class="text-muted small m-0 mt-1">إدارة التحصيل المالي للفواتير المعلقة</p>
            </div>
            
            <div class="d-flex gap-2">
                <a href="{{ url_for('billing.billing_history') }}" class="btn-action-sm text-decoration-none">
                    <i class="fa-solid fa-clock-rotate-left me-1"></i> الأرشيف
                </a>
                <a href="{{ url_for('billing.patient_statement') }}" class="btn-action-sm text-decoration-none">
                    <i class="fa-solid fa-file-contract me-1"></i> كشف حساب
                </a>
            </div>
        </div>

        <!-- --- REFUND QUEUE COLLAPSIBLE --- -->
        {% if refunds_data %}
        <div class="collapse mb-4" id="refundQueueCollapse">
            <div class="refund-section mx-auto" style="max-width: 900px;">
                <div class="d-flex align-items-center justify-content-between mb-4">
                    <div class="d-flex align-items-center gap-2">
                        <div class="icon-circle" style="background:#fee2e2; color:#ef4444; border-color:#fecaca;">
                            <i class="fas fa-hand-holding-dollar"></i>
                        </div>
                        <h5 class="fw-bold m-0" style="color:#b91c1c;">طلبات استرداد المبالغ الملغاة</h5>
                    </div>
                    <button type="button" class="btn-close" data-bs-toggle="collapse" data-bs-target="#refundQueueCollapse"></button>
                </div>
                
                <div class="table-responsive">
                    <table class="table table-hover align-middle border-top" style="font-size: 0.9rem;">
                        <thead>
                            <tr class="text-muted small">
                                <th>المريض</th>
                                <th>المادة الملغاة</th>
                                <th>المبلغ</th>
                                <th>وقت الإلغاء</th>
                                <th class="text-center">إجراء</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in refunds_data %}
                            <tr>
                                <td class="fw-bold">{{ r.full_name_ar }}</td>
                                <td>
                                    <span class="badge bg-light text-dark border">{{ 'كشفية' if r.type == 'appt' else ('تحليل' if r.type == 'lab' else 'أشعة') }}</span>
                                    {{ r.name }}
                                </td>
                                <td class="fw-bold text-danger">{{ "{:,.0f}".format(r.price) }} {{ currency }}</td>
                                <td class="small text-muted">{{ format_dt(r.cancelled_at, '%I:%M %p') }}</td>
                                <td class="text-center">
                                    <form method="POST" onsubmit="return confirm('هل تم إرجاع المبلغ للمريض بالفعل؟');">
                                        <input type="hidden" name="item_id" value="{{ r.id }}">
                                        <input type="hidden" name="item_type" value="{{ r.type }}">
                                        <button type="submit" name="confirm_refund" class="btn btn-sm btn-danger rounded-pill px-3 fw-bold shadow-sm">
                                            تم الإرجاع <i class="fas fa-check-circle ms-1"></i>
                                        </button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}
        
        {% if not patients_data %}
            <div class="text-center py-5">
                <div class="icon-circle mx-auto mb-3" style="width: 60px; height: 60px; font-size: 1.5rem; background: rgba(16, 185, 129, 0.1); color: #10b981;">
                    <i class="fas fa-check"></i>
                </div>
                <h4 class="fw-bold">لا توجد دفعات معلقة</h4>
                <p class="text-muted small">تم تصفية جميع الحسابات المفتوحة حالياً.</p>
            </div>
        {% else %}
            <div class="accordion" id="billingAccordion" style="max-width: 900px; margin: 0 auto;">
                {% for p in patients_data %}
                    <div class="accordion-item patient-billing-card {% if p.is_delayed %}delayed-card{% endif %}" id="card-{{ p.patient_id }}">
                        <div class="accordion-header p-2">
                            <div class="d-flex align-items-center gap-3 w-100">
                                <div class="icon-circle flex-shrink-0">
                                    <i class="fas fa-user-injured"></i>
                                </div>
                                <div class="flex-grow-1 overflow-hidden">
                                    <h6 class="fw-bold m-0 text-truncate" style="color: var(--text-col); font-size: 1.1rem;">
                                        {{ p.full_name_ar }}
                                        <i class="fas fa-circle-exclamation text-danger delay-warning-icon {% if not p.is_delayed %}d-none{% endif %} ms-1"></i>
                                    </h6>
                                    <div class="d-flex gap-2 mt-1">
                                        <span class="badge-compact"><i class="fas fa-hashtag me-1 opacity-50"></i>{{ p.file_number }}</span>
                                        <span class="badge-compact"><i class="fas fa-tag me-1 opacity-50"></i>{{ p.category_name }}</span>
                                    </div>
                                </div>
                                <div class="text-end me-2">
                                    <div class="text-muted" style="font-size: 0.7rem; font-weight: 700;">المطلوب</div>
                                    <div class="price-display lh-1">{{ "{:,.0f}".format(p.total - p.auto_discount) }} <small style="font-size: 0.65rem; color: var(--text-muted);">{{ currency }}</small></div>
                                </div>
                                <button class="expand-btn border-0 d-flex align-items-center justify-content-center collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{ p.patient_id }}">
                                    <i class="fas fa-chevron-down transition-all dropdown-icon" style="font-size: 0.8rem;"></i>
                                </button>
                            </div>
                        </div>

                        <div id="collapse{{ p.patient_id }}" class="accordion-collapse collapse" data-bs-parent="#billingAccordion">
                            <div class="accordion-body border-top border-secondary border-opacity-10 p-3 pt-4">
                                <form method="POST">
                                    <input type="hidden" name="patient_id" value="{{ p.patient_id }}">
                                    <input type="hidden" name="appointment_id" value="{{ p.appointment_id }}">
                                    <input type="hidden" name="total_original" value="{{ p.total }}">

                                    <div class="row g-3">
                                        <div class="col-md-7">
                                            <div class="p-3 rounded-3" style="background: var(--inp-bg); border: 1px solid var(--glass-border);">
                                                <div class="d-flex align-items-center gap-2 mb-3">
                                                    <i class="fas fa-list-ul text-primary"></i>
                                                    <span class="fw-bold small" style="color: var(--text-col);">تفاصيل الخدمات</span>
                                                </div>
                                                <div class="services-list" style="font-size: 0.9rem;">
                                                    {% for it in p.billing_items %}
                                                    <div class="d-flex justify-content-between service-row" style="color: var(--text-col);">
                                                        <span><i class="fas fa-check-circle text-success me-2" style="font-size: 0.7rem;"></i>{{ it.type }}</span>
                                                        <span class="fw-bold">{{ "{:,.0f}".format(it.price) }}</span>
                                                    </div>
                                                    {% if it.db_type == 'lab' %}<input type="hidden" name="pay_labs[]" value="{{ it.id }}">
                                                    {% elif it.db_type == 'rad' %}<input type="hidden" name="pay_rads[]" value="{{ it.id }}">
                                                    {% elif it.db_type == 'px' %}<input type="hidden" name="pay_prescs[]" value="{{ it.id }}">
                                                    {% elif it.db_type == 'appt' %}<input type="hidden" name="pay_appt" value="1">
                                                    {% endif %}
                                                    {% endfor %}
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="col-md-5">
                                            <div class="p-3 rounded-3 h-100 d-flex flex-column justify-content-between" style="background: var(--inp-bg); border: 1px solid var(--glass-border);">
                                                <div style="color: var(--text-col);">
                                                    <div class="d-flex justify-content-between mb-2">
                                                        <span class="small opacity-75">المجموع:</span>
                                                        <span class="fw-bold">{{ "{:,.0f}".format(p.total) }} {{ currency }}</span>
                                                    </div>
                                                    <div class="mb-3">
                                                        <label class="small opacity-75 mb-1 d-block" style="color: var(--text-col);">قيمة الخصم:</label>
                                                        <div class="input-group input-group-sm">
                                                            <input type="number" step="0.01" name="discount_amount" class="form-control form-control-compact text-center" value="{{ p.auto_discount }}">
                                                            <span class="input-group-text bg-transparent border-0 small opacity-75" style="color: var(--text-col);">{{ currency }}</span>
                                                        </div>
                                                        {% if p.auto_discount > 0 %}
                                                            <div class="mt-1" style="font-size: 0.7rem; color: #10b981;"><i class="fas fa-tag me-1"></i>خصم تلقائي: {{ p.category_name }}</div>
                                                        {% endif %}
                                                    </div>
                                                </div>
                                                
                                                <button type="submit" name="process_payment" class="btn-pay-compact">
                                                    إتمام الدفع <i class="fas fa-arrow-left ms-2 fs-6"></i>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>

    <!-- إشعارات التأخير في الدفع -->
    <div class="toast-container position-fixed bottom-0 start-0 p-4" id="delay-toasts-container" style="z-index: 10000;">
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        // Handle accordion icon rotation
        const accordions = document.querySelectorAll('.accordion-collapse');
        accordions.forEach(acc => {
            acc.addEventListener('show.bs.collapse', (e) => {
                const icon = document.querySelector(`[data-bs-target="#${e.target.id}"] .dropdown-icon`);
                if(icon) {
                    icon.style.transform = 'rotate(180deg)';
                    icon.parentElement.style.background = 'var(--primary-gradient)';
                    icon.parentElement.style.color = 'white';
                    icon.parentElement.style.borderColor = 'transparent';
                }
            });
            acc.addEventListener('hide.bs.collapse', (e) => {
                const icon = document.querySelector(`[data-bs-target="#${e.target.id}"] .dropdown-icon`);
                if(icon) {
                    icon.style.transform = 'rotate(0deg)';
                    icon.parentElement.style.background = '';
                    icon.parentElement.style.color = '';
                    icon.parentElement.style.borderColor = '';
                }
            });
        });

        const container = document.getElementById('delay-toasts-container');
        container.addEventListener('click', (e) => {
            if(e.target.classList.contains('btn-close')){
                const toast = e.target.closest('.toast');
                if(toast) { 
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 300);
                }
            }
        });
        
        setInterval(() => {
            const now = new Date();
            document.querySelectorAll('.patient-billing-card').forEach(card => {
                const arrivalStr = card.getAttribute('data-arrival-time');
                const pid = card.getAttribute('data-patient-id');
                const pname = card.getAttribute('data-patient-name');
                if(!arrivalStr) return;
                
                const dtParts = arrivalStr.split(' ');
                if(dtParts.length !== 2) return;
                const d = dtParts[0].split('-');
                const t = dtParts[1].split(':');
                const arrivalTime = new Date(d[0], d[1]-1, d[2], t[0], t[1], t[2]);
                
                const diffMs = now - arrivalTime;
                const diffMins = Math.floor(diffMs / 60000);
                
                if(diffMins >= 7) {
                    if(!card.classList.contains('delayed-card')) {
                        card.classList.add('delayed-card');
                    }
                    
                    const warningIcon = card.querySelector('.delay-warning-icon');
                    if(warningIcon) {
                        warningIcon.classList.remove('d-none');
                        warningIcon.title = `تأخر (${diffMins} دقيقة)`;
                    }
                    
                    if (diffMins === 7 && !card.dataset.toastShown) {
                        card.dataset.toastShown = 'true';
                        
                        const toastId = 'toast-' + pid + '-' + Date.now();
                        const toastHTML = `
                            <div id="${toastId}" class="toast show align-items-center text-white border-0 mb-3 shadow-lg delay-toast rounded-4" role="alert" aria-live="assertive" aria-atomic="true">
                              <div class="d-flex p-1">
                                <div class="toast-body fw-bold fs-6 pt-3 pb-3">
                                  <i class="fas fa-triangle-exclamation fa-beat-fade me-2 fs-4 text-warning"></i> 
                                  المرجع <span class="text-warning text-decoration-underline mx-1">${pname}</span> لم يسدد الفاتورة! تجاوز 7 دقائق
                                </div>
                                <button type="button" class="btn-close btn-close-white me-3 m-auto fa-lg" data-bs-dismiss="toast"></button>
                              </div>
                            </div>
                        `;
                        container.insertAdjacentHTML('beforeend', toastHTML);
                        
                        setTimeout(() => {
                            const tEl = document.getElementById(toastId);
                            if(tEl) {
                                tEl.classList.remove('show');
                                setTimeout(() => tEl.remove(), 300);
                            }
                        }, 8000);
                    }
                }
            });
        }, 5000);
    });
    </script>
    """ + footer_html
    
    return render_template_string(html, patients_data=patients_data, currency=currency, total_paid_today=total_paid_today, refunds_data=refunds_data, refund_count=refund_count)

@billing_bp.route('/billing/history', methods=['GET', 'POST'])
def billing_history():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Update current task
    cursor.execute("UPDATE users SET current_task = 'أرشيف وحسابات سابقة' WHERE user_id = %s", (session['user_id'],))
    conn.commit()
    
    search_query = request.form.get('search_query', '').strip() if request.method == 'POST' else ''
    
    sql = """
        SELECT i.invoice_id, i.amount, i.created_at, p.full_name_ar, p.file_number, p.patient_id
        FROM invoices i
        JOIN patients p ON i.patient_id = p.patient_id
        WHERE i.status = 'paid'
    """
    params = []
    if search_query:
        sql += " AND (p.full_name_ar LIKE %s OR p.file_number LIKE %s)"
        params.extend([f'%{search_query}%', f'%{search_query}%'])
        
    sql += " ORDER BY i.created_at DESC LIMIT 50"
    
    cursor.execute(sql, tuple(params))
    invoices = cursor.fetchall()
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    html = header_html + """
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            --card-bg: rgba(255, 255, 255, 0.85);
            --glass-border: rgba(255, 255, 255, 0.4);
            --text-col: #2c3e50;
            --text-muted: #64748b;
            --inp-bg: rgba(0, 0, 0, 0.03);
            --shadow-sm: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.05);
            --border-radius: 1.25rem;
            --table-header-bg: rgba(79, 172, 254, 0.05);
            --hover-bg: rgba(0,0,0,0.02);
            --icon-bg: rgba(79, 172, 254, 0.15);
            --icon-col: #4facfe;
        }

        

        .billing-redesign {
            font-family: 'Tajawal', sans-serif;
            min-height: calc(100vh - 100px);
            color: var(--text-col);
        }

        .header-title {
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
        }

        .glass-card {
            background: var(--card-bg) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border) !important;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-sm);
        }

        .search-input {
            background: var(--inp-bg) !important;
            color: var(--text-col) !important;
            border: 1px solid var(--glass-border) !important;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        .search-input:focus {
            box-shadow: 0 0 0 4px var(--table-header-bg);
            border-color: var(--icon-col) !important;
        }
        .search-input::placeholder { color: var(--text-muted); }

        .btn-top-action {
            background: var(--inp-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-col);
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        .btn-top-action:hover {
            transform: translateY(-2px);
            background: var(--icon-bg);
            color: var(--icon-col);
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }

        .custom-table {
            color: var(--text-col) !important;
            --bs-table-bg: transparent;
            --bs-table-color: var(--text-col);
            border-collapse: separate;
            border-spacing: 0;
            margin: 0;
        }
        .custom-table thead th {
            background: var(--table-header-bg);
            color: var(--text-muted);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid var(--glass-border);
            padding: 1rem;
            white-space: nowrap;
        }
        .custom-table tbody tr {
            transition: all 0.2s ease;
        }
        .custom-table tbody tr:hover {
            background: var(--hover-bg);
        }
        .custom-table tbody td {
            padding: 1rem;
            border-bottom: 1px dashed var(--glass-border);
            vertical-align: middle;
        }
        .custom-table tbody tr:last-child td {
            border-bottom: none;
        }

        .badge-file {
            background: var(--inp-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-col);
        }
    </style>

    <div class="billing-redesign py-5 container-fluid" style="max-width: 1400px;">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-5 gap-4">
            <div class="d-flex align-items-center gap-4">
                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-lg" style="width: 70px; height: 70px; background: var(--primary-gradient); color: white;">
                    <i class="fas fa-file-invoice-dollar fa-2x"></i>
                </div>
                <div>
                    <h1 class="display-5 m-0 header-title">أرشيف المدفوعات</h1>
                    <p class="text-muted mt-2 mb-0 fs-5">سجل الحسابات السابقة وإعادة طباعة الوصولات</p>
                </div>
            </div>
            
            <a href="{{ url_for('billing.billing') }}" class="btn btn-top-action rounded-pill px-4 py-2 fw-bold d-flex align-items-center gap-2">
                <i class="fas fa-arrow-right fs-5"></i> العودة للصندوق
            </a>
        </div>
        
        <div class="mb-5 mx-auto" style="max-width: 900px;">
            <form method="POST" class="d-flex gap-2">
                <div class="position-relative w-100 shadow-sm rounded-pill">
                    <i class="fas fa-search position-absolute top-50 translate-middle-y fs-5" style="right: 20px; color: var(--text-muted);"></i>
                    <input type="text" name="search_query" class="form-control form-control-lg rounded-pill search-input px-5 fs-5" placeholder="ابحث باسم المرجع أو رقم الملف..." value="{{ search_query }}" style="height: 60px;">
                </div>
                <button type="submit" class="btn rounded-pill px-5 fw-bold text-white shadow-sm" style="background: var(--primary-gradient); height: 60px; font-size: 1.1rem;">بحث</button>
            </form>
        </div>
        
        <div class="mx-auto" style="max-width: 1200px;">
            {% if not invoices %}
                <div class="glass-card text-center py-5 rounded-4 shadow-sm mx-auto" style="max-width: 600px;">
                    <div class="rounded-circle d-inline-flex align-items-center justify-content-center mb-4" style="width: 80px; height: 80px; background: var(--inp-bg);">
                        <i class="fas fa-search-minus fa-2x text-muted"></i>
                    </div>
                    <h4 class="fw-bold" style="color: var(--text-col);">لا توجد حركات مالية مسجلة</h4>
                    <p class="text-muted fs-5 mb-0">لم يتم العثور على أي وصولات مطابقة للبحث.</p>
                </div>
            {% else %}
                <div class="glass-card shadow-lg border-0 rounded-4 overflow-hidden">
                    <div class="table-responsive">
                    <table class="table custom-table mb-0 align-middle text-center">
                        <thead>
                            <tr>
                                <th>رقم الوصل</th>
                                <th>اسم المراجع</th>
                                <th>رقم الملف</th>
                                <th>تاريخ الدفع</th>
                                <th>المبلغ النهائي</th>
                                <th>إجراء</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for inv in invoices %}
                            <tr>
                                <td>
                                    <div class="d-inline-flex align-items-center gap-2 px-3 py-1 rounded-pill" style="background: var(--icon-bg); color: var(--icon-col);">
                                        <i class="fas fa-receipt"></i> <span class="fw-bold">INV-{{ inv.invoice_id }}</span>
                                    </div>
                                </td>
                                <td class="fw-bold fs-5 text-start ps-4">{{ inv.full_name_ar }}</td>
                                <td><span class="badge badge-file rounded-pill px-3 py-2 fs-6 shadow-sm"><i class="fas fa-folder-open me-2 text-muted"></i>{{ inv.file_number }}</span></td>
                                <td dir="ltr" class="text-muted fw-bold">{{ format_dt(inv.created_at, '%Y-%m-%d %H:%M:%S') or '—' }}</td>
                                <td>
                                    <span class="fs-4 fw-bold" style="color: #43e97b;">{{ "{:,.0f}".format(inv.amount) }}</span> 
                                    <span class="text-muted fs-6">{{ currency }}</span>
                                </td>
                                <td>
                                    <a href="{{ url_for('billing.print_receipt', invoice_id=inv.invoice_id) }}" target="_blank" class="btn btn-sm rounded-pill px-4 shadow-sm fw-bold border-0 text-white transition-all hover-lift" style="background: var(--primary-gradient);">
                                        <i class="fas fa-print me-2"></i> طباعة الوصل
                                    </a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    </div>
                </div>
            {% endif %}
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, invoices=invoices, currency=currency, search_query=search_query)

@billing_bp.route('/billing/print/<int:invoice_id>', methods=['GET'])
def print_receipt(invoice_id):
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Get invoice details
    sql = """
        SELECT i.*, p.full_name_ar, p.file_number, u.full_name_ar as cashier_name
        FROM invoices i
        JOIN patients p ON i.patient_id = p.patient_id
        LEFT JOIN users u ON u.user_id = %s
        WHERE i.invoice_id = %s
    """
    cursor.execute(sql, (session['user_id'], invoice_id))
    inv = cursor.fetchone()
    
    if not inv:
        return "Invoice not found"
        
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    appt_id = inv.get('appointment_id')
    items = []
    
    if appt_id:
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s AND status != 'scheduled'", (appt_id,))
        a = cursor.fetchone()
        if a:
            price_consult = float(prices.get('price_consultation', 25000))
            act_price = 0 if a.get('is_free') else price_consult
            items.append({'name': 'كشف طبي للعيادة', 'price': act_price})
            
        cursor.execute("SELECT test_type as name, price FROM lab_requests WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"مختبر: {r['name']}", 'price': float(r['price'] or 0)})
            
        cursor.execute("SELECT scan_type as name, price FROM radiology_requests WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"أشعة: {r['name']}", 'price': float(r['price'] or 0)})
            
        cursor.execute("SELECT medicine_name as name, price FROM prescriptions WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"صيدلية: {r['name']}", 'price': float(r['price'] or 0)})

    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>وصل قبض رقم INV-{{ inv.invoice_id }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
            body { font-family: 'Tajawal', sans-serif; background: #e9ecef; }
            
            .receipt-card {
                background: white;
                width: 80mm; /* typical thermal receipt width */
                min-height: auto;
                margin: 20px auto;
                padding: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                border-radius: 8px;
            }

            @media print {
                body { background: white; margin: 0; padding: 0; }
                .receipt-card { margin: 0; padding: 5px; box-shadow: none; border-radius: 0; width: 100%; border: none; }
                .no-print { display: none !important; }
            }
            .dashed-line { border-top: 1px dashed #999; margin: 12px 0; }
            .item-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 13px; }
            .center-col { text-align: center; }
        </style>
    </head>
    <body>
        <div class="container no-print mt-4 text-center mb-4">
            <button onclick="window.print()" class="btn btn-primary rounded-3 px-4 py-2 shadow-sm me-2">
                <i class="fas fa-print me-2"></i> طباعة الوصل (Thermal)
            </button>
            <button onclick="window.close()" class="btn btn-outline-secondary rounded-3 px-4 py-2">
                <i class="fas fa-times me-2"></i> إغلاق
            </button>
        </div>

        <div class="receipt-card text-dark">
            <div class="text-center mb-2">
                <div class="fs-4 fw-bold">HealthPro <i class="fas fa-plus-square text-danger"></i></div>
                <div class="small text-muted">الوصل المالي الموحد</div>
            </div>
            
            <div class="dashed-line"></div>
            
            <div class="mb-2" style="font-size: 13px;">
                <div class="item-row"><span>رقم الوصل:</span> <span class="fw-bold">INV-{{ inv.invoice_id }}</span></div>
                <div class="item-row"><span>التاريخ:</span> <span dir="ltr">{{ format_dt(inv.created_at, '%Y-%m-%d %H:%M:%S') or '—' }}</span></div>
                <div class="item-row"><span>اسم المراجع:</span> <span class="fw-bold">{{ inv.full_name_ar }}</span></div>
                <div class="item-row"><span>رقم الملف:</span> <span>{{ inv.file_number }}</span></div>
            </div>

            <div class="dashed-line"></div>
            
            <div style="font-size: 13px;" class="mb-2">
                <div class="fw-bold text-center mb-2 bg-light py-1 rounded">التفاصيل</div>
                {% if items %}
                    {% for item in items %}
                    <div class="item-row">
                        <span style="max-width: 70%;">{{ item.name }}</span>
                        <span class="fw-bold">{{ "{:,.0f}".format(item.price) }}</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="text-center text-muted small py-2">دفعة مسددة مسبقاً</div>
                {% endif %}
            </div>

            <div class="dashed-line" style="border-top-width: 2px;"></div>
            
            <div class="d-flex justify-content-between align-items-center mb-2 bg-light p-2 rounded">
                <span class="fw-bold">المبلغ المسدد:</span>
                <span class="fw-bold fs-5">{{ "{:,.0f}".format(inv.amount) }} <small class="fs-6">{{ currency }}</small></span>
            </div>

            <div class="dashed-line"></div>
            
            <div class="text-center mt-2" style="font-size: 11px; color:#555;">
                أمين الصندوق: {{ inv.cashier_name }}<br>
                نتمنى لكم دوام الصحة والعافية
            </div>
            
            <div class="text-center mt-3">
                <canvas id="barcode"></canvas>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <script>
            JsBarcode("#barcode", "INV-{{ inv.invoice_id }}", {
                format: "CODE128",
                width: 1.2,
                height: 35,
                displayValue: true,
                fontSize: 10,
                margin: 0
            });
            // window.print();
        </script>
    </body>
    </html>
    """
    return render_template_string(html, inv=inv, currency=currency, items=items)

@billing_bp.route('/billing/statement', methods=['GET', 'POST'])
def patient_statement():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
    cursor = conn.cursor(dictionary=True)
    
    search_query = request.form.get('search_query', '').strip() if request.method == 'POST' else ''
    
    patients = []
    selected_patient = None
    statement_data = []
    totals = {'paid': 0.0, 'unpaid': 0.0, 'total': 0.0}
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    if search_query:
        # Search for patients
        cursor.execute("SELECT patient_id, full_name_ar, file_number FROM patients WHERE full_name_ar LIKE %s OR file_number LIKE %s LIMIT 10", (f'%{search_query}%', f'%{search_query}%'))
        patients = cursor.fetchall()
        
        # If a single match or specific request, show their statement
        patient_id = request.form.get('patient_id')
        if not patient_id and len(patients) == 1:
            patient_id = patients[0]['patient_id']
            
        if patient_id:
            cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
            selected_patient = cursor.fetchone()
            
            if selected_patient:
                # Get paid invoices
                cursor.execute(
                    "SELECT invoice_id, appointment_id, amount, created_at, 'paid' as status FROM invoices WHERE patient_id = %s AND status = 'paid' ORDER BY invoice_id DESC",
                    (patient_id,),
                )
                statement_data.extend(cursor.fetchall())

                # Calculate unpaid services (simple estimation for statement overview)
                cursor.execute(
                    "SELECT appointment_id, appointment_date FROM appointments WHERE patient_id = %s AND status = 'scheduled'",
                    (patient_id,),
                )
                for a in cursor.fetchall():
                    statement_data.append({
                        'invoice_id': '-',
                        'appointment_id': a['appointment_id'],
                        'amount': float(prices.get('price_consultation', 25000)),
                        'created_at': a['appointment_date'],
                        'status': 'unpaid',
                        'type': 'كشف طبي',
                    })

                _heal_statement_timestamps(cursor, conn, statement_data)

                # Calculate totals
                for item in statement_data:
                    amt = float(item['amount'] or 0)
                    totals['total'] += amt
                    if item['status'] == 'paid':
                        totals['paid'] += amt
                    else:
                        totals['unpaid'] += amt

    html = header_html + """
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --info-gradient: linear-gradient(135deg, #1cd8d2 0%, #93edc7 100%);
            --warning-gradient: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
            --danger-gradient: linear-gradient(135deg, #ff0844 0%, #ffb199 100%);
            --card-bg: rgba(255, 255, 255, 0.85);
            --glass-border: rgba(255, 255, 255, 0.4);
            --text-col: #2c3e50;
            --text-muted: #64748b;
            --inp-bg: rgba(0, 0, 0, 0.03);
            --shadow-sm: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.05);
            --border-radius: 1.25rem;
            --table-header-bg: rgba(28, 216, 210, 0.05);
            --hover-bg: rgba(0,0,0,0.02);
            --list-hover: rgba(28, 216, 210, 0.05);
        }

        

        .billing-redesign {
            font-family: 'Tajawal', sans-serif;
            min-height: calc(100vh - 100px);
            color: var(--text-col);
        }

        .header-title {
            background: var(--info-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
        }

        .glass-card {
            background: var(--card-bg) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border) !important;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-sm);
        }

        .search-input {
            background: var(--inp-bg) !important;
            color: var(--text-col) !important;
            border: 1px solid var(--glass-border) !important;
            transition: all 0.3s ease;
        }
        .search-input:focus {
            box-shadow: 0 0 0 4px var(--table-header-bg);
            border-color: #2af598 !important;
        }

        .btn-top-action {
            background: var(--inp-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-col);
            transition: all 0.3s ease;
        }
        .btn-top-action:hover {
            transform: translateY(-2px);
            background: rgba(42, 245, 152, 0.1);
            color: #2af598;
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }

        .stat-card {
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card::before {
            content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 6px;
        }
        .stat-card-warning::before { background: var(--warning-gradient); }
        .stat-card-success::before { background: var(--primary-gradient); }
        .stat-card-danger::before { background: var(--danger-gradient); }

        .list-group-item-custom {
            background: transparent;
            border: none;
            border-bottom: 1px solid var(--glass-border);
            color: var(--text-col);
            transition: all 0.2s ease;
        }
        .list-group-item-custom:hover { background: var(--list-hover); }

        .custom-table {
            color: var(--text-col) !important;
            --bs-table-bg: transparent;
            --bs-table-color: var(--text-col);
            border-collapse: separate;
            border-spacing: 0;
            margin: 0;
        }
        .custom-table thead th {
            background: var(--table-header-bg);
            color: var(--text-muted);
            font-weight: 700;
            text-transform: uppercase;
            border-bottom: 2px solid var(--glass-border);
            padding: 1.25rem 1rem;
        }
        .custom-table tbody tr { transition: all 0.2s ease; }
        .custom-table tbody tr:hover { background: var(--hover-bg); }
        .custom-table tbody td {
            padding: 1.25rem 1rem;
            border-bottom: 1px dashed var(--glass-border);
            vertical-align: middle;
        }

        @media print {
            body * { visibility: hidden; }
            #statementPrintArea, #statementPrintArea * { visibility: visible; }
            #statementPrintArea { 
                position: absolute; left: 0; top: 0; width: 100%; 
                background: white !important; 
                color: black !important;
                box-shadow: none !important; border: none !important; 
            }
            .no-print { display: none !important; }
            .glass-card { background: white !important; border: 1px solid #ddd !important; }
            .custom-table thead th { background: #f8f9fa !important; border-bottom: 2px solid #333 !important; }
            .custom-table tbody td { border-bottom: 1px solid #ddd !important; }
        }

        .header-title-white {
            color: #ffffff !important;
            font-weight: 900;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .search-area-premium {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 15px;
            backdrop-filter: blur(10px);
        }
        .search-input-premium {
            background: rgba(0,0,0,0.2) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            color: #ffffff !important;
            height: 60px !important;
            font-size: 1.2rem !important;
            padding-right: 60px !important;
            border-radius: 15px !important;
            transition: all 0.3s;
        }
        .search-input-premium:focus {
            background: rgba(0,0,0,0.3) !important;
            border-color: #6366f1 !important;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.2) !important;
        }
        .btn-search-premium {
            background: var(--primary-gradient) !important;
            color: white !important;
            border: none !important;
            border-radius: 15px !important;
            padding: 0 40px !important;
            font-weight: 800 !important;
            font-size: 1.1rem !important;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
        }
        .btn-search-premium:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4) !important;
        }
    </style>

    <div class="billing-redesign py-5 container" style="max-width: 1200px;">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-5 gap-4">
            <div class="d-flex align-items-center gap-4">
                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-lg" style="width: 70px; height: 70px; background: var(--primary-gradient); color: white;">
                    <i class="fas fa-file-invoice-dollar fa-2x"></i>
                </div>
                <div>
                    <h1 class="header-title-white m-0">كشف الحساب</h1>
                    <p class="text-muted mt-2 mb-0 fs-5">متابعة الحركات المالية، المبالغ المسددة والمتبقية للمراجعين</p>
                </div>
            </div>
            
            <a href="{{ url_for('billing.billing') }}" class="btn btn-top-action rounded-pill px-4 py-2 fw-bold d-flex align-items-center gap-2">
                <i class="fas fa-arrow-right fs-5"></i> الرجوع للصندوق
            </a>
        </div>
        
        <div class="mb-5 mx-auto search-area-premium" style="max-width: 900px;">
            <form method="POST" class="d-flex gap-3">
                <div class="position-relative w-100">
                    <i class="fas fa-search position-absolute top-50 translate-middle-y fs-4" style="right: 25px; color: #6366f1;"></i>
                    <input type="text" name="search_query" class="form-control search-input-premium" placeholder="ابحث باسم المرجع أو رقم الملف..." value="{{ search_query }}">
                </div>
                <button type="submit" class="btn btn-search-premium">بـحـث</button>
            </form>
        </div>
        
        <div class="mx-auto" style="max-width: 1100px;">
            {% if patients and not selected_patient %}
                <div class="glass-card shadow-lg border-0 rounded-4 overflow-hidden mb-5">
                    <div class="p-4" style="background: var(--table-header-bg); border-bottom: 1px solid var(--glass-border);">
                        <h4 class="fw-bold m-0"><i class="fas fa-list-check me-2" style="color: #009efd;"></i> يرجى تحديد المراجع المطلوب</h4>
                    </div>
                    <div class="list-group list-group-flush p-3">
                    {% for p in patients %}
                        <form method="POST" class="list-group-item list-group-item-custom d-flex justify-content-between align-items-center p-3 rounded-3 mb-2">
                            <input type="hidden" name="search_query" value="{{ search_query }}">
                            <input type="hidden" name="patient_id" value="{{ p.patient_id }}">
                            <div class="d-flex align-items-center gap-3">
                                <div class="rounded-circle d-flex align-items-center justify-content-center" style="width: 45px; height: 45px; background: rgba(0, 158, 253, 0.1); color: #009efd;">
                                    <i class="fas fa-user"></i>
                                </div>
                                <div>
                                    <h5 class="fw-bold mb-1">{{ p.full_name_ar }}</h5>
                                    <span class="badge rounded-pill" style="background: var(--inp-bg); border: 1px solid var(--glass-border); color: var(--text-col);"><i class="fas fa-folder me-1 text-muted"></i> ملف: {{ p.file_number }}</span>
                                </div>
                            </div>
                            <button type="submit" class="btn rounded-pill px-4 fw-bold shadow-sm text-white" style="background: var(--primary-gradient); border: none;">استخراج الكشف <i class="fas fa-arrow-left ms-2"></i></button>
                        </form>
                    {% endfor %}
                    </div>
                </div>
            {% endif %}

            {% if selected_patient %}
                <div class="row g-4 mb-4">
                    <div class="col-md-4">
                        <div class="glass-card stat-card stat-card-warning p-4 rounded-4 text-center h-100 shadow-sm">
                            <div class="d-flex justify-content-center mb-3">
                                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm" style="width: 50px; height: 50px; background: rgba(246, 211, 101, 0.1); color: #f6d365;">
                                    <i class="fas fa-file-invoice fs-4"></i>
                                </div>
                            </div>
                            <div class="text-muted small mb-1 fw-bold fs-6">إجمالي المطالبات</div>
                            <h2 class="fw-bold" style="color: var(--text-col);">{{ "{:,.0f}".format(totals.total) }} <small class="fs-6 text-muted">{{ currency }}</small></h2>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card stat-card stat-card-success p-4 rounded-4 text-center h-100 shadow-sm">
                            <div class="d-flex justify-content-center mb-3">
                                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm" style="width: 50px; height: 50px; background: rgba(17, 153, 142, 0.1); color: #11998e;">
                                    <i class="fas fa-check-double fs-4"></i>
                                </div>
                            </div>
                            <div class="text-muted small mb-1 fw-bold fs-6">إجمالي المسدد</div>
                            <h2 class="fw-bold" style="color: #38ef7d;">{{ "{:,.0f}".format(totals.paid) }} <small class="fs-6 text-muted">{{ currency }}</small></h2>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card stat-card stat-card-danger p-4 rounded-4 text-center h-100 shadow-sm">
                            <div class="d-flex justify-content-center mb-3">
                                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm" style="width: 50px; height: 50px; background: rgba(255, 8, 68, 0.1); color: #ff0844;">
                                    <i class="fas fa-exclamation-circle fs-4"></i>
                                </div>
                            </div>
                            <div class="text-muted small mb-1 fw-bold fs-6">المتبقي (الذمة)</div>
                            <h2 class="fw-bold" style="color: #ff0844;">{{ "{:,.0f}".format(totals.unpaid) }} <small class="fs-6 text-muted">{{ currency }}</small></h2>
                        </div>
                    </div>
                </div>
                
                <div class="glass-card shadow-lg border-0 rounded-4 overflow-hidden mb-5" id="statementPrintArea">
                    <div class="p-4 d-flex justify-content-between align-items-center" style="background: var(--table-header-bg); border-bottom: 2px solid var(--glass-border);">
                        <div class="d-flex align-items-center gap-3">
                            <div class="rounded-circle bg-white text-dark d-flex align-items-center justify-content-center shadow-sm" style="width: 60px; height: 60px;">
                                <i class="fas fa-hospital fa-2x"></i>
                            </div>
                            <div>
                                <h3 class="fw-bold mb-1" style="color: var(--text-col);">كشف حساب شامل</h3>
                                <div class="d-flex gap-3 text-muted">
                                    <span><i class="fas fa-user-injured me-1"></i> {{ selected_patient.full_name_ar }}</span>
                                    <span><i class="fas fa-hashtag me-1"></i> {{ selected_patient.file_number }}</span>
                                </div>
                            </div>
                        </div>
                        <button onclick="window.print()" class="btn rounded-pill px-4 py-2 shadow-sm fw-bold no-print text-white" style="background: var(--info-gradient);">
                            <i class="fas fa-print me-2"></i> طباعة الكشف
                        </button>
                    </div>
                    
                    <div class="table-responsive">
                    <table class="table custom-table mb-0 align-middle text-center">
                        <thead>
                            <tr>
                                <th>التاريخ والتوقيت</th>
                                <th>رقم الحركة</th>
                                <th>البيان والتفاصيل</th>
                                <th>المبلغ ({{ currency }})</th>
                                <th>الحالة</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if statement_data %}
                                {% for item in statement_data %}
                                <tr>
                                    <td dir="ltr" class="text-muted fw-bold">
                                        {{ format_dt(item.created_at, '%Y-%m-%d %H:%M:%S') or '—' }}
                                        {% if item.is_frozen %}
                                            <span class="ms-1 text-success" title="الوقت محفوظ وثابت في قاعدة البيانات"><i class="fas fa-shield-check"></i></span>
                                        {% else %}
                                            <span class="ms-1 text-warning" title="وقت تلقائي - سيتم تثبيته الآن"><i class="fas fa-clock-rotate-left"></i></span>
                                        {% endif %}
                                    </td>

                                    <td>
                                        <span class="badge rounded-pill px-3 py-2 fw-bold" style="background: rgba(0, 158, 253, 0.1); color: #009efd; border: 1px solid rgba(0, 158, 253, 0.2);">
                                            {{ item.invoice_id if item.invoice_id != '-' else 'بدون وصل' }}
                                        </span>
                                    </td>
                                    <td class="fw-bold text-start ps-4">{{ item.type if item.get('type') else 'دفعة نقدية مسددة بالصندوق' }}</td>
                                    <td class="fs-5 fw-bold" style="color: var(--text-col);">{{ "{:,.0f}".format(item.amount) }}</td>
                                    <td>
                                        {% if item.status == 'paid' %}
                                            <span class="badge rounded-pill border border-success border-opacity-25 px-4 py-2" style="background: rgba(17, 153, 142, 0.1); color: #11998e;"><i class="fas fa-check-double me-1"></i> مسدد بالكامل</span>
                                        {% else %}
                                            <span class="badge rounded-pill border border-danger border-opacity-25 px-4 py-2" style="background: rgba(255, 8, 68, 0.1); color: #ff0844;"><i class="fas fa-circle-xmark me-1"></i> مطلوب الدفع</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="5" class="py-5 text-center">
                                        <i class="fas fa-inbox fa-3x text-muted mb-3 opacity-50"></i>
                                        <h5 class="text-muted">لا يوجد سجل مالي لهذا المراجع</h5>
                                    </td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                    </div>
                </div>
            {% endif %}
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, search_query=search_query, patients=patients, selected_patient=selected_patient, statement_data=statement_data, totals=totals, currency=currency)
