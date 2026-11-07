@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem API do Server_SUS. Por enquanto so na propria maquina (127.0.0.1); o token fica no .env.
if not exist "..\.venv\Scripts\python.exe" (
  echo Rode ..\autosus\downloads\instalar.bat primeiro.
  pause
  exit /b 1
)
"..\.venv\Scripts\python.exe" -m uvicorn api.app:app --host 127.0.0.1 --port 8765 %*
