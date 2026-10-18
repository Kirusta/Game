@echo off
cd /d "%~dp0"
set "PYTHON_EXE=C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0\python.exe"
echo Tiek palaists Cyber Tower Defense serveris. Neaizver šo logu.
start "CyberTD datubāze" /min /D "%~dp0" "%PYTHON_EXE%" start_server.py
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000/rules"
start "" "http://127.0.0.1:8000/leaderboard"
start "" "http://127.0.0.1:8000/database"
echo Serveris ir palaists. Šo logu vari aizvērt tikai tad, kad lapas vairs nevajag.
pause
