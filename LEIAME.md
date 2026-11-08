# AutoSUS

Automação do faturamento de AIH do hospital, em dois aplicativos:

| Pasta | O que é |
| --- | --- |
| `autosus\` | App AutoSUS: `web\` (Next.js), `api\` (NestJS + PostgreSQL) e `downloads\` (downloader Python). Veja `autosus\LEIAME.md`. |
| `server_sus\` | Robô de processamento: liga a VM "AIH" pelo VBoxManage e opera SISAIH01, FPO, SIHD2 e Transmissor pelo agente que roda dentro da VM. Veja `server_sus\LEIAME_robo.md`. |
| `ferramentas\converte_webAIH\` | Conversor do CSV do WebAIH para o layout de importação do SISAIH01. |

O ambiente Python fica em `C:\AutoSUS\.venv` e é compartilhado pelos dois. Para criar:
`autosus\downloads\instalar.bat`.

Credenciais ficam separadas: `autosus\downloads\.env` (CNES, WebAIH, Gmail), `autosus\api\.env` (banco,
segredo do JWT, administrador) e `server_sus\.env` (SISAIH01, SIHD, FPO, secretário para o Transmissor
e o token da API do Server_SUS). Nenhum `.env` vai para o git.
