@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "..\.venv\Scripts\python.exe" (
  echo Rode ..\autosus\downloads\instalar.bat primeiro.
  pause
  exit /b 1
)
"..\.venv\Scripts\python.exe" robo.py %*
