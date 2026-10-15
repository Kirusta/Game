@echo off
cd /d "%~dp0"
set "PYTHON_EXE=C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0\python.exe"
start "CyberTD datubāze" /min /D "%~dp0" "%PYTHON_EXE%" start_server.py
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/"
"%PYTHON_EXE%" CyberTD.PY
pause
