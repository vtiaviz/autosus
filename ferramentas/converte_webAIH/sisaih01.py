"""
Leitura, geração e validação do arquivo texto do SISAIH01 (registro de 1800 posições, CR+LF).

O layout abaixo foi mapeado a partir de um arquivo real exportado pelo SISAIH01
(competência 08/2026) e conferido com o "Layout da interface texto do SISAIH01" publicado
na Portaria SAS nº 133/2012 (registro de 1600 posições). O layout atual tem 1800 posições:
a partir da 1486 os campos estão deslocados 1 posição e foram acrescentados e-mail e o
bloco de 9 diagnósticos secundários. Cada campo tem um nível de confiança:

  alta   - posição e significado confirmados pelos dados (datas, códigos SIGTAP, CNS etc.)
  media  - posição confirmada, significado deduzido (ex.: ordem de profissionais)
  baixa  - posição e/ou significado são hipótese; no exemplo o campo estava vazio/zerado

Campos de confiança "baixa" devem ser conferidos com o layout oficial vigente antes de
serem preenchidos com dados reais. Enquanto isso, o gerador usa o valor padrão observado.

Uso:
  python3 sisaih01.py ler     ARQUIVO.txt  > aihs.json
  python3 sisaih01.py gerar   aihs.json    > ARQUIVO.txt
  python3 sisaih01.py validar ARQUIVO.txt
  python3 sisaih01.py layout               > layout.md
"""
from __future__ import annotations

import json
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime

TAM_REGISTRO = 1800


@dataclass(frozen=True)
class Campo:
    nome: str
    ini: int          # posição inicial (1-based, inclusiva)
    tam: int
    tipo: str         # 'N' numérico (zeros à esquerda) | 'A' alfanumérico (espaços à direita)
    descricao: str
    confianca: str = "alta"
    padrao: str | None = None   # valor usado quando o campo não é informado

    @property
    def fim(self) -> int:
        return self.ini + self.tam - 1


def _c(nome, ini, tam, tipo, descricao, confianca="alta", padrao=None):
    return Campo(nome, ini, tam, tipo, descricao, confianca, padrao)


# --------------------------------------------------------------------------------------
# Campos simples (fora dos blocos repetitivos)
# --------------------------------------------------------------------------------------
CAMPOS = [
    _c("lote", 1, 8, "N", "Número do lote", padrao="1"),
    _c("qtd_aih_lote", 9, 3, "N", "Quantidade de AIHs no lote (preencher com zeros)"),
    _c("apresentacao", 12, 6, "N", "Ano/mês de apresentação (AAAAMM)"),
    _c("seq_aih_lote", 18, 3, "N", "Sequencial da AIH no lote (preencher com zeros)"),
    _c("orgao_emissor", 21, 10, "A", "Órgão emissor da AIH (ex.: M + IBGE + sufixo)"),
    _c("cnes", 31, 7, "N", "CNES do hospital"),
    _c("municipio", 38, 6, "N", "Município (IBGE, 6 dígitos) do hospital"),
    _c("numero_aih", 44, 13, "N", "Número da AIH"),
    _c("identificacao", 57, 2, "N", "Identificação: 01 principal, 03 continuação, 05 longa permanência", padrao="01"),
    _c("especialidade", 59, 2, "N", "Especialidade do leito"),
    _c("filler_061", 61, 45, "N", "Filler (zeros)"),
    _c("modalidade", 106, 2, "N", "Modalidade: 02 hospitalar, 03 hospital-dia, 04 internação domiciliar", padrao="02"),
    _c("seq_aih5", 108, 3, "N", "Sequencial da AIH 5 (longa permanência)"),
    _c("aih_proxima", 111, 13, "N", "Número da AIH próxima (posterior)"),
    _c("aih_anterior", 124, 13, "N", "Número da AIH anterior"),
    _c("dt_emissao", 137, 8, "N", "Data de emissão (AAAAMMDD)"),
    _c("dt_internacao", 145, 8, "N", "Data de internação (AAAAMMDD)"),
    _c("dt_saida", 153, 8, "N", "Data de saída (AAAAMMDD)"),
    _c("proc_solicitado", 161, 10, "N", "Procedimento solicitado (SIGTAP)"),
    _c("mudanca_proc", 171, 1, "N", "Mudança de procedimento: 1 sim, 2 não", padrao="2"),
    _c("proc_realizado", 172, 10, "N", "Procedimento realizado/principal (SIGTAP)"),
    _c("carater_internacao", 182, 2, "N", "Caráter da internação (01 eletivo, 02 urgência...)"),
    _c("motivo_saida", 184, 2, "N", "Motivo de saída/permanência (ex.: 12 alta melhorado)"),
    _c("solicitante_tipo_doc", 186, 1, "N", "Profissional solicitante – tipo de documento (1 CPF, 2 CNS)", "media", "2"),
    _c("solicitante_doc", 187, 15, "N", "Profissional solicitante – documento", "media"),
    _c("responsavel_tipo_doc", 202, 1, "N", "Profissional responsável – tipo de documento", "media", "2"),
    _c("responsavel_doc", 203, 15, "N", "Profissional responsável – documento", "media"),
    _c("diretor_tipo_doc", 218, 1, "N", "Diretor clínico – tipo de documento", "media", "2"),
    _c("diretor_doc", 219, 15, "N", "Diretor clínico – documento", "media"),
    _c("autorizador_tipo_doc", 234, 1, "N", "Autorizador (gestor) – tipo de documento", "media", "2"),
    _c("autorizador_doc", 235, 15, "N", "Autorizador (gestor) – documento", "media"),
    _c("cid_principal", 250, 4, "A", "CID-10 principal (sem ponto; 3 caracteres + espaço se for categoria)"),
    _c("cid_secundario_legado", 254, 4, "A", "DIAG_SEC – CID secundário (campo antigo; hoje usa-se o bloco 1591-1635)", "media", "0000"),
    _c("cid_causas_associadas", 258, 4, "A", "DIAG_COMPL – CID de causas associadas", "media", "0000"),
    _c("cid_obito", 262, 4, "A", "DIAG_OBITO – CID da causa do óbito", "media", "0000"),
    _c("cod_solicitacao_liberacao", 266, 3, "N", "COD_SOL_LIB – 001 permanência a menor, 002 idade a menor, 003 idade a maior, 004 permanência e idade", "media"),
    _c("paciente_nome", 269, 70, "A", "Nome do paciente"),
    _c("paciente_nascimento", 339, 8, "N", "Data de nascimento (AAAAMMDD)"),
    _c("paciente_sexo", 347, 1, "A", "Sexo: M ou F"),
    _c("paciente_raca_cor", 348, 2, "N", "Raça/cor (01 branca, 02 preta, 03 parda, 04 amarela, 05 indígena, 99 sem informação)"),
    _c("paciente_nome_mae", 350, 70, "A", "Nome da mãe"),
    _c("paciente_nome_responsavel", 420, 70, "A", "Nome do responsável"),
    _c("paciente_tipo_doc", 490, 1, "N", "TP_DOC_PAC – 1 PIS/PASEP, 2 RG, 3 certidão nasc., 4 CPF, 5 ignorado, 6 matrícula da certidão", "media", "5"),
    _c("paciente_etnia", 491, 4, "N", "ETNIA_INDIGENA – código da etnia; 0000 se raça/cor não for 05", "media"),
    _c("desconhecido_495", 495, 4, "N", "Filler em 2012; zeros em todos os exemplos", "baixa"),
    _c("liberacao_critica", 499, 1, "N", "Liberação de crítica gravada pelo SISAIH01: 7 = permanência a menor liberada "
       "(confirmado: o SISAIH01 grava 7 aqui ao solicitar a liberação)", "media"),
    _c("desconhecido_500", 500, 2, "A", "Filler em 2012; hoje usado ('NA' em todo o exemplo)", "baixa", "NA"),
    _c("paciente_cns", 502, 15, "N", "CNS do paciente"),
    _c("paciente_nacionalidade", 517, 3, "N", "Nacionalidade (010 Brasil)", padrao="010"),
    _c("end_tipo_logradouro", 520, 3, "N", "Tipo de logradouro (tabela DNE: 081 rua, 008 avenida...)"),
    _c("end_logradouro", 523, 50, "A", "Logradouro"),
    _c("end_numero", 573, 7, "A", "Número", "media"),
    _c("end_complemento", 580, 15, "A", "Complemento", "media"),
    _c("end_bairro", 595, 30, "A", "Bairro (BAIRRO_PAC 595-624 no layout de 2012)"),
    _c("end_municipio", 625, 6, "N", "Município de residência (IBGE)"),
    _c("end_uf", 631, 2, "A", "UF de residência"),
    _c("end_cep", 633, 8, "N", "CEP"),
    _c("paciente_prontuario", 641, 15, "N", "Nº do prontuário (confirmado pela coluna 3 do CSV do sistema atual)", "media"),
    _c("enfermaria", 656, 4, "N", "NU_ENFERMARIA – número da enfermaria", "media"),
    _c("leito", 660, 4, "N", "NU_LEITO – número do leito", "media"),
    # bloco de procedimentos: 664-1393 (ver PROC_*)
    _c("utineo_saida", 1394, 1, "N", "SAÍDA_UTINEO – motivo de saída da UTI neonatal", "media"),
    _c("utineo_peso", 1395, 4, "N", "PESO_UTINEO – peso ao nascer (g)", "media"),
    _c("utineo_mes_gestacao", 1399, 1, "N", "MESGEST_UTINEO – mês de gestação", "media"),
    _c("cnpj_empregador", 1400, 14, "N", "CNPJ_EMPREG – acidente de trabalho", "media"),
    _c("cbor", 1414, 6, "N", "CBOR – ocupação (acidente de trabalho)", "media"),
    _c("cnaer", 1420, 3, "N", "CNAER – atividade econômica (acidente de trabalho)", "media"),
    _c("vinculo_previdencia", 1423, 1, "N", "TP_VINCPREV – 1 autônomo, 2 desempregado, 3 aposentado, 4 não segurado, 5 empregado, 6 empregador", "media"),
    _c("parto_nascidos_vivos", 1424, 1, "N", "QT_VIVOS – nascidos vivos"),
    _c("parto_nascidos_mortos", 1425, 1, "N", "QT_MORTOS – nascidos mortos"),
    _c("parto_saida_alta", 1426, 1, "N", "QT_ALTA – saídas por alta"),
    _c("parto_saida_transf", 1427, 1, "N", "QT_TRANSF – saídas por transferência"),
    _c("parto_saida_obito", 1428, 1, "N", "QT_OBITO – saídas por óbito"),
    _c("filler_1429", 1429, 10, "N", "Filler (zeros)"),
    _c("laq_qtd_filhos", 1439, 2, "N", "QT_FILHOS – nº de filhos (laqueadura/vasectomia)", "media"),
    _c("laq_grau_instrucao", 1441, 1, "N", "GRAU_INSTRU – 1 analfabeto, 2 1º grau, 3 2º grau, 4 3º grau", "media"),
    _c("laq_cid_indicacao", 1442, 4, "A", "CID_INDICAÇÃO – laqueadura"),
    _c("laq_contraceptivo1", 1446, 2, "N", "TP_CONTRACEP1 – método contraceptivo (01-12)", "media"),
    _c("laq_contraceptivo2", 1448, 2, "N", "TP_CONTRACEP2 – método contraceptivo (01-12)", "media"),
    _c("laq_gestacao_risco", 1450, 1, "N", "ST_GESTRISCO – gestação de alto risco: 0 sim, 1 não", "alta", "1"),
    _c("reservado_1451", 1451, 35, "N", "Reservado (zeros)"),
    _c("nu_prenatal", 1486, 12, "N", "NU_PRENATAL – nº SISPRENATAL (11 posições em 2012; hoje 12, deduzido do deslocamento)", "media"),
    _c("paciente_nu_doc", 1498, 32, "A", "NU_DOC_PAC – número do documento do paciente (1497-1528 em 2012)", "media"),
    _c("paciente_telefone", 1530, 11, "A", "Telefone com DDD", "media"),
    _c("paciente_email", 1541, 50, "A", "Provável e-mail (vazio no exemplo)", "baixa"),
    # bloco de diagnósticos secundários: 1591-1635 (ver DIAG_*)
    _c("filler_1636", 1636, 165, "N", "Filler (zeros)"),
]

# --------------------------------------------------------------------------------------
# Bloco de procedimentos: 10 ocorrências de 73 posições (664-1393), conforme layout oficial
# --------------------------------------------------------------------------------------
PROC_INI, PROC_OCORR, PROC_TAM = 664, 10, 73
PROC_CAMPOS = [  # posições relativas (0-based dentro da ocorrência)
    _c("prof_tipo_doc", 0, 1, "N", "Profissional executante – tipo de documento (1 CPF, 2 CNS)", padrao="2"),
    _c("prof_doc", 1, 15, "N", "Profissional executante – documento"),
    _c("cbo", 16, 6, "A", "CBO do profissional"),
    _c("ind_equipe", 22, 1, "N", "IN_EQUIPE – indicador de equipe"),
    _c("prestador_tipo_doc", 23, 1, "N", "IN_SERVICO – tipo de documento do serviço (5 = CNES no exemplo)", "alta", "5"),
    _c("prestador_doc", 24, 14, "N", "IDENT_SERVICO – documento do serviço (CNES com zeros à esquerda)"),
    _c("executante_tipo_doc", 38, 1, "N", "IN_EXECUTOR – tipo de documento do executor (5 = CNES)", "alta", "5"),
    _c("executante_doc", 39, 15, "N", "IDENT_EXECUTOR – documento do executor (CNES com zeros à esquerda)"),
    _c("procedimento", 54, 10, "N", "Código do procedimento (SIGTAP)"),
    _c("quantidade", 64, 3, "N", "Quantidade"),
    _c("competencia", 67, 6, "N", "Competência de realização (AAAAMM)"),
]

# --------------------------------------------------------------------------------------
# Diagnósticos secundários: 9 ocorrências de 5 posições, a partir da 1591
# --------------------------------------------------------------------------------------
DIAG_INI, DIAG_OCORR, DIAG_TAM = 1591, 9, 5
DIAG_CAMPOS = [
    _c("cid", 0, 4, "A", "CID-10 secundário"),
    _c("classificacao", 4, 1, "N", "Classificação do diagnóstico secundário", "media"),
]


def _checar_layout() -> None:
    """Garante que os campos cobrem as 1800 posições sem sobreposição nem buracos."""
    faixas = [(c.ini, c.fim) for c in CAMPOS]
    faixas.append((PROC_INI, PROC_INI + PROC_OCORR * PROC_TAM - 1))
    faixas.append((DIAG_INI, DIAG_INI + DIAG_OCORR * DIAG_TAM - 1))
    faixas.sort()
    pos = 1
    for ini, fim in faixas:
        assert ini == pos, f"buraco/sobreposição na posição {pos} (campo começa em {ini})"
        pos = fim + 1
    assert pos == TAM_REGISTRO + 1, f"layout termina em {pos - 1}, esperado {TAM_REGISTRO}"
    assert sum(c.tam for c in PROC_CAMPOS) == PROC_TAM
    assert sum(c.tam for c in DIAG_CAMPOS) == DIAG_TAM


_checar_layout()


# --------------------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------------------
def _ascii(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt)
    return "".join(ch for ch in txt if not unicodedata.combining(ch)).encode("ascii", "replace").decode()


def formatar(campo: Campo, valor) -> str:
    if valor is None or valor == "":
        valor = campo.padrao if campo.padrao is not None else ""
    valor = str(valor)
    if campo.tipo == "N":
        valor = valor.strip()
        if valor and not valor.isdigit():
            raise ValueError(f"{campo.nome}: valor numérico inválido {valor!r}")
        if len(valor) > campo.tam:
            raise ValueError(f"{campo.nome}: {valor!r} excede {campo.tam} posições")
        return valor.rjust(campo.tam, "0")
    valor = _ascii(valor).upper()
    if len(valor) > campo.tam:
        raise ValueError(f"{campo.nome}: {valor!r} excede {campo.tam} posições")
    return valor.ljust(campo.tam, " ")


def _ler_campo(campo: Campo, reg: str, base: int = 0) -> str:
    ini = base + campo.ini - 1 if base == 0 else base + campo.ini
    bruto = reg[ini: ini + campo.tam]
    return bruto if campo.tipo == "N" else bruto.rstrip()


# --------------------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------------------
def ler_registro(reg: str) -> dict:
    reg = reg.rstrip("\r\n")
    if len(reg) != TAM_REGISTRO:
        raise ValueError(f"registro com {len(reg)} posições (esperado {TAM_REGISTRO})")
    aih = {c.nome: _ler_campo(c, reg) for c in CAMPOS}
    procs = []
    for i in range(PROC_OCORR):
        base = PROC_INI - 1 + i * PROC_TAM
        oc = {c.nome: _ler_campo(c, reg, base) for c in PROC_CAMPOS}
        if oc["procedimento"].strip("0"):
            procs.append(oc)
    diags = []
    for i in range(DIAG_OCORR):
        base = DIAG_INI - 1 + i * DIAG_TAM
        oc = {c.nome: _ler_campo(c, reg, base) for c in DIAG_CAMPOS}
        if oc["cid"].strip():
            diags.append(oc)
    aih["procedimentos"] = procs
    aih["diagnosticos_secundarios"] = diags
    return aih


def ler_arquivo(caminho: str) -> list[dict]:
    with open(caminho, encoding="latin-1", newline="") as f:
        return [ler_registro(l) for l in f if l.strip()]


# --------------------------------------------------------------------------------------
# Geração
# --------------------------------------------------------------------------------------
def gerar_registro(aih: dict) -> str:
    reg = [" "] * TAM_REGISTRO

    def por(ini0: int, txt: str):
        reg[ini0: ini0 + len(txt)] = list(txt)

    for c in CAMPOS:
        por(c.ini - 1, formatar(c, aih.get(c.nome)))

    procs = aih.get("procedimentos", [])
    if len(procs) > PROC_OCORR:
        raise ValueError(f"AIH {aih.get('numero_aih')}: {len(procs)} procedimentos (máximo {PROC_OCORR} por registro)")
    for i in range(PROC_OCORR):
        oc = procs[i] if i < len(procs) else None
        base = PROC_INI - 1 + i * PROC_TAM
        for c in PROC_CAMPOS:
            # ocorrência vazia = tudo zero (inclusive campos com valor padrão)
            txt = formatar(c, oc.get(c.nome)) if oc else formatar(Campo(c.nome, 0, c.tam, "N", ""), "")
            por(base + c.ini, txt)

    diags = aih.get("diagnosticos_secundarios", [])
    if len(diags) > DIAG_OCORR:
        raise ValueError(f"AIH {aih.get('numero_aih')}: {len(diags)} diagnósticos secundários (máximo {DIAG_OCORR})")
    for i in range(DIAG_OCORR):
        oc = diags[i] if i < len(diags) else {}
        base = DIAG_INI - 1 + i * DIAG_TAM
        for c in DIAG_CAMPOS:
            por(base + c.ini, formatar(c, oc.get(c.nome)))

    out = "".join(reg)
    assert len(out) == TAM_REGISTRO
    return out


def gerar_arquivo(aihs: list[dict]) -> str:
    return "".join(gerar_registro(a) + "\r\n" for a in aihs)


# --------------------------------------------------------------------------------------
# Validação (pré-críticas simples, não substitui a consistência do SISAIH01)
# --------------------------------------------------------------------------------------
def cns_valido(cns: str) -> bool:
    cns = cns.strip()
    if len(cns) != 15 or not cns.isdigit() or cns[0] not in "12789":
        return False
    return sum(int(d) * (15 - i) for i, d in enumerate(cns)) % 11 == 0


# Dois primeiros dígitos da AIH: código de UF do IBGE, ou 99 (CNRAC)
UF_AIH = {"11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25", "26", "27", "28",
          "29", "31", "32", "33", "35", "41", "42", "43", "50", "51", "52", "53", "99"}


def aih_dv(base12: str) -> str:
    """Dígito verificador da AIH: resto da divisão dos 12 primeiros dígitos por 11 (resto 10 -> 0).
    É o mesmo que a forma do Manual do SIH (último algarismo de N - N // 11), porque
    N - N // 11 = (N mod 11) + 10 * (N // 11). Conferido nas AIHs aceitas pelo SISAIH01."""
    return str(int(base12) % 11 % 10)


def aih_valida(numero: str) -> bool:
    numero = numero.strip()
    return len(numero) == 13 and numero.isdigit() and aih_dv(numero[:12]) == numero[12]


def _data_ok(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y%m%d")
        return True
    except ValueError:
        return False


def validar_aih(aih: dict) -> list[str]:
    erros = []
    n = aih.get("numero_aih", "?")
    if not aih_valida(str(n)):
        certo = str(n)[:12] + aih_dv(str(n)[:12]) if str(n)[:12].isdigit() and len(str(n)) == 13 else "?"
        erros.append(f"{n}: dígito verificador da AIH inválido (com o DV correto seria {certo})")
    if str(n)[:2] not in UF_AIH:
        erros.append(f"{n}: os 2 primeiros dígitos da AIH ({str(n)[:2]}) não são um código de UF do IBGE nem 99")
    for campo in ("dt_emissao", "dt_internacao", "dt_saida", "paciente_nascimento"):
        if not _data_ok(aih.get(campo, "")):
            erros.append(f"{n}: {campo} inválida ({aih.get(campo)!r})")
    if all(_data_ok(aih.get(c, "")) for c in ("dt_internacao", "dt_saida", "paciente_nascimento")):
        if aih["dt_saida"] < aih["dt_internacao"]:
            erros.append(f"{n}: data de saída anterior à internação")
        if aih["paciente_nascimento"] > aih["dt_internacao"]:
            erros.append(f"{n}: nascimento posterior à internação")
    if aih.get("paciente_sexo") not in ("M", "F"):
        erros.append(f"{n}: sexo deve ser M ou F")
    if aih.get("paciente_cns", "").strip("0") and not cns_valido(aih["paciente_cns"]):
        erros.append(f"{n}: CNS do paciente inválido")
    for papel in ("solicitante", "responsavel", "diretor", "autorizador"):
        if aih.get(f"{papel}_tipo_doc") == "2" and not cns_valido(aih.get(f"{papel}_doc", "")):
            erros.append(f"{n}: CNS do {papel} inválido")
    if not aih.get("procedimentos"):
        erros.append(f"{n}: nenhum procedimento informado")
    for i, p in enumerate(aih.get("procedimentos", []), 1):
        if p.get("prof_tipo_doc") == "2" and p.get("prof_doc", "").strip("0") and not cns_valido(p["prof_doc"]):
            erros.append(f"{n}: procedimento {i}: CNS do profissional inválido")
        if not str(p.get("quantidade", "")).strip("0"):
            erros.append(f"{n}: procedimento {i}: quantidade zerada")
    return erros


def validar_arquivo(caminho: str) -> list[str]:
    erros = []
    with open(caminho, "rb") as f:
        bruto = f.read()
    linhas = bruto.split(b"\r\n")
    if linhas and linhas[-1] == b"":
        linhas.pop()
    else:
        erros.append("arquivo deve terminar com CR+LF")
    for i, l in enumerate(linhas, 1):
        if len(l) != TAM_REGISTRO:
            erros.append(f"linha {i}: {len(l)} posições (esperado {TAM_REGISTRO})")
    if erros:
        return erros
    vistos = set()
    for aih in ler_arquivo(caminho):
        if aih["numero_aih"] in vistos:
            erros.append(f"{aih['numero_aih']}: número de AIH duplicado no arquivo")
        vistos.add(aih["numero_aih"])
        erros.extend(validar_aih(aih))
    return erros


# --------------------------------------------------------------------------------------
# Documentação do layout
# --------------------------------------------------------------------------------------
def layout_markdown() -> str:
    linhas = ["| Início | Fim | Tam | Tipo | Campo | Descrição | Confiança |", "|---|---|---|---|---|---|---|"]
    def add(ini, fim, c, nome):
        linhas.append(f"| {ini} | {fim} | {c.tam} | {c.tipo} | `{nome}` | {c.descricao} | {c.confianca} |")
    itens = [(c.ini, "c", c) for c in CAMPOS] + [(PROC_INI, "p", None), (DIAG_INI, "d", None)]
    for ini, k, c in sorted(itens, key=lambda x: x[0]):
        if k == "c":
            add(c.ini, c.fim, c, c.nome)
        elif k == "p":
            linhas.append(f"| **{PROC_INI}** | **{PROC_INI + PROC_OCORR * PROC_TAM - 1}** | {PROC_OCORR}×{PROC_TAM} | | **procedimentos** | Bloco repetitivo (1ª ocorrência abaixo) | |")
            for pc in PROC_CAMPOS:
                add(PROC_INI + pc.ini, PROC_INI + pc.ini + pc.tam - 1, pc, f"procedimentos[].{pc.nome}")
        else:
            linhas.append(f"| **{DIAG_INI}** | **{DIAG_INI + DIAG_OCORR * DIAG_TAM - 1}** | {DIAG_OCORR}×{DIAG_TAM} | | **diagnosticos_secundarios** | Bloco repetitivo (1ª ocorrência abaixo) | |")
            for dc in DIAG_CAMPOS:
                add(DIAG_INI + dc.ini, DIAG_INI + dc.ini + dc.tam - 1, dc, f"diagnosticos_secundarios[].{dc.nome}")
    return "\n".join(linhas) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "ler":
        json.dump(ler_arquivo(argv[2]), sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif cmd == "gerar":
        with open(argv[2], encoding="utf-8") as f:
            aihs = json.load(f)
        sys.stdout.buffer.write(gerar_arquivo(aihs).encode("ascii"))
    elif cmd == "validar":
        erros = validar_arquivo(argv[2])
        for e in erros:
            print(e)
        print(f"{len(erros)} problema(s) encontrado(s)")
        return 1 if erros else 0
    elif cmd == "layout":
        sys.stdout.write(layout_markdown())
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
