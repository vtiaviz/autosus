# Cria (ou atualiza) a tarefa diaria do AutoSUS no Agendador de Tarefas.
# Uso: agendar.bat            -> todo dia as 10:00
#      agendar.bat 09:30      -> outro horario
#      agendar.bat remover    -> apaga a tarefa
param([string]$Horario = "10:00")

$ErrorActionPreference = "Stop"
$Nome = "AutoSUS - downloads mensais"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Horario -eq "remover") {
    Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
    Write-Host "Tarefa '$Nome' removida."
    exit 0
}

# o ambiente Python fica na raiz do C:\AutoSUS (compartilhado com o server_sus)
$Pythonw = Join-Path $Dir "..\..\.venv\Scripts\pythonw.exe" | Resolve-Path -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path
if (-not $Pythonw -or -not (Test-Path $Pythonw)) { throw "Rode instalar.bat antes de agendar." }

$Acao = New-ScheduledTaskAction -Execute $Pythonw -Argument "-m autosus" -WorkingDirectory $Dir
$Gatilho = New-ScheduledTaskTrigger -Daily -At $Horario
$Opcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nome -Action $Acao -Trigger $Gatilho -Settings $Opcoes `
    -Description "Verifica e baixa os arquivos SIH/SIA/CNES do DATASUS (AutoSUS)." -Force | Out-Null

Write-Host "Tarefa '$Nome' agendada para todo dia as $Horario."
Write-Host "Se o computador estiver desligado nesse horario, ela roda assim que ele for ligado."
Write-Host "Para conferir: abra o Agendador de Tarefas > Biblioteca."
