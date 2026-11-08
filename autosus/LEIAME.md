# AutoSUS (app cliente)

App web com login para acompanhar as atualizações do DATASUS e o processamento das AIHs do hospital.
Usa a mesma stack do H-SUS: **Next.js** (`web\`), **NestJS** (`api\`), **PostgreSQL** e login com **JWT**,
e o visual do Prototipo H-SUS.

| Pasta | O que é |
| --- | --- |
| `api\` | API NestJS + Prisma (porta 3001, só 127.0.0.1) |
| `web\` | Site Next.js (http://localhost:3000); repassa `/api/*` para a API |
| `downloads\` | Downloader Python (arquivos e programas do DATASUS, CNES e WebAIH) |

## Primeira vez

1. PostgreSQL 16 instalado como serviço (`postgresql-x64-16`), com o banco `autosus` e o usuário `autosus`.
2. `api\.env`: copie de `api\.env.example` e preencha `DATABASE_URL`, `JWT_SEGREDO`, `ADMIN_EMAIL` e
   `ADMIN_SENHA`. O administrador é criado na primeira subida, quando o banco não tem usuários.
3. Rode `preparar.bat` (dependências, migrações do banco e compilação).
4. Rode `iniciar.bat`: abre a API, o site e o navegador em http://localhost:3000.

## Telas

- **Dashboard**: competência aberta com abertura e fechamento, itens pendentes, atualizações por
  competência, cronograma das próximas competências e a situação de SISAIH01, FPO, SIHD2 e Transmissor.
- **Atualizações**: arquivos (DSIHD017, FORNEC, IMPORT, TERCEIROS, TXTPROC, produção do WebAIH) e programas
  (SISAIH01, SIHD2, FPO, Transmissor, BDSIA) da competência escolhida. **Verificar agora** roda o
  downloader e mostra a saída dele.
- **Processamento AIH**: situação do Server_SUS (VM, agente, espaço no disco da VM), botões **Ligar servidor**,
  **Atualizar sistemas**, **SISAIH01**, **FPO**, **SIHD2**, **Testar conexão**, **Transmitir** e
  **Processar tudo**; o processamento em andamento com cada passo, o log do robô, os prints e o botão
  **Cancelar**; os arquivos no servidor (**Enviar downloads**), os arquivos gerados e o histórico.

### Envio pelo Transmissor

- **Manual** (padrão): o SIHD2 libera as AIHs bloqueadas e para no .DTS. O envio só acontece pelo botão
  **Transmitir**, que pede para digitar a competência (MM/AAAA) como confirmação.
- **Automático**: o SIHD2 roda parando nas AIHs bloqueadas (críticas). Se terminar sem nenhuma, o mesmo
  processamento transmite o .DTS. Se houver crítica, nada é enviado, o processamento fica "Com críticas" e
  chega um aviso por e-mail dizendo que o envio passou para manual.
- Todo processamento que termina (concluído, com críticas, falhou ou cancelado) manda um aviso pelo Windows
  e por e-mail, com a mesma configuração do downloader (`downloads\config.yaml` e `downloads\.env`).
- Só um processamento roda por vez. O SIHD2 leva de 4 a 5 horas.

## Como as peças conversam

- **Competências**: a API lê o [cronograma do CNES](https://wiki.saude.gov.br/cnes/index.php/Cronograma)
  na primeira subida e toda segunda-feira às 7h (`POST /api/competencias/sincronizar` força a leitura).
  Abertura = "Disponibilização dos aplicativos de processamento"; fechamento = "Envio da remessa do SIA/SIH".
- **Atualizações**: a cada execução, o downloader grava `downloads\estado\AAAAMM.json`. A API importa esse
  arquivo a cada 5 minutos e sempre que a tela pede. Por isso a tela mostra também o que a tarefa agendada
  do Windows baixou. Com `ATUALIZACOES_AGENDA` no `.env` (ex.: `0 10 * * *`), a própria API passa a
  agendar o downloader; nesse caso, remova a tarefa do Windows (`downloads\agendar.bat remover`).

## Rotas da API (todas exigem login, menos `auth/entrar` e `auth/sair`)

```
POST /api/auth/entrar          {email, senha} -> cookie de sessão (8 h)
POST /api/auth/sair
GET  /api/auth/eu
GET  /api/competencias         com situação (aguardando, aberta, encerrada) e contagem de itens
GET  /api/competencias/:aaaamm
POST /api/competencias/sincronizar
GET  /api/atualizacoes/:aaaamm arquivos, programas e a última verificação
POST /api/atualizacoes/:aaaamm/verificar   roda o downloader (um por vez)
GET  /api/processamento/servidor            VM e agente do Server_SUS
POST /api/processamento/servidor/ligar
GET  /api/processamento/:aaaamm             sistemas, processamentos, arquivos no servidor e gerados
GET  /api/processamento/:aaaamm/resumo      situação de cada sistema (Dashboard)
POST /api/processamento/:aaaamm/arquivos    envia ao Server_SUS os arquivos baixados (SHA-256 conferido)
POST /api/processamento/:aaaamm             {etapas, modoEnvio}: iniciar, atualizar, sisaih01, fpo, sihd, transmissor_testar
POST /api/processamento/:aaaamm/transmitir  {confirmacao: "MM/AAAA"}: envio real do .DTS
GET  /api/processamento/jobs/:id/log?desde=N
GET  /api/processamento/jobs/:id/imagens/:nome
POST /api/processamento/jobs/:id/cancelar
```

O AutoSUS fala com o Server_SUS pela API dele (`SERVER_SUS_URL` e `SERVER_SUS_TOKEN` no `api\.env`, o mesmo
token do `server_sus\.env`). O navegador nunca recebe esse token.

## Testes

```
cd api
npx jest
```
