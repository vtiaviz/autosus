@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem O ambiente Python fica na raiz do C:\AutoSUS e e compartilhado com o server_sus
set "VENV=%~dp0..\..\.venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo Rode instalar.bat primeiro.
  pause
  exit /b 1
)
"%VENV%\Scripts\python.exe" -m autosus %*
