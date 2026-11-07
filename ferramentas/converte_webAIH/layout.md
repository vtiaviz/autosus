| Início | Fim | Tam | Tipo | Campo | Descrição | Confiança |
|---|---|---|---|---|---|---|
| 1 | 8 | 8 | N | `lote` | Número do lote | alta |
| 9 | 11 | 3 | N | `qtd_aih_lote` | Quantidade de AIHs no lote (preencher com zeros) | alta |
| 12 | 17 | 6 | N | `apresentacao` | Ano/mês de apresentação (AAAAMM) | alta |
| 18 | 20 | 3 | N | `seq_aih_lote` | Sequencial da AIH no lote (preencher com zeros) | alta |
| 21 | 30 | 10 | A | `orgao_emissor` | Órgão emissor da AIH (ex.: M + IBGE + sufixo) | alta |
| 31 | 37 | 7 | N | `cnes` | CNES do hospital | alta |
| 38 | 43 | 6 | N | `municipio` | Município (IBGE, 6 dígitos) do hospital | alta |
| 44 | 56 | 13 | N | `numero_aih` | Número da AIH | alta |
| 57 | 58 | 2 | N | `identificacao` | Identificação: 01 principal, 03 continuação, 05 longa permanência | alta |
| 59 | 60 | 2 | N | `especialidade` | Especialidade do leito | alta |
| 61 | 105 | 45 | N | `filler_061` | Filler (zeros) | alta |
| 106 | 107 | 2 | N | `modalidade` | Modalidade: 02 hospitalar, 03 hospital-dia, 04 internação domiciliar | alta |
| 108 | 110 | 3 | N | `seq_aih5` | Sequencial da AIH 5 (longa permanência) | alta |
| 111 | 123 | 13 | N | `aih_proxima` | Número da AIH próxima (posterior) | alta |
| 124 | 136 | 13 | N | `aih_anterior` | Número da AIH anterior | alta |
| 137 | 144 | 8 | N | `dt_emissao` | Data de emissão (AAAAMMDD) | alta |
| 145 | 152 | 8 | N | `dt_internacao` | Data de internação (AAAAMMDD) | alta |
| 153 | 160 | 8 | N | `dt_saida` | Data de saída (AAAAMMDD) | alta |
| 161 | 170 | 10 | N | `proc_solicitado` | Procedimento solicitado (SIGTAP) | alta |
| 171 | 171 | 1 | N | `mudanca_proc` | Mudança de procedimento: 1 sim, 2 não | alta |
| 172 | 181 | 10 | N | `proc_realizado` | Procedimento realizado/principal (SIGTAP) | alta |
| 182 | 183 | 2 | N | `carater_internacao` | Caráter da internação (01 eletivo, 02 urgência...) | alta |
| 184 | 185 | 2 | N | `motivo_saida` | Motivo de saída/permanência (ex.: 12 alta melhorado) | alta |
| 186 | 186 | 1 | N | `solicitante_tipo_doc` | Profissional solicitante – tipo de documento (1 CPF, 2 CNS) | media |
| 187 | 201 | 15 | N | `solicitante_doc` | Profissional solicitante – documento | media |
| 202 | 202 | 1 | N | `responsavel_tipo_doc` | Profissional responsável – tipo de documento | media |
| 203 | 217 | 15 | N | `responsavel_doc` | Profissional responsável – documento | media |
| 218 | 218 | 1 | N | `diretor_tipo_doc` | Diretor clínico – tipo de documento | media |
| 219 | 233 | 15 | N | `diretor_doc` | Diretor clínico – documento | media |
| 234 | 234 | 1 | N | `autorizador_tipo_doc` | Autorizador (gestor) – tipo de documento | media |
| 235 | 249 | 15 | N | `autorizador_doc` | Autorizador (gestor) – documento | media |
| 250 | 253 | 4 | A | `cid_principal` | CID-10 principal (sem ponto; 3 caracteres + espaço se for categoria) | alta |
| 254 | 257 | 4 | A | `cid_secundario_legado` | DIAG_SEC – CID secundário (campo antigo; hoje usa-se o bloco 1591-1635) | media |
| 258 | 261 | 4 | A | `cid_causas_associadas` | DIAG_COMPL – CID de causas associadas | media |
| 262 | 265 | 4 | A | `cid_obito` | DIAG_OBITO – CID da causa do óbito | media |
| 266 | 268 | 3 | N | `cod_solicitacao_liberacao` | COD_SOL_LIB – 001 permanência a menor, 002 idade a menor, 003 idade a maior, 004 permanência e idade | media |
| 269 | 338 | 70 | A | `paciente_nome` | Nome do paciente | alta |
| 339 | 346 | 8 | N | `paciente_nascimento` | Data de nascimento (AAAAMMDD) | alta |
| 347 | 347 | 1 | A | `paciente_sexo` | Sexo: M ou F | alta |
| 348 | 349 | 2 | N | `paciente_raca_cor` | Raça/cor (01 branca, 02 preta, 03 parda, 04 amarela, 05 indígena, 99 sem informação) | alta |
| 350 | 419 | 70 | A | `paciente_nome_mae` | Nome da mãe | alta |
| 420 | 489 | 70 | A | `paciente_nome_responsavel` | Nome do responsável | alta |
| 490 | 490 | 1 | N | `paciente_tipo_doc` | TP_DOC_PAC – 1 PIS/PASEP, 2 RG, 3 certidão nasc., 4 CPF, 5 ignorado, 6 matrícula da certidão | media |
| 491 | 494 | 4 | N | `paciente_etnia` | ETNIA_INDIGENA – código da etnia; 0000 se raça/cor não for 05 | media |
| 495 | 498 | 4 | N | `desconhecido_495` | Filler em 2012; zeros em todos os exemplos | baixa |
| 499 | 499 | 1 | N | `liberacao_critica` | Liberação de crítica gravada pelo SISAIH01: 7 = permanência a menor liberada (confirmado: o SISAIH01 grava 7 aqui ao solicitar a liberação) | media |
| 500 | 501 | 2 | A | `desconhecido_500` | Filler em 2012; hoje usado ('NA' em todo o exemplo) | baixa |
| 502 | 516 | 15 | N | `paciente_cns` | CNS do paciente | alta |
| 517 | 519 | 3 | N | `paciente_nacionalidade` | Nacionalidade (010 Brasil) | alta |
| 520 | 522 | 3 | N | `end_tipo_logradouro` | Tipo de logradouro (tabela DNE: 081 rua, 008 avenida...) | alta |
| 523 | 572 | 50 | A | `end_logradouro` | Logradouro | alta |
| 573 | 579 | 7 | A | `end_numero` | Número | media |
| 580 | 594 | 15 | A | `end_complemento` | Complemento | media |
| 595 | 624 | 30 | A | `end_bairro` | Bairro (BAIRRO_PAC 595-624 no layout de 2012) | alta |
| 625 | 630 | 6 | N | `end_municipio` | Município de residência (IBGE) | alta |
| 631 | 632 | 2 | A | `end_uf` | UF de residência | alta |
| 633 | 640 | 8 | N | `end_cep` | CEP | alta |
| 641 | 655 | 15 | N | `paciente_prontuario` | Nº do prontuário (confirmado pela coluna 3 do CSV do sistema atual) | media |
| 656 | 659 | 4 | N | `enfermaria` | NU_ENFERMARIA – número da enfermaria | media |
| 660 | 663 | 4 | N | `leito` | NU_LEITO – número do leito | media |
| **664** | **1393** | 10×73 | | **procedimentos** | Bloco repetitivo (1ª ocorrência abaixo) | |
| 664 | 664 | 1 | N | `procedimentos[].prof_tipo_doc` | Profissional executante – tipo de documento (1 CPF, 2 CNS) | alta |
| 665 | 679 | 15 | N | `procedimentos[].prof_doc` | Profissional executante – documento | alta |
| 680 | 685 | 6 | A | `procedimentos[].cbo` | CBO do profissional | alta |
| 686 | 686 | 1 | N | `procedimentos[].ind_equipe` | IN_EQUIPE – indicador de equipe | alta |
| 687 | 687 | 1 | N | `procedimentos[].prestador_tipo_doc` | IN_SERVICO – tipo de documento do serviço (5 = CNES no exemplo) | alta |
| 688 | 701 | 14 | N | `procedimentos[].prestador_doc` | IDENT_SERVICO – documento do serviço (CNES com zeros à esquerda) | alta |
| 702 | 702 | 1 | N | `procedimentos[].executante_tipo_doc` | IN_EXECUTOR – tipo de documento do executor (5 = CNES) | alta |
| 703 | 717 | 15 | N | `procedimentos[].executante_doc` | IDENT_EXECUTOR – documento do executor (CNES com zeros à esquerda) | alta |
| 718 | 727 | 10 | N | `procedimentos[].procedimento` | Código do procedimento (SIGTAP) | alta |
| 728 | 730 | 3 | N | `procedimentos[].quantidade` | Quantidade | alta |
| 731 | 736 | 6 | N | `procedimentos[].competencia` | Competência de realização (AAAAMM) | alta |
| 1394 | 1394 | 1 | N | `utineo_saida` | SAÍDA_UTINEO – motivo de saída da UTI neonatal | media |
| 1395 | 1398 | 4 | N | `utineo_peso` | PESO_UTINEO – peso ao nascer (g) | media |
| 1399 | 1399 | 1 | N | `utineo_mes_gestacao` | MESGEST_UTINEO – mês de gestação | media |
| 1400 | 1413 | 14 | N | `cnpj_empregador` | CNPJ_EMPREG – acidente de trabalho | media |
| 1414 | 1419 | 6 | N | `cbor` | CBOR – ocupação (acidente de trabalho) | media |
| 1420 | 1422 | 3 | N | `cnaer` | CNAER – atividade econômica (acidente de trabalho) | media |
| 1423 | 1423 | 1 | N | `vinculo_previdencia` | TP_VINCPREV – 1 autônomo, 2 desempregado, 3 aposentado, 4 não segurado, 5 empregado, 6 empregador | media |
| 1424 | 1424 | 1 | N | `parto_nascidos_vivos` | QT_VIVOS – nascidos vivos | alta |
| 1425 | 1425 | 1 | N | `parto_nascidos_mortos` | QT_MORTOS – nascidos mortos | alta |
| 1426 | 1426 | 1 | N | `parto_saida_alta` | QT_ALTA – saídas por alta | alta |
| 1427 | 1427 | 1 | N | `parto_saida_transf` | QT_TRANSF – saídas por transferência | alta |
| 1428 | 1428 | 1 | N | `parto_saida_obito` | QT_OBITO – saídas por óbito | alta |
| 1429 | 1438 | 10 | N | `filler_1429` | Filler (zeros) | alta |
| 1439 | 1440 | 2 | N | `laq_qtd_filhos` | QT_FILHOS – nº de filhos (laqueadura/vasectomia) | media |
| 1441 | 1441 | 1 | N | `laq_grau_instrucao` | GRAU_INSTRU – 1 analfabeto, 2 1º grau, 3 2º grau, 4 3º grau | media |
| 1442 | 1445 | 4 | A | `laq_cid_indicacao` | CID_INDICAÇÃO – laqueadura | alta |
| 1446 | 1447 | 2 | N | `laq_contraceptivo1` | TP_CONTRACEP1 – método contraceptivo (01-12) | media |
| 1448 | 1449 | 2 | N | `laq_contraceptivo2` | TP_CONTRACEP2 – método contraceptivo (01-12) | media |
| 1450 | 1450 | 1 | N | `laq_gestacao_risco` | ST_GESTRISCO – gestação de alto risco: 0 sim, 1 não | alta |
| 1451 | 1485 | 35 | N | `reservado_1451` | Reservado (zeros) | alta |
| 1486 | 1497 | 12 | N | `nu_prenatal` | NU_PRENATAL – nº SISPRENATAL (11 posições em 2012; hoje 12, deduzido do deslocamento) | media |
| 1498 | 1529 | 32 | A | `paciente_nu_doc` | NU_DOC_PAC – número do documento do paciente (1497-1528 em 2012) | media |
| 1530 | 1540 | 11 | A | `paciente_telefone` | Telefone com DDD | media |
| 1541 | 1590 | 50 | A | `paciente_email` | Provável e-mail (vazio no exemplo) | baixa |
| **1591** | **1635** | 9×5 | | **diagnosticos_secundarios** | Bloco repetitivo (1ª ocorrência abaixo) | |
| 1591 | 1594 | 4 | A | `diagnosticos_secundarios[].cid` | CID-10 secundário | alta |
| 1595 | 1595 | 1 | N | `diagnosticos_secundarios[].classificacao` | Classificação do diagnóstico secundário | media |
| 1636 | 1800 | 165 | N | `filler_1636` | Filler (zeros) | alta |
