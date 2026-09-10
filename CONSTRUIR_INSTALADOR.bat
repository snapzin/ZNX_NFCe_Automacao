@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller api\server.spec --noconfirm
if errorlevel 1 exit /b 1
REM Configuracao nasce no primeiro uso; nenhum dado local entra no pacote.
cd electron
call npm ci --no-audit --no-fund
if errorlevel 1 exit /b 1
node node_modules\electron\install.js
if errorlevel 1 exit /b 1
set ELECTRON_RUN_AS_NODE=
call npm run build
if errorlevel 1 exit /b 1
echo Instalador gerado em electron\dist\ZNX-SAT-Setup-*.exe
