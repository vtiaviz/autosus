@echo off
chcp 65001 >nul
rem  AutoSUS - instala o agente do robô DENTRO da VM (rodar uma vez, com o usuário do login automático)
setlocal
set DESTINO=C:\AutoSUS_agente
set ORIGEM=%~dp0

set PYW=
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do if not defined PYW set PYW=%%P
if not defined PYW (
  for /f "delims=" %%P in ('where pyw.exe 2^>nul') do if not defined PYW set PYW=%%P
)
if not defined PYW (
  echo Nao encontrei o Python ^(pythonw.exe^) nesta VM. Instale o Python marcando "Add to PATH".
  pause
  exit /b 1
)
echo Python encontrado: %PYW%

if not exist "%DESTINO%" mkdir "%DESTINO%"
copy /y "%ORIGEM%agente.py" "%DESTINO%\" >nul
copy /y "%ORIGEM%iniciar.py" "%DESTINO%\" >nul

set ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AutoSUS agente.lnk
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%ATALHO%'); $s.TargetPath='%PYW%'; $s.Arguments='\"%DESTINO%\iniciar.py\"'; $s.WorkingDirectory='%DESTINO%'; $s.Save()"
echo Atalho criado em: %ATALHO%

echo Iniciando o agente...
start "" "%PYW%" "%DESTINO%\iniciar.py"
echo.
echo Pronto. O agente inicia sozinho a cada login. No host, rode: robo.bat ping
pause
