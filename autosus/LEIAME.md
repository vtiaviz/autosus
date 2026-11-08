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
  competência, cronograma das próximas competências. Os processamentos chegam na etapa 5.
- **Atualizações**: arquivos (DSIHD017, FORNEC, IMPORT, TERCEIROS, TXTPROC, produção do WebAIH) e programas
  (SISAIH01, SIHD2, FPO, Transmissor, BDSIA) da competência escolhida. **Verificar agora** roda o
  downloader e mostra a saída dele.
- **Processamento AIH**: só a lista dos passos por enquanto (etapa 5).

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
```

## Testes

```
cd api
npx jest
```
