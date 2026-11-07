@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0teste_completo.ps1" %*
set COD=%ERRORLEVEL%
pause
exit /b %COD%
