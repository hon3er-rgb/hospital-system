
    /* ════════════════════════════════════
       HealthPro Consultation v4 - Event Delegation JS
       ════════════════════════════════════ */

    if (!window.hpConsultationBound_v9) {
        window.hpConsultationBound_v9 = true;
        window.hpTagStore = { selectedLabs: [], selectedRads: [] };

        window.hpAddTag = function(val, areaId, hiddenId, countId, badgeId, btnId, paramName) {
            val = val.trim();
            if (!val) return;
            if (window.hpTagStore[areaId].indexOf(val) !== -1) return;
            window.hpTagStore[areaId].push(val);

            var area = document.getElementById(areaId);
            if (!area) return;
            var hint = area.querySelector('.empty-hint');
            if (hint) hint.remove();

            var tag = document.createElement('div');
            tag.className = 'hp-tag';
            tag.setAttribute('data-v', val);
            
            var s = document.createElement('span'); s.textContent = val; tag.appendChild(s);
            
            var i = document.createElement('i');
            i.className = 'fas fa-times-circle x';
            i.onclick = function() { window.hpRemoveTag(val, areaId, countId, badgeId, btnId); };
            tag.appendChild(i);

            var h = document.createElement('input');
            h.type = 'hidden'; h.name = paramName; h.value = val;
            tag.appendChild(h);

            area.appendChild(tag);

            var hiddenCont = document.getElementById(hiddenId);
            if (hiddenCont) {
                var hc = document.createElement('input');
                hc.type = 'hidden'; hc.name = paramName; hc.value = val; hc.setAttribute('data-v', val);
                hiddenCont.appendChild(hc);
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpRemoveTag = function(val, areaId, countId, badgeId, btnId) {
            window.hpTagStore[areaId] = window.hpTagStore[areaId].filter(function(v){ return v !== val; });
            var area = document.getElementById(areaId);
            if (!area) return;
            area.querySelectorAll('.hp-tag').forEach(function(t){
                if (t.getAttribute('data-v') === val) t.remove();
            });
            if (window.hpTagStore[areaId].length === 0) {
                area.innerHTML = '<div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على فحص أو ابحث ثم Enter لإضافته</div>';
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpUpdateCount = function(areaId, countId, badgeId, btnId) {
            var n = window.hpTagStore[areaId].length;
            var c = document.getElementById(countId);  if (c) c.textContent = n;
            var b = document.getElementById(badgeId);  if (b) b.textContent = n;
            var btn = document.getElementById(btnId);  if (btn) btn.disabled = (n === 0);
        };

        window.hpAppendMed = function(val) {
            var rxArea = document.getElementById('rxArea');
            var medInp = document.getElementById('medInput');
            val = val.trim();
            if (!val || !rxArea) return;
            var cur = rxArea.value.trim();
            rxArea.value = cur ? cur + '\\n' + val + ' - ' : val + ' - ';
            if(medInp) medInp.value = '';
            rxArea.focus();
        };

        window.hpUseTpl = function(text) {
            var rxArea = document.getElementById('rxArea');
            if (rxArea) rxArea.value = text;
        };

        window.hpToggleSection = function(id, btn) {
            var content = document.getElementById(id);
            if (!content) return;
            
            var isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'block' : 'none';
            
            var isLab = id.includes('lab');
            var txtShow = isLab ? 'إظهار الفحوصات' : 'إظهار الأشعة';
            var txtHide = isLab ? 'إخفاء الفحوصات' : 'إخفاء الأشعة';
            var color = isLab ? '#007aff' : '#ff2d55';

            if (isHidden) {
                btn.innerHTML = '<i class="fas fa-eye-slash me-1"></i> ' + txtHide;
                btn.style.background = '#ffffff';
                btn.style.color = color;
                btn.classList.remove('text-white');
            } else {
                btn.innerHTML = '<i class="fas fa-eye me-1"></i> ' + txtShow;
                btn.style.background = color;
                btn.style.color = '#ffffff';
                btn.classList.add('text-white');
            }
        };

        window.hpStartSpeech = function(targetName, btn) {
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert("عذراً، متصفحك لا يدعم التعرف على الصوت. يرجى استخدام متصفح Chrome.");
                return;
            }

            var recognition = new SpeechRecognition();
            recognition.lang = 'ar-SA';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            var originalHTML = btn.innerHTML;
            var originalColor = btn.style.color;

            recognition.onstart = function() {
                btn.innerHTML = '<i class="fas fa-rss animate-pulse me-1"></i> جاري الاستماع...';
                btn.style.background = '#ff2d55';
                btn.style.color = '#ffffff';
                btn.classList.add('shadow-lg');
            };

            recognition.onresult = function(event) {
                var transcript = event.results[0][0].transcript;
                var target = document.querySelector('[name="' + targetName + '"]');
                if (target) {
                    var currentVal = target.value.trim();
                    target.value = (currentVal ? currentVal + ' ' : '') + transcript;
                    target.focus();
                }
            };

            recognition.onend = function() {
                btn.innerHTML = originalHTML;
                btn.style.background = '#fdfdfd';
                btn.style.color = originalColor;
                btn.classList.remove('shadow-lg');
            };

            recognition.onerror = function(event) {
                console.error("Speech Error:", event.error);
                btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i> خطأ!';
                setTimeout(function() {
                    btn.innerHTML = originalHTML;
                    btn.style.background = '#fdfdfd';
                    btn.style.color = originalColor;
                }, 2000);
            };

            recognition.start();
        };

        // Advanced Lab Result Validation
        window.hpValidateLabs = function() {
            const ranges = {
                // --- Basic & Hematology ---
                'GLUCOSE': { min: 70, max: 110, range: '70 - 110 mg/dL' },
                'WBC': { min: 4, max: 11, range: '4.0 - 11.0 10³/uL' },
                'RBC': { min: 4.5, max: 5.9, range: '4.5 - 5.9 10⁶/uL' },
                'HGB': { min: 12, max: 17.5, range: '12.0 - 17.5 g/dL' },
                'HBA1C': { min: 4, max: 5.6, range: '4.0 - 5.6 %' },
                'PLT': { min: 150, max: 450, range: '150 - 450 10³/uL' },
                'ESR': { min: 0, max: 20, range: '0 - 20 mm/hr' },
                
                // --- Renal Profile (وظائف الكلى) ---
                'UREA': { min: 15, max: 45, range: '15 - 45 mg/dL' },
                'CREA': { min: 0.7, max: 1.3, range: '0.7 - 1.3 mg/dL' },
                'BUN': { min: 7, max: 20, range: '7 - 20 mg/dL' },
                'URIC': { min: 3.5, max: 7.2, range: '3.5 - 7.2 mg/dL' },
                
                // --- Liver Profile (وظائف الكبد) ---
                'ALT': { min: 0, max: 41, range: '< 41 U/L' },
                'AST': { min: 0, max: 40, range: '< 40 U/L' },
                'ALP': { min: 40, max: 129, range: '40 - 129 U/L' },
                'BILI': { min: 0.1, max: 1.2, range: '0.1 - 1.2 mg/dL' },
                'ALB': { min: 3.5, max: 5.2, range: '3.5 - 5.2 g/dL' },
                'GGT': { min: 8, max: 61, range: '8 - 61 U/L' },

                // --- Lipid Profile (الدهون) ---
                'CHOL': { min: 100, max: 200, range: '< 200 mg/dL' },
                'TRIG': { min: 0, max: 150, range: '< 150 mg/dL' },
                'LDL': { min: 0, max: 130, range: '< 130 mg/dL' },
                'HDL': { min: 40, max: 60, range: '> 40 mg/dL' },

                // --- Thyroid & Hormones (الغدد) ---
                'TSH': { min: 0.4, max: 4.0, range: '0.4 - 4.0 mIU/L' },
                'T4': { min: 5, max: 12, range: '5 - 12 ug/dL' },
                'T3': { min: 80, max: 200, range: '80 - 200 ng/dL' },

                // --- Cardiac & Inflammatory ---
                'CRP': { min: 0, max: 5, range: '< 5.0 mg/L' },
                'TROPONIN': { min: 0, max: 0.04, range: '< 0.04 ng/mL' },
                'CK': { min: 22, max: 198, range: '22 - 198 U/L' },
                'LDH': { min: 140, max: 280, range: '140 - 280 U/L' },

                // --- Electrolytes & Others ---
                'SODIUM': { min: 135, max: 145, range: '135 - 145 mmol/L' },
                'POTASSIUM': { min: 3.5, max: 5.1, range: '3.5 - 5.1 mmol/L' },
                'CALCIUM': { min: 8.5, max: 10.5, range: '8.5 - 10.5 mg/dL' },
                'OSMOL': { min: 50, max: 1200, range: '50 - 1200 mOsm/kg' },

                // --- Specialty (Immunology & Specific mentioned) ---
                'HLA': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'ANTHRAX': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'SPERM': { min: 0, max: 60, range: '< 60 U/mL', type: 'hybrid', normal: 'NEGATIVE' },
                'HBV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'HCV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'HIV': { type: 'string', normal: 'NEGATIVE', range: 'Negative' },
                'PAP': { min: 0, max: 3.5, range: '< 3.5 ng/mL' },
                'HBS': { type: 'hybrid', min: 10, max: 999999, range: '> 10 mIU/mL', normal: 'POSITIVE' }
            };

            const rows = document.querySelectorAll('#labResultsTable tbody tr');
            rows.forEach(row => {
                const testName = row.getAttribute('data-test-name');
                const resultText = row.getAttribute('data-result-val');
                const resultVal = parseFloat(resultText.replace(/[^\\d.-]/g, ''));
                
                const rangeDisp = row.querySelector('.range-display');
                const statusCell = row.querySelector('.status-cell');
                const resDisp = row.querySelector('.result-display');

                // Advanced Matching
                let matchedKey = Object.keys(ranges).find(k => testName.includes(k));
                if (matchedKey) {
                    const r = ranges[matchedKey];
                    rangeDisp.innerHTML = r.range;
                    
                    let statusHtml = '';
                    let statusColor = '';

                    if (r.type === 'string' || (r.type === 'hybrid' && isNaN(resultVal))) {
                        // Handle String Results (Positive/Negative)
                        const resUpper = resultText.toUpperCase();
                        if (resUpper.includes('NEG') || resUpper.includes('طبيعي') || resUpper.includes('سالب')) {
                            statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-check me-1"></i> سليم</span>';
                            statusColor = '#10b981';
                        } else if (resUpper.includes('POS') || resUpper.includes('موجب') || resUpper.includes('+')) {
                            statusHtml = '<span class="badge bg-danger text-white rounded-pill px-3 shadow-sm"><i class="fas fa-exclamation-triangle me-1"></i> إيجابي</span>';
                            statusColor = '#ef4444';
                        }
                    } else if (!isNaN(resultVal)) {
                        // Handle Numerical Results
                        if (matchedKey === 'HBS') {
                            // Hepatitis B Immunity Logic (Antibodies)
                            if (resultVal >= 10) {
                                statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-shield-alt me-1"></i> محصن</span>';
                                statusColor = '#10b981';
                            } else {
                                statusHtml = '<span class="badge bg-warning text-dark rounded-pill px-3 shadow-sm"><i class="fas fa-times me-1"></i> غير محصن</span>';
                                statusColor = '#f59e0b';
                            }
                        } else if (resultVal < r.min) {
                            statusHtml = '<span class="badge bg-warning text-dark rounded-pill px-3 shadow-sm"><i class="fas fa-arrow-down me-1"></i> منخفضة</span>';
                            statusColor = '#f59e0b';
                        } else if (resultVal > r.max) {
                            statusHtml = '<span class="badge bg-danger text-white rounded-pill px-3 shadow-sm"><i class="fas fa-arrow-up me-1"></i> مرتفعة</span>';
                            statusColor = '#ef4444';
                        } else {
                            statusHtml = '<span class="badge bg-success text-white rounded-pill px-3 shadow-sm"><i class="fas fa-check me-1"></i> طبيعية</span>';
                            statusColor = '#10b981';
                        }
                    }

                    statusCell.innerHTML = statusHtml || '<span class="badge bg-secondary text-white rounded-pill px-3">تحليل نصي</span>';
                    resDisp.style.color = statusColor || '#3b82f6';
                } else {
                    rangeDisp.innerHTML = '<span class="opacity-50">غير محدد</span>';
                    statusCell.innerHTML = '<span class="badge bg-light text-muted border px-3">مراجعة يدوية</span>';
                    resDisp.style.color = '#3b82f6';
                }
            });
        };

        // Initialize validations
        setTimeout(window.hpValidateLabs, 100);

        // Event delegation for clicks (Tabs, Add Buttons, Grid Items)
        document.addEventListener('click', function(e) {
            // Tab switching
            var tabBtn = e.target.closest('.hp-tab');
            if (tabBtn) {
                document.querySelectorAll('.hp-tab').forEach(function(b){ b.classList.remove('active'); });
                document.querySelectorAll('.hp-tab-pane').forEach(function(p){ p.style.display = 'none'; });
                tabBtn.classList.add('active');
                var target = document.getElementById(tabBtn.getAttribute('data-hp-target'));
                if (target) target.style.display = 'block';
                return;
            }

            // Grid Items
            var gItem = e.target.closest('.g-item');
            if (gItem) {
                var gridId = gItem.parentElement.id;
                if (gridId === 'labGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                } else if (gridId === 'radGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                }
                return;
            }

            // Add Actions
            if (e.target.closest('#labAddBtn')) {
                var labInp = document.getElementById('labSearch');
                if (labInp && labInp.value.trim()) {
                    window.hpAddTag(labInp.value.trim(), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                    labInp.value = '';
                    document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            } else if (e.target.closest('#radAddBtn')) {
                var radInp = document.getElementById('radSearch');
                if (radInp && radInp.value.trim()) {
                    window.hpAddTag(radInp.value.trim(), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                    radInp.value = '';
                    document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            }
        });

        // Search filtering logic
        document.addEventListener('input', function(e) {
            if (e.target.id === 'labSearch') {
                var q1 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#labGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q1) ? '' : 'none';
                });
            } else if (e.target.id === 'radSearch') {
                var q2 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#radGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q2) ? '' : 'none';
                });
            }
        });

        // Enter key to add tags and meds
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                if (e.target.id === 'labSearch') {
                    e.preventDefault();
                    var v1 = e.target.value.trim();
                    if (v1) {
                        window.hpAddTag(v1, 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                        e.target.value = '';
                        document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'radSearch') {
                    e.preventDefault();
                    var v2 = e.target.value.trim();
                    if (v2) {
                        window.hpAddTag(v2, 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                        e.target.value = '';
                        document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'medInput') {
                    e.preventDefault();
                    window.hpAppendMed(e.target.value);
                }
            }
        });

        document.addEventListener('change', function(e) {
            if (e.target.id === 'medInput') {
                window.hpAppendMed(e.target.value);
            }
        });
        // --- Smart Assistant Logic ---
        window.hpSmartAssistant = function() {
            var notesArea = document.getElementById("notes-area");
            var notes = notesArea ? notesArea.value.trim() : "";
            var resBox = document.getElementById("smart-assistant-result");
            var container = document.getElementById("smart-assistant-container");
            if (!notes) {
                if(container) container.style.display = "block";
                if(resBox) resBox.innerHTML = "<span class='text-danger'>يرجى كتابة الشكوى أولاً ليتمكن المساعد من تحليلها.</span>";
                return;
            }
            if(container) container.style.display = "block";
            if(resBox) resBox.innerHTML = "<i class='fas fa-spinner fa-spin text-primary'></i> جاري التحليل والبحث...";
            
            fetch('/smart_assistant_search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: notes })
            })
            .then(response => response.json())
            .then(data => {
                var text = data.result || "لا توجد نتائج.";
                if(resBox) {
                    resBox.innerHTML = "";
                    var i = 0;
                    var speed = 20;
                    function typeWriter() {
                        if (i < text.length) {
                            resBox.innerHTML += text.charAt(i);
                            i++;
                            setTimeout(typeWriter, speed);
                        }
                    }
                    typeWriter();
                }
            })
            .catch(err => {
                if(resBox) resBox.innerHTML = "<span class='text-danger'><i class='fas fa-exclamation-triangle'></i> حدث خطأ محلي: " + err + "</span>";
            });
        };

        // --- Smart Rx Assistant ---
        window.hpSmartRx = function(e) {
            var btn = (e && e.currentTarget) ? e.currentTarget : (window.event ? window.event.srcElement : null);
            if (!btn) btn = this; 
            
            var notes = (document.getElementById("notes-area") ? document.getElementById("notes-area").value.trim() : "");
            var assInput = document.querySelector('input[name="assessment"]');
            var ass   = (assInput ? assInput.value.trim() : "");
            var rxArea = document.getElementById("rxArea");
            
            if (!notes && !ass) {
                alert("يرجى كتابة الشكوى أو التشخيص أولاً ليتمكن المساعد من اقتراح العلاج.");
                return;
            }
            
            var original = btn.innerHTML;
            btn.innerHTML = "<i class='fas fa-spinner fa-spin'></i> جاري الاقتراح...";
            btn.disabled = true;

            var q = "بناءً على الشكوى (" + notes + ") والتشخيص (" + ass + ")، اقترح مجموعة أدوية وعلاجات مناسبة (أسماء الأدوية فقط مع جرعاتها). لا تستخدم أي تنسيق مارك داون (لا تستخدم نجوم **).";

            fetch('/smart_assistant_search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q })
            })
            .then(response => response.json())
            .then(data => {
                var text = data.result || "";
                if (text) {
                    text = text.replace(/✅ التقرير الطبي الذكي لـ: .*\n\n/g, "");
                    text = text.replace(/\\*\\*/g, "");
                    if (rxArea) {
                        if (rxArea.value) rxArea.value += "\n" + text;
                        else rxArea.value = text;
                        rxArea.dispatchEvent(new Event('input'));
                    }
                }
            })
            .catch(err => alert("حدث خطأ في جلب الاقتراحات: " + err))
            .finally(() => {
                btn.innerHTML = original;
                btn.disabled = false;
            });
        };
    } // End if (!window.hpConsultationBound_v9)

    // --- DOM Initialization Loop (Runs on every PJAX load) ---
    (function() {
        var apptId = "{{ data.appointment_id }}";
        var fieldConfigs = [
            { id: "notes-area", key: "cln_notes_" + apptId },
            { id: "diag-input", key: "cln_diag_" + apptId },
            { id: "rxArea",     key: "cln_rx_" + apptId }
        ];

        // 1. Load saved values and set up real-time auto-save
        fieldConfigs.forEach(function(cfg) {
            var el = document.getElementById(cfg.id);
            if (el) {
                try {
                    var saved = localStorage.getItem(cfg.key);
                    if (saved) el.value = saved;
                    
                    el.oninput = function() {
                        try {
                            localStorage.setItem(cfg.key, this.value);
                        } catch(e) { console.error("Auto-save error:", e); }
                    };
                } catch(e) { console.warn("Storage access denied:", e); }
            }
        });

        // 2. Clear only on successful main form submission
        var mForm = document.getElementById("notes-area") ? document.getElementById("notes-area").closest("form") : null;
        if (mForm) {
            var oldOnSubmit = mForm.onsubmit;
            mForm.onsubmit = function(event) {
                try {
                    fieldConfigs.forEach(function(cfg) { localStorage.removeItem(cfg.key); });
                } catch(e) {}
                if (typeof oldOnSubmit === 'function') return oldOnSubmit.apply(this, arguments);
            };
        }

        // 3. Update initial badges and validations
        if (window.hpUpdateCount) {
            window.hpUpdateCount('selectedLabs', 'labCount', 'labBadge', 'labSubmitBtn');
            window.hpUpdateCount('selectedRads', 'radCount', 'radBadge', 'radSubmitBtn');
        }
        if (window.hpValidateLabs) window.hpValidateLabs();
    })();

    