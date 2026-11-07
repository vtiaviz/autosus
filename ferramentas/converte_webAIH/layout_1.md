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
| 254 | 268 | 15 | N | `reservado_254` | CIDs legados/reservado (zeros no exemplo) | baixa |
| 269 | 338 | 70 | A | `paciente_nome` | Nome do paciente | alta |
| 339 | 346 | 8 | N | `paciente_nascimento` | Data de nascimento (AAAAMMDD) | alta |
| 347 | 347 | 1 | A | `paciente_sexo` | Sexo: M ou F | alta |
| 348 | 349 | 2 | N | `paciente_raca_cor` | Raça/cor (01 branca, 02 preta, 03 parda, 04 amarela, 05 indígena, 99 sem informação) | alta |
| 350 | 419 | 70 | A | `paciente_nome_mae` | Nome da mãe | alta |
| 420 | 489 | 70 | A | `paciente_nome_responsavel` | Nome do responsável | alta |
| 490 | 490 | 1 | N | `paciente_tipo_doc` | Provável tipo de documento do paciente (5 em todo o exemplo) | baixa |
| 491 | 499 | 9 | N | `desconhecido_491` | Desconhecido (zeros; última posição 0 ou 7 no exemplo) | baixa |
| 500 | 501 | 2 | A | `desconhecido_500` | Desconhecido ('NA' em todo o exemplo) | baixa |
| 502 | 516 | 15 | N | `paciente_cns` | CNS do paciente | alta |
| 517 | 519 | 3 | N | `paciente_nacionalidade` | Nacionalidade (010 Brasil) | alta |
| 520 | 522 | 3 | N | `end_tipo_logradouro` | Tipo de logradouro (tabela DNE: 081 rua, 008 avenida...) | alta |
| 523 | 572 | 50 | A | `end_logradouro` | Logradouro | media |
| 573 | 579 | 7 | A | `end_numero` | Número (hipótese: 50+7+15+30 = 102 posições vazias no exemplo) | baixa |
| 580 | 594 | 15 | A | `end_complemento` | Complemento (hipótese) | baixa |
| 595 | 624 | 30 | A | `end_bairro` | Bairro (hipótese) | baixa |
| 625 | 630 | 6 | N | `end_municipio` | Município de residência (IBGE) | alta |
| 631 | 632 | 2 | A | `end_uf` | UF de residência | alta |
| 633 | 640 | 8 | N | `end_cep` | CEP | alta |
| 641 | 655 | 15 | N | `paciente_prontuario` | Nº do prontuário (confirmado pela coluna 3 do CSV do sistema atual) | media |
| 656 | 663 | 8 | N | `reservado_656` | Reservado (zeros) | baixa |
| **664** | **1423** | 10×76 | | **procedimentos** | Bloco repetitivo (1ª ocorrência abaixo) | |
| 664 | 664 | 1 | N | `procedimentos[].prof_tipo_doc` | Profissional executante – tipo de documento (1 CPF, 2 CNS) | alta |
| 665 | 679 | 15 | N | `procedimentos[].prof_doc` | Profissional executante – documento | alta |
| 680 | 685 | 6 | A | `procedimentos[].cbo` | CBO do profissional | alta |
| 686 | 686 | 1 | N | `procedimentos[].ind_equipe` | Indicador de equipe (0 no exemplo) | baixa |
| 687 | 687 | 1 | N | `procedimentos[].prestador_tipo_doc` | Estabelecimento prestador – tipo de documento (5 = CNES no exemplo) | media |
| 688 | 701 | 14 | N | `procedimentos[].prestador_doc` | Estabelecimento prestador – documento (CNES com zeros à esquerda) | media |
| 702 | 702 | 1 | N | `procedimentos[].executante_tipo_doc` | Estabelecimento executante – tipo de documento (5 = CNES) | media |
| 703 | 717 | 15 | N | `procedimentos[].executante_doc` | Estabelecimento executante – documento (CNES com zeros à esquerda) | media |
| 718 | 727 | 10 | N | `procedimentos[].procedimento` | Código do procedimento (SIGTAP) | alta |
| 728 | 730 | 3 | N | `procedimentos[].quantidade` | Quantidade | alta |
| 731 | 736 | 6 | N | `procedimentos[].competencia` | Competência de realização (AAAAMM) | alta |
| 737 | 739 | 3 | N | `procedimentos[].reservado` | Reservado (zeros; possivelmente serviço/classificação) | baixa |
| 1424 | 1424 | 1 | N | `parto_nascidos_vivos` | Parto – nascidos vivos (hipótese; '1' na AIH de parto) | baixa |
| 1425 | 1425 | 1 | N | `parto_nascidos_mortos` | Parto – nascidos mortos (hipótese) | baixa |
| 1426 | 1426 | 1 | N | `parto_saida_alta` | Parto – saídas por alta (hipótese) | baixa |
| 1427 | 1427 | 1 | N | `parto_saida_transf` | Parto – saídas por transferência (hipótese) | baixa |
| 1428 | 1428 | 1 | N | `parto_saida_obito` | Parto – saídas por óbito (hipótese) | baixa |
| 1429 | 1441 | 13 | N | `reservado_1429` | Reservado / dados de gestante (zeros) | baixa |
| 1442 | 1445 | 4 | A | `reservado_1442` | Provável CID (indicação de laqueadura?) – espaços | baixa |
| 1446 | 1450 | 5 | N | `desconhecido_1446` | Desconhecido ('00001' em todo o exemplo) | baixa |
| 1451 | 1497 | 47 | N | `reservado_1451` | Reservado (zeros) | baixa |
| 1498 | 1529 | 32 | A | `reservado_1498` | Reservado (espaços) | baixa |
| 1530 | 1540 | 11 | A | `paciente_telefone` | Telefone com DDD | media |
| 1541 | 1590 | 50 | A | `paciente_email` | Provável e-mail (vazio no exemplo) | baixa |
| **1591** | **1635** | 9×5 | | **diagnosticos_secundarios** | Bloco repetitivo (1ª ocorrência abaixo) | |
| 1591 | 1594 | 4 | A | `diagnosticos_secundarios[].cid` | CID-10 secundário | alta |
| 1595 | 1595 | 1 | N | `diagnosticos_secundarios[].classificacao` | Classificação do diagnóstico secundário | media |
| 1636 | 1800 | 165 | N | `filler_1636` | Filler (zeros) | alta |
