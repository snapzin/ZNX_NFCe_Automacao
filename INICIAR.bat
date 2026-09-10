@echo off
setlocal
title ZNX NFC-e SAT
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
set "SAT_PROJECT_ROOT=%CD%"
set "SAT_PYTHON_PATH=%CD%\.venv\Scripts\python.exe"
set ELECTRON_RUN_AS_NODE=
cd electron
if not exist "node_modules\electron\dist\electron.exe" (
  call npm ci --no-audit --no-fund
  if errorlevel 1 exit /b 1
  node node_modules\electron\install.js
  if errorlevel 1 exit /b 1
)
call npm run dev
