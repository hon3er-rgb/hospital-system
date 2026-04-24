import json
from flask import Blueprint, session, redirect, url_for, request, render_template_string # type: ignore
from config import get_db, can_access, local_now_naive # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore

connect_bp = Blueprint('connect', __name__)

@connect_bp.route('/connect', methods=['GET'])
def connect():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    my_id = session['user_id']
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Update task
    cursor.execute("UPDATE users SET current_task = 'متاح للتواصل', active_patient_name = NULL WHERE user_id = %s", (my_id,))
    conn.commit()
    
    # Fetch all users with presence info and department
    cursor.execute("""
        SELECT u.user_id, u.full_name_ar, u.is_active, u.photo, d.department_name_ar,
               p.last_seen
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.department_id 
        LEFT JOIN user_presence p ON u.user_id = p.user_id
        WHERE u.user_id != %s AND u.is_active = 1
        ORDER BY d.department_name_ar ASC, u.full_name_ar ASC
    """, (my_id,))
    
    users_raw = cursor.fetchall()
    
    # Process into departments and check online status
    now = local_now_naive()
    departments = {}
    for u in users_raw:
        is_online = False
        if u['last_seen']:
            diff = (now - u['last_seen']).total_seconds()
            if diff < 60: is_online = True
        
        dept = u['department_name_ar'] or 'عام'
        if dept not in departments:
            departments[dept] = []
            
        u['is_online'] = is_online
        u['dept'] = dept
        departments[dept].append(u)
        
    conn.close()

    html = header_html + """
    <style>
        .connect-hero {
            background: linear-gradient(135deg, #0f172a, #1e293b);
            border-radius: 30px; padding: 40px; margin-bottom: 30px; color: white;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        }
        .search-container {
            max-width: 600px; margin: -50px auto 40px; position: relative; z-index: 100;
        }
        .search-container input {
            height: 60px; border-radius: 30px; border: none; padding-left: 60px; padding-right: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1); font-size: 1.1rem;
        }
        .search-container i {
            position: absolute; left: 25px; top: 18px; font-size: 1.5rem; color: #94a3b8;
        }
        .dept-title {
            font-size: 0.9rem; font-weight: 800; color: #64748b; text-transform: uppercase;
            letter-spacing: 1px; margin-top: 40px; margin-bottom: 20px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;
        }
        .user-glass-card {
            background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.4);
            border-radius: 20px; padding: 15px; transition: all 0.3s;
            cursor: pointer; position: relative;
        }
        .user-glass-card:hover {
            transform: translateY(-5px); box-shadow: 0 15px 35px rgba(0,0,0,0.05); border-color: #007aff;
        }
        .presence-dot {
            width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;
            position: absolute; top: 15px; right: 15px; z-index: 5;
        }
        .online-dot { background: #10b981; animation: pulse-online 2s infinite; }
        .offline-dot { background: #cbd5e1; }
        
        .role-badge { font-size: 0.65rem; padding: 3px 10px; border-radius: 50px; background: rgba(0, 122, 255, 0.1); color: #007aff; font-weight: bold; }
        @keyframes pulse-online { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }
    </style>

    <div class="p-4" style="background: #f8fafc; min-height: 100vh;">
        <div class="connect-hero text-center">
            <h1 class="fw-bold mb-3"><i class="fas fa-network-wired me-2"></i> شبكة تواصل HealthPro الموحدة</h1>
            <p class="opacity-75 fs-5">تواصل مع كافة الطواقم الطبية والإدارية والمالية بنقرة واحدة</p>
        </div>

        <div class="search-container">
            <input type="text" id="globalUserSearch" class="form-control" placeholder="ابحث عن زميل، ممرض، محاسب أو قسم..." onkeyup="filterAllUsers()">
            <i class="fas fa-search"></i>
        </div>

        <div id="usersRoot">
            {% for dept, users in departments.items() %}
            <div class="dept-section animate__animated animate__fadeInUp" id="section-{{ loop.index }}">
                <div class="dept-title"><i class="fas fa-users-cog me-2 text-primary"></i> قسم {{ dept }}</div>
                <div class="row g-3">
                    {% for u in users %}
                    <div class="col-lg-3 col-md-6 user-card-item" data-search="{{ u.full_name_ar }} {{ dept }}">
                        <div class="user-glass-card d-flex align-items-center gap-3">
                            <span class="presence-dot {{ 'online-dot' if u.is_online else 'offline-dot' }}"></span>
                            <div class="avatar-circle rounded-circle bg-primary bg-opacity-10 text-primary fw-bold d-flex align-items-center justify-content-center" 
                                 style="width: 55px; height: 55px; font-size: 1.3rem; flex-shrink: 0;">
                                {% if u.photo %}
                                    <img src="/{{ u.photo }}" style="width:100%; height:100%; object-fit: cover; border-radius:50%;">
                                {% else %}
                                    {{ u.full_name_ar[0] }}
                                {% endif %}
                            </div>
                            <div class="flex-grow-1 overflow-hidden">
                                <div class="fw-bold text-dark text-truncate small mb-1">{{ u.full_name_ar }}</div>
                                <span class="role-badge">{{ dept }}</span>
                            </div>
                            <div class="d-flex w-100">
                                <button class="w-100 btn btn-primary border-0 rounded-pill py-2 fw-bold shadow-sm hover-scale" 
                                        onclick="makeCall({{ u.user_id }}, '{{ u.full_name_ar }}')">
                                    <i class="fas fa-video me-1"></i> اتصال طبي
                                </button>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        function filterAllUsers() {
            const query = document.getElementById('globalUserSearch').value.toLowerCase();
            const cards = document.querySelectorAll('.user-card-item');
            const sections = document.querySelectorAll('.dept-section');
            
            cards.forEach(card => {
                const text = card.getAttribute('data-search').toLowerCase();
                if (text.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
            
            sections.forEach(sec => {
                const visibleInSec = Array.from(sec.querySelectorAll('.user-card-item')).filter(c => c.style.display !== 'none').length;
                sec.style.display = visibleInSec > 0 ? 'block' : 'none';
            });
        }

        async function startVideoCall(uid, name) {
            if (window.makeCall) {
                await window.makeCall(uid, name);
            }
        }
    </script>
    """ + footer_html
    
    return render_template_string(html, departments=departments)
