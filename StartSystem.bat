@echo off
echo Starting HealthPro OS - Offline Mode...
py init_db.py
echo Database status: OK
start http://127.0.0.1:5000/login
py app.py
pause
