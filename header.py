header_html = r"""
<!DOCTYPE html>
<html lang="{{ session.get('lang', 'ar') }}" dir="{{ 'rtl' if session.get('lang', 'ar') == 'ar' else 'ltr' }}" data-theme="light">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ system_name }}</title>
    <!-- Dependencies -->
    {% if session.get('lang', 'ar') == 'ar' %}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css">
    {% else %}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    {% endif %}
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='apple_ui.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='apple_ui_pro.css') }}">
    <script src="{{ url_for('static', filename='speed_core.js') }}" defer></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        :root {
            --ui-blue: #007aff;
            --ui-canvas: #ffffff;
            --ui-text: #1c1c1e;
            --ui-border: rgba(0,0,0,0.06);
            --ui-panel: rgba(255, 255, 255, 0.8);
            --ui-gray: #f2f2f7;
            --ui-row-hover: rgba(0, 122, 255, 0.02);
            --primary-rgb: 0, 122, 255;
        }

        /* Essential Global Fixes */
        body { background: var(--ui-canvas) !important; color: var(--ui-text) !important; transition: background 0.3s, color 0.3s; }
        .apple-nav { background: var(--ui-panel) !important; backdrop-filter: blur(20px) !important; border-bottom: 1px solid var(--ui-border) !important; }
        
        /* Universal Slim Table System */
        .slim-card { background: var(--ui-panel); backdrop-filter: blur(20px); border-radius: 18px; border: 1px solid var(--ui-border); overflow: hidden; margin-bottom: 2rem; box-shadow: 0 10px 40px rgba(0,0,0,0.05); }
        .mock-table { width: 100%; border-collapse: separate; border-spacing: 0; }
        .mock-table th { background: rgba(0,0,0,0.02); padding: 0.8rem 1rem; font-size: 0.68rem; font-weight: 900; opacity: 0.45; border: none; text-align: center; text-transform: uppercase; }
        .mock-table td { padding: 0.65rem 1rem; border-bottom: 1px solid var(--ui-border); vertical-align: middle; text-align: center; color: var(--ui-text); }
        .mock-table tr:last-child td { border-bottom: none; }
        .mock-table tr:hover td { background: var(--ui-row-hover); }

        /* Icon Glow System */
        .icon-group { display: flex; gap: 12px; justify-content: center; align-items: center; }
        .act-icon { font-size: 1.15rem; color: var(--ui-text); opacity: 0.4; transition: 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); text-decoration: none; cursor: pointer; }
        .act-icon:hover { opacity: 1; transform: scale(1.3) translateY(-2px); }
        .act-icon.blue:hover { color: #007aff; filter: drop-shadow(0 0 8px rgba(0, 122, 255, 0.5)); }
        .act-icon.gold:hover { color: #f39c12; filter: drop-shadow(0 0 8px rgba(243, 156, 18, 0.5)); }
        .act-icon.green:hover { color: #27ae60; filter: drop-shadow(0 0 8px rgba(39, 174, 96, 0.5)); }
        .act-icon.red:hover { color: #e74c3c; filter: drop-shadow(0 0 8px rgba(231, 76, 60, 0.5)); }
        .act-icon.wa { color: #25d366; }

        .theme-adaptive-btn { background: var(--ui-gray) !important; color: var(--ui-text) !important; border: 1px solid var(--ui-border) !important; transition: all 0.3s; }
        .theme-adaptive-user-bg { background: var(--ui-gray) !important; }
    </style>
</head>

<body>
    <!-- Live Animated Background -->
    <div class="mesh-bg">
        <div class="blob1"></div>
        <div class="blob2"></div>
        <div class="blob3"></div>
    </div>

    <!-- Top Minimal Bar -->
    <div class="apple-nav no-print shadow-sm d-flex align-items-center px-3 justify-content-between">
        <div class="d-flex align-items-center">
            <!-- Distinctive Back Button -->
            <a href="javascript:history.back()"
                class="btn rounded-circle shadow-sm p-0 d-flex align-items-center justify-content-center me-3 hover-scale border-0 theme-adaptive-btn"
                style="width: 40px; height: 40px;"
                title="عودة">
                <i class="fas fa-chevron-{{ 'right' if session.get('lang', 'ar') == 'ar' else 'left' }} text-primary"></i>
            </a>
            <a href="{{ url_for('dashboard.dashboard') }}" class="text-decoration-none d-flex align-items-center">
                <span class="fw-bold" style="color: var(--text) !important;">{{ system_name }}</span>
            </a>
        </div>

        <div class="d-none d-lg-flex flex-column text-center px-4">
            <div class="fw-bold small mb-0" id="current-date" style="color: var(--text);"></div>
            <div class="text-muted" style="font-size: 0.65rem;" id="current-time"></div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <!-- Connection Health (The Pulse) -->
            <div class="d-none d-xl-flex align-items-center border-end pe-3 me-2" id="connection-widget-container">
                <div class="connection-widget">
                    <div class="status-pulse" id="connectionPulse"></div>
                    <span class="status-text h-connection-text" id="connectionText" style="color: var(--text);">{{ 'متصل بالسيرفر' if session.get('lang', 'ar') == 'ar' else 'Connected' }}</span>
                </div>
            </div>

            <!-- User Info (Smart Gender & Role) -->
            <div class="text-end d-none d-md-flex align-items-center gap-2 border-end pe-3 me-1">
                <div class="d-flex flex-column align-items-end" style="line-height: 1.2;">
                    <div class="fw-bold small mb-0" style="color: var(--text);">{{ session.get('full_name', 'مستخدم' if session.get('lang', 'ar') == 'ar' else 'User') }}</div>
                </div>
                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm theme-adaptive-user-bg"
                    style="width: 38px; height: 38px; border: 1px solid rgba(255,255,255,0.1);">
                    <i class="fas fa-user-tie text-primary" style="font-size: 1.1rem;"></i>
                </div>
            </div>

            <!-- Call Center Global Link -->
            <a href="{{ url_for('connect.connect') }}" class="p-2 text-primary hover-scale" title="مركز الاتصال الموحد">
                <div class="position-relative">
                    <i class="fas fa-satellite-dish"></i>
                    <span class="position-absolute top-0 start-100 translate-middle p-1 bg-success border border-light rounded-circle" style="width: 8px; height: 8px;"></span>
                </div>
            </a>



            <!-- Refresh Button -->
            <a href="javascript:location.reload()" class="p-2 text-primary hover-scale" title="{{ 'تحديث' if session.get('lang', 'ar') == 'ar' else 'Refresh' }}">
                <i class="fas fa-sync-alt"></i>
            </a>

            <!-- Settings & Logout -->
            {% if session.get('role') == 'admin' or 'settings' in session.get('permissions', []) %}
                <a href="{{ url_for('settings.view_settings') }}" class="p-2 text-dark" style="color: var(--text-color) !important;" title="الإعدادات">
                    <i class="fas fa-cog"></i>
                </a>
            {% endif %}

            <a href="{{ url_for('logout.logout') }}" class="p-2 text-danger no-pjax" title="خروج">
                <i class="fas fa-sign-out-alt"></i>
            </a>
        </div>
    </div>

    <script>
        const lang = '{{ session.get('lang', 'ar') }}';
        
        // Theme Engine Disabled - Keeping light theme
        localStorage.setItem('theme', 'light');

        // Live Clock
        function toArabicDigits(str) {
            return str.replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
        }

        const daysAr = { 0: 'الأحد', 1: 'الاثنين', 2: 'الثلاثاء', 3: 'الأربعاء', 4: 'الخميس', 5: 'الجمعة', 6: 'السبت' };
        const monthsAr = { 0: 'يناير', 1: 'فبراير', 2: 'مارس', 3: 'أبريل', 4: 'مايو', 5: 'يونيو', 6: 'يوليو', 7: 'أغسطس', 8: 'سبتمبر', 9: 'أكتوبر', 10: 'نوفمبر', 11: 'ديسمبر' };

        setInterval(() => {
            const now = new Date();
            const dayName = daysAr[now.getDay()];
            const dayNum = toArabicDigits(now.getDate().toString());
            const monthName = monthsAr[now.getMonth()];
            const dateEl = document.getElementById('current-date');
            if (dateEl) {
                {% if session.get('lang', 'ar') == 'ar' %}
                     dateEl.innerText = `${dayName}، ${dayNum} ${monthName}`;
                {% else %}
                     dateEl.innerText = now.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long' });
                {% endif %}
            }

            let hours = now.getHours();
            const minutes = now.getMinutes().toString().padStart(2, '0');
            const seconds = now.getSeconds().toString().padStart(2, '0');
            const ampm = hours >= 12 ? (lang == 'ar' ? 'م' : 'PM') : (lang == 'ar' ? 'ص' : 'AM');
            hours = hours % 12;
            hours = hours ? hours : 12;
            const timeStr = lang == 'ar' ? toArabicDigits(`${hours}:${minutes}:${seconds}`) : `${hours}:${minutes}:${seconds}`;
            const timeEl = document.getElementById('current-time');
            if (timeEl) timeEl.innerText = `${timeStr} ${ampm}`;
        }, 1000);

        function updateConnectionStatus() {
            const pulse = document.getElementById('connectionPulse');
            const text = document.getElementById('connectionText');
            
            if (navigator.onLine) {
                pulse.style.background = '#2ecc71';
                pulse.style.boxShadow = '0 0 10px rgba(46, 204, 113, 0.5)';
                text.innerText = 'متصل بالسيرفر';
                text.style.color = '';
            } else {
                pulse.style.background = '#e74c3c';
                pulse.style.boxShadow = '0 0 10px rgba(231, 76, 60, 0.5)';
                text.innerText = 'انقطع الاتصال';
                text.style.color = '#e74c3c';
            }
        }

        window.addEventListener('online', updateConnectionStatus);
        window.addEventListener('offline', updateConnectionStatus);
        updateConnectionStatus();

        // Global UI Utilities
        function showSection(id) {
            console.log("Switching to section:", id);
            const sections = document.querySelectorAll('.section-content');
            if (sections.length === 0) {
                console.warn("No .section-content elements found in DOM.");
                return;
            }
            
            sections.forEach(s => {
                s.style.display = 'none';
                s.classList.remove('animate__animated', 'animate__fadeIn');
            });
            
            const target = document.getElementById(id);
            if (target) {
                target.style.display = 'block';
                target.classList.add('animate__animated', 'animate__fadeIn');
                // Ensure visibility if there are competing styles
                target.setAttribute('style', 'display: block !important;');
            } else {
                console.error("Section with ID '" + id + "' not found.");
            }
        }
        // Global Real-Time Heartbeat (Standard 5s Pulse)
        let lastEntropy = null;
        let heartbeatInterval = 5000; // Efficient 5s pulse
        let isHeartbeatPending = false;
        
        async function checkPulse() {
            if (isHeartbeatPending) return;
            isHeartbeatPending = true;
            try {
                const resp = await fetch('{{ url_for("api.api_ping") }}');
                const data = await resp.json();
                
                const pulse = document.getElementById('connectionPulse');
                if(pulse) {
                    pulse.style.transform = 'scale(1.4)';
                    setTimeout(() => pulse.style.transform = 'scale(1)', 300);
                }

                if (lastEntropy !== null && data.sys_entropy !== lastEntropy) {
                    window.dispatchEvent(new CustomEvent('systemUpdate', { detail: data }));
                    if (typeof loadMonitorData === 'function') {
                        loadMonitorData();
                    }
                }
                lastEntropy = data.sys_entropy;
            } catch (e) {
                console.warn("Heartbeat missed.");
            } finally {
                isHeartbeatPending = false;
            }
        }

        setInterval(checkPulse, heartbeatInterval);
        checkPulse();
    </script>


    <div id="pjax-container" class="container mt-4 pb-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert bg-white shadow-sm border-0 rounded-4 text-center mb-4">
                        <span class="text-{{ category }} fw-bold">{{ message }}</span>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
"""
