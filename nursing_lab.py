"""
nursing_lab.py — Specimen Collection Station
Offline AI engine determines sample type, tube, volume, and instructions
from the test name automatically.
"""
from flask import Blueprint, render_template_string, redirect, url_for, session, flash  # type: ignore
from config import get_db, can_access, local_now_naive, local_today_str
from header import header_html
from footer import footer_html
import datetime

nursing_lab_bp = Blueprint('nursing_lab', __name__)

# ══════════════════════════════════════════════════════════════════
#  OFFLINE AI — Sample Intelligence Engine
#  Each entry: keywords (Arabic/English) → full sample profile
# ══════════════════════════════════════════════════════════════════
SAMPLE_AI = [
    # ─── Complete Blood Count ───────────────────────────────────
    {
        "keywords": ["cbc", "صورة دم", "دم كامل", "blood count", "هيموغلوبين",
                     "hemoglobin", "hematocrit", "wbc", "rbc", "platelets",
                     "صفائح", "كريات بيضاء", "كريات حمراء", "تعداد دم"],
        "tube_color": "#7c3aed",
        "tube_ar": "أنبوب بنفسجي (EDTA 3 مل)",
        "blood_type_ar": "دم وريدي كامل",
        "blood_type_en": "Whole Venous Blood",
        "volume_ml": 3,
        "icon": "fa-tint",
        "mixing": "اقلب الأنبوب 8 مرات برفق بعد السحب",
        "fasting": False,
        "instructions_ar": "سحب 3 مل دم وريدي في أنبوب EDTA (الغطاء البنفسجي). لا يُحتاج صيام. اقلب الأنبوب برفق ولا تهزّه.",
        "ai_reason": "تحتاج خلايا الدم كاملةً — الأنبوب البنفسجي يحتوي EDTA مانع تخثر يحافظ على شكل الخلايا."
    },
    # ─── Blood Glucose / Diabetes ───────────────────────────────
    {
        "keywords": ["glucose", "سكر", "غلوكوز", "fasting glucose", "سكر صائم",
                     "random glucose", "سكر عشوائي", "ogtt", "اختبار تحمل"],
        "tube_color": "#6b7280",
        "tube_ar": "أنبوب رمادي (Fluoride-Oxalate)",
        "blood_type_ar": "بلازما صائمة",
        "blood_type_en": "Fasting Plasma",
        "volume_ml": 2,
        "icon": "fa-tint",
        "mixing": "اقلب 8 مرات",
        "fasting": True,
        "instructions_ar": "2 مل دم وريدي بعد صيام 8 ساعات. أنبوب رمادي يحتوي فلوريد يمنع تكسّر الجلوكوز.",
        "ai_reason": "الفلوريد في الأنبوب الرمادي يوقف تكسّر الجلوكوز مما يضمن دقة النتيجة."
    },
    # ─── HbA1c ──────────────────────────────────────────────────
    {
        "keywords": ["hba1c", "السكر التراكمي", "سكر تراكمي", "glycated hemoglobin", "a1c"],
        "tube_color": "#7c3aed",
        "tube_ar": "أنبوب بنفسجي (EDTA 2 مل)",
        "blood_type_ar": "دم وريدي كامل",
        "blood_type_en": "Whole Venous Blood",
        "volume_ml": 2,
        "icon": "fa-tint",
        "mixing": "اقلب 8 مرات",
        "fasting": False,
        "instructions_ar": "2 مل دم وريدي في EDTA. لا يُشترط صيام — يعكس متوسط 3 أشهر.",
        "ai_reason": "HbA1c يُقاس داخل خلايا الدم الحمراء، لذا نحتاج دماً كاملاً بأنبوب EDTA."
    },
    # ─── Liver Function ─────────────────────────────────────────
    {
        "keywords": ["alt", "ast", "sgot", "sgpt", "alp", "ggt", "bilirubin",
                     "بيليروبين", "كبد", "liver", "وظائف كبد", "lft",
                     "albumin", "البومين", "total protein", "بروتين كلي"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST — Gel Separator)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 5,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات — انتظر 30 دق للتخثر",
        "fasting": True,
        "instructions_ar": "5 مل دم وريدي في SST الذهبي. صيام 8-12 ساعة مُفضَّل. انتظر 30 دقيقة قبل الطرد المركزي.",
        "ai_reason": "وظائف الكبد تُقاس في مصل الدم الخالي من الخلايا — الأنبوب الذهبي يحتوي صمغاً فاصلاً للمصل."
    },
    # ─── Kidney Function ────────────────────────────────────────
    {
        "keywords": ["creatinine", "كرياتينين", "urea", "يوريا", "bun",
                     "كلى", "kidney", "renal", "وظائف كلى", "uric acid",
                     "حمض بوليك", "electrolytes", "سوائل"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST — Gel Separator)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 4,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات — انتظر 30 دق",
        "fasting": False,
        "instructions_ar": "4 مل دم وريدي في SST الذهبي. لا يُشترط صيام. انتظر 30 دق ثم أرسل للمختبر.",
        "ai_reason": "الكرياتينين واليوريا يُقاسان في مصل الدم — SST الذهبي يفصل المصل بالجاذبية."
    },
    # ─── Lipid Profile ──────────────────────────────────────────
    {
        "keywords": ["cholesterol", "كوليسترول", "triglyceride", "دهون", "hdl", "ldl",
                     "lipid", "شحوم", "vldl", "دهنيات"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST)",
        "blood_type_ar": "مصل دم صائم (Fasting Serum)",
        "blood_type_en": "Fasting Blood Serum",
        "volume_ml": 4,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات",
        "fasting": True,
        "instructions_ar": "صيام 12 ساعة ضروري. 4 مل في SST الذهبي. الدهون الثلاثية تتأثر جداً بالأكل.",
        "ai_reason": "الدهون تُقاس في المصل ويجب الصيام 12 ساعة لأن الوجبات ترفع الدهون الثلاثية بشكل مؤقت."
    },
    # ─── Electrolytes ───────────────────────────────────────────
    {
        "keywords": ["sodium", "صوديوم", "potassium", "بوتاسيوم", "chloride",
                     "كلوريد", "calcium", "كالسيوم", "magnesium", "ماغنيسيوم",
                     "phosphorus", "فسفور", "electrolyte"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 3,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات",
        "fasting": False,
        "instructions_ar": "3 مل دم وريدي في SST الذهبي. لا يُشترط صيام. أرسل بسرعة لتجنب تسرب البوتاسيوم.",
        "ai_reason": "الشوارد تُقاس في المصل — الإرسال السريع مهم خاصةً للبوتاسيوم لمنع التسرب من الخلايا."
    },
    # ─── Coagulation ────────────────────────────────────────────
    {
        "keywords": ["pt", "aptt", "inr", "coagulation", "تخثر", "تجلط",
                     "d-dimer", "د-دايمر", "fibrinogen", "فيبرينوجين",
                     "bleeding time", "clotting time"],
        "tube_color": "#3b82f6",
        "tube_ar": "أنبوب أزرق (سيترات الصوديوم 2.7 مل)",
        "blood_type_ar": "بلازما سيترات",
        "blood_type_en": "Citrated Plasma",
        "volume_ml": 2.7,
        "icon": "fa-tint",
        "mixing": "اقلب 3-4 مرات برفق — لا تفيض",
        "fasting": False,
        "instructions_ar": "2.7 مل بالضبط في الأنبوب الأزرق. لا تترك فراغاً — نسبة الدم للسيترات 9:1 ضرورية للدقة.",
        "ai_reason": "السيترات يثبط التخثر مؤقتاً للتمكن من قياسه. الحجم الدقيق ضروري جداً لأن تخفيف غير صحيح يغير النتائج."
    },
    # ─── Urine Analysis ─────────────────────────────────────────
    {
        "keywords": ["urine", "بول", "ادرار", "إدرار", "urinalysis", "ua",
                     "urine routine", "فحص بول", "بيلة"],
        "tube_color": "#f59e0b",
        "tube_ar": "كوب عينة بول معقم",
        "blood_type_ar": "بول منتصف التدفق (Midstream Urine)",
        "blood_type_en": "Midstream Urine",
        "volume_ml": 30,
        "icon": "fa-flask",
        "mixing": "لا يُقلب",
        "fasting": False,
        "instructions_ar": "تبوّل قليلاً ثم اجمع في المنتصف 30-50 مل. نظّف المنطقة قبل السحب. أرسل خلال ساعتين.",
        "ai_reason": "البول من المنتصف يتجنب التلوث بالبكتيريا الخارجية مما يعطي نتيجة أدق للزراعة والفحص."
    },
    # ─── Urine Culture ──────────────────────────────────────────
    {
        "keywords": ["urine culture", "زرع بول", "culture sensitivity", "cs بول"],
        "tube_color": "#f59e0b",
        "tube_ar": "كوب زرع بول معقم (Boric Acid)",
        "blood_type_ar": "بول منتصف التدفق معقم",
        "blood_type_en": "Sterile Midstream Urine",
        "volume_ml": 30,
        "icon": "fa-flask",
        "mixing": "لا يُقلب",
        "fasting": False,
        "instructions_ar": "نظّف المنطقة جيداً. اجمع من المنتصف في كوب معقم بحمض البوريك. أرسل فوراً أو احفظ 4°C.",
        "ai_reason": "الزرع يتطلب نقاءً عالياً — كوب بحمض البوريك يمنع نمو البكتيريا أثناء النقل."
    },
    # ─── Blood Culture ──────────────────────────────────────────
    {
        "keywords": ["blood culture", "زرع دم", "كالتشر", "sepsis", "إنتان", "bacteremia"],
        "tube_color": "#1e293b",
        "tube_ar": "زجاجات الكالتشر (هوائي + لاهوائي)",
        "blood_type_ar": "دم وريدي معقم (Aseptic Venous Blood)",
        "blood_type_en": "Aseptic Venous Blood",
        "volume_ml": 20,
        "icon": "fa-biohazard",
        "mixing": "اقلب الزجاجة برفق — لا تهزّ",
        "fasting": False,
        "instructions_ar": "10 مل لكل زجاجة. عقّم الجلد بكلورهيكسيدين 30 ث. احقن فوراً. إجمالي 20 مل (2 زجاجة).",
        "ai_reason": "الزرع الدموي يتطلب كمية كبيرة (20مل) وتعقيماً دقيقاً حيث أن أي تلوث يُفسد النتيجة."
    },
    # ─── Thyroid ────────────────────────────────────────────────
    {
        "keywords": ["tsh", "t3", "t4", "thyroid", "درقية", "غدة درقية",
                     "hypothyroid", "hyperthyroid", "free t4", "free t3"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 3,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات",
        "fasting": False,
        "instructions_ar": "3 مل دم وريدي. يفضَّل السحب صباحاً. لا يُشترط صيام. تجنب التمرين قبل السحب.",
        "ai_reason": "هرمونات الغدة الدرقية تُقاس في المصل — صباح الباكر يعطي أعلى مستوى لـ TSH."
    },
    # ─── Reproductive Hormones ──────────────────────────────────
    {
        "keywords": ["lh", "fsh", "estrogen", "estradiol", "testosterone",
                     "prolactin", "prl", "progesterone", "هرمون", "hormone",
                     "dhea", "cortisol", "كورتيزول", "insulin", "انسولين",
                     "amh", "احتياطي مبيض"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 4,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات",
        "fasting": False,
        "instructions_ar": "4 مل في SST ذهبي. اذكر اليوم من الدورة للهرمونات الأنثوية (LH/FSH: اليوم 2-5). الكورتيزول: صباح الباكر.",
        "ai_reason": "الهرمونات تُقاس في المصل وتتأثر بوقت السحب — توقيت السحب بحسب الدورة يُغير النتيجة جذرياً."
    },
    # ─── CRP / Inflammation ─────────────────────────────────────
    {
        "keywords": ["crp", "c-reactive", "inflammation", "التهاب",
                     "bsr", "esr", "sed rate", "ترسب دم", "سرعة ترسيب"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST) + أنبوب أسود (ESR)",
        "blood_type_ar": "مصل + دم كامل",
        "blood_type_en": "Serum + Whole Blood",
        "volume_ml": 5,
        "icon": "fa-tint",
        "mixing": "SST: 5 مرات | أسود: قلّب 8 مرات",
        "fasting": False,
        "instructions_ar": "للـ CRP: 3 مل في SST ذهبي. للـ ESR: 2 مل في أنبوب أسود (EDTA). اقلب كل أنبوب حسبه.",
        "ai_reason": "CRP يُقاس في المصل أما ESR فيحتاج دماً كاملاً — لذا نحتاج أنبوبين مختلفين."
    },
    # ─── Blood Group / Cross-match ──────────────────────────────
    {
        "keywords": ["blood group", "فصيلة دم", "blood type", "abo",
                     "crossmatch", "كروس ماتش", "تطابق دم", "rh factor"],
        "tube_color": "#ef4444",
        "tube_ar": "أنبوب أحمر (plain) أو EDTA بنفسجي",
        "blood_type_ar": "دم وريدي (للتصنيف)",
        "blood_type_en": "Venous Blood for Grouping",
        "volume_ml": 5,
        "icon": "fa-tint",
        "mixing": "اقلب 8 مرات (EDTA)",
        "fasting": False,
        "instructions_ar": "5 مل في EDTA بنفسجي. للكروس ماتش: أنبوبان منفصلان لضمان التطابق. ضع اسم المريض بدقة.",
        "ai_reason": "تحديد الفصيلة يحتاج خلايا دم كاملة — الخطأ في التسمية قد يكون قاتلاً لذا التوثيق حرفي."
    },
    # ─── Vitamins ───────────────────────────────────────────────
    {
        "keywords": ["vitamin d", "فيتامين د", "vitamin b12", "فيتامين ب12",
                     "folate", "حمض فوليك", "vitamin b9", "ferritin",
                     "فيريتين", "iron", "حديد", "transferrin"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST)",
        "blood_type_ar": "مصل دم (Serum)",
        "blood_type_en": "Blood Serum",
        "volume_ml": 4,
        "icon": "fa-tint",
        "mixing": "اقلب 5 مرات",
        "fasting": True,
        "instructions_ar": "صيام 8 ساعات. 4 مل في SST ذهبي. احمِ الأنبوب من الضوء (فيتامين ب12 يتكسر بالضوء).",
        "ai_reason": "الفيتامينات والحديد تُقاس في المصل — الصيام يضمن استقرار المستويات وعدم تأثر النتائج بالوجبات."
    },
    # ─── Cultures / Swabs ───────────────────────────────────────
    {
        "keywords": ["swab", "culture", "مسحة", "خماج", "wound culture",
                     "throat", "حلق", "nasal", "أنفي", "vaginal", "مهبلي"],
        "tube_color": "#10b981",
        "tube_ar": "مسحة Amies Transport Medium",
        "blood_type_ar": "مسحة بكتيرية (Bacterial Swab)",
        "blood_type_en": "Bacterial Culture Swab",
        "volume_ml": 0,
        "icon": "fa-vial",
        "mixing": "لا ينطبق",
        "fasting": False,
        "instructions_ar": "استخدم مسحة في وسط Amies. سحب قبل إعطاء مضادات حيوية. لا تلمس الجزء الأزرق. أرسل فوراً.",
        "ai_reason": "المسح البكتيرية يجب أن تُؤخذ قبل المضادات الحيوية وتُرسل فوراً لمنع جفاف البكتيريا ونموها."
    },
    # ─── Cardiac Markers ────────────────────────────────────────
    {
        "keywords": ["troponin", "تروبونين", "ck-mb", "myoglobin", "ميوغلوبين",
                     "bnp", "pro-bnp", "قلب", "cardiac", "احتشاء", "infarction"],
        "tube_color": "#d97706",
        "tube_ar": "أنبوب ذهبي (SST) — STAT",
        "blood_type_ar": "مصل دم عاجل (STAT Serum)",
        "blood_type_en": "STAT Blood Serum",
        "volume_ml": 5,
        "icon": "fa-heartbeat",
        "mixing": "اقلب 5 مرات",
        "fasting": False,
        "instructions_ar": "⚡ URGENT — 5 مل في SST. ابعث مباشرة للمختبر بدون انتظار. وثّق وقت السحب بالدقيقة.",
        "ai_reason": "علامات القلب تتغير بسرعة — التوقيت الدقيق للسحب ضروري لمتابعة منحنى الارتفاع والانخفاض."
    },
]

DEFAULT_SAMPLE = {
    "tube_color": "#64748b",
    "tube_ar": "SST ذهبي (قياسي)",
    "blood_type_ar": "مصل دم — حسب طلب الطبيب",
    "blood_type_en": "Serum (as ordered)",
    "volume_ml": 3,
    "icon": "fa-vial",
    "mixing": "اقلب 5 مرات",
    "fasting": False,
    "instructions_ar": "راجع الطبيب المحيل للتحقق من نوع العينة المطلوبة.",
    "ai_reason": "لم يتعرف النظام على التحليل — استخدام الأنبوب القياسي الذهبي كافتراضي آمن."
}


# Mapping for Dynamic Tubes from Lab Maintenance
TUBE_MAP = {
    "Lavender (EDTA)":    {"color": "#7c3aed", "icon": "fa-tint"},
    "Gold (SST/Serum)":   {"color": "#d97706", "icon": "fa-tint"},
    "Light Blue (Citrate)":{"color": "#3b82f6", "icon": "fa-tint"},
    "Grey (Fluoride)":    {"color": "#6b7280", "icon": "fa-tint"},
    "Red (Plain)":        {"color": "#ef4444", "icon": "fa-tint"},
    "Green (Heparin)":    {"color": "#10b981", "icon": "fa-tint"},
    "Urine Cup":          {"color": "#f59e0b", "icon": "fa-flask"},
    "Stool Container":    {"color": "#b45309", "icon": "fa-poop"},
}

def normalize_text(t):
    if not t: return ""
    import re
    # Remove anything not Kurdish/Arabic/Latin letters or numbers
    t = re.sub(r'[^\w\s]', '', t)
    return " ".join(t.lower().split())

def ai_sample(test_name: str, db_config: dict = None) -> dict:
    """Match test name → specimen profile. Prioritize db_config from Lab Maintenance."""
    
    # Clean the input test name for lookup
    search_name = normalize_text(test_name)
    
    # 1. Use Database Config if available (passed from the query join)
    # We check if there's any actual data from the lab_tests table
    if db_config and (db_config.get('tube_type') or db_config.get('sample_type') or db_config.get('instructions')):
        tube_val = db_config.get('tube_type') or "Gold (SST/Serum)"
        tube_info = TUBE_MAP.get(tube_val, {"color": "#64748b", "icon": "fa-vial"})
        
        # CRITICAL: Always prioritize manual instructions from DB
        instr = db_config.get('instructions')
        if not instr or instr.strip() == "":
             instr = "اتباع التعليمات القياسية للمختبر."
             
        return {
            "tube_color":    tube_info["color"],
            "tube_ar":       tube_val,
            "blood_type_ar": db_config.get('sample_type') or "غير محدد",
            "blood_type_en": "Database Link: Active",
            "volume_ml":     db_config.get('volume_ml') or 0,
            "icon":          tube_info["icon"],
            "mixing":        "اقلب (Manual)",
            "fasting":       False,
            "instructions_ar": instr,
            "ai_reason":     "يتم عرض تعليمات الإدارة اليدوية الآن بنجاح."
        }

    # 2. Fallback to AI (Static List)
    t = (test_name or "").lower()
    for entry in SAMPLE_AI:
        if any(kw in t for kw in entry["keywords"]):
            return entry
            
    return DEFAULT_SAMPLE


def _ensure_table(cursor, conn):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nursing_lab_collections (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id   INTEGER UNIQUE,
                collector_id INTEGER,
                collected_at TIMESTAMP,
                notes        TEXT
            )
        """)
        conn.commit()
    except Exception:
        try:
            conn.commit()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  MAIN VIEW
# ══════════════════════════════════════════════════════════════════
@nursing_lab_bp.route('/nursing_lab')
def nursing_lab():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
    if not can_access('nursing'):
        return "غير مصرح لك", 403

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    _ensure_table(cursor, conn)

    cursor.execute("""
        SELECT
            l.request_id, l.test_type, l.status, l.created_at,
            l.appointment_id, l.patient_id,
            p.full_name_ar AS p_name, p.file_number,
            p.date_of_birth, p.gender, p.photo,
            u.full_name_ar  AS doc_name,
            nc.collected_at, nc.collector_id, nc.notes,
            nu.full_name_ar AS collector_name,
            lt.tube_type, lt.sample_type, lt.volume_ml, lt.instructions
        FROM lab_requests l
        LEFT JOIN patients   p  ON l.patient_id = p.patient_id
        LEFT JOIN users u  ON l.doctor_id  = u.user_id
        LEFT JOIN nursing_lab_collections nc ON nc.request_id = l.request_id
        LEFT JOIN users nu ON nu.user_id = nc.collector_id
        LEFT JOIN lab_tests lt ON LOWER(TRIM(lt.test_name)) = LOWER(TRIM(l.test_type))
        WHERE l.status NOT IN ('cancelled', 'completed')
          AND (nc.collected_at IS NULL OR nc.id IS NULL)
        ORDER BY l.created_at DESC
    """)
    rows = cursor.fetchall()

    urgent_ids = set()
    try:
        cursor.execute("""
            SELECT DISTINCT l.request_id
            FROM lab_requests l
            JOIN appointments a ON a.appointment_id = l.appointment_id
            WHERE a.is_urgent = 1 
              AND l.status NOT IN ('cancelled', 'completed')
        """)
        urgent_ids = {r['request_id'] for r in cursor.fetchall()}
    except Exception:
        pass

    today = local_now_naive()
    for r in rows:
        r['is_urgent'] = r['request_id'] in urgent_ids
        r['sample']    = ai_sample(r['test_type'], r)
        
        # Robust 12-hour formatting for the main list
        cr = r.get('created_at')
        if not cr or (isinstance(cr, str) and 'CURRENT' in cr.upper()):
            cr = today
        if isinstance(cr, str):
            from datetime import datetime
            for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
                try:
                    cr = datetime.strptime(cr.split('.')[0], f)
                    break
                except: continue
        if hasattr(cr, 'strftime'):
            r['created_at_12h'] = cr.strftime('%I:%M %p').replace('AM', 'ص').replace('PM', 'م')
        else:
            r['created_at_12h'] = str(cr)[11:16]

        dob = r.get('date_of_birth')
        if dob and hasattr(dob, 'year'):
            r['age'] = today.year - dob.year - ((today.month, today.day) < (today.month, today.day))
        else:
            r['age'] = '?'

    grouped = {}
    for r in rows:
        key = f"{r['appointment_id']}_{r['patient_id']}"
        if key not in grouped:
            grouped[key] = {
                'p_name':     r['p_name'],
                'file_number':r['file_number'],
                'photo':      r['photo'],
                'age':        r['age'],
                'doc_name':   r['doc_name'] or 'غير محدد',
                'is_urgent':  r['is_urgent'],
                'tubes':      {},
                'total_tests': 0,
                'has_pending_payment': False
            }
        
        if r.get('status') == 'pending_payment':
            grouped[key]['has_pending_payment'] = True
        
        # Grouping by Tube Name
        t_name = r['sample']['tube_ar']
        if t_name not in grouped[key]['tubes']:
            grouped[key]['tubes'][t_name] = {
                'sample':     r['sample'],
                'tests':      [],
                'req_ids':    [],
                'created_at': r['created_at']
            }
        
        grouped[key]['tubes'][t_name]['tests'].append(r['test_type'])
        grouped[key]['tubes'][t_name]['req_ids'].append(str(r['request_id']))
        grouped[key]['total_tests'] += 1

    # Statistics — All pending (not date-limited)
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN nc.collected_at IS NOT NULL THEN 1 ELSE 0 END) as collected,
            SUM(CASE WHEN nc.collected_at IS NULL AND l.status NOT IN ('cancelled', 'completed') THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN a.is_urgent = 1 AND nc.collected_at IS NULL AND l.status NOT IN ('cancelled', 'completed') THEN 1 ELSE 0 END) as urgent
        FROM lab_requests l
        LEFT JOIN nursing_lab_collections nc ON nc.request_id = l.request_id
        LEFT JOIN appointments a ON a.appointment_id = l.appointment_id
        WHERE l.status NOT IN ('cancelled', 'completed')
    """)
    db_stats = cursor.fetchone()

    stats = {
        'total':     db_stats['total'] or 0,
        'collected': db_stats['collected'] or 0,
        'pending':   db_stats['pending'] or 0,
        'urgent':    db_stats['urgent'] or 0,
    }

    html = header_html + """
    <div class="container-fluid py-4 px-lg-5" dir="rtl">
        <!-- Dashboard Stats Grid -->
        <div class="row g-4 mb-5 anim">
            <div class="col-md-3">
                <div class="stat-card stat-card-purple shadow-sm">
                    <div class="text-end">
                        <h3 class="fw-black mb-0">{{ stats.total }}</h3>
                        <span class="small fw-bold opacity-75">إجمالي العينات</span>
                    </div>
                    <div class="stat-icon-wrapper bg-primary bg-opacity-10 text-primary">
                        <i class="fas fa-vials"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card stat-card-orange shadow-sm">
                    <div class="text-end">
                        <h3 class="fw-black mb-0">{{ stats.pending }}</h3>
                        <span class="small fw-bold opacity-75">بانتظار السحب</span>
                    </div>
                    <div class="stat-icon-wrapper bg-warning bg-opacity-10 text-warning">
                        <i class="fas fa-clock"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card stat-card-green shadow-sm">
                    <div class="text-end">
                        <h3 class="fw-black mb-0">{{ stats.collected }}</h3>
                        <span class="small fw-bold opacity-75">تم سحبها</span>
                    </div>
                    <div class="stat-icon-wrapper bg-success bg-opacity-10 text-success">
                        <i class="fas fa-check-circle"></i>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card stat-card-red shadow-sm">
                    <div class="text-end">
                        <h3 class="fw-black mb-0 text-danger">{{ stats.urgent }}</h3>
                        <span class="small fw-bold opacity-75">عينات طارئة</span>
                    </div>
                    <div class="stat-icon-wrapper bg-danger bg-opacity-10 text-danger">
                        <i class="fas fa-bolt"></i>
                    </div>
                </div>
            </div>
        </div>

        <!-- Action Header Bar -->
        <div class="glass-header p-3 rounded-4 mb-4 d-flex justify-content-between align-items-center shadow-premium">
            <div class="d-flex align-items-center gap-3 text-end">
                <div class="bg-primary rounded-3 d-flex align-items-center justify-content-center shadow-sm" style="width: 45px; height: 45px; color: white;">
                    <i class="fas fa-syringe fa-lg"></i>
                </div>
                <div class="text-end">
                    <h5 class="fw-bold mb-0" style="color: var(--text);">محطة سحب العينات</h5>
                </div>
            </div>

            <div class="d-flex align-items-center gap-2">
                <!-- Live Search Bar -->
                <div class="search-container-premium d-flex align-items-center bg-white border rounded-pill px-3 py-1 shadow-sm" style="min-width: 250px;">
                    <i class="fas fa-search text-muted me-2"></i>
                    <input type="text" id="patientSearchInput" class="form-control border-0 bg-transparent p-1" placeholder="بحث باسم المريض أو رقم الملف..." style="font-size: 0.85rem; box-shadow: none;">
                </div>

                <a href="{{ url_for('nursing_lab.nursing_lab') }}" class="btn-action-outline px-3 py-2 rounded-pill small fw-bold">
                    <i class="fas fa-sync-alt"></i> تحديث القائمة
                </a>
            </div>
        </div>

        <!-- Patients List -->
        <div class="patient-grid">
            {% for key, data in grouped.items() %}
            <div class="card patient-card mb-3 border-0 shadow-sm anim" style="animation-delay:{{ loop.index0 * 0.05 }}s">
                <div class="card-header border-0 bg-transparent p-3 patient-row-header" data-bs-toggle="collapse" data-bs-target="#nsc{{ loop.index }}">
                    <div class="d-flex align-items-center justify-content-between w-100">
                        <!-- Patient Identity (Right) -->
                        <div class="d-flex align-items-center gap-3">
                            <div class="patient-avatar-box">
                                {% if data.photo %}
                                    <img src="/{{ data.photo }}" class="rounded-pill shadow-sm" style="width: 48px; height: 48px; object-fit: cover; border: 2px solid var(--border);">
                                {% else %}
                                    <div class="rounded-pill bg-light d-flex align-items-center justify-content-center shadow-sm" style="width: 48px; height: 48px; border: 2px solid var(--border);">
                                        <i class="fas fa-user text-muted"></i>
                                    </div>
                                {% endif %}
                            </div>
                            <div class="text-end">
                                <div class="d-flex align-items-center gap-2">
                                    <h6 class="fw-bold mb-0 patient-title" style="color: var(--text);">{{ data.p_name }}</h6>
                                    {% if data.is_urgent %}<span class="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-25 small pulse-anim" style="font-size: 0.65rem;">STAT ⚡</span>{% endif %}
                                    {% if data.has_pending_payment %}<span class="badge bg-warning bg-opacity-10 text-warning border border-warning border-opacity-25 small pulse-anim" style="font-size: 0.65rem; color: #b45309 !important;">بانتظار الدفع 💰</span>{% endif %}
                                </div>
                                <div class="p-meta-compact d-flex gap-3 mt-1">
                                    <span class="meta-item"><i class="fas fa-birthday-cake me-1"></i> {{ data.age }} سنة</span>
                                    <span class="meta-item"><i class="fas fa-hashtag me-1"></i> #{{ data.file_number }}</span>
                                    <span class="meta-item"><i class="fas fa-user-md me-1"></i> د. {{ data.doc_name }}</span>
                                </div>
                            </div>
                        </div>

                        <div class="d-flex align-items-center gap-3">
                            <div class="sample-count-badge px-3 py-1 rounded-pill">
                                <span class="fw-bold">{{ data.total_tests }} عينة</span>
                            </div>
                            <i class="fas fa-chevron-right opacity-25"></i>
                        </div>
                    </div>
                </div>

                <div id="nsc{{ loop.index }}" class="collapse {{ 'show' if grouped|length == 1 }}">
                    <div class="card-body p-4 pt-0">
                        {% if data.has_pending_payment %}
                        <div class="alert alert-warning text-center rounded-4 border-warning fw-bold d-flex flex-column align-items-center py-5 shadow-sm" style="background: #fffbeb; color: #b45309; border: 2px dashed #fcd34d;">
                            <i class="fas fa-money-bill-wave fa-3x mb-3 text-warning"></i>
                            <span class="fs-5 mb-2">يرجى مراجعة قسم الحسابات لتسديد الرسوم أولاً</span>
                            <span class="small opacity-75">لن يتم عرض نوع العينة أو طباعة الملصق حتى يتم الدفع وتأكيد الحسابات</span>
                        </div>
                        {% else %}
                        {% for tube_name, tube_data in data.tubes.items() %}
                        {% set s = tube_data.sample %}
                        {% set req_ids_str = tube_data.req_ids|join(',') %}
                        <div class="test-item-row p-4 rounded-4 mb-3 border border-dashed text-end" style="background: var(--section-bg); border-color: var(--border);">
                            <div class="d-flex justify-content-between align-items-start flex-wrap gap-4">
                                <!-- Test Header (Right) -->
                                <div class="flex-grow-1">
                                    <div class="d-flex align-items-center justify-content-between mb-3 gap-3">
                                        <!-- Right Side: Instructions & Test Names -->
                                        <div class="d-flex align-items-center gap-3">

                                            <h5 class="fw-black mb-0 text-end" style="color: var(--text); font-size: 1.05rem;">
                                                {{ tube_data.tests|join(', ') }}
                                            </h5>
                                        </div>

                                        <!-- Left: Tube & Metadata -->
                                        <div class="d-flex align-items-center gap-2">
                                            <div class="specimen-badges-row d-flex gap-1">
                                                {% if s.fasting %}<div class="badge-vibrant bg-warning text-dark fw-black" style="font-size: 0.6rem; padding: 2px 6px;">صيام</div>{% endif %}

                                                <div class="badge-vibrant bg-info text-dark fw-black" style="font-size: 0.6rem; padding: 2px 6px;"><i class="fas fa-redo"></i> {{ s.mixing }}</div>
                                                <div class="badge-vibrant bg-primary text-white" style="font-size: 0.6rem; padding: 2px 6px;"><i class="fas fa-flask-glass"></i> {{ s.volume_ml if s.volume_ml > 0 else '0' }}ml</div>
                                            </div>
                                            <div class="badge-tube-solid d-flex align-items-center gap-2 shadow-sm" 
                                                 style="background: {{ s.tube_color }}; color: #fff; padding: 6px 14px; border-radius: 10px; font-weight: 900; white-space: nowrap; min-width: 140px; justify-content: center;">
                                                <i class="fas fa-vial fa-sm"></i>
                                                <span style="font-size: 0.8rem;">{{ tube_name }}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Action Strip -->
                                    <div class="d-flex justify-content-start gap-2 mt-3 pt-3 border-top" style="border-color: rgba(0,0,0,0.05) !important;">
                                        <a href="{{ url_for('nursing_lab.collect_sample', req_id=req_ids_str) }}" class="btn-collect-premium px-4 py-2 rounded-3 fw-black text-center" style="font-size: 0.85rem;" onclick="return confirm('تأكيد سحب هذه المجموعة؟')">
                                            تأكيد سحب العينة
                                        </a>
                                        <a href="{{ url_for('nursing_lab.print_label', req_id=req_ids_str) }}" target="_blank" class="btn-print-premium px-4 py-2 rounded-3 small fw-bold text-center" style="font-size: 0.8rem;">
                                            طباعة الملصق
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
            
            {% if not grouped %}
            <div class="empty-state text-center py-5">
                <div class="bg-light p-5 rounded-circle d-inline-block mb-4 shadow-sm">
                    <i class="fas fa-check-double fa-4x text-success opacity-25"></i>
                </div>
                <h4 class="fw-black mb-1">لا توجد عينات معلقة</h4>
                <p class="text-muted small">تم سحب جميع العينات المطلوبة لهذا اليوم</p>
            </div>
            {% endif %}
        </div>
    </div>

    <style>
        :root {
            --primary-g: linear-gradient(135deg, #7c3aed, #4f46e5);
            --info-g: linear-gradient(135deg, #0ea5e9, #0284c7);
        }

        body { background: var(--bg); color: var(--text); }

        .stat-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
        .stat-icon-wrapper {
            width: 50px; height: 50px;
            border-radius: 15px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem;
        }

        .glass-header {
            background: var(--card);
            border: 1px solid var(--border);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }
        

        .btn-action-outline {
            border: 1px solid var(--border);
            background: var(--card);
            color: var(--text);
            text-decoration: none;
            transition: 0.3s;
        }
        .btn-action-outline:hover { background: var(--section-bg); transform: translateY(-2px); }

        .patient-card {
            background: var(--card);
            border: 1px solid var(--border) !important;
            border-radius: 20px;
            overflow: hidden;
        }
        .patient-row-header { cursor: pointer; transition: 0.2s; }
        .patient-row-header:hover { background: var(--section-bg); }

        .sample-count-badge {
            background: var(--section-bg);
            border: 1px solid var(--border);
            color: var(--primary);
            font-size: 0.75rem;
        }

        .badge-premium { padding: 4px 12px; border-radius: 50px; font-size: 0.75rem; font-weight: 800; }

        .info-bubble {
            padding: 12px 15px;
            border-radius: 12px;
            font-size: 0.75rem;
            line-height: 1.6;
            height: 100%;
        }
        .bubble-orange { background: rgba(245, 158, 11, 0.1); color: #b45309; border: 1px dashed rgba(245, 158, 11, 0.5); }
        .bubble-blue { background: rgba(59, 130, 246, 0.1); color: #1e40af; border: 1px dashed rgba(59, 130, 246, 0.5); }
        
        

        
        
        

        
        
        
        

        .btn-collected { background: #10b981; color: white; cursor: default; }

        .fw-black { font-weight: 900; }
        .x-small { font-size: 0.65rem; }

        .pulse-anim { animation: pulseS 2s infinite; }
        @keyframes pulseS {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        .action-panel {
            min-width: 180px;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        

        .btn-collect-premium {
            background: linear-gradient(135deg, #7c3aed, #4f46e5);
            color: white;
            text-decoration: none;
            transition: 0.3s;
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
        }
        .btn-collect-premium:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(124, 58, 237, 0.4); color: white; }

        .status-badge-collected {
            background: #10b981;
            color: white;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }

        .btn-print-premium {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text);
            text-decoration: none;
            transition: 0.2s;
        }
        .btn-print-premium:hover { background: var(--section-bg); border-color: var(--primary); transform: translateY(-2px); }

        
        

        .badge-vibrant {
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.68rem;
            display: flex;
            align-items: center;
            gap: 4px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.06);
            border: 1px solid rgba(0,0,0,0.05);
        }
        
        
        /* Light mode punchier colors */
        .badge-vibrant.bg-primary { background: #4f46e5 !important; }
        .badge-vibrant.bg-info { background: #06b6d4 !important; }
        .badge-vibrant.bg-warning { background: #f59e0b !important; }
        
        .specimen-badges-row { 
            background: rgba(0,0,0,0.04); 
            padding: 8px; 
            border-radius: 12px;
            display: inline-flex !important;
            min-width: fit-content;
        }
        

        .p-meta-compact { gap: 15px !important; }
        .meta-item {
            font-size: 0.85rem;
            font-weight: 600;
            color: #64748b;
            display: flex;
            align-items: center;
        }
        .meta-item i { margin-left: 5px; color: var(--primary); font-size: 0.9rem; }
        
        
        

        .patient-title { font-size: 1.1rem !important; margin-bottom: 2px !important; }

        .anim { animation: fadeInU 0.4s ease-out both; }
        @keyframes fadeInU { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }

        .font-arabic { font-family: 'Cairo', sans-serif; }
    </style>
    <script>
    document.getElementById('patientSearchInput').addEventListener('keyup', function() {
        let val = this.value.toLowerCase().trim();
        let cards = document.querySelectorAll('.patient-card');
        
        cards.forEach(card => {
            let pName = card.querySelector('.patient-title').innerText.toLowerCase();
            let fileNum = card.querySelector('.p-meta-compact').innerText.toLowerCase();
            
            if (pName.includes(val) || fileNum.includes(val)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    });
    </script>
    """ + footer_html

    return render_template_string(html, grouped=grouped, stats=stats)


# ══════════════════════════════════════════════════════════════════
#  COLLECT SAMPLE
# ══════════════════════════════════════════════════════════════════
@nursing_lab_bp.route('/nursing_lab/collect/<req_id>')
def collect_sample(req_id):
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    _ensure_table(cursor, conn)

    ids = str(req_id).split(',')
    for r_id in ids:
        r_id = r_id.strip()
        if not r_id: continue
        
        cursor.execute("SELECT id FROM nursing_lab_collections WHERE request_id = ?", (r_id,))
        now_ts = local_now_naive()
        if cursor.fetchone():
            cursor.execute("""
                UPDATE nursing_lab_collections
                SET collector_id = ?, collected_at = ?
                WHERE request_id = ?
            """, (session['user_id'], now_ts, r_id))
        else:
            cursor.execute("""
                INSERT INTO nursing_lab_collections (request_id, collector_id, collected_at)
                VALUES (?, ?, ?)
            """, (r_id, session['user_id'], now_ts))

        cursor.execute("""
            UPDATE lab_requests SET status = 'pending'
            WHERE request_id = ? AND status != 'completed'
        """, (r_id,))
    
    conn.commit()
    flash("تم تأكيد سحب العينات بنجاح", "success")
    return redirect(url_for('nursing_lab.nursing_lab'))


# ══════════════════════════════════════════════════════════════════
#  PRINT LABEL
# ══════════════════════════════════════════════════════════════════
@nursing_lab_bp.route('/nursing_lab/label/<req_id>')
def print_label(req_id):
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    ids = str(req_id).split(',')
    first_id = ids[0].strip()

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get Patient & Common Info from first test
    cursor.execute("""
        SELECT l.request_id, l.test_type, l.created_at,
               p.full_name_ar AS p_name, p.file_number, p.date_of_birth,
               u.full_name_ar AS doc_name,
               lt.tube_type, lt.sample_type, lt.volume_ml, lt.instructions
        FROM lab_requests l
        JOIN patients   p ON l.patient_id = p.patient_id
        LEFT JOIN users u ON l.doctor_id  = u.user_id
        LEFT JOIN lab_tests lt ON LOWER(TRIM(lt.test_name)) = LOWER(TRIM(l.test_type))
        WHERE l.request_id = ?
    """, (first_id,))
    r = cursor.fetchone()
    if not r:
        return "طلب غير موجود", 404

    # Fetch all test names for the label
    test_names = []
    for rid in ids:
        cursor.execute("SELECT test_type FROM lab_requests WHERE request_id = ?", (rid,))
        row = cursor.fetchone()
        if row: test_names.append(row['test_type'])
    
    combined_tests = ", ".join(test_names)

    s   = ai_sample(r['test_type'], r)
    dob = r.get('date_of_birth')
    age = "?"
    today_dt = local_now_naive()
    if dob and hasattr(dob, 'year'):
        age = today_dt.year - dob.year - ((today_dt.month, today_dt.day) < (dob.month, dob.day))

    bc    = f"{r['file_number']}-{first_id}"
    cr    = r['created_at']
    
    # Robust 12-hour formatting logic
    if not cr or (isinstance(cr, str) and 'CURRENT' in cr.upper()):
        cr = today_dt
    
    if isinstance(cr, str):
        from datetime import datetime
        for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
            try:
                cr = datetime.strptime(cr.split('.')[0], f)
                break
            except: continue
            
    if hasattr(cr, 'strftime'):
        cr_s = cr.strftime('%Y-%m-%d %I:%M %p').replace('AM', 'ص').replace('PM', 'م')
    else:
        cr_s = str(cr)[:16]

    vol   = f"{s['volume_ml']} مل" if s['volume_ml'] > 0 else "مسحة"
    doc   = r.get('doc_name') or ''

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><title>بطاقة — {r['p_name']}</title>
<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
<style>
  @page{{size:62mm 45mm;margin:0}}
  *{{box-sizing:border-box;font-family:Arial,sans-serif;margin:0;padding:0}}
  body{{width:62mm;height:45mm;padding:2mm;background:#fff;overflow:hidden}}
  .lbl{{border:1.5px solid #e2e8f0;border-right:5px solid {s['tube_color']};
        border-radius:3px;padding:2mm;height:100%;display:flex;flex-direction:column;justify-content:space-between}}
  .n{{font-size:9pt;font-weight:900;text-align:right;color:#1e293b}}
  .m{{display:flex;justify-content:space-between;font-size:6pt;color:#475569;direction:rtl}}
  .t{{font-size:7pt;font-weight:800;color:{s['tube_color']};border-top:1px dashed #e2e8f0;padding-top:1mm;text-align:right}}
  .bt{{font-size:6.5pt;font-weight:800;color:{s['tube_color']};text-align:right}}
  .r{{display:flex;justify-content:space-between;align-items:center}}
  .v{{background:{s['tube_color']};color:#fff;padding:1px 5px;border-radius:4px;font-size:6.5pt;font-weight:900}}
  .bc{{text-align:center}}
  #bc{{width:100%;height:9mm}}
  .bct{{font-size:5pt;color:#94a3b8}}
</style></head>
<body onload="window.print();">
<div class="lbl">
  <div class="n">{r['p_name']}</div>
  <div class="m"><span>#{r['file_number']}</span><span>{age} سنة</span><span>{cr_s}</span></div>
  <div class="t" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{combined_tests}</div>
  <div class="bt">{s['blood_type_ar']}</div>
  <div class="r">
    <span class="v">{vol}</span>
    <span style="font-size:6pt;color:{s['tube_color']};font-weight:800">{s['tube_ar']}</span>
  </div>
  <div style="font-size:5.5pt;color:#64748b;text-align:right">د. {doc}</div>
  <div class="bc"><svg id="bc"></svg><div class="bct">{bc}</div></div>
</div>
<script>JsBarcode("#bc","{bc}",{{format:"CODE128",width:1.3,height:25,displayValue:false,margin:0}});</script>
</body></html>"""
