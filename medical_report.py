from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from datetime import datetime, date

medical_report_bp = Blueprint('medical_report', __name__)

@medical_report_bp.route('/medical_report')
def medical_report():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    patient_id = request.args.get('id')
    appointment_id = request.args.get('appointment_id')
    
    if not patient_id and not appointment_id:
        return "Please select a patient or appointment"

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)

    # 1. Fetch Patient Info
    if appointment_id:
        cursor.execute("""
            SELECT p.*, a.appointment_id, a.appointment_date as visit_date, a.doctor_id, a.department_id,
                   u.full_name_ar as doc_name, u.full_name_en as doc_name_en, u.role as doc_role
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN users u ON a.doctor_id = u.user_id
            WHERE a.appointment_id = %s
        """, (appointment_id,))
        patient = cursor.fetchone()
        if not patient:
            conn.close()
            return "Appointment not found"
        patient_id = patient['patient_id']
    else:
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
        patient = cursor.fetchone()
        if not patient:
            conn.close()
            return "Patient not found"

    # Calculate Age
    age = "N/A"
    if patient.get('date_of_birth'):
        dob = patient['date_of_birth']
        if isinstance(dob, (datetime, date)):
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    patient['age'] = age

    # 2. Fetch Latest Consultation (Clinical Summary)
    if appointment_id:
        cursor.execute("""
            SELECT c.*, u.full_name_ar as doc_name, u.full_name_en as doc_name_en, u.role as doc_role
            FROM consultations c 
            JOIN users u ON c.doctor_id = u.user_id 
            WHERE c.appointment_id = %s 
            ORDER BY c.created_at DESC LIMIT 1
        """, (appointment_id,))
    else:
        cursor.execute("""
            SELECT c.*, u.full_name_ar as doc_name, u.full_name_en as doc_name_en, u.role as doc_role, a.appointment_date as visit_date
            FROM consultations c 
            JOIN users u ON c.doctor_id = u.user_id 
            JOIN appointments a ON c.appointment_id = a.appointment_id
            WHERE c.patient_id = %s 
            ORDER BY c.created_at DESC LIMIT 1
        """, (patient_id,))
    latest_consult = cursor.fetchone()

    # 3. Fetch Triage Data
    triage = None
    if latest_consult:
        cursor.execute("SELECT * FROM triage WHERE appointment_id = %s", (latest_consult['appointment_id'],))
        triage = cursor.fetchone()

    # 4. Find Next Follow-up from appointments table
    cursor.execute("""
        SELECT appointment_date 
        FROM appointments 
        WHERE patient_id = %s 
        AND appointment_date > %s
        AND status IN ('scheduled', 'confirmed', 'pending_triage')
        ORDER BY appointment_date ASC LIMIT 1
    """, (patient_id, latest_consult['visit_date'] if latest_consult and latest_consult.get('visit_date') else datetime.now().strftime('%Y-%m-%d')))
    next_apt = cursor.fetchone()
    
    # Logic: Prefer next_apt if found, otherwise 'Not Scheduled'
    display_followup = "Not Scheduled"
    if next_apt:
        try:
            d_val = next_apt['appointment_date']
            if isinstance(d_val, (datetime, date)):
                display_followup = d_val.strftime('%Y-%m-%d')
            else:
                display_followup = str(d_val)[:10]
        except:
            display_followup = str(next_apt['appointment_date'])

    # 5. Fetch System Settings for Header/Footer
    cursor.execute("SELECT setting_key, setting_value FROM system_settings")
    settings = {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}

    conn.close()

    # --- Preparation: Parse treatment plan into items ---
    plan_items = []
    if latest_consult and latest_consult.get('plan'):
        import re
        # Splitting by newline, comma, or /-
        raw_items = re.split(r'\n|,|/-', latest_consult['plan'])
        plan_items = [i.strip() for i in raw_items if i.strip()]

    # --- Preparation: QR Code Content ---
    # Construct a string with patient name and treatment plan for verification
    qr_data = f"Patient: {patient['full_name_ar']}\\nTreatment:\\n" + "\\n".join([f"{i+1}- {item}" for i, item in enumerate(plan_items)])
    import urllib.parse
    qr_encoded = urllib.parse.quote(qr_data)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={qr_encoded}"

    # --- Preparation: Translate Gender ---
    gender_en = "Male" if patient.get('gender') in ['ذكر', 'Male', 'M'] else "Female" if patient.get('gender') in ['أنثى', 'female', 'Female', 'F'] else patient.get('gender', 'N/A')
    
    # Enhanced Dynamic Doctor Retrieval
    # Check session for full names first as fallback
    session_name = session.get('full_name_en') or session.get('user_name') or session.get('full_name_ar', "Attending Specialist")
    
    doc_name = session_name
    if latest_consult and latest_consult.get('doc_name_en'):
        doc_name = latest_consult['doc_name_en']
    elif latest_consult and latest_consult.get('doc_name'): # Arabic name from consult
        doc_name = latest_consult['doc_name']
    elif patient and patient.get('doc_name_en'):
        doc_name = patient['doc_name_en']
    elif patient and patient.get('doc_name'):
        doc_name = patient['doc_name']

    # Final cleanup and prefixing
    if not doc_name.lower().startswith('dr.'):
        doc_name = "Dr. " + doc_name

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Medical Report - {{ patient.full_name_en or patient.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            .fas, .fab, .far { display: inline-block !important; visibility: visible !important; }
            @page {
                size: A4;
                margin: 0;
            }
            :root {
                --primary: #0f172a;
                --accent: #2563eb;
                --text: #1e293b;
                --white: #ffffff;
                --border: #e2e8f0;
            }
            * { box-sizing: border-box; }
            body {
                background: #f1f5f9;
                font-family: 'Outfit', sans-serif;
                color: var(--text);
                margin: 0; padding: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .a4-container {
                width: 210mm;
                height: 297mm;
                background: white;
                position: relative;
                display: flex;
                flex-direction: column;
                padding: 15mm;
                overflow: hidden;
                box-sizing: border-box;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }
            .inner-frame {
                height: 100%;
                display: flex;
                flex-direction: column;
                flex-grow: 1;
                box-sizing: border-box;
                border: none; /* Removed as requested */
            }

            header {
                border-bottom: 2px solid var(--primary);
                padding-bottom: 15px;
                margin-bottom: 25px;
            }
            .h-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
            .h-title h1 { font-size: 14pt; font-weight: 800; color: var(--primary); margin: 0; }
            .h-title p { font-size: 9pt; color: var(--accent); margin: 0; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
            
            .h-info-grid {
                display: grid;
                grid-template-columns: 1.5fr 1fr;
                gap: 20px;
                background: #f8fafc;
                padding: 10px 15px;
                border-radius: 6px;
                border: 1px solid #edf2f7;
            }
            .h-col { display: flex; flex-direction: column; gap: 4px; }
            .h-row { display: flex; align-items: center; gap: 8px; font-size: 9pt; color: #1e293b; font-weight: 600; }
            .h-row i { color: var(--accent); width: 14px; text-align: center; font-size: 8pt; }
            .h-row b { color: #64748b; font-weight: 800; text-transform: uppercase; font-size: 8px; min-width: 90px; }

            .ref-box { text-align: right; }
            .ref-item { font-size: 9pt; color: #64748b; font-weight: 700; }

            .content-grid {
                display: grid;
                grid-template-columns: 1.1fr 0.9fr; /* Wider right column for Medications */
                gap: 40px;
                flex-grow: 1;
            }

            .section { margin-bottom: 25px; }
            .section-header {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 2px solid #f1f5f9;
            }
            .section-icon {
                width: 32px;
                height: 32px;
                background: rgba(37, 99, 235, 0.1);
                color: var(--accent);
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 11pt;
            }
            .section-label {
                font-size: 11pt; font-weight: 800; color: var(--primary);
                text-transform: uppercase;
                margin: 0;
            }
            .section-text { font-size: 10.5pt; line-height: 1.6; color: #1e293b; white-space: pre-wrap; margin-left: 0; }

            /* Treatment Section Professional */
            .treatment-box {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 18px;
                margin-top: 0;
                position: relative;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            }
            .treatment-title { 
                font-size: 10pt; font-weight: 800; color: #1a237e; margin-bottom: 12px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;
                display: flex; justify-content: space-between; align-items: center;
            }
            .treatment-list { list-style: none; padding: 0; margin: 0; font-family: 'Times New Roman', Times, serif; }
            .treatment-item { display: flex; align-items: baseline; gap: 0; padding: 4px 0; border-bottom: 1px solid #f8fafc; }
            .treatment-item:last-child { border-bottom: none; }
            .treatment-num { font-size: 10pt; color: #1a237e; font-weight: 400; min-width: 20px; }
            .treatment-name { font-size: 10pt; font-weight: 400; color: #1e293b; line-height: 1.2; }

            /* Vitals Stat Cards */
            .vitals-card {
                background: var(--primary);
                color: white;
                border-radius: 16px;
                padding: 30px;
                box-shadow: 0 15px 40px rgba(0,0,0,0.15);
            }
            .vital-row {
                display: flex; justify-content: space-between; align-items: center;
                padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            .vital-row:last-child { border-bottom: none; }
            .v-info { display: flex; align-items: center; gap: 15px; }
            .v-icon { width: 40px; text-align: center; font-size: 20px; color: #38bdf8; }
            .v-label { font-size: 13px; opacity: 0.85; }
            .v-val { font-size: 16px; font-weight: 800; color: #38bdf8; }

            .doctor-box {
                background: rgba(37, 99, 235, 0.04);
                border: 1px solid rgba(37, 99, 235, 0.15);
                border-left: 6px solid var(--accent);
                padding: 20px 25px;
                border-radius: 12px;
                margin-bottom: 25px;
            }
            .doc-q { font-size: 11px; font-weight: 900; color: var(--accent); text-transform: uppercase; margin-bottom: 5px; }
            .doc-n { font-size: 22px; font-weight: 800; color: var(--primary); }

            .footer-sig { 
                margin-top: auto; 
                display: flex; 
                justify-content: space-between; 
                align-items: flex-end; /* Align bottom lines */
                padding: 30px 0 40px; /* Increased bottom padding to space away from the indigo box */
                min-height: 120px;
            }
            .sig-box { text-align: center; width: 42%; }
            .sig-line { border-bottom: 2px solid #000; width: 100%; margin: 0 auto 12px; height: 1px; }
            .sig-name { font-size: 10pt; font-weight: 800; color: #000; margin: 0; }
            .sig-title { font-size: 9px; color: #64748b; line-height: 1.4; font-weight: 600; }

            .bottom-info-bar {
                position: absolute;
                bottom: 0;
                left: 0;
                width: 100%;
                padding: 12px 30px;
                background: #1a237e; /* Indigo / Navy */
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 50px;
                font-size: 10pt;
                color: #ffffff;
                font-weight: 700;
            }
            .info-item { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
            .info-item i { color: #ffffff; font-size: 10pt; opacity: 0.8; }

            @media print {
                body { background: white; }
                .a4-container { box-shadow: none; border: none; padding: 15mm 15mm 0 15mm; height: 297mm; }
                header { border-bottom: 1px solid #eee; }
                .footer-sig { 
                    margin-top: auto;
                    padding-bottom: 80px;
                }
                .bottom-info-bar { 
                    position: absolute; bottom: 0; left: 0; width: 100%;
                    background: #1a237e !important; color: #ffffff !important;
                    -webkit-print-color-adjust: exact;
                    justify-content: center; gap: 40px;
                }
                .info-item i { color: #ffffff !important; }
            }
        </style>
    </head>
    <body onload="window.print()">
        <div class="a4-container">
            <div class="inner-frame">
                <header>
                    <div class="h-top">
                        <div class="h-title">
                            <h1>Intelligent Medical Specialty Center</h1>
                            <p>Premium Clinical Diagnostic & Specialized Care</p>
                        </div>
                        <div class="ref-box">
                            <div class="ref-item">REFERENCE ID: {{ latest_consult.appointment_id if latest_consult else '000000' }}</div>
                            <div style="font-size: 8px; color: #94a3b8; font-weight: 800;">VERIFIED CLINICAL DOCUMENT</div>
                        </div>
                    </div>
                    
                    <div class="h-info-grid">
                        <div class="h-col">
                            <div class="h-row">
                                <i class="fas fa-user"></i>
                                <b>Patient Full Name :</b>
                                <span>{{ patient.full_name_ar }}</span>
                            </div>
                            <div class="h-row">
                                <i class="fas fa-calendar-day"></i>
                                <b>Current Age :</b>
                                <span>{{ patient.age }} Years</span>
                            </div>
                            <div class="h-row">
                                <i class="fas fa-user-md"></i>
                                <b>Treating Consultant :</b>
                                <span style="color: var(--accent); font-weight: 800;">{{ doc_name }}</span>
                            </div>
                        </div>
                        <div class="h-col" style="border-left: 1px solid #edf2f7; padding-left: 20px;">
                            <div class="h-row">
                                <i class="fas fa-venus-mars"></i>
                                <b>Gender Identity :</b>
                                <span>{{ gender_en }}</span>
                            </div>
                            <div class="h-row">
                                <i class="fas fa-clock"></i>
                                <b>Report Issue Date :</b>
                                <span>{{ now.strftime('%d / %m / %Y') }}</span>
                            </div>
                            <div class="h-row">
                                <i class="fas fa-file-invoice"></i>
                                <b>Medical Reference :</b>
                                <span>{{ patient.file_number or patient.patient_id }}</span>
                            </div>
                        </div>
                    </div>
                </header>

                <div class="content-grid">
                    <div class="left-col">
                        <div class="section">
                            <div class="section-header">
                                <div class="section-icon"><i class="fas fa-history"></i></div>
                                <h6 class="section-label">CLINICAL HISTORY & SYMPTOMS</h6>
                            </div>
                            <div class="section-text">{{ latest_consult.subjective if latest_consult else 'No clinical history reported.' }}</div>
                        </div>

                        <div class="section">
                            <div class="section-header">
                                <div class="section-icon"><i class="fas fa-notes-medical"></i></div>
                                <h6 class="section-label">CLINICAL EXAMINATION FINDINGS</h6>
                            </div>
                            <div class="section-text">{{ latest_consult.objective if latest_consult else 'Comprehensive examination completed.' }}</div>
                        </div>

                        <div class="section">
                            <div class="section-header">
                                <div class="section-icon"><i class="fas fa-stethoscope"></i></div>
                                <h6 class="section-label">FINAL EVALUATION & DIAGNOSIS</h6>
                            </div>
                            <div class="section-text fw-bold" style="font-size:10.5pt; color: #000 !important;">{{ latest_consult.assessment if latest_consult else 'Routine Monitoring' }}</div>
                        </div>
                        
                        <div style="margin-top: 25px; padding: 8px 18px; background: #f0f7ff; border-radius: 50px; display: inline-flex; align-items: center; gap: 8px; border: 1px solid #e0eeff;">
                            <i class="fas fa-calendar-check" style="color: var(--accent); font-size: 9pt;"></i>
                            <span style="font-size: 8px; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">Confirmed Follow-up :</span>
                            <span style="font-size: 9pt; color: var(--accent); font-weight: 700;">{{ display_followup }}</span>
                        </div>
                    </div>

                    <div class="right-col">
                        <div class="treatment-box" style="margin-top: 0;">
                            <div class="treatment-title">
                                <span><i class="fas fa-prescription me-2"></i> MEDICATION PLAN</span>
                                <span style="font-size: 10pt; opacity: 0.3;">R𝓍</span>
                            </div>
                            <ul class="treatment-list">
                                {% if plan_items %}
                                    {% for item in plan_items %}
                                        <li class="treatment-item">
                                            <span class="treatment-num">{{ loop.index }}-</span>
                                            <span class="treatment-name">{{ item }}</span>
                                        </li>
                                    {% endfor %}
                                {% else %}
                                    <li class="text-muted" style="font-size: 10pt; font-style: italic;">No medications prescribed.</li>
                                {% endif %}
                            </ul>
                            <div style="margin-top: 15px; font-size: 9px; font-style: italic; opacity: 0.4; text-align: center; border-top: 1px dashed #eee; padding-top: 10px;">
                                Verified Medication Protocol
                            </div>
                        </div>

                    </div>
                </div>

                <div class="footer-sig">
                    <div class="sig-box">
                        <div class="sig-line"></div>
                        <p class="sig-name">{{ doc_name }}</p>
                        <p class="sig-title">Senior Consultant Medical Specialist<br>Medical Board Certified Practitioner</p>
                    </div>
                    <div class="sig-box">
                        <div class="sig-line"></div>
                        <p class="sig-name">OFFICIAL CENTER SEAL</p>
                        <p class="sig-title">Electronically Validated Document<br>Hospital Authority Office</p>
                    </div>
                </div>

                <div class="bottom-info-bar">
                    <div class="info-item"><i class="fas fa-map-marker-alt"></i> Iraq, Dhi Qar, Near Al-Huboobi Sq.</div>
                    <div class="info-item"><i class="fas fa-phone-alt"></i> Support: +964 783 000 4266</div>
                    <div class="info-item"><i class="fas fa-globe"></i> intelligent-medical.com</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, patient=patient, latest_consult=latest_consult, triage=triage, datetime=datetime, settings=settings, session=session, plan_items=plan_items, qr_url=qr_url, display_followup=display_followup, doc_name=doc_name, gender_en=gender_en, now=datetime.now())
