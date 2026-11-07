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

Senhas dos programas ficam no `C:\AutoSUS\server_sus\.env` (SISAIH01_USUARIO, SISAIH01_SENHA, ...).
Sem elas, o robô usa o padrão do DATASUS (mestre/mestre).
