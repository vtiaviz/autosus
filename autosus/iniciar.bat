@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem AutoSUS: sobe a API (NestJS, 127.0.0.1:3001) e o site (Next.js, http://localhost:3000) em duas janelas.
rem Na primeira vez, ou depois de atualizar o codigo, rode antes: preparar.bat
start "AutoSUS - API" /min cmd /c "cd /d "%~dp0api" && node dist\main.js"
start "AutoSUS - site" /min cmd /c "cd /d "%~dp0web" && npx next start -p 3000"
timeout /t 5 >nul
start "" http://localhost:3000
