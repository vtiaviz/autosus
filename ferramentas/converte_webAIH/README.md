# Gerador do arquivo SISAIH01 (Importar → Produção)

Módulo Python sem dependências para ler, gerar e validar o arquivo texto do SISAIH01:
registros de **1800 posições**, um por AIH, terminados em **CR+LF**, em ASCII.

## Arquivos

| Arquivo | Para quê |
|---|---|
| `sisaih01.py` | Layout (como dados), leitor, gerador e validador |
| `layout.md` | Tabela de posições gerada a partir do código (`python3 sisaih01.py layout`) |
| `teste_ida_volta.py` | Lê um arquivo e gera de novo; os bytes têm que sair idênticos |
| `exemplo_entrada.json` | Uma AIH **fictícia** no formato de entrada do gerador |

## Converter o CSV do sistema atual

```bash
python3 csv_para_sisaih01.py AIH_07-2026.csv config_hospital.json SAIDA_SISAIH01.txt
```

* `csv_para_sisaih01.py`: lê o CSV (sem cabeçalho, `;`, 24 colunas; a ordem está em
  `COLUNAS` no início do script) e grava o arquivo de 1800 posições.
* `config_hospital.json`: guarda os dados que não estão no CSV. São eles: competência de
  apresentação, CNES, município, órgão emissor, CNS do autorizador, telefone padrão e
  `especialidade_fixa` (vazio = usa a coluna 18 do CSV), `media_permanencia_sigtap`
  (média de dias de cada procedimento no SIGTAP, para avisar quando a permanência for
  menor que a metade) e `preencher_liberacao_permanencia` (se `true`, grava a solicitação
  de liberação de permanência a menor do mesmo jeito que o SISAIH01: "7" na posição 499).
  **Troque `apresentacao` a cada mês.**
* Colunas opcionais 25 a 30: `25` CIDs secundários (`X20:1,E119:2`, isto é, CID[:classificação]),
  `26` nascidos vivos, `27` nascidos mortos, `28` saídas por alta, `29` por transferência e
  `30` por óbito (dados do parto). Podem faltar ou vir vazias.
* SIGTAP: informe em `"sigtap"` o caminho do zip mensal da Tabela Unificada (pode ser a pasta
  descompactada). O conversor usa as médias de permanência, a compatibilidade CID x procedimento
  e os CIDs secundários vinculados. Use sempre a tabela da competência das AIHs.
  `media_permanencia_sigtap` só é necessário para sobrescrever algum valor.
* CID secundário obrigatório: CID principal de lesão (S00–T98) exige causa externa (V01–Y98) no
  1º CID secundário. Essa regra vem da Portaria SAS/MS 1.324/2014 e não está no SIGTAP. Ela e as
  regras do SIGTAP estão listadas em `cids_com_secundario_obrigatorio.csv`.
* Complementos: quando o sistema de origem não exporta o CID secundário, crie um CSV
  `numero_aih;cns_paciente;cids_secundarios` (veja `complementos_202609.csv`) e passe
  `--complementos=arquivo.csv`. A AIH e o CNS precisam bater com o CSV principal.
* Parto: se as colunas 26 a 30 vierem vazias, entram os valores de `parto_padrao`
  (1 nascido vivo, 0 mortos, 1 alta, 0 transferência, 0 óbito). Se o motivo de saída não for
  obstétrico (6x), ele é trocado por `motivo_saida_parto_padrao` (61). As duas trocas
  aparecem como aviso. Para desligar, deixe esses campos vazios no config.
* Dígito verificador da AIH: resto da divisão dos 12 primeiros dígitos por 11 (resto 10 vira 0).
  Com `corrigir_dv_aih: true`, o conversor recalcula o DV e grava a lista de/para em
  `SAIDA.txt.correcoes_aih.csv`. Com `false`, AIH com DV errado é tratada como erro.
* O script para e não grava nada se houver erro (data inválida, CNS com dígito errado,
  AIH repetida, campo maior que o permitido etc.).
* Ele também mostra **avisos** do que o SISAIH01 vai criticar: trauma (CID S/T) sem causa
  externa, parto sem os dados do parto e permanência menor que a metade da média do SIGTAP.

Regras de conversão, conferidas contra o arquivo exportado pelo SISAIH01:

| Origem no CSV | Vai para o SISAIH01 |
|---|---|
| sexo 1/3 | M/F |
| datas AAAA-MM-DD | AAAAMMDD; data de emissão = data de internação |
| município com 7 dígitos | 6 dígitos (sem DV); UF tirada do código IBGE |
| CEP / telefone com máscara | só dígitos; sem telefone → `telefone_padrao` |
| procedimento | solicitado = realizado; 1 linha de procedimento, qtd 1, competência = mês da internação |
| CNS do médico (col. 22) | solicitante, responsável, diretor clínico e executante; sem CNS usa o CPF (col. 21) |

## Uso

```bash
python3 sisaih01.py ler     202608_SISAIH01_2312166.txt > aihs.json   # arquivo -> JSON
python3 sisaih01.py gerar   aihs.json > NOVO.txt                       # JSON -> arquivo
python3 sisaih01.py validar NOVO.txt                                   # pré-críticas
python3 teste_ida_volta.py  202608_SISAIH01_2312166.txt                # regressão
```

Para integrar ao seu sistema, monte uma lista de dicionários com os nomes de campo de
`layout.md` (veja `exemplo_entrada.json`) e chame `sisaih01.gerar_arquivo(aihs)`.
Campos não informados recebem o valor padrão: zeros, espaços ou o valor fixo observado.
O gerador remove acentos e passa texto para maiúsculas.

## O que já foi confirmado

* O arquivo real de 08/2026 (60 AIHs) passa no teste de ida e volta **byte a byte**.
* Todos os CNS (paciente e profissionais) nas posições mapeadas passam no dígito
  verificador, o que confirma essas posições.
* Layout conferido com o oficial da Portaria SAS nº 133/2012 (1600 posições). O atual tem
  1800: da posição 1486 em diante os campos estão 1 posição à frente, e foram acrescentados
  e-mail e diagnósticos secundários.
* Bloco de procedimentos: 10 ocorrências × 73 posições (664–1393), depois UTI neonatal
  (1394–1399) e acidente de trabalho (1400–1423).
* Diagnósticos secundários: 9 ocorrências × 5 posições (1591–1635).

## O que ainda precisa ser conferido

Só 3 campos ainda estão com confiança **baixa** em `layout.md`: 495–498, 500–501 e o
e-mail (1541–1590). Eles não existiam no layout de 2012. A posição 499 foi confirmada: é onde
o SISAIH01 grava a liberação de permanência a menor (7). Para fechar esses campos:

1. Pegue o layout oficial vigente ("Layout da interface texto do SISAIH01", página de
   manuais do SIHD/DATASUS) e compare com `layout.md`.
2. Ou digite no SISAIH01 AIHs de teste que preencham esses campos (endereço completo,
   parto, laqueadura, CID secundário, e-mail), exporte e rode `ler` para ver onde caem.
3. Teste de aceitação final: importar o arquivo gerado no SISAIH01 (Importar → Produção),
   rodar *Consistir produção* e *Apurar prévia* sem críticas.

A validação deste módulo é só uma pré-crítica (datas, sexo, CNS, duplicidade). Ela não
substitui as regras do SIGTAP (compatibilidade com CID, idade, sexo, permanência,
habilitação) aplicadas pelo SISAIH01/SIHD.
