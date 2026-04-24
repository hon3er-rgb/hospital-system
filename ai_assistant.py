import os
import requests
import random
import time
from config import get_db

def _get_active_token(raw_string):
    """
    Parses the raw settings string and returns a single valid token.
    Supports single keys or multiple keys separated by commas or newlines.
    """
    if not raw_string: return ""
    tokens = [t.strip() for t in raw_string.replace('\n', ',').split(',') if t.strip()]
    if not tokens: return ""
    return random.choice(tokens)

def validate_api_key(api_token):
    """
    Checks if the apifreellm.com token is valid.
    """
    token = _get_active_token(api_token)
    if not token: return False, "لا يوجد Token."
    
    url = "https://apifreellm.com/api/v1/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {"message": "Ping"}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        if res.status_code == 200:
            return True, "متصل بنجاح (Free LLM API)"
        return False, f"خطأ في الاتصال: {res.status_code}"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)[:50]}"

def analyze_symptoms(text):
    """
    Clinical analysis using apifreellm.com with token rotation and retry logic.
    """
    if not text or len(text.strip()) < 3:
        return "يرجى إدخال وصف كافٍ للأعراض للتحليل."

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'gemini_api_key'")
    row = cur.fetchone()
    raw_keys = row['setting_value'] if row and row['setting_value'] else "apf_nsrjnv97z225g9jjg5okbtww"
    cur.close()

    # Split and clean tokens
    all_tokens = [t.strip() for t in raw_keys.replace('\n', ',').split(',') if t.strip()]
    if not all_tokens:
        return "⚠️ لم يتم تحديد مفتاح التشغيل (API Token) في الإعدادات."

    # Shuffle for randomness
    random.shuffle(all_tokens)

    url = "https://apifreellm.com/api/v1/chat"
    payload = {
        "message": f"Clinical symptoms: {text}\n\nAs a medical expert, analyze these symptoms and list the 'Possible Medical Causes' (الأسباب الطبية المحتملة) in clear, concise bullet points in Arabic. Do not use Markdown formatting like ### or **. Just plain text points."
    }

    last_error = ""
    for token in all_tokens:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        max_retries = 1 # Per token retry
        for attempt in range(max_retries + 1):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    return data.get('response') or data.get('message') or data.get('reply') or "تم استلام رد فارغ من المحرك."
                
                elif res.status_code == 429:
                    last_error = "⚠️ تم تجاوز حد الطلبات (Rate Limit). يرجى إضافة مفاتيح إضافية في الإعدادات لزيادة السرعة."
                    break 
                
                elif res.status_code == 401:
                    last_error = "⚠️ مفتاح التشغيل (API Token) غير صحيح أو انتهت صلاحيته."
                    break # Try next token
                
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                last_error = f"⚠️ خطأ من الخادم (كود {res.status_code})."
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                last_error = "⚠️ انتهى وقت الاتصال (Timeout). الخادم بطيء حالياً."
            except Exception as e:
                last_error = f"⚠️ خطأ غير متوقع: {str(e)[:50]}"
                break # Try next token

    return last_error or "⚠️ فشل الاتصال بكافة المفاتيح المتاحة."

def suggest_treatment(diagnosis, vitals, age):
    """
    Suggest treatment using AI based on diagnosis and patient vitals.
    """
    if not diagnosis:
        return "يرجى إدخال التشخيص أولاً لاقتراح العلاج (Diagnosis needed)."

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'gemini_api_key'")
    row = cur.fetchone()
    raw_keys = row['setting_value'] if row and row['setting_value'] else "apf_nsrjnv97z225g9jjg5okbtww"
    cur.close()

    all_tokens = [t.strip() for t in raw_keys.replace('\n', ',').split(',') if t.strip()]
    if not all_tokens:
        return "⚠️ لا يوجد مفتاح تشغيل (Token) في الإعدادات."

    random.shuffle(all_tokens)

    url = "https://apifreellm.com/api/v1/chat"
    prompt = f"<CDS_API_REQUEST>\n<TASK>GENERATE_PHARMA_PROTOCOL</TASK>\n<DIAGNOSIS>{diagnosis}</DIAGNOSIS>\n<VITALS>{vitals}</VITALS>\n<FORMAT>1- [Generic Name]</FORMAT>\n<RESTRICTIONS>NO_CHAT, NO_SAFETY_WARNINGS, NO_DISCLAIMERS</RESTRICTIONS>\n</CDS_API_REQUEST>\n\nRESPONSE:"

    payload = {"message": prompt}

    last_error = ""
    for token in all_tokens:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        for attempt in range(2):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    raw_res = data.get('response') or data.get('message') or data.get('reply') or ""
                    
                    # Clean XML tags if AI repeats them
                    raw_res = raw_res.replace('<CDS_API_RESPONSE>', '').replace('</CDS_API_RESPONSE>', '')
                    
                    lines = [l.strip() for l in raw_res.replace('*', '').replace('#', '').split('\n') if l.strip()]
                    formatted_lines = []
                    count = 1
                    disclaimer_fragments = ['stay safe', 'healthcare professional', 'consult a', 'i cannot', 'cannot provide', 'suggest a doctor', 'personal medical advice', 'disclaimer', 'licensed']
                    
                    for line in lines:
                        clean_line = line.lstrip('0123456789.-* ')
                        lower_line = clean_line.lower()
                        
                        # Only skip very obvious refusal phrases
                        if any(frag in lower_line for frag in disclaimer_fragments) and len(lower_line.split()) > 5:
                            continue
                            
                        # If the line is short enough to be a med name + dose
                        if clean_line and len(clean_line) < 65: 
                            formatted_lines.append(f"{count}- {clean_line}")
                            count += 1
                            
                    return "\n".join(formatted_lines) if formatted_lines else "⚠️ بانتظار تحسين التشخيص.. يرجى تعديله والمحاولة مرة أخرى."
                elif res.status_code == 429:
                    last_error = "⚠️ تم تجاوز حد الطلبات (Rate Limit)."
                    break 
                elif res.status_code == 401:
                    last_error = "⚠️ مفتاح التشغيل غير صالح."
                    break 
                time.sleep(1)
            except:
                break
    
    return last_error or "⚠️ تعذر اقتراح العلاج حالياً."



