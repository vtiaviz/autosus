@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   AutoSUS - instalacao
echo ============================================
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version || (echo Python nao encontrado. Instale em https://www.python.org & pause & exit /b 1)

rem O ambiente Python fica na raiz do C:\AutoSUS e e compartilhado com o server_sus
set "VENV=%~dp0..\..\.venv"

echo.
echo [1/4] Criando ambiente virtual (C:\AutoSUS\.venv)...
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%" || goto erro

echo [2/4] Instalando bibliotecas...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt || goto erro
"%VENV%\Scripts\python.exe" -m pip install -r ..\..\server_sus\requirements.txt || goto erro

echo [3/4] Instalando o navegador do Playwright (Chromium)...
"%VENV%\Scripts\python.exe" -m playwright install chromium || goto erro

echo [4/4] Preparando o arquivo .env...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Preencha usuario, senha e CPF do CNES e a senha de app do Gmail no Bloco de Notas.
  notepad ".env"
) else (
  echo .env ja existe, mantido.
)

echo.
echo Instalacao concluida. Proximos passos:
echo   1) autosus.bat --testar-aviso     (testa notificacao e e-mail)
echo   2) autosus.bat --simular          (mostra o que seria baixado)
echo   3) autosus.bat                    (baixa de verdade)
echo   4) agendar.bat                    (agenda todo dia as 10h)
pause
exit /b 0

:erro
echo.
echo *** A instalacao falhou. Veja a mensagem acima. ***
pause
exit /b 1
