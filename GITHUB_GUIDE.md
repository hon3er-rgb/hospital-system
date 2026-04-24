# دليل رفع المشروع على GitHub

## الخطوات:

### 1. إنشاء حساب على GitHub
- اذهب إلى https://github.com
- سجل حساب جديد (مجاني)

### 2. إنشاء Repository جديد
1. سجل دخول على GitHub
2. اضغط على "+" في الزاوية العلوية اليمنى
3. اختر "New repository"
4. أدخل اسم للمشروع (مثلاً: hospital-system)
5. اختر "Public" أو "Private"
6. اضغط "Create repository"

### 3. تهيئة Git في المشروع
افتح terminal أو cmd في مجلد المشروع ونفذ الأوامر التالية:

```bash
git init
git add .
git commit -m "Initial commit - Hospital Management System"
```

### 4. ربط المشروع بـ GitHub
استبدل `YOUR_USERNAME` باسم مستخدم GitHub و `hospital-system` باسم الـ repository:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hospital-system.git
git push -u origin main
```

### 5. إدخال بيانات الدخول
- سيطلب GitHub اسم المستخدم وكلمة المرور
- أو استخدم GitHub Personal Access Token (أنسب للمستخدمين الجدد)

## إنشاء Personal Access Token (موصى به):

1. اذهب إلى GitHub Settings
2. اختر "Developer settings"
3. اختر "Personal access tokens" → "Tokens (classic)"
4. اضغط "Generate new token (classic)"
5. أعطِ الصلاحيات المطلوبة (repo, workflow)
6. انسخ الـ token
7. استخدمه ككلمة مرور عند git push

## ملاحظات هامة:

- تم إنشاء ملف `.gitignore` لاستبعاد الملفات غير الضرورية:
  - قواعد البيانات (*.db)
  - الملفات المؤقتة (__pycache__)
  - ملفات البيئة (.env)
  - ملفات البناء (build/, dist/)

- الملفات التي سيتم رفعها:
  - جميع ملفات .py
  - مجلد templates
  - مجلد static
  - requirements.txt
  - ملفات الإعدادات

## بعد الرفع على GitHub:

يمكنك الآن نشر المشروع على منصات الاستضافة المجانية:
- Render.com (أسهل من GitHub)
- Railway.app
- Vercel

راجع ملف `DEPLOYMENT_GUIDE.md` للتفاصيل.
