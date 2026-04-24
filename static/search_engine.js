/**
 * HealthPro Smart Search Engine
 * Works from the FIRST character typed
 */

function hpSearch(inputId, resultsId, dataList, onSelect) {
    const input = document.getElementById(inputId);
    const results = document.getElementById(resultsId);
    if (!input || !results) return;

    function showResults(val) {
        if (!val || val.length === 0) {
            results.style.cssText = 'display:none!important';
            return;
        }
        const matches = dataList.filter(d => d.toLowerCase().includes(val.toLowerCase())).slice(0, 15);
        if (matches.length === 0) {
            results.style.cssText = 'display:none!important';
            return;
        }
        results.innerHTML = matches.map(m => `
            <div class="hp-result-item" data-value="${m.replace(/"/g, '&quot;')}">
                <i class="fas fa-plus-circle"></i> ${m}
            </div>
        `).join('');
        results.style.cssText = 'display:block!important; position:absolute; top:100%; left:0; right:0; background:#fff; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.15); z-index:99999; max-height:260px; overflow-y:auto; margin-top:4px; border:1px solid #eee;';

        results.querySelectorAll('.hp-result-item').forEach(item => {
            item.style.cssText = 'padding:12px 18px; cursor:pointer; border-bottom:1px solid #f0f0f5; font-size:0.95rem; font-weight:500; color:#333; display:flex; align-items:center; gap:10px; transition:background 0.15s;';
            item.onmouseenter = () => item.style.background = '#f0f7ff';
            item.onmouseleave = () => item.style.background = '';
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                onSelect(item.getAttribute('data-value'));
                results.style.cssText = 'display:none!important';
            });
        });
    }

    input.addEventListener('input', () => showResults(input.value));
    input.addEventListener('focus', () => showResults(input.value));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') results.style.cssText = 'display:none!important';
    });

    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.style.cssText = 'display:none!important';
        }
    });
}

function addOrderTag(item, containerId, paramName, countId, submitBtnId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Don't add duplicates
    const existing = container.querySelector(`input[value="${CSS.escape(item)}"]`);
    if (existing) return;

    const emptyMsg = container.querySelector('.empty-msg');
    if (emptyMsg) emptyMsg.style.display = 'none';

    const tag = document.createElement('div');
    tag.style.cssText = 'background:#eef7ff; color:#007aff; padding:6px 14px; border-radius:10px; display:inline-flex; align-items:center; gap:8px; font-weight:600; font-size:0.9rem; border:1px solid rgba(0,122,255,0.15); margin:3px;';
    tag.innerHTML = `<span>${item}</span><input type="hidden" name="${paramName}" value="${item}"><i class="fas fa-times-circle" style="cursor:pointer; font-size:0.8rem; opacity:0.6;" onclick="this.parentElement.remove(); hpCheckEmpty('${containerId}', '${countId}', '${submitBtnId}');"></i>`;
    container.appendChild(tag);

    const submitBtn = document.getElementById(submitBtnId);
    if (submitBtn) submitBtn.disabled = false;

    const badge = document.getElementById(countId);
    if (badge) badge.innerText = container.querySelectorAll('input[type=hidden]').length;
}

function hpCheckEmpty(containerId, countId, submitBtnId) {
    const container = document.getElementById(containerId);
    const badge = document.getElementById(countId);
    const submitBtn = document.getElementById(submitBtnId);
    const emptyMsg = container ? container.querySelector('.empty-msg') : null;
    const items = container ? container.querySelectorAll('input[type=hidden]') : [];

    if (badge) badge.innerText = items.length;
    if (items.length === 0) {
        if (emptyMsg) emptyMsg.style.display = '';
        if (submitBtn) submitBtn.disabled = true;
    }
}

function filterGrid(inputId, gridId) {
    const input = document.getElementById(inputId);
    const grid = document.getElementById(gridId);
    if (!input || !grid) return;

    input.addEventListener('input', () => {
        const val = input.value.toLowerCase().trim();
        grid.querySelectorAll('.test-item').forEach(item => {
            const text = (item.getAttribute('data-value') || item.innerText || '').toLowerCase();
            item.style.display = text.includes(val) ? 'flex' : 'none';
        });
    });
}

// Initialize all searches once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // These will be set by the inline script
    const labs = window.HP_LABS || [];
    const rads = window.HP_RADS || [];
    const diags = window.HP_DIAGS || [];
    const meds = window.HP_MEDS || [];

    // --- LAB SEARCH ---
    hpSearch('labSearch', 'labResults', labs, (val) => {
        addOrderTag(val, 'selectedLabs', 'selected_tests[]', 'labCount', 'labSubmitBtn');
    });
    filterGrid('labSearch', 'labGrid');

    const labGrid = document.getElementById('labGrid');
    if (labGrid) {
        labGrid.querySelectorAll('.test-item').forEach(item => {
            item.addEventListener('click', () => {
                addOrderTag(item.getAttribute('data-value'), 'selectedLabs', 'selected_tests[]', 'labCount', 'labSubmitBtn');
            });
        });
    }

    const labAddBtn = document.getElementById('labAddBtn');
    if (labAddBtn) {
        labAddBtn.onclick = () => {
            const inp = document.getElementById('labSearch');
            if (inp && inp.value.trim()) {
                addOrderTag(inp.value.trim(), 'selectedLabs', 'selected_tests[]', 'labCount', 'labSubmitBtn');
                inp.value = '';
            }
        };
    }

    // --- RADIOLOGY SEARCH ---
    hpSearch('radSearch', 'radResults', rads, (val) => {
        addOrderTag(val, 'selectedRads', 'selected_scans[]', 'radCount', 'radSubmitBtn');
    });
    filterGrid('radSearch', 'radGrid');

    const radGrid = document.getElementById('radGrid');
    if (radGrid) {
        radGrid.querySelectorAll('.test-item').forEach(item => {
            item.addEventListener('click', () => {
                addOrderTag(item.getAttribute('data-value'), 'selectedRads', 'selected_scans[]', 'radCount', 'radSubmitBtn');
            });
        });
    }

    const radAddBtn = document.getElementById('radAddBtn');
    if (radAddBtn) {
        radAddBtn.onclick = () => {
            const inp = document.getElementById('radSearch');
            if (inp && inp.value.trim()) {
                addOrderTag(inp.value.trim(), 'selectedRads', 'selected_scans[]', 'radCount', 'radSubmitBtn');
                inp.value = '';
            }
        };
    }

    // --- DIAGNOSIS SEARCH ---
    const diagInput = document.getElementById('diagSearch');
    hpSearch('diagSearch', 'diagResults', diags, (val) => {
        if (diagInput) diagInput.value = val;
    });

    // --- MEDICATION SEARCH ---
    const rxArea = document.getElementById('rx_area');
    hpSearch('medSearch', 'medResults', meds, (val) => {
        if (rxArea) {
            const cur = rxArea.value.trim();
            rxArea.value = cur ? cur + '\n' + val + ' - ' : val + ' - ';
            rxArea.focus();
        }
        const medInp = document.getElementById('medSearch');
        if (medInp) medInp.value = '';
    });

    // --- TAB SWITCHING ---
    document.querySelectorAll('.nav-medical .nav-link').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelectorAll('.nav-medical .nav-link').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('show', 'active'));
            this.classList.add('active');
            const target = document.querySelector(this.getAttribute('data-bs-target'));
            if (target) target.classList.add('show', 'active');
        });
    });

    // Template function
    window.useTemplate = (text) => {
        const rx = document.getElementById('rx_area');
        if (rx) rx.value = text;
    };
});
