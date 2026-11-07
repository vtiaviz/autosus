# AutoSUS - download mensal SIH / SIA / CNES

Verifica e baixa todos os dias, às 10h, os arquivos da **competência do mês anterior**.
Quando os 11 itens estiverem completos, você recebe uma notificação do Windows e um e-mail.

| Item | Arquivo | Origem |
| --- | --- | --- |
| SISAIH01 | sisaih01_verXXXX.exe (maior versão) | ftp2.datasus.gov.br/public/sistemas/dsweb/SIHD/Programas |
| SIHD2 | SIHD2_XXXX.exe (maior versão) | mesma pasta |
| DSIHD017 | DSIHD017_15_AAAAMM[letra].ZIP | .../SIHD/Programas/DSIHD017 |
| FORNEC | FORNEC_AAAAMM[letra].ZIP | ftp.datasus.gov.br/cnes |
| IMPORT | IMPORT_AAAAMM[letra].ZIP | ftp.datasus.gov.br/cnes |
| TERCEIROS | TERCEIROSBRASIL15_AAAAMM[letra].ZIP | ftp.datasus.gov.br/cnes |
| BDSIA | BDSIAAAAAMM[letra].exe | arpoador.datasus.gov.br/siasus/sia |
| TXTPROC | TXTPROC_150175_AAAAMM.ZIP | portal do gestor CNES (login) |
| FPO | FPOMAG_Atualiza_XXXX.exe (maior versão) | arpoador.datasus.gov.br/siasus/fpo |
| TRANSMISSOR | TransmissorXXX.exe (maior versão) | página de downloads do Transmissor |
| WEBAIH | AAAAMM_SISAIH01_CNES.txt | WebAIH (Exportar SISAIH01, login) |

Quando há letra, sempre é baixada a mais alta (sem letra < a < b < c...). As versões anteriores são mantidas.

## 1. Instalação (uma vez)

1. Extraia esta pasta em um lugar fixo, por exemplo `C:\AutoSUS`.
2. Dê dois cliques em **instalar.bat**. Ele cria o ambiente Python, instala as bibliotecas e o navegador
   Chromium (cerca de 150 MB) e abre o `.env` no Bloco de Notas.
3. Preencha o `.env`:
   - `CNES_USUARIO`, `CNES_SENHA`, `CNES_CPF`: seu acesso ao portal do gestor do CNES.
   - `WEBAIH_USUARIO`, `WEBAIH_SENHA`: login do WebAIH (o mesmo usuário que cadastra os formulários).
   - `GMAIL_SENHA_APP`: gere em https://myaccount.google.com/apppasswords (exige verificação em duas
     etapas ativa na conta). Cole os 16 caracteres.

## 2. Teste

Abra o Prompt de Comando na pasta (clique na barra de endereço do Explorer, digite `cmd` e Enter):

```
autosus.bat --testar-aviso        (deve aparecer a notificação e chegar o e-mail)
autosus.bat --simular             (lista o que seria baixado, sem baixar)
autosus.bat                       (baixa de verdade)
```

## 3. Agendamento

Dê dois cliques em **agendar.bat**. A tarefa "AutoSUS - downloads mensais" roda todo dia às 10h, sem
abrir janela. Se o computador estiver desligado nesse horário, ela roda assim que ele for ligado.

- Outro horário: `agendar.bat 09:30`
- Remover: `agendar.bat remover`

## Onde ficam os arquivos

```
Área de Trabalho\AutoSUS_Downloads\
  2026-10\SIH\   DSIHD017, FORNEC, IMPORT, TERCEIROS, TXTPROC
  2026-10\SIA\   BDSIA
  2026-10\manifesto.json   (o que foi baixado, tamanho, hash SHA-256, data)
  programas\     sisaih01 e SIHD2 (todas as versões baixadas)
```

Logs diários ficam em `logs\` dentro da pasta do AutoSUS.

## Outros comandos

```
autosus.bat 202502                    competência específica
autosus.bat --somente FORNEC,TXTPROC  só alguns itens
autosus.bat --versao SISAIH01=2520    baixa uma versão antiga de um programa (para reprocessar
                                      uma competência com a versão da época); pode repetir o --versao
autosus.bat --mostrar-navegador       vê o navegador trabalhando no portal CNES
autosus.bat --diagnostico-cnes        lista os campos da tela de login do CNES
```

## Se algo der errado

- **TXTPROC com erro de login**: confira o `.env`. Se a tela do CNES mudou, rode
  `autosus.bat --diagnostico-cnes` e preencha `cnes_portal.seletores` no `config.yaml` com os nomes dos
  campos mostrados. Em cada falha, uma captura de tela (`cnes_*.png`) e o HTML são salvos em `logs\`.
- **FTP fora do ar**: o DATASUS cai com frequência. Cada arquivo tem 3 tentativas, e o que faltar é
  tentado de novo no dia seguinte.
- **Mudou uma pasta ou nome de arquivo no DATASUS**: ajuste `config.yaml` (pastas e padrões).
- **E-mail não chega**: rode `autosus.bat --testar-aviso` e veja a mensagem de erro no log.

## WebAIH

O arquivo da produção é baixado a cada execução pela opção "Exportar SISAIH01" do WebAIH, para a
apresentação = competência + 1 mês. Se a produção mudar (AIH corrigida ou incluída), a versão nova
substitui a anterior, que fica guardada com `_anterior_` no nome. Se o WebAIH apontar AIHs com erro,
o item fica PENDENTE e a página com a lista de erros é salva em `logs\webaih_*.html`: corrija no
WebAIH e o AutoSUS tenta de novo na próxima execução.

## Como funciona o aviso

- Competência completa (os 8 itens): uma notificação e um e-mail, uma única vez.
- Saiu uma letra nova (ex.: FORNEC_202610b) ou uma versão nova de programa depois disso: novo aviso.
- Se o e-mail falhar, o aviso é tentado de novo na próxima execução.
