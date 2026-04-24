@echo off
cd /d "%~dp0"
echo ========================================
echo Building Hospital System EXE
echo ========================================
echo Current directory: %CD%
echo.

echo Step 1: Installing dependencies...
pip install -r requirements.txt
echo.

echo Step 2: Building EXE with PyInstaller...
pyinstaller --clean hospital_system.spec
echo.

echo ========================================
echo Build Complete!
echo The EXE file is located in: dist\HospitalSystem.exe
echo.
pause
