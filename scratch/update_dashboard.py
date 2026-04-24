import re

with open('dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

style = """    <style>
        .circular-badge {
            position: absolute;
            top: -6px;
            right: -6px;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            color: white !important;
            font-size: 0.75rem;
            border: 2px solid #fff;
            z-index: 10;
            box-shadow: 0 3px 8px rgba(0,0,0,0.15);
        }
        .circular-badge.bg-danger { background: #ef4444 !important; }
        .circular-badge.bg-warning { background: #f59e0b !important; }
        .circular-badge.bg-info { background: #06b6d4 !important; }
        .circular-badge.bg-success { background: #10b981 !important; }
        .circular-badge.bg-secondary { background: #64748b !important; }
        .circular-badge.bg-primary { background: #3b82f6 !important; }
        .neo-tile { position: relative; }
    </style>
"""

if 'circular-badge' not in content:
    content = content.replace('<!-- Tiny Neo-Tiles Grid (Permission Based) -->', style + '    <!-- Tiny Neo-Tiles Grid (Permission Based) -->')

# Replace Neo-tiles badges
content = re.sub(r'<span class="tile-count bg-(danger|warning|info|secondary|success|primary)[^"]*">', r'<div class="circular-badge bg-\1">', content)
content = re.sub(r'(<div class="circular-badge[^"]*">[^<]*)</span>', r'\1</div>', content)

# Replace timeline badges
content = re.sub(r'<span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-(danger|success|info|warning|secondary|primary)[^"]*">', r'<div class="circular-badge bg-\1">', content)
content = re.sub(r'(<div class="circular-badge[^"]*">[^<]*)(</span>)', r'\1</div>', content)

# Replace the one unpaid invoices
content = re.sub(r'<div class="position-absolute d-flex align-items-center justify-content-center fw-bold text-white"\s*style="top:-8px; right:-8px; width:22px; height:22px; border-radius:50%; background:#ef4444; font-size:0.7rem; border:2px solid #fff; z-index:10; box-shadow:0 2px 6px rgba\(239,68,68,0.5\);">', r'<div class="circular-badge bg-danger">', content)


with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(content)
