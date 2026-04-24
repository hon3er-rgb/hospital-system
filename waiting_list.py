from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, local_now_naive
from header import header_html
from footer import footer_html
waiting_list_bp = Blueprint('waiting_list', __name__)

@waiting_list_bp.route('/waiting_list', methods=['GET'])
def waiting_list():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    current_date = local_now_naive().strftime('%Y/%m/%d')

    html = header_html + """
    <div class="monitor-dashboard pt-3 pb-4">
        <div class="container-fluid px-4">
            <!-- Header Section (Compact) -->
            <div class="row align-items-center mb-3">
                <div class="col-md-8">
                    <h1 class="fw-bold text-dark mb-0" style="font-size: 1.8rem;">نظام المراقبة الذكي <span class="text-primary">{{ system_name }}</span></h1>
                </div>
                <div class="col-md-4 text-md-end">
                    <div class="clock-card apple-card d-inline-block px-3 py-1 text-center bg-white shadow-sm border-0">
                        <span id="live-clock" class="fw-bold text-primary" style="font-size: 1.4rem;">00:00:00</span>
                        <span class="ms-2 small text-muted fw-bold">{{ current_date }}</span>
                    </div>
                </div>
            </div>

            <!-- 3-Column Monitor Screen -->
            <div class="monitor-grid">
                <!-- 1. Registration / Triage (Merged Queue) -->
                <div class="monitor-col">
                    <div class="stage-header d-flex align-items-center mb-2">
                        <div class="stage-num">1</div>
                        <div class="ms-2">
                            <div class="fw-bold mb-0" style="font-size: 1rem;">الاستقبال والفحص الأولي</div>
                        </div>
                        <span class="badge rounded-pill bg-light text-dark ms-auto border" id="count-reception">0</span>
                    </div>
                    <div id="list-reception" class="list-container"></div>
                </div>

                <!-- 2. Doctor -->
                <div class="monitor-col">
                    <div class="stage-header d-flex align-items-center mb-2">
                        <div class="stage-num bg-info text-white">2</div>
                        <div class="ms-2">
                            <div class="fw-bold mb-0" style="font-size: 1rem;">انتظار الطبيب</div>
                        </div>
                        <span class="badge rounded-pill bg-light text-dark ms-auto border" id="count-doctor">0</span>
                    </div>
                    <div id="list-doctor" class="list-container"></div>
                </div>

                <!-- 3. Labs/Rads/Pharmacy (Medical Depts) -->
                <div class="monitor-col">
                    <div class="stage-header d-flex align-items-center mb-2">
                        <div class="stage-num bg-dark text-white">3</div>
                        <div class="ms-2">
                            <div class="fw-bold mb-0" style="font-size: 1rem;">المختبر والأشعة والصيدلية</div>
                        </div>
                        <span class="badge rounded-pill bg-light text-dark ms-auto border" id="count-medical">0</span>
                    </div>
                    <div id="list-medical" class="list-container"></div>
                </div>
            </div>
        </div>
    </div>

    <style>
        :root {
            --stage-bg: rgba(245, 245, 247, 0.7);
            --accent-color: #0071e3;
        }

        .monitor-dashboard {
            background: #fbfbfd;
            min-height: 100vh;
            overflow: hidden;
        }

        .monitor-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            align-items: start;
        }

        .monitor-col {
            background: var(--stage-bg);
            border-radius: 15px;
            padding: 10px;
            min-height: 90vh;
            background: #ffffff;
            border: 1px solid rgba(0, 0, 0, 0.03);
            display: flex;
            flex-direction: column;
        }

        .stage-num {
            width: 28px;
            height: 28px;
            background: var(--accent-color);
            color: white;
            border-radius: 50%; /* Made it a circle as requested */
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.95rem;
            flex-shrink: 0;
        }

        .list-container {
            display: flex;
            flex-direction: column;
            gap: 4px;
            overflow: hidden;
        }

        .patient-card {
            background: white;
            border-radius: 6px;
            padding: 4px 8px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.01);
            border-right: 3px solid var(--accent-color);
            transition: all 0.3s;
        }

        .p-name {
            font-size: 0.85rem;
            font-weight: 700;
            color: #1d1d1f;
            margin-bottom: 0px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .p-meta {
            font-size: 0.65rem;
            color: #86868b;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .entrance-tag {
            font-weight: 600;
        }

        .timer-tag {
            color: var(--accent-color);
            font-weight: 700;
        }

        #live-clock {
            font-variant-numeric: tabular-nums;
            letter-spacing: 1px;
        }

        @media print {
            .no-print {
                display: none;
            }
        }

        @keyframes urgentGlow {
            0% { box-shadow: 0 0 5px rgba(220, 53, 69, 0.2); }
            50% { box-shadow: 0 0 15px rgba(220, 53, 69, 0.5); }
            100% { box-shadow: 0 0 5px rgba(220, 53, 69, 0.2); }
        }

        .shadow-urgent {
            animation: urgentGlow 1.5s infinite;
            border-right: 5px solid #dc3545 !important;
        }
    </style>

    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('live-clock').innerText = now.toLocaleTimeString('en-GB');
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
    <script>
        async function loadMonitorData() {
            try {
                const resp = await fetch("{{ url_for('api.api_waiting') }}");
                const data = await resp.json();

                // 1. Column 1: Reception + Triage
                renderList('list-reception', data.reception, 'count-reception', p => {
                    let isScheduled = p.status === 'scheduled';
                    let statusColor = isScheduled ? '#000000' : '#0071e3'; // Black if not paid, Blue if paid
                    let cardBg = isScheduled ? 'rgba(0,0,0,0.02)' : 'rgba(0,113,227,0.02)';
                    
                    return `
                    <div class="patient-card" style="border-right-color: ${statusColor}; background: ${cardBg};">
                        <div class="d-flex align-items-center">
                            <div class="stage-num me-2" style="background: ${statusColor}; width:12px; height:12px; min-width:12px;"></div>
                            <div class="p-name">${p.name}</div>
                        </div>
                        <div class="p-meta">
                            <span class="entrance-tag">${p.entrance} - <span style="font-weight:bold; color:${statusColor};">${p.sub_status}</span></span>
                            <span class="timer-tag">${p.wait}د</span>
                        </div>
                    </div>
                    `;
                });

                // 2. Column 2: Doctor
                renderList('list-doctor', data.doctor, 'count-doctor', p => {
                    let isInProgress = p.status === 'in_progress';
                    let isCalled = p.call_status === 1;

                    let cardClass = p.is_urgent ? 'border-danger shadow-urgent' : '';
                    let statusColor = '';
                    let bgStyle = '';
                    let statusBadge = '';

                    if (p.in_lab) {
                        statusColor = '#0dcaf0'; // Cyan/Teal
                        bgStyle = 'rgba(13,202,240,0.02)';
                        statusBadge = '<span class="badge bg-info text-dark rounded-pill" style="font-size:0.6rem;"><i class="fas fa-flask"></i> في المختبر</span>';
                    } else if (p.is_ready) {
                        statusColor = '#198754'; // Green
                        bgStyle = 'rgba(25,135,84,0.02)';
                        statusBadge = '<span class="badge bg-success rounded-pill" style="font-size:0.6rem;">مكتمل ✓</span>';
                    } else if (isInProgress) {
                        statusColor = '#fd7e14'; // Orange
                        bgStyle = 'rgba(253,126,20,0.02)';
                        statusBadge = '<span class="badge bg-warning text-dark rounded-pill" style="font-size:0.6rem;"><i class="fas fa-stethoscope"></i> يم الطبيب</span>';
                    } else if (isCalled) {
                        statusColor = '#6f42c1'; // Purple
                        bgStyle = 'rgba(111,66,193,0.02)';
                        statusBadge = '<span class="badge rounded-pill" style="background:#6f42c1; font-size:0.6rem;"><i class="fas fa-bullhorn"></i> تم الاستدعاء</span>';
                    } else if (p.status === 'scheduled' && p.is_free) {
                        statusColor = '#20c997'; // Teal/Mint
                        bgStyle = 'rgba(32,201,151,0.02)';
                        statusBadge = '<span class="badge rounded-pill" style="background:#20c997; font-size:0.6rem;"><i class="fas fa-undo"></i> مراجعة (فحص مجاني)</span>';
                    } else { // waiting_doctor
                        statusColor = '#dc3545'; // Red
                        bgStyle = 'rgba(220,53,69,0.02)';
                        statusBadge = '<span class="badge bg-danger rounded-pill" style="font-size:0.6rem;">بانتظار الطبيب</span>';
                    }

                    return `
                    <div class="patient-card ${cardClass}" style="border-right-width: 5px; border-right-color: ${statusColor}; background: ${bgStyle};">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center">
                                <div class="stage-num me-2" style="background: ${statusColor}; width:12px; height:12px; min-width:12px;"></div>
                                <div class="p-name ${p.is_urgent ? 'text-danger' : (isCalled ? 'text-purple' : '')}" style="${isCalled && !p.is_urgent ? 'color: #6f42c1;' : ''}">
                                    ${p.is_urgent ? '<i class="fas fa-exclamation-circle animate__animated animate__flash animate__infinite me-1"></i>' : ''}
                                    ${p.patient}
                                </div>
                            </div>
                            <div class="d-flex gap-1 align-items-center">
                                ${statusBadge}
                            </div>
                        </div>
                        <div class="p-meta mt-1">
                            <span class="entrance-tag">${p.entrance} <span class="ms-1" style="font-size:0.6rem;">د.${p.doctor}</span></span>
                            <span class="timer-tag">${p.wait}د</span>
                        </div>
                    </div>
                    `;
                });

                // 3. Column 3: Medical (Pending Exams)
                renderList('list-medical', data.medical, 'count-medical', p => `
                    <div class="patient-card" style="border-right-color: #ffc107; background: #fffcf2;">
                        <div class="p-name">${p.patient}</div>
                        <div class="p-meta mt-1">
                            <span class="entrance-tag">${p.entrance}</span>
                            <div class="d-flex gap-1">
                                ${p.has_lab ? '<span class="badge bg-warning text-dark border border-warning" style="font-size:0.55rem;">مختبر</span>' : ''}
                                ${p.has_rad ? '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle" style="font-size:0.55rem;">أشعة</span>' : ''}
                                ${p.has_pharma ? '<span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:0.55rem;">صيدلية</span>' : ''}
                            </div>
                        </div>
                    </div>
                `);

            } catch (e) {
                console.error("Update error: ", e);
                if (e.name === 'SyntaxError') {
                    // Try to fetch text to see what happened
                    fetch("{{ url_for('api.api_waiting') }}").then(r => r.text()).then(txt => {
                        console.log("Raw Response:", txt);
                        if (!txt.trim().startsWith('{')) {
                            Swal.fire({
                                icon: 'error',
                                title: 'خطأ في البيانات',
                                text: 'استجابة الخادم غير صالحة. الرجاء ابلاغ الدعم.\\n' + txt.substring(0, 100)
                            });
                        }
                    });
                }
            }
        }

        function renderList(targetId, array, countId, templateFn) {
            const container = document.getElementById(targetId);
            document.getElementById(countId).innerText = array.length;
            container.innerHTML = array.length > 0 ? array.map(templateFn).join("") :
                `<div class="text-center py-5 text-muted small opacity-50">لا يوجد مراجعين</div>`;
        }

        // Listen for Global Heartbeat for instant reaction
        window.addEventListener('systemUpdate', () => {
            console.log("Monitor: System change detected. Refreshing...");
            loadMonitorData();
        });

        // Independent Turbo Refresh (Light-Speed 100ms)
        let isMonitorPending = false;
        async function loadMonitorProtected() {
            if (isMonitorPending) return;
            isMonitorPending = true;
            try { await loadMonitorData(); } finally { isMonitorPending = false; }
        }
        setInterval(loadMonitorProtected, 100);
        loadMonitorProtected();


    </script>

    """ + footer_html
    
    return render_template_string(html, current_date=current_date)
