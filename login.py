from flask import Blueprint, render_template_string, request, session, redirect, url_for, flash, Response
from werkzeug.security import check_password_hash, generate_password_hash
from config import get_db, log_activity
import json

login_bp = Blueprint('login', __name__)

@login_bp.route('/manifest.json')
def manifest():
    return {
        "name": "Hospital Management Core",
        "short_name": "HMC-OS",
        "start_url": "/login",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#000000",
        "icons": [
            {
                "src": "/icon.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }

@login_bp.route('/sw.js')
def sw():
    return "self.addEventListener('fetch', function(e) { });", 200, {'Content-Type': 'application/javascript'}

@login_bp.route('/icon.png')
def icon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512"><rect width="512" height="512" fill="#000"/><text x="50%" y="50%" font-family="Arial" font-size="200" fill="#d07afb" text-anchor="middle" dominant-baseline="middle">H</text></svg>'
    return Response(svg, mimetype='image/svg+xml')

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index.index'))
        
    error = None
    
    if request.method == 'POST':
        user = request.form.get('username')
        passwd = request.form.get('password')
        
        conn = get_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s AND is_active = 1", (user,))
            row = cursor.fetchone()
            
            if row:
                verified = False
                try:
                    if check_password_hash(row['password_hash'], passwd):
                        verified = True
                except ValueError:
                    import bcrypt
                    if row['password_hash'].startswith('$2y$'):
                        compatible_hash = row['password_hash'].replace('$2y$', '$2b$', 1).encode('utf-8')
                        if bcrypt.checkpw(passwd.encode('utf-8'), compatible_hash):
                            verified = True

                if not verified and passwd == row['password_hash']:
                    verified = True
                    new_hash = generate_password_hash(passwd)
                    cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, row['user_id']))
                    conn.commit()
                
                if verified:
                    session['user_id'] = row['user_id']
                    session['role'] = row['role']
                    session['full_name'] = row['full_name_ar']
                    
                    try:
                        perms = json.loads(row['permissions']) if row['permissions'] else []
                    except json.JSONDecodeError:
                        perms = []
                    
                    session['permissions'] = perms if isinstance(perms, list) else []
                    log_activity(row['user_id'], "تسجيل دخول", "قام المستخدم بتسجيل الدخول إلى النظام")
                    conn.close()
                    return redirect(url_for('index.index'))
                else:
                    error = "كلمة المرور غير صحيحة"
            else:
                error = "اسم المستخدم غير موجود"
            conn.close()

    html = """
    <!DOCTYPE html>
    <html lang="en" dir="ltr" data-theme="light">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ system_name }} | SECURE CORE</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#ffffff">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #007aff;
                --bg: #f8fafc;
                --card: rgba(255, 255, 255, 0.85);
                --input: rgba(0, 0, 0, 0.05);
                --text: #0f172a;
                --border: rgba(0, 122, 255, 0.1);
                --sub: rgba(15, 23, 42, 0.5);
            }

            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Lexend', sans-serif; transition: background 0.4s, color 0.4s; }
            
            body {
                background: var(--bg);
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                color: var(--text);
            }

            /* Ultimate Cyber HUD - Core System Color */
            .boot-screen {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: #f8fafc;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .hud-main-box {
                position: relative;
                width: 380px; height: 380px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .hud-svg-core { width: 100%; height: 100%; transform: rotate(-90deg); }
            
            .sys-color { stroke: var(--primary); fill: none; }
            .sys-text { color: var(--primary); }

            /* Detailed Hub Layers */
            .l-outer-ring { transform-origin: center; animation: rotateCW 20s linear infinite; stroke-width: 10; stroke-dasharray: 100 120; opacity: 0.8; }
            .l-outer-fine { transform-origin: center; animation: rotateCW 35s linear infinite; stroke-width: 4; stroke-dasharray: 30 170; opacity: 0.4; }
            .l-mid-track { transform-origin: center; animation: rotateCCW 15s linear infinite; stroke-width: 1.5; opacity: 0.6; }
            .l-inner-dash { transform-origin: center; animation: rotateCW 6s linear infinite; stroke-width: 15; stroke-dasharray: 2 10; opacity: 0.5; }
            
            .progress-glow-ring {
                fill: none;
                stroke: var(--primary);
                stroke-width: 4;
                stroke-dasharray: 565;
                stroke-dashoffset: 565;
                transition: stroke-dashoffset 0.05s linear;
                filter: drop-shadow(0 0 15px var(--primary));
            }

            @keyframes rotateCW { 0% { transform: rotate(0); } 100% { transform: rotate(360deg); } }
            @keyframes rotateCCW { 0% { transform: rotate(0); } 100% { transform: rotate(-360deg); } }

            .hud-center-content {
                position: absolute;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            .hud-center-content h1 {
                font-size: 4.2rem;
                font-weight: 800;
                color: var(--primary);
                margin: 0;
                line-height: 1;
                text-shadow: 0 0 10px rgba(0, 122, 255, 0.2);
                animation: glowPulse 1.5s infinite alternate;
            }

            @keyframes glowPulse {
                from { text-shadow: 0 0 10px rgba(0, 122, 255, 0.2); transform: scale(1); }
                to { text-shadow: 0 0 20px rgba(0, 122, 255, 0.4); transform: scale(1.05); }
            }

            .hud-center-content p {
                font-size: 0.6rem;
                letter-spacing: 5px;
                color: var(--primary);
                text-transform: uppercase;
                margin-top: 15px;
                opacity: 0.6;
            }

            .boot-msg-bottom {
                font-size: 0.7rem;
                font-weight: 400;
                letter-spacing: 12px;
                color: var(--primary);
                text-transform: uppercase;
                margin-top: 50px;
                opacity: 0.3;
                animation: sysBlink 2s infinite alternate;
            }

            @keyframes sysBlink { 0% { opacity: 0.1; } 100% { opacity: 0.6; } }

            /* HUD Top Bar */
            .hud-bar {
                position: fixed;
                top: 30px; left: 40px; right: 40px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 0.7rem;
                font-weight: 700;
                color: var(--sub);
                text-transform: uppercase;
                letter-spacing: 2px;
                z-index: 10;
            }

            /* Login Interface */
            .login-container {
                width: 100%;
                max-width: 380px;
                background: var(--card);
                backdrop-filter: blur(60px);
                -webkit-backdrop-filter: blur(60px);
                border: 1px solid var(--border);
                border-radius: 35px;
                padding: 45px 35px;
                box-shadow: 0 50px 100px rgba(0, 0, 0, 0.1);
                opacity: 1;
                filter: none;
                transform: none;
            }

            .brand { text-align: center; margin-bottom: 35px; }
            .brand i { font-size: 3.2rem; color: var(--primary); margin-bottom: 15px; }
            .brand h2 { font-weight: 800; font-size: 1.8rem; color: var(--text); }
            .brand p { color: var(--sub); font-size: 0.8rem; margin-top: 5px; }

            .input-group-custom {
                position: relative;
                margin-bottom: 20px;
                background: var(--input);
                border: 1px solid var(--border);
                border-radius: 15px;
                overflow: hidden;
                transition: 0.3s;
            }

            .input-group-custom:focus-within { border-color: var(--primary); box-shadow: 0 0 15px rgba(0, 122, 255, 0.1); }

            .input-group-custom input {
                width: 100%; background: transparent; border: none; padding: 18px;
                color: var(--text); outline: none; font-size: 1rem; text-align: center;
            }

            .remember-check { display: flex; align-items: center; margin-bottom: 25px; font-size: 0.85rem; color: var(--sub); cursor: pointer; padding-left: 5px; }
            .remember-check input { width: 18px; height: 18px; margin-right: 12px; accent-color: var(--primary); cursor: pointer; }

            .btn-auth { width: 100%; background: var(--primary); color: #fff; padding: 18px; border: none; border-radius: 15px; font-size: 1rem; font-weight: 700; cursor: pointer; transition: 0.4s; }
            .btn-auth:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: 0 10px 20px rgba(0, 122, 255, 0.2); }

            .error-box { background: rgba(255, 82, 82, 0.1); color: #ff5252; padding: 12px; border-radius: 12px; font-size: 0.8rem; margin-bottom: 25px; text-align: center; border: 1px solid rgba(255, 82, 82, 0.2); }
        </style>
    </head>
    <body dir="ltr">
        <div class="bg-accent"></div>

        <div class="hud-bar">
            <div class="d-flex align-items-center gap-3">
                <div class="theme-toggle" id="theme-btn" style="display:none;"><i class="fas fa-sun"></i></div>
                <div><i id="n-icon" class="fas fa-satellite"></i> <span id="n-val">NETWORK: SECURE</span></div>
            </div>
            <div class="d-flex align-items-center gap-3">
                <div><i class="fas fa-shield-halved sys-text"></i> <span>OS SECURE</span></div>
                <div><i id="b-icon" class="fas fa-bolt"></i> <span id="b-val">PWR: 100%</span></div>
            </div>
        </div>

        <div class="login-container" id="login-panel">
            <div class="brand">
                <i class="{{ system_icon }}"></i>
                <h2>{{ system_name }}</h2>
                <p>Advanced Management Core Access</p>
            </div>

            {% if error %}
                <div class="error-box"><i class="fas fa-shield-virus mr-2"></i> {{ error }}</div>
            {% endif %}

            <form id="login-form" method="POST">
                <div class="input-group-custom"><input type="text" name="username" id="username" placeholder="Operator ID" required autofocus autocomplete="off"></div>
                <div class="input-group-custom"><input type="password" name="password" id="password" placeholder="Passkey" required></div>
                <label class="remember-check"><input type="checkbox" id="remember-me"><span>Remember Access ID</span></label>
                <button type="submit" class="btn-auth">AUTHENTICATE SYSTEM</button>
            </form>
        </div>

        <script>
            // Professional 2-Second Success Sound (Synthesized)
            function playSystemChime() {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const master = ctx.createGain();
                    master.gain.setValueAtTime(0, ctx.currentTime);
                    master.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.3);
                    master.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 2.0);
                    master.connect(ctx.destination);
                    [261.63, 329.63, 392.00, 523.25].forEach((f, i) => {
                        const o = ctx.createOscillator();
                        o.type = 'sine'; o.frequency.setValueAtTime(f, ctx.currentTime + (i*0.1));
                        o.connect(master); o.start(ctx.currentTime + (i*0.1)); o.stop(ctx.currentTime + 2.0);
                    });
                } catch(e) {}
            }

            function startBootProcess() {
                // Boot screen removed as per user request
            }

            window.addEventListener('load', () => {
                const savedUser = localStorage.getItem('op_id');
                const savedPass = localStorage.getItem('op_pass');
                if (savedUser && savedPass) {
                    document.getElementById('username').value = savedUser;
                    document.getElementById('password').value = savedPass;
                    document.getElementById('remember-me').checked = true;
                }
                startBootProcess();
            });

            document.getElementById('login-form').addEventListener('submit', () => {
                const remember = document.getElementById('remember-me').checked;
                if (remember) {
                    localStorage.setItem('op_id', document.getElementById('username').value);
                    localStorage.setItem('op_pass', document.getElementById('password').value);
                } else {
                    localStorage.removeItem('op_id');
                    localStorage.removeItem('op_pass');
                }
            });

            async function monitorHUD() {
                if (navigator.getBattery) {
                    const bat = await navigator.getBattery();
                    const upHUD = () => {
                        document.getElementById('b-val').textContent = `PWR: ${Math.round(bat.level * 100)}%`;
                        document.getElementById('b-icon').style.color = bat.charging ? '#ffeb3b' : (bat.level < 0.2 ? '#ff5252' : 'var(--primary)');
                    }
                    upHUD(); bat.onlevelchange = upHUD; bat.onchargingchange = upHUD;
                }
                const netHUD = () => {
                    const status = navigator.onLine;
                    document.getElementById('n-val').textContent = status ? 'NET: SECURE' : 'NET: OFFLINE';
                    document.getElementById('n-icon').style.color = status ? '#4caf50' : '#ff5252';
                }
                window.ononline = netHUD; window.onoffline = netHUD; netHUD();
            }
            monitorHUD();
        </script>
    </body>
    </html>
    """
    return render_template_string(html, error=error)
