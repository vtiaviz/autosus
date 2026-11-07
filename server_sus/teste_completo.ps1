<#
  Teste completo do robô: arquivos já baixados (AutoSUS + WebAIH) -> SISAIH01 -> FPO -> SIHD -> Transmissor (só Testar Conexão).
  Padrão: competência 08/2026, apresentação 09/2026, SISAIH01 2520, SIHD2 2340.

  Uso (pela pasta C:\AutoSUS\processamento):
    .\teste_completo.bat                              tudo, AIHs bloqueadas liberadas automaticamente (--auto)
    .\teste_completo.bat -Manual                      para nas AIHs bloqueadas para você decidir
    .\teste_completo.bat -APartirDe sihd              retoma a partir de uma etapa
                                                      (preparacao, arquivos, sisaih01, fpo, sihd, transmissor, conferencia)
    .\teste_completo.bat -APartirDe sihd -SihdAPartirDe bloqueadas   retoma o SIHD numa etapa interna
    .\teste_completo.bat -Pasta "C:\Users\vtiav\Desktop\AIH\Produção 08-2026"   arquivos de entrada de outra pasta
    .\teste_completo.bat -Baixar                      roda o AutoSUS antes (por padrão NÃO baixa nada: o
                                                      processamento usa os arquivos que já estão na pasta e só
                                                      confere se estão todos lá)

  Nunca transmite: a última etapa só clica em Testar Conexão.
#>
param(
    [ValidateSet("preparacao", "arquivos", "downloads", "sisaih01", "fpo", "sihd", "transmissor", "conferencia")]
    [string]$APartirDe = "preparacao",
    [string]$SihdAPartirDe = "",
    [switch]$Manual,
    [switch]$Baixar,
    [string]$Pasta = "",
    [string]$Competencia = "08/2026",
    [string]$VersaoSisaih01 = "2520",
    [string]$VersaoSihd = "2340",
    [string]$SnapshotInicio = "antes_sihd_202608",
    [string]$SnapshotTransmissor = "com_transmissor_teste"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Raiz = $PSScriptRoot
Set-Location $Raiz

$mes, $ano = $Competencia.Split("/")
$comp = "$ano$mes"                                                   # 202608
$apresData = (Get-Date -Year ([int]$ano) -Month ([int]$mes) -Day 1).AddMonths(1)
$apres = $apresData.ToString("yyyyMM")                               # 202609
$apresTxt = $apresData.ToString("MM/yyyy")                           # 09/2026
$saida = Join-Path $Raiz "saida\$apres"

New-Item -ItemType Directory -Force (Join-Path $Raiz "logs") | Out-Null
$logTeste = Join-Path $Raiz ("logs\teste_completo_{0:yyyyMMdd_HHmm}.log" -f (Get-Date))
Start-Transcript -Path $logTeste | Out-Null
$inicio = Get-Date

$tempos = [ordered]@{}
function Titulo($texto) {
    if ($texto -match '^(\d)\. ') { $script:tempos[$texto] = Get-Date }
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Cyan
    Write-Host ("  {0:HH:mm:ss}  {1}" -f (Get-Date), $texto) -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor Cyan
}

function Parar($texto, $retomar) {
    Write-Host ""
    Write-Host "*** TESTE PAROU: $texto" -ForegroundColor Red
    if ($retomar) { Write-Host "    Depois de resolver, continue com: .\teste_completo.bat $retomar" -ForegroundColor Yellow }
    Write-Host "    Log deste teste: $logTeste"
    Stop-Transcript | Out-Null
    exit 1
}

function Robo([string]$etapa, [string[]]$argumentos) {
    Write-Host "> robo.bat $($argumentos -join ' ')" -ForegroundColor DarkGray
    & (Join-Path $Raiz "robo.bat") @argumentos
    $cod = $LASTEXITCODE
    if ($cod -ne 0) {
        $retomar = "-APartirDe $etapa$sufixo"
        Parar "robo.bat $($argumentos[0..1] -join ' ') terminou com código $cod" $retomar
    }
}

function Snapshots() {
    $estado = Get-Content (Join-Path $Raiz "estado_vm.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($estado.snapshots) { return @($estado.snapshots.PSObject.Properties.Name) } else { return @() }
}

$livreC = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
if ($livreC -lt 2) { Parar "só $livreC GB livres no C: (o teste precisa de pelo menos 2 GB)" $null }
if ($livreC -lt 5) { Write-Host "ATENÇÃO: só $livreC GB livres no C:" -ForegroundColor Yellow }

if ($APartirDe -eq "downloads") { $APartirDe = "arquivos" }
$etapas = "preparacao", "arquivos", "sisaih01", "fpo", "sihd", "transmissor", "conferencia"
$rodar = $etapas[[array]::IndexOf($etapas, $APartirDe)..($etapas.Count - 1)]
$pastaArg = @(); if ($Pasta) { $pastaArg = @("--pasta", $Pasta) }
$sufixo = ""
if ($Manual) { $sufixo += " -Manual" }
if ($Pasta) { $sufixo += ' -Pasta "' + $Pasta + '"' }

Titulo "TESTE COMPLETO - competência $Competencia, apresentação $apresTxt | AIHs bloqueadas: $(if ($Manual) {'MANUAL'} else {'AUTOMÁTICA'}) | etapas: $($rodar -join ', ')"

# ---------------------------------------------------------------- 0. preparação
if ($rodar -contains "preparacao") {
    Titulo "0. Preparação da VM"
    if (-not ((Snapshots) -contains $SnapshotInicio)) {
        Parar "o snapshot '$SnapshotInicio' (ponto de partida do teste) não existe. Veja: .\robo.bat snapshots" $null
    }
    Robo "preparacao" @("iniciar")
    Robo "preparacao" @("snapshots")
    if ((Snapshots) -contains $SnapshotTransmissor) {
        Write-Host "Snapshot '$SnapshotTransmissor' já existe (VM com Java + Transmissor): mantido."
    } else {
        Write-Host "Guardando o estado atual da VM (com Java + Transmissor) em '$SnapshotTransmissor'..."
        Robo "preparacao" @("snapshot", $SnapshotTransmissor)
    }
    if (Test-Path $saida) {
        $destino = "{0}_antes_teste_{1:yyyyMMdd_HHmm}" -f $saida, (Get-Date)
        Move-Item $saida $destino
        Write-Host "Saídas anteriores movidas para $destino"
    }
    New-Item -ItemType Directory -Force $saida | Out-Null
    Robo "preparacao" @("restaurar", $SnapshotInicio, "--confirmar")
    Robo "preparacao" @("iniciar")
    Robo "preparacao" @("preparar")
}

# ---------------------------------------------------------------- 1. arquivos de entrada
if ($rodar -contains "arquivos") {
    Titulo "1. Arquivos de entrada da competência $comp (já baixados)"
    $downloads = Join-Path ([Environment]::GetFolderPath("Desktop")) "AutoSUS_Downloads"
    if ($Baixar) {
        # só com -Baixar: o processamento normalmente começa com tudo já baixado
        Push-Location (Join-Path (Split-Path $Raiz -Parent) "autosus\downloads")
        & .\autosus.bat $comp --versao "SISAIH01=$VersaoSisaih01" --versao "SIHD2=$VersaoSihd"
        & .\autosus.bat $comp
        Pop-Location
    }
    $pastas = @(Join-Path $downloads "$ano-$mes") + $(if ($Pasta) { @($Pasta) } else { @() })
    $necessarios = [ordered]@{
        "Produção do WebAIH"      = "${apres}_SISAIH01*.txt"
        "DSIHD (SIHD)"            = "DSIHD*_$comp.zip"
        "Fornecedores (CNES)"     = "FORNEC_$comp.zip"
        "Importadores (CNES)"     = "IMPORT_$comp.zip"
        "Terceiros Brasil (CNES)" = "TERCEIROSBRASIL*_$comp.zip"
        "TXTPROC (portal CNES)"   = "TXTPROC_*_$comp.zip"
        "BDSIA (SIA)"             = "BDSIA$comp*.exe"
    }
    $faltando = @()
    foreach ($item in $necessarios.GetEnumerator()) {
        $achado = $pastas | Where-Object { Test-Path $_ } |
            ForEach-Object { Get-ChildItem $_ -Recurse -File -ErrorAction SilentlyContinue } |
            Where-Object { $_.Name -like $item.Value } |
            Sort-Object LastWriteTime | Select-Object -Last 1
        if ($achado) { Write-Host ("  ok  {0,-25} {1} ({2:N0} bytes)" -f $item.Key, $achado.Name, $achado.Length) }
        else { Write-Host ("  FALTA {0,-23} {1}" -f $item.Key, $item.Value) -ForegroundColor Red; $faltando += $item.Key }
    }
    $instSihd = Join-Path $downloads "programas\SIHD2_$VersaoSihd.exe"
    if (Test-Path $instSihd) { Write-Host ("  ok  {0,-25} {1}" -f "Instalador do SIHD2", (Split-Path $instSihd -Leaf)) }
    elseif (-not $Pasta) { Write-Host "  FALTA Instalador do SIHD2    SIHD2_$VersaoSihd.exe" -ForegroundColor Red; $faltando += "instalador SIHD2 $VersaoSihd" }
    if ($faltando) {
        Parar "faltam arquivos de entrada ($($faltando -join ', ')). Baixe com o AutoSUS e continue" "-APartirDe arquivos$sufixo"
    }
}

# ---------------------------------------------------------------- 2. SISAIH01
if ($rodar -contains "sisaih01") {
    Titulo "2. SISAIH01 (apresentação $apresTxt)"
    Robo "sisaih01" @("sisaih01", "completo", $apresTxt, "--confirmar", "--sem-snapshot")
}

# ---------------------------------------------------------------- 3. FPO
if ($rodar -contains "fpo") {
    Titulo "3. FPO (competência $Competencia)"
    Robo "fpo" (@("fpo", "completo", $Competencia, "--sem-snapshot") + $pastaArg)
}

# ---------------------------------------------------------------- 4. SIHD
if ($rodar -contains "sihd") {
    Titulo "4. SIHD (competência $Competencia) - leva de 4 a 5 horas"
    $sihd = @("sihd", "completo", $Competencia, "--versao", $VersaoSihd, "--confirmar", "--sem-snapshot") + $pastaArg
    $sihd += $(if ($Manual) { "--manual" } else { "--auto" })
    if ($SihdAPartirDe) { $sihd += @("--a-partir-de", $SihdAPartirDe) }
    Write-Host "> robo.bat $($sihd -join ' ')" -ForegroundColor DarkGray
    & (Join-Path $Raiz "robo.bat") @sihd
    $cod = $LASTEXITCODE
    if ($cod -eq 3 -and $Manual) {
        Parar "AIHs bloqueadas aguardando sua decisão. Libere as aprovadas com: .\robo.bat sihd liberar <AIH> ... --confirmar" `
              "-APartirDe sihd -SihdAPartirDe bloqueadas$sufixo"
    }
    if ($cod -ne 0) {
        Parar "o SIHD parou (código $cod). Veja acima a etapa em que parou" `
              "-APartirDe sihd -SihdAPartirDe <etapa indicada acima>$sufixo"
    }
}

# ---------------------------------------------------------------- 5. Transmissor (só teste de conexão)
if ($rodar -contains "transmissor") {
    Titulo "5. Transmissor - preparar e Testar Conexão (NÃO transmite)"
    if (-not (Get-ChildItem $saida -Filter "*$comp.DTS" -ErrorAction SilentlyContinue)) {
        Parar "não há .DTS em $saida (o SIHD não encerrou)" "-APartirDe sihd -SihdAPartirDe encerrar"
    }
    if (-not ((Snapshots) -contains $SnapshotTransmissor)) {
        Parar "o snapshot '$SnapshotTransmissor' (VM com Transmissor) não existe" $null
    }
    Robo "transmissor" @("restaurar", $SnapshotTransmissor, "--confirmar")
    Robo "transmissor" @("iniciar")
    Robo "transmissor" @("preparar")
    Robo "transmissor" @("transmissor", "preparar", $Competencia)
    Robo "transmissor" @("transmissor", "testar")
    Robo "transmissor" @("rede", "status")
}

# ---------------------------------------------------------------- conferência
Titulo "Conferência dos arquivos gerados em $saida"
$marca = Join-Path $saida ".inicio_teste"
$inicioTeste = if (Test-Path $marca) { (Get-Item $marca -Force).LastWriteTime } else { $inicio }
Write-Host ("Início do teste: {0:dd/MM HH:mm}" -f $inicioTeste)
$esperados = @("${apres}AIH*.Zip", "Valores_$comp.VTP", "*$comp.DTS", "SIH$($comp.Substring(2)).txt")
$faltou = $false
foreach ($padrao in $esperados) {
    $f = Get-ChildItem $saida -Filter $padrao -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($f) {
        $novo = $f.LastWriteTime -ge $inicioTeste
        Write-Host ("  {0,-30} {1,14:N0} bytes  {2:dd/MM HH:mm}  {3}" -f $f.Name, $f.Length, $f.LastWriteTime,
                    $(if ($novo) { "gerado neste teste" } else { "ANTIGO (não gerado nesta execução)" }))
    } else {
        Write-Host "  FALTOU: $padrao" -ForegroundColor Red
        $faltou = $true
    }
}
$resumo = Get-ChildItem $saida -Filter "SIH$($comp.Substring(2)).txt" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($resumo) {
    Write-Host ""
    Write-Host "  Resumo do SIHD ($($resumo.Name)):"
    Get-Content $resumo.FullName -TotalCount 3 | ForEach-Object { Write-Host "    $_" }
}
if ($tempos.Count) {
    Write-Host ""
    Write-Host "  Tempo por etapa (nesta execução):"
    $nomes = @($tempos.Keys); $marcas = @($tempos.Values) + @(Get-Date)
    for ($i = 0; $i -lt $nomes.Count; $i++) {
        Write-Host ("    {0,-62} {1:hh\:mm}" -f $nomes[$i], ($marcas[$i + 1] - $marcas[$i]))
    }
}
$prints = Get-ChildItem (Join-Path $Raiz "logs") -Filter "transmissor_testar_msg*.png" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $inicioTeste }
if ($prints) { Write-Host ""; Write-Host "  Resultado do Testar Conexão: confira $(($prints | ForEach-Object FullName) -join ', ')" }
$duracao = (Get-Date) - $inicio
Write-Host ""
if ($faltou) {
    Write-Host ("TESTE TERMINOU COM FALTAS em {0:hh\:mm} h. Log: {1}" -f $duracao, $logTeste) -ForegroundColor Yellow
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host ("TESTE CONCLUÍDO em {0:hh\:mm} h. Log: {1}" -f $duracao, $logTeste) -ForegroundColor Green
Write-Host "A VM ficou no estado '$SnapshotTransmissor' + teste de conexão (rede desligada). Nada foi transmitido."
Stop-Transcript | Out-Null
exit 0
