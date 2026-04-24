from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from datetime import datetime

print_lab_bp = Blueprint('print_lab', __name__)

@print_lab_bp.route('/print_lab')
def print_lab():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    patient_id = request.args.get('patient_id')
    print_date = request.args.get('date') # Format: YYYY-MM-DD or 'CURRENT_DATE'
    
    if not patient_id:
        return "Patient ID is missing"
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # 1. If date is empty or invalid, find the latest date that has results for this patient
    is_date_valid = False
    if print_date and len(print_date) == 10 and print_date[4] == '-' and print_date[7] == '-':
        is_date_valid = True

    from config import local_today_str
    today_str = local_today_str()

    if not print_date or not is_date_valid or print_date.upper().startswith('CURRENT_DA') or print_date == 'None' or print_date == '':
        cursor.execute("""
            SELECT created_at FROM lab_requests 
            WHERE patient_id = %s AND result IS NOT NULL 
            ORDER BY request_id DESC LIMIT 1;
        """, (patient_id,))
        row = cursor.fetchone()
        
        if row:
            raw_val = str(row['created_at'])
            if 'CURRENT' in raw_val.upper():
                print_date = today_str
            else:
                print_date = raw_val[:10]
        else:
            print_date = today_str

    # Fetch Patient Info with Age calculation for SQLite
    cursor.execute("""
        SELECT p.*, 
               CAST((julianday('now') - julianday(p.date_of_birth)) / 365.25 AS INTEGER) as age
        FROM patients p WHERE p.patient_id = %s
    """, (patient_id,))
    patient = cursor.fetchone()

    # Fetch Doctor name from the latest lab request for this date
    doctor_name = "N/A"
    cursor.execute("""
        SELECT u.full_name_ar 
        FROM lab_requests lr
        LEFT JOIN users u ON lr.doctor_id = u.user_id
        WHERE lr.patient_id = %s 
          AND lr.result IS NOT NULL
          AND (DATE(lr.created_at) = %s OR lr.created_at LIKE %s || '%%')
        ORDER BY lr.request_id DESC LIMIT 1
    """, (patient_id, print_date, print_date))
    doctor_row = cursor.fetchone()
    if doctor_row and doctor_row.get('full_name_ar'):
        doctor_name = doctor_row['full_name_ar']

    # Fetch Labs for this specific date
    # We use a more robust WHERE clause that handles both valid dates and the corrupted 'CURRENT' string
    cursor.execute("""
        SELECT lr.*, lt.unit, lt.min_value, lt.max_value
        FROM lab_requests lr
        LEFT JOIN lab_tests lt ON lr.test_type = lt.test_name
        WHERE lr.patient_id = %s 
          AND lr.result IS NOT NULL
          AND (
              DATE(lr.created_at) = %s 
              OR lr.created_at LIKE CONCAT(%s, '%%')
              OR (lr.created_at LIKE '%%CURRENT%%' AND %s = %s)
          )
        ORDER BY lr.request_id ASC
    """, (patient_id, print_date, print_date, print_date, today_str))
    labs = cursor.fetchall()
    
    # Final Fallback: If no results for this specific date, check if there are ANY results at all and use the latest
    if not labs:
        cursor.execute("""
            SELECT created_at FROM lab_requests 
            WHERE patient_id = %s AND result IS NOT NULL 
            ORDER BY request_id DESC LIMIT 1;
        """, (patient_id,))
        row = cursor.fetchone()
        if row:
            raw_val = str(row['created_at'])
            if 'CURRENT' in raw_val.upper():
                print_date = today_str
            else:
                print_date = raw_val[:10]

            cursor.execute("""
                SELECT lr.*, lt.unit, lt.min_value, lt.max_value
                FROM lab_requests lr
                LEFT JOIN lab_tests lt ON lr.test_type = lt.test_name
                WHERE lr.patient_id = %s 
                  AND lr.result IS NOT NULL
                  AND (
                      DATE(lr.created_at) = %s 
                      OR lr.created_at LIKE CONCAT(%s, '%%')
                      OR (lr.created_at LIKE '%%CURRENT%%' AND %s = %s)
                  )
                ORDER BY lr.request_id ASC
            """, (patient_id, print_date, print_date, print_date, today_str))
            labs = cursor.fetchall()

    # Enrich labs with abnormal status for the template
    for l in labs:
        l['status_text'] = "Normal"
        l['status_class'] = "status-normal"
        l['is_abnormal'] = False
        l['direction'] = None
        
        if l.get('result') and l.get('min_value') is not None and l.get('max_value') is not None:
            try:
                val = float(str(l['result']).strip())
                min_v = float(l['min_value'])
                max_v = float(l['max_value'])
                
                if val < min_v:
                    l['is_abnormal'] = True
                    l['direction'] = 'down'
                    l['status_text'] = "Low"
                    l['status_class'] = "status-low"
                elif val > max_v:
                    l['is_abnormal'] = True
                    l['direction'] = 'up'
                    l['status_text'] = "High"
                    l['status_class'] = "status-high"
            except (ValueError, TypeError):
                l['status_text'] = "---"
                l['status_class'] = "status-none"

    conn.close()

    if not labs:
        return f"No lab results found for patient #{patient_id}. Please ensure results have been entered in the lab module."

    html = """
    <!DOCTYPE html>
    <html dir="ltr" lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Laboratory Report - {{ patient.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');
            
            :root {
                --primary-color: #0369a1; /* Professional Medical Blue */
                --accent-color: #0ea5e9;
                --success-bg: #f0fdf4;
                --success-text: #166534;
                --danger-bg: #fef2f2;
                --danger-text: #991b1b;
                --warning-bg: #fffbeb;
                --warning-text: #92400e;
                --border-color: #e2e8f0;
            }

            body { 
                font-family: 'Tajawal', sans-serif; 
                background: #f1f5f9; 
                padding: 40px 0;
                color: #1e293b;
            }

            .report-container {
                max-width: 1000px; /* Slightly wider to accommodate single-line layout */
                margin: 0 auto;
            }

            .report-box { 
                background: #fff;
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
                padding: 40px; 
                position: relative; 
                min-height: 297mm;
                border: 1px solid var(--border-color);
            }

            .header-banner {
                background: linear-gradient(135deg, #0369a1 0%, #075985 100%);
                margin: -40px -40px 30px -40px;
                padding: 30px 40px;
                border-radius: 16px 16px 0 0;
                color: white;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .brand-logo {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .brand-logo i {
                font-size: 2rem;
                color: #60a5fa;
            }

            .brand-name h2 {
                margin: 0;
                font-weight: 700;
                font-size: 1.5rem;
            }

            .brand-name p {
                margin: 0;
                font-size: 0.75rem;
                opacity: 0.8;
                text-transform: uppercase;
            }

            .patient-info-card {
                background: #f8fafc;
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 15px 20px;
                margin-bottom: 30px;
            }

            .patient-info-row {
                display: flex;
                flex-wrap: wrap;
                gap: 8px 25px;
                background: #f8fafc;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                margin: 15px 20px 20px 20px;
                align-items: center;
                justify-content: center;
            }

            .info-item {
                display: flex;
                align-items: center;
                gap: 6px;
                white-space: nowrap;
            }

            .info-item.wide {
                flex: 1;
                min-width: 150px;
            }

            .info-icon {
                color: #0369a1;
                font-size: 0.9rem;
                margin-right: 4px;
            }

            .info-value-sm {
                font-size: 0.85rem;
                font-weight: 600;
                color: #0f172a;
            }

            .info-label {
                font-size: 0.65rem;
                font-weight: 700;
                color: #64748b;
                text-transform: uppercase;
                margin-bottom: 2px;
            }

            .info-value {
                font-weight: 700;
                color: #0f172a;
                font-size: 0.9rem;
            }

            .lab-table { 
                width: 100%; 
                border-collapse: collapse;
            }

            .lab-table th { 
                padding: 10px 12px;
                font-weight: 700;
                color: #475569;
                font-size: 0.8rem;
                text-transform: uppercase;
                border-bottom: 2px solid #e2e8f0;
                white-space: nowrap;
            }

            .lab-table td { 
                padding: 12px 12px;
                border-bottom: 1px solid #f1f5f9;
                vertical-align: middle;
                font-size: 0.85rem;
                white-space: nowrap;
            }

            .status-badge {
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 0.65rem;
                font-weight: 600;
                text-transform: uppercase;
                display: inline-flex;
                align-items: center;
                gap: 3px;
                border: none;
            }

            .status-normal { background: #dcfce7; color: #166534; }
            .status-high { background: #fee2e2; color: #991b1b; }
            .status-low { background: #fee2e2; color: #991b1b; }
            .status-none { background: #f1f5f9; color: #64748b; }

            .result-value {
                font-weight: 700;
                font-size: 0.85rem;
            }

            .abnormal-indicator {
                font-size: 0.8rem;
                margin-left: 5px;
            }

            .footer-signature {
                position: absolute;
                bottom: 80px;
                left: 40px;
                right: 40px;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 40px;
                text-align: center;
            }

            .sig-box {
                border-top: 2px solid #334155;
                padding-top: 10px;
            }

            .generation-info {
                position: absolute;
                bottom: 30px;
                left: 0;
                right: 0;
                text-align: center;
            }

            @media print {
                @page {
                    size: A4;
                    margin: 0;
                }
                * {
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                    color-adjust: exact !important;
                    box-sizing: border-box !important;
                }
                html, body {
                    background: white !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    width: 210mm !important;
                    height: 297mm !important;
                    overflow: hidden !important;
                    -webkit-print-color-adjust: exact !important;
                }
                .no-print { display: none !important; }
                .report-container {
                    max-width: 100% !important;
                    width: 100% !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }
                .report-box {
                    box-shadow: none !important;
                    border: none !important;
                    border-radius: 0 !important;
                    padding: 0 !important;
                    width: 100% !important;
                    min-height: 297mm !important;
                    height: 297mm !important;
                    max-height: 297mm !important;
                    margin: 0 !important;
                    position: relative !important;
                    overflow: hidden !important;
                    page-break-after: always;
                    page-break-inside: avoid !important;
                    -webkit-print-color-adjust: exact !important;
                }
                .header-banner {
                    margin: 0 !important;
                    padding: 15px 20px !important;
                    border-radius: 6px 6px 0 0 !important;
                    background: linear-gradient(135deg, #0369a1 0%, #075985 100%) !important;
                    border-bottom: 3px solid #0284c7 !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }
                .patient-info-card {
                    background: #f8fafc !important;
                    border: 1px solid #e2e8f0 !important;
                    border-radius: 8px !important;
                    margin: 15px 20px !important;
                    padding: 12px 15px !important;
                    -webkit-print-color-adjust: exact !important;
                    page-break-inside: avoid !important;
                }
                .patient-info-row {
                    display: flex !important;
                    flex-wrap: wrap !important;
                    gap: 4px 20px !important;
                    background: #f8fafc !important;
                    border: none !important;
                    border-radius: 6px !important;
                    padding: 8px 15px !important;
                    margin: 10px 15px 15px 15px !important;
                    align-items: center !important;
                    justify-content: center !important;
                    -webkit-print-color-adjust: exact !important;
                    page-break-inside: avoid !important;
                }
                .info-item {
                    display: flex !important;
                    align-items: center !important;
                    gap: 5px !important;
                    white-space: nowrap !important;
                }
                .info-item.wide {
                    flex: 1 !important;
                    min-width: 100px !important;
                }
                .info-icon {
                    color: #0369a1 !important;
                    font-size: 0.8rem !important;
                    margin-right: 3px !important;
                    -webkit-print-color-adjust: exact !important;
                }
                .info-value-sm {
                    font-size: 0.75rem !important;
                    font-weight: 600 !important;
                    color: #0f172a !important;
                }
                .lab-table {
                    width: calc(100% - 30px) !important;
                    margin: 0 15px !important;
                    border-collapse: collapse !important;
                    font-size: 0.75rem !important;
                }
                .lab-table thead {
                    display: table-header-group !important;
                }
                .lab-table th {
                    background: #f1f5f9 !important;
                    border-bottom: 2px solid #0369a1 !important;
                    border-top: none !important;
                    padding: 8px 6px !important;
                    font-size: 0.7rem !important;
                    color: #0369a1 !important;
                    -webkit-print-color-adjust: exact !important;
                }
                .lab-table td {
                    border-bottom: 1px solid #e2e8f0 !important;
                    padding: 6px !important;
                    font-size: 0.75rem !important;
                }
                .lab-table tr {
                    page-break-inside: avoid !important;
                }
                .status-badge {
                    padding: 1px 4px !important;
                    border-radius: 2px !important;
                    font-size: 0.6rem !important;
                    border: none !important;
                    font-weight: 600 !important;
                    -webkit-print-color-adjust: exact !important;
                }
                .status-normal {
                    background: #dcfce7 !important;
                    color: #166534 !important;
                }
                .status-high, .status-low {
                    background: #fee2e2 !important;
                    color: #991b1b !important;
                }
                .result-value {
                    font-weight: bold !important;
                }
                .footer-signature {
                    position: absolute !important;
                    bottom: 40px !important;
                    left: 15px !important;
                    right: 15px !important;
                    display: grid !important;
                    grid-template-columns: 1fr 1fr !important;
                    gap: 40px !important;
                    page-break-inside: avoid !important;
                }
                .sig-box {
                    border-top: 2px solid #334155 !important;
                    padding-top: 8px !important;
                }
                .generation-info {
                    position: absolute !important;
                    bottom: 15px !important;
                    left: 0 !important;
                    right: 0 !important;
                    text-align: center !important;
                }
                .text-danger { color: #dc2626 !important; }
                .text-dark { color: #1e293b !important; }
                .text-muted { color: #64748b !important; }
                .text-secondary { color: #475569 !important; }
                .badge { 
                    background: #0369a1 !important; 
                    color: white !important;
                    padding: 4px 8px !important;
                    border-radius: 4px !important;
                    -webkit-print-color-adjust: exact !important;
                }
            }

            .btn-action {
                border-radius: 10px;
                padding: 10px 20px;
                font-weight: 600;
                transition: all 0.3s;
            }
        </style>
    </head>
    <body>
        <div class="no-print text-center mb-5">
             <button onclick="window.print()" class="btn btn-dark btn-action shadow-sm me-2"><i class="fas fa-print me-2"></i> PRINT REPORT</button>
             <button onclick="shareAsPDF()" class="btn btn-success btn-action shadow-sm me-2" id="waBtn">
                 <i class="fab fa-whatsapp me-2"></i> WHATSAPP (PDF)
             </button>
             <button onclick="window.close()" class="btn btn-outline-secondary btn-action shadow-sm">CLOSE</button>
        </div>

        <div class="report-container">
            <div class="report-box">
                <div class="header-banner">
                    <div class="brand-logo">
                        <i class="fas fa-microscope"></i>
                        <div class="brand-name">
                            <h2>{{ system_name|default('HealthPro Intelligence') }}</h2>
                            <p>Advanced Clinical Laboratory</p>
                        </div>
                    </div>
                    <div class="text-end">
                        <h4 class="mb-1 fw-bold">LABORATORY REPORT</h4>
                        <div class="badge bg-primary px-3 py-2" style="font-size: 0.9rem;">Date: {{ print_date }}</div>
                    </div>
                </div>

                <div class="patient-info-row">
                    <div class="info-item">
                        <i class="fas fa-user-circle info-icon"></i>
                        <span class="info-value-sm">{{ patient.full_name_ar }}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-birthday-cake info-icon"></i>
                        <span class="info-value-sm">{{ patient.age }} Y</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-venus-mars info-icon"></i>
                        <span class="info-value-sm">{{ patient.gender|capitalize }}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-calendar-alt info-icon"></i>
                        <span class="info-value-sm">{{ print_date }}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-id-card info-icon"></i>
                        <span class="info-value-sm">{{ patient.file_number }}</span>
                    </div>
                </div>

                <table class="lab-table">
                    <thead>
                        <tr>
                            <th style="width: 25%;">Test Description</th>
                            <th style="width: 15%;" class="text-center">Result</th>
                            <th style="width: 15%;" class="text-center">Status</th>
                            <th style="width: 18%;" class="text-center">Reference Range</th>
                            <th style="width: 12%;" class="text-center">Unit</th>
                            <th style="width: 15%;" class="text-center">Test Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for l in labs %}
                        <tr>
                            <td class="fw-bold text-dark">{{ l.test_type }}</td>
                            <td class="text-center">
                                <span class="result-value {{ 'text-danger' if l.is_abnormal else 'text-dark' }}">
                                    {{ l.result }}
                                </span>
                            </td>
                            <td class="text-center">
                                <span class="status-badge {{ l.status_class }}">
                                    {% if l.status_text == 'High' %}
                                        <i class="fas fa-arrow-up"></i>
                                    {% elif l.status_text == 'Low' %}
                                        <i class="fas fa-arrow-down"></i>
                                    {% else %}
                                        <i class="fas fa-check-circle"></i>
                                    {% endif %}
                                    {{ l.status_text }}
                                </span>
                            </td>
                            <td class="text-center text-secondary">
                                {% if l.min_value is not none and l.max_value is not none %}
                                    <span class="fw-medium">{{ l.min_value }} - {{ l.max_value }}</span>
                                {% else %}
                                    <span class="opacity-25">---</span>
                                {% endif %}
                            </td>
                            <td class="text-center fw-semibold text-muted">
                                {{ l.unit if l.unit else '---' }}
                            </td>
                            <td class="text-center text-muted" style="font-size: 0.85rem;">
                                {{ dt(l.created_at) }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>

                <div class="footer-signature">
                    <div class="sig-box">
                        <div class="info-label mb-2">Laboratory Specialist</div>
                        <div class="fw-bold">__________________________</div>
                        <small class="text-muted">Signature & Stamp</small>
                    </div>
                    <div class="sig-box">
                        <div class="info-label mb-2">Medical Director</div>
                        <div class="fw-bold">__________________________</div>
                        <small class="text-muted">Signature & Stamp</small>
                    </div>
                </div>

                <div class="generation-info">
                    <p class="text-muted" style="font-size: 0.7rem; margin: 0;">
                        This is an electronically generated report. Total tests: {{ labs|length }} | System: {{ system_name|default('HealthPro Intelligence') }} | Time: {{ generation_time }}
                    </p>
                </div>
            </div>
        </div>

        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <script>
            async function shareAsPDF() {
                const btn = document.getElementById('waBtn');
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PREPARING...';
                
                try {
                    const element = document.querySelector('.report-box');
                    const filename = 'Laboratory_Report_{{ patient.full_name_ar }}';
                    
                    // Copy image to clipboard
                    const canvas = await html2canvas(element, { scale: 3, useCORS: true });
                    canvas.toBlob(async (blob) => {
                        try {
                            const item = new ClipboardItem({ "image/png": blob });
                            await navigator.clipboard.write([item]);
                        } catch (err) { console.error("Clipboard failed", err); }
                    });

                    // Download PDF
                    const opt = {
                        margin: 0,
                        filename: filename + '.pdf',
                        image: { type: 'jpeg', quality: 0.98 },
                        html2canvas: { scale: 2, useCORS: true, letterRendering: true },
                        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                    };
                    await html2pdf().set(opt).from(element).save();

                    // Open WhatsApp
                    const waText = "Hello, here is your Laboratory Report. The image is copied to your clipboard, just press (Ctrl+V) in the chat to send it immediately.";
                    const waUrl = "https://wa.me/{{ patient.phone1|string|replace('+', '')|replace(' ', '') }}?text=" + encodeURIComponent(waText);
                    window.open(waUrl, '_blank');
                    
                    btn.innerHTML = original;
                } catch (err) {
                    console.error(err);
                    btn.innerHTML = original;
                    alert("Error generating report. Please try printing normally.");
                }
            }
        </script>
    </body>
    </html>
    """
    def dt_formatter(val):
        if not val: return "-"
        if isinstance(val, str) and 'CURRENT' in val.upper():
            val = datetime.now()
        if isinstance(val, str):
            for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
                try:
                    val = datetime.strptime(val.split('.')[0], f)
                    break
                except: continue
        if hasattr(val, 'strftime'):
            return val.strftime('%Y-%m-%d %I:%M %p').replace('AM', 'ص').replace('PM', 'م')
        return str(val)

    from config import format_datetime
    return render_template_string(html, 
                                patient=patient, 
                                labs=labs, 
                                print_date=print_date,
                                doctor_name=doctor_name,
                                dt=dt_formatter,
                                generation_time=dt_formatter(datetime.now()))
