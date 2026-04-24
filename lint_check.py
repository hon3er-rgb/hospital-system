import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

blueprints = [
    'index', 'login', 'logout', 'dashboard', 'patients', 'doctor_clinic',
    'consultation', 'pharmacy', 'lab', 'radiology', 'triage', 'patient_index',
    'patient_file', 'book', 'connect', 'archive', 'system_data', 'manage_staff',
    'waiting_list', 'api', 'billing', 'reservations', 'add_patient', 'edit_patient',
    'settings', 'price_control', 'print_rx', 'registration_settings', 'lab_maintenance'
]

def check_imports():
    failed = []
    for bp in blueprints:
        try:
            __import__(bp)
            print(f"Successfully imported {bp}")
        except Exception as e:
            print(f"Failed to import {bp}: {e}")
            failed.append((bp, e))
    
    if failed:
        print("\n--- Summary ---")
        for bp, e in failed:
            print(f"{bp}: {e}")
    else:
        print("\nAll blueprints imported successfully.")

if __name__ == "__main__":
    check_imports()
