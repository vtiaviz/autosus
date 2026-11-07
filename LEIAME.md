# AutoSUS

Automação do faturamento de AIH do hospital, em dois aplicativos:

| Pasta | O que é |
| --- | --- |
| `autosus\downloads\` | Downloader diário dos arquivos e programas do DATASUS, CNES e WebAIH (Python). Veja o `LEIAME.md` dessa pasta. Mais tarde, `autosus\web` (Next.js) e `autosus\api` (NestJS) ficam ao lado dele. |
| `server_sus\` | Robô de processamento: liga a VM "AIH" pelo VBoxManage e opera SISAIH01, FPO, SIHD2 e Transmissor pelo agente que roda dentro da VM. Veja `server_sus\LEIAME_robo.md`. |
| `ferramentas\converte_webAIH\` | Conversor do CSV do WebAIH para o layout de importação do SISAIH01. |

O ambiente Python fica em `C:\AutoSUS\.venv` e é compartilhado pelos dois. Para criar:
`autosus\downloads\instalar.bat`.

Credenciais ficam separadas: `autosus\downloads\.env` (CNES, WebAIH, Gmail) e `server_sus\.env`
(SISAIH01, SIHD, FPO e secretário para o Transmissor). Nenhum `.env` vai para o git.
