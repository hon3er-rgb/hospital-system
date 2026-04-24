import sys
import re

file_path = r'c:\Users\Lenovo\OneDrive\Desktop\نظام الممستشفئ - Copy - Copy - Copy\patient_file.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. REMOVE the showSection duplicate from patient_file.py (it's now in header.py)
# And clean the whole script area
js_code = r"""
    <script>
        // PDF & WhatsApp Share System (Local-Safe)
        async function robustShare(url, filename, phone) {
            const btn = event.currentTarget;
            if (!btn) return;
            const original = btn.innerHTML;
            
            try {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ...';
                btn.style.pointerEvents = 'none';

                const iframe = document.createElement('iframe');
                iframe.style.cssText = 'position:fixed; top:-10000px; left:-10000px; width:850px; height:1200px;';
                document.body.appendChild(iframe);
                iframe.src = window.location.origin + url;
                
                iframe.onload = async function() {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        const el = doc.querySelector('.rx-card, .lab-report, .report-box, body');
                        
                        // Copy image to clipboard
                        if (window.html2canvas) {
                             const canvas = await html2canvas(el, { scale: 1.5, useCORS: true });
                             canvas.toBlob(b => {
                                 if (navigator.clipboard && window.ClipboardItem) {
                                     navigator.clipboard.write([new ClipboardItem({ "image/png": b })]).catch(e => console.warn(e));
                                 }
                             });
                        }

                        // Download PDF
                        if (window.html2pdf) {
                             await html2pdf().set({ margin: 10, filename: filename + '.pdf' }).from(el).save();
                        }

                        const msg = encodeURIComponent(`مرحباً، إليك ملف ${filename} الخاص بك. التقرير متاح الآن كملف PDF في جهازك، وصوره منسوخة للذاكرة.`);
                        window.open(`https://wa.me/${phone.replace(/\D/g, '')}?text=${msg}`, '_blank');
                        
                        setTimeout(() => alert("✅ جاهز! الملف في التنزيلات، والصورة منسوخة للذاكرة لإرسالها بالضغط على (Ctrl+V) في الواتساب."), 300);
                    } catch (e) {
                         console.error(e);
                         window.open(`https://wa.me/${phone.replace(/\D/g, '')}`, '_blank');
                    } finally {
                        btn.innerHTML = original;
                        btn.style.pointerEvents = 'auto';
                        if (iframe.parentNode) document.body.removeChild(iframe);
                    }
                };
            } catch (err) {
                btn.innerHTML = original;
                btn.style.pointerEvents = 'auto';
            }
        }
    </script>
"""

# Find the script block and replace it
# Searching for the <script> block at the end (containing shareReport or showSection)
pattern = r'<script>.*?</script>'
# I'll just find the last script and replace it.
new_content = re.sub(r'    <script>.*?</script>', js_code, content, flags=re.DOTALL)

# Also update the buttons in the file to use robustShare instead of shareReport or shareReportAsPDF
new_content = new_content.replace('onclick="shareReport(', 'onclick="robustShare(')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Patient File Refactored.")
