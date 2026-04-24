# دليل نشر نظام المستشفى على استضافة مجانية

## الخيارات المجانية المتاحة:

### 1. PythonAnywhere (الأفضل لتطبيقات Flask)
- **الموقع**: https://www.pythonanywhere.com
- **المميزات**:
  - خطة مجانية تدعم تطبيقات Flask
  - سهل الإعداد
  - يدعم قاعدة بيانات SQLite (موجودة لديك)
  - دعم Python
- **الخطوات**:
  1. إنشاء حساب مجاني
  2. رفع الملفات عبر Web interface أو Git
  3. إنشاء Web App جديد
  4. اختيار Flask framework
  5. ربط الملفات
  6. تشغيل التطبيق

### 2. Render.com
- **الموقع**: https://render.com
- **المميزات**:
  - خطة مجانية مع SSL
  - دعم Docker
  - سهل النشر من GitHub
- **الخطوات**:
  1. رفع الكود على GitHub
  2. إنشاء حساب على Render
  3. ربط GitHub repository
  4. إنشاء Web Service جديد
  5. سيتم النشر تلقائياً

### 3. Railway.app
- **الموقع**: https://railway.app
- **المميزات**:
  - $5 مجانية شهرياً
  - دعم قواعد بيانات PostgreSQL
  - واجهة سهلة
- **الخطوات**:
  1. رفع الكود على GitHub
  2. إنشاء مشروع جديد
  3. إضافة قاعدة بيانات PostgreSQL
  4. نشر التطبيق

### 4. Vercel (مع Adapter)
- **الموقع**: https://vercel.com
- **المميزات**:
  - خطة مجانية غير محدودة
  - سرعة عالية
  - دعم Python عبر Serverless Functions
- **الخطوات**:
  1. تثبيت Vercel Python Adapter
  2. رفع الكود على GitHub
  3. ربط Repository
  4. النشر

### 5. Glitch.com
- **الموقع**: https://glitch.com
- **المميزات**:
  - مجاني بالكامل
  - تحرير مباشر في المتصفح
  - سهل للمبتدئين
- **الخطوات**:
  1. إنشاء مشروع جديد
  2. رفع الملفات
  3. تشغيل التطبيق

## التوصية:

**PythonAnywhere** هو الخيار الأفضل لأن:
- مصمم خصيصاً لتطبيقات Python
- يدعم Flask بشكل أصلي
- سهل الإعداد للمبتدئين
- قاعدة البيانات SQLite ستعمل مباشرة

## ملاحظات هامة:

1. **قاعدة البيانات**: نظامك يستخدم SQLite (HospitalSystem.db) - ستعمل مباشرة على PythonAnywhere
2. **الملفات المطلوبة للنشر**:
   - جميع ملفات .py
   - مجلد templates
   - مجلد static
   - مجلد uploads
   - ملف requirements.txt
   - ملف .env (بدون كلمات مرور حساسة)
   - HospitalSystem.db

3. **تعديل app.py للنشر**:
   - تغيير `host='0.0.0.0'` إلى `host='127.0.0.1'` في بيئة الإنتاج
   - تعطيل debug mode: `debug=False`

## خطوات النشر على PythonAnywhere:

1. سجل حساب مجاني على https://www.pythonanywhere.com
2. اذهب إلى "Files" وارفع جميع الملفات
3. اذهب إلى "Web" واضغط "Add a new web app"
4. اختر "Flask"
5. اختر إصدار Python (3.8 أو أحدث)
6. أدخل مسار المشروع: `/home/username/العمل - Copy - Copy`
7. أدخل ملف الإدخال: `app.py`
8. اذهب إلى "Virtualenv" وقم بتثبيت المكتبات:
   ```
   pip install -r requirements.txt
   ```
9. اضغط "Reload" لتشغيل التطبيق
