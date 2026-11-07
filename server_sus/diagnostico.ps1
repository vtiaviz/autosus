# AutoSUS - diagnóstico da VirtualBox (somente leitura: não altera nada)
# Gera diagnostico_resultado.txt nesta pasta.
$ErrorActionPreference = 'Continue'
$saida = Join-Path $PSScriptRoot 'diagnostico_resultado.txt'
$vbm = Join-Path $env:ProgramFiles 'Oracle\VirtualBox\VBoxManage.exe'
if (-not (Test-Path $vbm)) { $vbm = (Get-Command VBoxManage.exe -ErrorAction SilentlyContinue).Source }

function Bloco($titulo, [scriptblock]$cmd) {
    "`n===== $titulo =====" | Out-File $saida -Append -Encoding utf8
    try { & $cmd 2>&1 | Out-File $saida -Append -Encoding utf8 } catch { $_ | Out-File $saida -Append -Encoding utf8 }
}

"Diagnóstico AutoSUS - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $saida -Encoding utf8
Bloco 'Windows (host)' { (Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture | Format-List | Out-String).Trim() }
Bloco 'Python no host' { where.exe python; python --version; & 'C:\AutoSUS\.venv\Scripts\python.exe' --version }
Bloco 'VBoxManage' { "caminho: $vbm"; & $vbm --version }
Bloco 'VMs cadastradas' { & $vbm list vms }
Bloco 'VMs ligadas' { & $vbm list runningvms }

$vms = & $vbm list vms | ForEach-Object { if ($_ -match '^"(.+)" \{(.+)\}$') { $Matches[1] } }
foreach ($vm in $vms) {
    Bloco "showvminfo: $vm" {
        & $vbm showvminfo "$vm" --machinereadable | Select-String -Pattern '^(name|ostype|memory|cpus|VMState|VRAM|graphicscontroller|clipboard|draganddrop|SharedFolder|CurrentSnapshot|SnapshotName|GuestAdditions|GuestOSType|vrde|nic1|natnet1)' | ForEach-Object { $_.Line }
    }
    Bloco "guestproperty (VM ligada): $vm" {
        & $vbm guestproperty enumerate "$vm" | Select-String -Pattern 'OS/|LoggedIn|GuestAdd|Net/0/V4/IP|Resolution|VideoMode' | ForEach-Object { $_.Line }
    }
}
Bloco 'Pastas do AutoSUS' { Get-ChildItem 'C:\AutoSUS' | Select-Object Mode, Name | Format-Table -AutoSize | Out-String }
"`nFim." | Out-File $saida -Append -Encoding utf8
Write-Host "Resultado gravado em $saida"
