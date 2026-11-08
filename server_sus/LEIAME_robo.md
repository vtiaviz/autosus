# AutoSUS - robô de processamento (VM "AIH")

O robô opera os programas do DATASUS dentro da VM. Ele tem duas partes:

- **robo.bat** (no host): liga a VM, tira snapshots, copia arquivos para a pasta compartilhada,
  envia tarefas e mostra o resultado. Logs e prints ficam em `processamento\logs\`.
- **agente** (dentro da VM): inicia sozinho no login, recebe as tarefas pela pasta compartilhada
  (`\\VBOXSVR\AIH\_robo`) e executa. Ele só executa tarefas conhecidas.

## Primeira vez

1. No host: `robo.bat preparar` (copia o agente para a pasta compartilhada).
2. Ligue a VM e, dentro dela, rode `\\VBOXSVR\AIH\_robo\agente\instalar_agente.bat`.
3. No host: `robo.bat ping` (deve mostrar a versão do Python e o usuário da VM).

## Comandos

```
robo.bat status                 estado da VM, snapshots e agente
robo.bat iniciar                liga a VM e espera o agente
robo.bat ping                   testa o agente
robo.bat snapshot [nome]        snapshot da VM (padrão antes_AAAAMMDD_HHMM)
robo.bat instalar SISAIH01      instala sem telas a maior versão baixada pelo AutoSUS
robo.bat instalar SIHD2
robo.bat resolucao [1366x768]   fixa a resolução da VM (também é aplicada no "iniciar")
robo.bat pacotes                baixa o pywinauto no host e instala na VM (a VM não tem internet)
robo.bat inspecionar [titulo]   grava os controles das janelas abertas na VM em logs\inspecao_*.txt
robo.bat sisaih01 abrir         abre o SISAIH01, faz login e grava a inspeção das telas
robo.bat print                  print da tela da VM
robo.bat desligar               desliga a VM (ACPI)
```

Para atualizar o agente depois de uma mudança: `robo.bat preparar` (copia e reinicia o agente).

## API (usada pelo AutoSUS)

`api.bat` sobe a API em `http://127.0.0.1:8765` (documentação interativa em `/docs`). Toda rota,
menos `/saude`, exige `Authorization: Bearer <SERVER_SUS_TOKEN>` (token no `.env`).

```
GET  /saude              API no ar (sem token)
GET  /vm                 estado, memória, espaço no host, snapshots, versões instaladas
POST /vm/ligar           liga ou retoma a VM e volta na hora; acompanhe GET /agente
POST /vm/desligar        desligamento normal (ACPI)
GET  /vm/snapshots       lista de snapshots com as versões de cada um
POST /vm/snapshots       cria snapshot {"nome": "...", "descricao": "..."}
GET  /vm/print           print da tela da VM (PNG)
GET  /agente             último sinal do agente e tarefas na fila
POST /agente/ping        pede um ping ao agente (até 60 s)

GET  /competencias/{AAAAMM}/arquivos   o que a competência precisa e o que já chegou (null = falta)
POST /competencias/{AAAAMM}/arquivos   envia um arquivo (multipart: arquivo, sha256 opcional)
GET  /competencias/{AAAAMM}/saidas     arquivos gerados em saida\<apresentação> com SHA-256

POST /jobs               novo processamento (veja abaixo)
GET  /jobs               últimos jobs
GET  /jobs/{id}          situação, passo atual, progresso do agente e conferência das saídas
GET  /jobs/{id}/log?desde=N   saída do robô a partir do byte N (devolve "proximo")
GET  /jobs/{id}/imagens/{nome}  prints que o robô guardou durante o job (citados no log)
POST /jobs/{id}/cancelar      tira da fila ou para o job em andamento
```

### Arquivos

O envio aceita só os nomes conhecidos (instaladores, DSIHD017, FORNEC, IMPORT, TERCEIROS, TXTPROC,
BDSIA e a produção `AAAAMM_SISAIH01_<CNES>.txt`) e guarda na mesma pasta que o robô já usa
(`pasta_destino` do downloader): `programas\`, `AAAA-MM\SIH\` ou `AAAA-MM\SIA\`. Se o arquivo já
existe igual, nada muda (`ja_existe`); se é diferente, o anterior fica com `_anterior_<data>` no nome.

### Jobs

Um job é uma lista de etapas, executadas uma por vez, cada uma pelo próprio `robo.py`:

| Etapa | Comandos do robô |
| --- | --- |
| `iniciar` | `iniciar`, `preparar` |
| `atualizar` | `instalar` (maior versão baixada de cada programa) |
| `sisaih01` | `sisaih01 completo <apresentação> --confirmar` |
| `fpo` | `fpo completo <competência>` |
| `sihd` | `sihd completo <competência> --confirmar --auto` (ou `--manual` com `"sihd_manual": true`) |
| `transmissor_testar` | `transmissor preparar <competência>`, `transmissor testar` (não transmite) |
| `transmissor_enviar` | `transmissor preparar <competência>`, `transmissor enviar --confirmar` — **transmite de verdade**; só aceita com `"confirmar_envio": true` no pedido |
| `restaurar:<snapshot>` | `restaurar <snapshot> --confirmar`, `iniciar`, `preparar` |

Exemplo (o mesmo roteiro do `teste_completo.ps1`):

```json
{"competencia": "202608",
 "etapas": ["restaurar:antes_sihd_202608", "sisaih01", "fpo", "sihd",
            "restaurar:com_transmissor_teste", "transmissor_testar"],
 "versao_sihd": 2340, "sem_snapshot": true}
```

Situações: `na_fila`, `executando`, `concluido`, `falhou`, `aguardando_decisao` (SIHD em modo manual
com AIHs bloqueadas), `cancelado` e `interrompido` (a API foi fechada no meio). No fim, o job confere
se cada etapa gerou sua saída depois do início dele (`.Zip` do SISAIH01, `.VTP` do FPO, `.DTS` e
resumo do SIHD). Cada job fica em `server_sus\jobs\<id>\` (`job.json` e `saida.log`).

### Testes

```
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m pytest
```
Os testes automáticos não usam a VM.

O código comum ao `robo.py` e à API (VirtualBox, fila do agente, configuração e estado) fica em `nucleo\`.

Senhas dos programas ficam no `C:\AutoSUS\server_sus\.env` (SISAIH01_USUARIO, SISAIH01_SENHA, ...).
Sem elas, o robô usa o padrão do DATASUS (mestre/mestre).
