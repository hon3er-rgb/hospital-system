from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, format_datetime, local_now

print_rx_bp = Blueprint('print_rx', __name__)

@print_rx_bp.route('/print_rx', methods=['GET'])
def print_rx():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    presc_id = request.args.get('prescription_id')
    appt_id = request.args.get('id')

    if not presc_id and not appt_id:
        return "No ID provided"

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)
    
    # Use LEFT JOINs so we still get data even if appointment/dept records are missing
    sql = """
        SELECT pr.*, p.full_name_ar, p.file_number, p.gender, p.date_of_birth, p.phone1,
               u.full_name_ar as doc_name, d.department_name_ar
        FROM prescriptions pr
        JOIN patients p ON pr.patient_id = p.patient_id
        LEFT JOIN users u ON pr.doctor_id = u.user_id
        LEFT JOIN appointments a ON pr.appointment_id = a.appointment_id
        LEFT JOIN departments d ON a.department_id = d.department_id
        WHERE """
    
    if presc_id:
        sql += "pr.prescription_id = %s"
        param = (presc_id,)
    else:
        sql += "pr.appointment_id = %s"
        param = (appt_id,)
        
    sql += " LIMIT 1"
    
    cursor.execute(sql, param)
    data = cursor.fetchone()
    conn.close()

    if not data:
        return "Prescription not found"

    # Use centralized formatter for all date fields
    data['created_at_fmt'] = format_datetime(data.get('created_at'), '%d %b %Y | %H:%M:%S')
    if not data['created_at_fmt'] or 'CURRENT' in str(data.get('created_at')).upper():
        data['created_at_fmt'] = local_now().strftime('%d %b %Y | %H:%M:%S')
    
    data['dob_fmt'] = format_datetime(data.get('date_of_birth'), '%Y-%m-%d')

    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">

    <head>
        <meta charset="UTF-8">
        <title>وصفة طبية - {{ data.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;800&display=swap');

            * { box-sizing: border-box; }

            body {
                font-family: 'Cairo', sans-serif;
                background: #eef0f3;
                color: #1e293b;
                font-size: 12px;
                margin: 0;
            }

            .rx-card {
                background: white;
                width: 190mm;
                margin: 24px auto;
                padding: 28px 32px 24px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.1);
                border-radius: 6px;
                position: relative;
                border-top: 5px solid #1e3a5f;
            }

            /* الهيدر */
            .header-box {
                border-bottom: 1.5px solid #e2e8f0;
                padding-bottom: 14px;
                margin-bottom: 14px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .hospital-name {
                font-size: 16px;
                font-weight: 800;
                color: #1e3a5f;
                line-height: 1.2;
            }

            .hospital-sub {
                font-size: 10px;
                color: #94a3b8;
                margin-top: 2px;
            }

            .rx-badge {
                background: #1e3a5f;
                color: white;
                font-size: 18px;
                font-weight: 900;
                font-style: italic;
                width: 46px; height: 46px;
                border-radius: 10px;
                display: flex; align-items: center; justify-content: center;
                letter-spacing: -1px;
            }

            /* شريط معلومات slim */
            .info-bar {
                display: flex;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                overflow: hidden;
                margin-bottom: 16px;
                font-size: 11px;
            }
            .info-bar .ib-cell {
                flex: 1;
                padding: 7px 12px;
                border-left: 1px solid #e2e8f0;
                text-align: center;
            }
            .info-bar .ib-cell:last-child { border-left: none; }
            .info-bar .ib-cell.wide { flex: 1.8; }
            .info-bar .ib-label {
                font-size: 9px;
                font-weight: 700;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.4px;
                margin-bottom: 2px;
            }
            .info-bar .ib-val {
                font-weight: 800;
                color: #1e293b;
                font-size: 11.5px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .info-bar .ib-cell.shaded { background: #f8fafc; }

            /* قسم الدواء */
            .rx-label {
                font-size: 10px;
                font-weight: 700;
                color: #3b82f6;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .rx-label::after {
                content: '';
                flex: 1;
                height: 1px;
                background: #e2e8f0;
            }

            .medication-area {
                min-height: 90px;
                font-size: 12px;
                line-height: 2;
                padding: 14px 18px;
                border-right: 4px solid #3b82f6;
                background: #f8faff;
                border-radius: 0 6px 6px 0;
                text-align: right;
                color: #1e293b;
                font-weight: 600;
                margin-bottom: 16px;
            }

            /* الفوتر */
            .rx-footer {
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                border-top: 1px solid #e2e8f0;
                padding-top: 12px;
                margin-top: 12px;
                font-size: 10px;
                color: #94a3b8;
            }
            .sig-line {
                width: 120px;
                border-bottom: 1px solid #cbd5e1;
                margin-top: 28px;
                margin-bottom: 2px;
            }

            @media print {
                body { background: white; margin: 0; font-size: 12px; }
                .rx-card {
                    margin: 0 auto;
                    box-shadow: none;
                    border-radius: 0;
                    width: 100%;
                    padding: 20px 28px;
                }
                .no-print { display: none !important; }
            }
        </style>

    </head>

    <body>

        <div class="container no-print mt-3 text-center">
            <div class="d-inline-flex align-items-center gap-2 bg-white shadow rounded-pill px-4 py-2">
                <button onclick="window.print()" class="btn btn-dark px-4 rounded-pill btn-sm">
                    <i class="fas fa-print me-1"></i> طباعة الوصفة
                </button>
                <button onclick="shareAsPDF()" class="btn btn-success px-4 rounded-pill btn-sm" id="waBtn">
                    <i class="fab fa-whatsapp me-1"></i> إرسال واتساب (PDF)
                </button>
                <a href="/doctor_clinic" class="btn btn-primary px-4 rounded-pill btn-sm">
                    <i class="fas fa-clinic-medical me-1"></i> العودة للعيادة
                </a>
            </div>
        </div>

        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <script>
            async function shareAsPDF() {
                const btn = document.getElementById('waBtn');
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> التجهيز...';
                
                try {
                    const element = document.querySelector('.rx-card');
                    const filename = 'وصفة طبية - {{ data.full_name_ar }}';
                    
                    // 1. Copy image to clipboard
                    const canvas = await html2canvas(element, { scale: 2 });
                    canvas.toBlob(async (blob) => {
                        try {
                            const item = new ClipboardItem({ "image/png": blob });
                            await navigator.clipboard.write([item]);
                        } catch (err) {}
                    });

                    // 2. Download PDF
                    const opt = {
                        margin: 10,
                        filename: filename + '.pdf',
                        html2canvas: { scale: 2 },
                        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                    };
                    await html2pdf().set(opt).from(element).save();

                    // 3. Open WhatsApp
                    const waText = "مرحباً، إليك ملف الوصفة الطبية الخاصة بك. تم نسخ الصورة في جهازك، فقط اضغط (Ctrl+V) في المحادثة.";
                    const waUrl = "https://wa.me/{{ data.phone1|string|replace('+', '')|replace(' ', '') }}?text=" + encodeURIComponent(waText);
                    window.open(waUrl, '_blank');
                    
                    alert("تم التحويل! يمكنك الآن الضغط على (Ctrl+V) في الواتساب لإرسال التقرير فوراً.");
                    btn.innerHTML = original;
                } catch (err) {
                    btn.innerHTML = original;
                }
            }
        </script>

        <div class="rx-card">

            <!-- ── Header ── -->
            <div class="header-box">
                <div>
                    <div class="hospital-name">{% if system_icon %}<i class="{{ system_icon }}"></i>{% endif %} {{ system_name }}</div>
                    <div class="hospital-sub">للخدمات الطبية الرقمية &nbsp;|&nbsp; Electronic Medical Services</div>
                </div>
                <div class="rx-badge">Rx</div>
            </div>

            <!-- ── Slim Info Bar ── -->
            <div class="info-bar">
                <div class="ib-cell wide" style="text-align:right;">
                    <div class="ib-label">اسم المريض / Patient</div>
                    <div class="ib-val">{{ data.full_name_ar }}</div>
                </div>
                <div class="ib-cell">
                    <div class="ib-label">رقم الملف / File</div>
                    <div class="ib-val">#{{ data.file_number }}</div>
                </div>
                <div class="ib-cell">
                    <div class="ib-label">الجنس / Gender</div>
                    <div class="ib-val">{{ 'ذكر' if data.gender == 'male' else 'أنثى' }}</div>
                </div>
                <div class="ib-cell wide">
                    <div class="ib-label">الطبيب / Physician</div>
                    <div class="ib-val">د. {{ data.doc_name }}</div>
                </div>
                <div class="ib-cell">
                    <div class="ib-label">القسم / Dept</div>
                    <div class="ib-val">{{ data.department_name_ar or '—' }}</div>
                </div>
                <div class="ib-cell shaded">
                    <div class="ib-label">التاريخ والوقت / Date & Time</div>
                    <div class="ib-val" dir="ltr" style="font-size: 10px;">
                        {{ data.created_at_fmt }}
                    </div>
                </div>
            </div>

            <!-- ── Prescription ── -->
            <div class="rx-label"><i class="fas fa-prescription"></i> الوصفة الطبية &nbsp;/&nbsp; Prescription</div>
            <div class="medication-area">
                {{ data.medicine_name | replace('\\n', '<br>') | safe }}
            </div>

            <!-- ── Footer ── -->
            <div class="rx-footer">
                <div style="text-align:right;">
                    <div class="sig-line"></div>
                    <div>توقيع الطبيب / Physician Signature</div>
                </div>
                <div style="text-align:center;">
                    <canvas id="barcode"></canvas>
                    <div style="font-size:9px;margin-top:2px;color:#cbd5e1;">{{ data.file_number }}</div>
                </div>
                <div style="text-align:left;">
                    <div>✓ صالح لمدة 7 أيام من تاريخه</div>
                    <div style="margin-top:4px;">{{ system_name }} — Medical System</div>
                </div>
            </div>
        </div>


        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <script>
            JsBarcode("#barcode", "{{ data.file_number }}", {
                format: "CODE128",
                width: 1.2,
                height: 40,
                displayValue: false,
                margin: 0
            });
            // طباعة تلقائية عند الفتح بعد 600ms
            window.addEventListener('load', function() {
                setTimeout(function() { window.print(); }, 600);
            });
        </script>
    </body>
    </html>
    """
    
    return render_template_string(html, data=data)
