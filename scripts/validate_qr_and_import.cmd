@echo off
cd /d "%~dp0.."
"d:\my apps\career_copilot_premium\career_copilot_premium\.venv\Scripts\python.exe" scripts\benchmark_import_main.py
"d:\my apps\career_copilot_premium\career_copilot_premium\.venv\Scripts\python.exe" scripts\check_pairing_qr_route.py
