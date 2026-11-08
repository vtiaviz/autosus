@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Instala as dependencias, aplica as migracoes do banco e compila a API e o site.
echo [1/4] API: dependencias...
cd api || goto erro
call npm install || goto erro
echo [2/4] API: banco (migracoes)...
call npx prisma migrate deploy || goto erro
call npx prisma generate || goto erro
echo [3/4] API: compilando...
call npx nest build || goto erro
cd ..\web || goto erro
echo [4/4] Site: dependencias e compilacao...
call npm install || goto erro
call npx next build || goto erro
echo.
echo Pronto. Para abrir o AutoSUS: iniciar.bat
pause
exit /b 0

:erro
echo.
echo *** Falhou. Veja a mensagem acima. ***
pause
exit /b 1
