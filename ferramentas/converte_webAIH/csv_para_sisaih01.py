"""
Converte o CSV de AIHs do sistema atual para o arquivo de importação do SISAIH01
(Importar -> Produção).

Uso:
  python3 csv_para_sisaih01.py ENTRADA.csv config_hospital.json SAIDA.txt [--apresentacao=AAAAMM]

--complementos=ARQ.csv  arquivo com CIDs secundários que o sistema de origem não exporta
(colunas numero_aih;cns_paciente;cids_secundarios, ex.: 1526101594424;704205253573289;V28).
A AIH e o CNS precisam bater com o CSV principal; o complemento substitui a coluna 25.

--apresentacao sobrescreve o valor do config. O SISAIH01 importa cada AIH na apresentação
gravada no arquivo; ela tem que ser a mesma que está aberta no SISAIH01 (barra de status
"APRES.: MM / AAAA"), senão a produção importa "com sucesso" mas não aparece na tela.

O CSV não tem cabeçalho, é separado por ';' e tem 24 colunas, na ordem de COLUNAS abaixo.
Opcionalmente pode ter até 30 colunas (COLUNAS_EXTRAS): CIDs secundários e dados do parto,
que o SISAIH01 exige em alguns casos (trauma sem causa externa, parto).
Os dados que não estão no CSV (CNES, município, órgão emissor, autorizador, competência
de apresentação...) vêm do config_hospital.json.

O script aborta se alguma AIH tiver erro de formato e lista avisos de situações que
o SISAIH01 provavelmente vai criticar (ex.: parto sem dados do parto).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date

import sigtap
import sisaih01

COLUNAS = [
    "cns_paciente",         # 1  CNS do paciente
    "nome",                 # 2
    "prontuario",           # 3
    "nascimento",           # 4  AAAA-MM-DD
    "sexo",                 # 5  1 masculino, 3 feminino
    "raca_cor",             # 6  1..5 / 99
    "nome_mae",             # 7
    "nome_responsavel",     # 8
    "tipo_logradouro",      # 9  código DNE (081 rua, 008 avenida...)
    "logradouro",           # 10
    "cep",                  # 11 99999-999
    "municipio_residencia", # 12 IBGE com 7 dígitos (com DV)
    "telefone",             # 13 (99) 9999-99999
    "dt_internacao",        # 14 AAAA-MM-DD
    "dt_saida",             # 15 AAAA-MM-DD
    "cid_principal",        # 16
    "procedimento",         # 17 SIGTAP
    "especialidade",        # 18 especialidade do leito (2 obstétrico, 3 clínico, 7 pediátrico...)
    "carater_internacao",   # 19
    "motivo_saida",         # 20
    "cpf_medico",           # 21
    "cns_medico",           # 22
    "cbo_medico",           # 23
    "numero_aih",           # 24
]

# UF a partir dos 2 primeiros dígitos do código IBGE do município
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
           "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
           "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
           "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}

# Colunas opcionais depois da 24ª (podem faltar ou vir vazias)
COLUNAS_EXTRAS = [
    "cids_secundarios",     # 25 ex.: "X20:1" ou "X20:1,E119:2" (CID[:classificação]), separados por vírgula
    "parto_nascidos_vivos", # 26
    "parto_nascidos_mortos",# 27
    "parto_saida_alta",     # 28
    "parto_saida_transf",   # 29
    "parto_saida_obito",    # 30
]

SEXO = {"1": "M", "3": "F", "M": "M", "F": "F"}

# Procedimentos de parto: o SISAIH01 exige os dados do parto (nascidos vivos etc.)
PREFIXOS_PARTO = ("031001", "041101")


def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def data(v: str) -> str:
    d = so_digitos(v)
    if len(d) != 8:
        raise ValueError(f"data inválida {v!r}")
    return d


def cid(v: str) -> str:
    return (v or "").replace(".", "").strip().upper()


def texto(v: str) -> str:
    return (v or "").strip()   # mantém espaços internos como no sistema de origem (igual ao SISAIH01)


def diagnosticos(v: str, cfg: dict) -> list[dict]:
    out = []
    for item in filter(None, (x.strip() for x in (v or "").split(","))):
        c, _, classif = item.partition(":")
        out.append({"cid": cid(c), "classificacao": classif.strip() or cfg.get("classificacao_cid_secundario_padrao", "1")})
    return out


def converter_linha(lin: dict, cfg: dict) -> dict:
    dt_int = data(lin["dt_internacao"])
    numero_aih = so_digitos(lin["numero_aih"])
    if cfg.get("corrigir_dv_aih") and len(numero_aih) == 13 and not sisaih01.aih_valida(numero_aih):
        numero_aih = numero_aih[:12] + sisaih01.aih_dv(numero_aih[:12])
    cns_med = so_digitos(lin["cns_medico"])
    if cns_med:
        tipo_doc_med, doc_med = "2", cns_med
    else:  # sem CNS: usa o CPF
        tipo_doc_med, doc_med = "1", so_digitos(lin["cpf_medico"])

    telefone = so_digitos(lin["telefone"]) or cfg.get("telefone_padrao", "")
    if cfg.get("especialidade_fixa"):
        espec = cfg["especialidade_fixa"]
    else:
        espec = so_digitos(lin["especialidade"]).zfill(2)

    mun_res = so_digitos(lin["municipio_residencia"])
    if len(mun_res) == 7:   # o SISAIH01 usa o código IBGE sem o dígito verificador
        mun_res = mun_res[:6]

    aih = {
        "lote": cfg.get("lote", "1"),
        "apresentacao": cfg["apresentacao"],
        "orgao_emissor": cfg["orgao_emissor"],
        "cnes": cfg["cnes"],
        "municipio": cfg["municipio"],
        "numero_aih": numero_aih,
        "identificacao": "01",
        "especialidade": espec,
        "modalidade": cfg.get("modalidade", "02"),
        "dt_emissao": dt_int,               # no SISAIH01 de referência, emissão = internação
        "dt_internacao": dt_int,
        "dt_saida": data(lin["dt_saida"]),
        "proc_solicitado": so_digitos(lin["procedimento"]),
        "mudanca_proc": "2",
        "proc_realizado": so_digitos(lin["procedimento"]),
        "carater_internacao": so_digitos(lin["carater_internacao"]).zfill(2),
        "motivo_saida": so_digitos(lin["motivo_saida"]).zfill(2),
        "solicitante_tipo_doc": tipo_doc_med, "solicitante_doc": doc_med,
        "responsavel_tipo_doc": tipo_doc_med, "responsavel_doc": doc_med,
        "diretor_tipo_doc": cfg.get("diretor_tipo_doc", tipo_doc_med),
        "diretor_doc": cfg.get("diretor_doc") or doc_med,
        "autorizador_tipo_doc": "2", "autorizador_doc": cfg["autorizador_cns"],
        "cid_principal": cid(lin["cid_principal"]),
        "paciente_nome": texto(lin["nome"]),
        "paciente_nascimento": data(lin["nascimento"]),
        "paciente_sexo": SEXO.get(lin["sexo"].strip().upper(), lin["sexo"]),
        "paciente_raca_cor": so_digitos(lin["raca_cor"]).zfill(2),
        "paciente_nome_mae": texto(lin["nome_mae"]),
        "paciente_nome_responsavel": texto(lin["nome_responsavel"]),
        "paciente_cns": so_digitos(lin["cns_paciente"]),
        "end_tipo_logradouro": so_digitos(lin["tipo_logradouro"]).zfill(3),
        "end_logradouro": texto(lin["logradouro"]),
        "end_municipio": mun_res,
        "end_uf": UF_IBGE.get(mun_res[:2], ""),
        "end_cep": so_digitos(lin["cep"]),
        "paciente_prontuario": so_digitos(lin["prontuario"]),
        "paciente_telefone": telefone,
        "procedimentos": [{
            "prof_tipo_doc": tipo_doc_med,
            "prof_doc": doc_med,
            "cbo": so_digitos(lin["cbo_medico"]),
            "prestador_doc": cfg["cnes"],
            "executante_doc": cfg["cnes"],
            "procedimento": so_digitos(lin["procedimento"]),
            "quantidade": "1",
            "competencia": dt_int[:6],      # mês da internação (confirmado nas 60 AIHs de referência)
        }],
        "diagnosticos_secundarios": diagnosticos(lin.get("cids_secundarios", ""), cfg),
        **{k: so_digitos(lin.get(k, "")) for k in COLUNAS_EXTRAS[1:]},
    }
    aplicar_padrao_parto(aih, cfg)
    return aih


def aplicar_padrao_parto(aih: dict, cfg: dict) -> None:
    """Em AIH de parto, completa com os valores padrão do config o que o CSV não trouxe."""
    aih["_padroes_parto"] = []
    if not aih["proc_realizado"].startswith(PREFIXOS_PARTO):
        return
    padrao = cfg.get("parto_padrao") or {}
    campos = COLUNAS_EXTRAS[1:]
    if padrao and not any(aih.get(k, "").strip("0") for k in campos):
        for k in campos:
            aih[k] = str(padrao.get(k, "0"))
        aih["_padroes_parto"].append("dados do parto (" + ", ".join(f"{k.replace('parto_', '')}={aih[k]}" for k in campos) + ")")
    motivo = cfg.get("motivo_saida_parto_padrao")
    if motivo and not aih["motivo_saida"].startswith("6"):
        aih["_padroes_parto"].append(f"motivo de saída {aih['motivo_saida']} -> {motivo}")
        aih["motivo_saida"] = motivo


def permanencia(aih: dict) -> int:
    d = lambda s: date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return (d(aih["dt_saida"]) - d(aih["dt_internacao"])).days


SIGTAP: sigtap.Sigtap | None = None


def media_permanencia(proc: str, cfg: dict) -> int | None:
    """Média do config (se houver, tem prioridade) ou da tabela do SIGTAP carregada."""
    manual = cfg.get("media_permanencia_sigtap", {}).get(proc)
    if manual:
        return int(manual)
    return SIGTAP.media(proc) if SIGTAP else None


def permanencia_a_menor(aih: dict, cfg: dict) -> bool:
    """Regra do SISAIH01: permanência < média // 2 (divisão inteira), ex. "1 menor que 3 (Media: 6)".
    Conferido: crise hipertensiva (média 3) com 1 dia NÃO é criticada; anemia (média 6) e
    pneumonia (média 4) com 1 dia são."""
    media = media_permanencia(aih["proc_realizado"], cfg)
    return bool(media) and permanencia(aih) < media // 2


def avisos(aih: dict, cfg: dict) -> list[str]:
    """Situações que passam no formato, mas o SISAIH01/SIHD costuma criticar."""
    n, out = aih["numero_aih"], []
    if n[4:5] not in ("1", "2", "3", "4", "5"):
        out.append(f"{n}: 5º dígito da AIH (série) = {n[4:5]}; o normal é de 1 a 5 – confira o número")
    if n[2:4] != aih["dt_internacao"][2:4] and n[2:4] != aih["dt_emissao"][2:4]:
        out.append(f"{n}: o ano no número da AIH (dígitos 3-4 = {n[2:4]}) difere do ano da internação – confira")
    if permanencia_a_menor(aih, cfg):
        media = media_permanencia(aih["proc_realizado"], cfg)
        acao = ("solicitação de liberação gravada (posição 499 = 7); o gestor ainda precisa autorizar"
                if aih.get("liberacao_critica") == "7"
                else "o SISAIH01 vai criticar 'PERMANÊNCIA A MENOR (SOLICITAR LIBERAÇÃO)'; registre a solicitação de liberação")
        out.append(f"{n}: permanência de {permanencia(aih)} dia(s), menor que a metade da média "
                   f"do SIGTAP ({media} dias, limite {media // 2}) para {aih['proc_realizado']} – {acao}")
    out.extend(c + (" – informe na coluna 25" if "SERÁ REJEITADA" in c else "")
               for c in sigtap.criticas_cid(aih, SIGTAP))
    if aih.get("_padroes_parto"):
        out.append(f"{n}: parto completado com os valores padrão do config: " + "; ".join(aih["_padroes_parto"])
                   + " – confira no prontuário")
    if aih["proc_realizado"].startswith(PREFIXOS_PARTO):
        if not aih["motivo_saida"].startswith("6"):
            out.append(f"{n}: parto com motivo de saída {aih['motivo_saida']} – SERÁ REJEITADA (o SISAIH01 exige "
                       "motivo obstétrico 6x, ex.: 61 alta da mãe e do recém-nascido)")
        if not any(aih.get(k, "").strip("0") for k in COLUNAS_EXTRAS[1:]):
            out.append(f"{n}: parto sem dados do parto (nascidos vivos/mortos, saídas) – preencha as colunas 26 a 30")
    if not aih["end_uf"]:
        out.append(f"{n}: UF não encontrada para o município {aih['end_municipio']}")
    return out


def ler_complementos(caminho: str) -> dict[str, dict]:
    """numero_aih -> {cns_paciente, cids_secundarios}; a 1ª linha é cabeçalho."""
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = [l for l in csv.reader(f, delimiter=";") if any(x.strip() for x in l)]
    out = {}
    for l in linhas[1:]:
        aih, cns, cids = (l + ["", "", ""])[:3]
        out[so_digitos(aih)] = {"cns_paciente": so_digitos(cns), "cids_secundarios": cids.strip()}
    return out


def ler_csv(caminho: str) -> list[dict]:
    with open(caminho, encoding="latin-1", newline="") as f:
        linhas = [l for l in csv.reader(f, delimiter=";") if any(x.strip() for x in l)]
    out = []
    for i, l in enumerate(linhas, 1):
        if not len(COLUNAS) <= len(l) <= len(COLUNAS) + len(COLUNAS_EXTRAS):
            raise ValueError(f"linha {i}: {len(l)} colunas (esperado de {len(COLUNAS)} a "
                             f"{len(COLUNAS) + len(COLUNAS_EXTRAS)})")
        out.append(dict(zip(COLUNAS + COLUNAS_EXTRAS, l)))
    return out


def main() -> int:
    opcoes = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        print(__doc__)
        return 1
    entrada, cfg_path, saida = args[:3]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    if "--apresentacao" in opcoes:
        cfg["apresentacao"] = opcoes["--apresentacao"]
    ap = cfg["apresentacao"]
    if not (len(ap) == 6 and ap.isdigit() and 1 <= int(ap[4:]) <= 12):
        print(f"ERRO: apresentação inválida {ap!r} (use AAAAMM)")
        return 1
    global SIGTAP
    if cfg.get("sigtap"):
        SIGTAP = sigtap.carregar(cfg["sigtap"])
        print(f"SIGTAP competência {SIGTAP.competencia} carregado ({len(SIGTAP.procedimentos)} procedimentos)")
        if SIGTAP.competencia < cfg["apresentacao"][:6]:
            print(f"AVISO: SIGTAP {SIGTAP.competencia} é anterior à apresentação {cfg['apresentacao']}; "
                  "use a tabela da competência vigente")
    linhas = ler_csv(entrada)
    complementos = ler_complementos(opcoes["--complementos"]) if "--complementos" in opcoes else {}
    usados = set()
    for i, lin in enumerate(linhas, 1):
        comp = complementos.get(so_digitos(lin["numero_aih"]))
        if comp:
            if comp["cns_paciente"] and comp["cns_paciente"] != so_digitos(lin["cns_paciente"]):
                print(f"ERRO: complemento da AIH {lin['numero_aih']}: CNS {comp['cns_paciente']} não confere com o "
                      f"CSV ({lin['cns_paciente']}, linha {i}) – complemento ignorado")
                continue
            lin["cids_secundarios"] = comp["cids_secundarios"]
            usados.add(so_digitos(lin["numero_aih"]))
    for aih in sorted(set(complementos) - usados):
        print(f"AVISO: complemento da AIH {aih} não aplicado (AIH não encontrada no CSV ou CNS divergente)")
    if usados:
        print(f"Complementos aplicados em {len(usados)} AIH(s): {', '.join(sorted(usados))}")

    aihs, erros, alertas, correcoes = [], [], [], []
    for i, lin in enumerate(linhas, 1):
        try:
            aih = converter_linha(lin, cfg)
            if aih["numero_aih"] != so_digitos(lin["numero_aih"]):
                correcoes.append((so_digitos(lin["numero_aih"]), aih["numero_aih"], lin["cns_paciente"]))
            sisaih01.gerar_registro(aih)          # valida tamanhos/tipos
        except ValueError as e:
            erros.append(f"linha {i}: {e}")
            continue
        erros.extend(f"linha {i}: {e}" for e in sisaih01.validar_aih(aih))
        if cfg.get("preencher_liberacao_permanencia") and permanencia_a_menor(aih, cfg):
            # o SISAIH01 grava a solicitação de liberação de permanência a menor como "7" na posição 499
            # (confirmado comparando a exportação feita após a liberação manual); COD_SOL_LIB fica zerado
            aih["liberacao_critica"] = "7"
        alertas.extend(avisos(aih, cfg))
        aihs.append(aih)

    nums = [a["numero_aih"] for a in aihs]
    erros.extend(f"AIH {n} repetida no CSV" for n in sorted({n for n in nums if nums.count(n) > 1}))

    sem_media = sorted({a["proc_realizado"] for a in aihs if media_permanencia(a["proc_realizado"], cfg) is None})
    if sem_media:
        alertas.append("permanência a menor NÃO verificada para estes procedimentos (informe \"sigtap\" "
                       "no config ou cadastre a média em media_permanencia_sigtap): " + ", ".join(sem_media))
    if correcoes:
        mapa = saida + ".correcoes_aih.csv"
        with open(mapa, "w", encoding="utf-8") as f:
            f.write("aih_no_csv;aih_corrigida;cns_paciente\n")
            f.writelines(f"{a};{b};{c}\n" for a, b, c in correcoes)
        alertas.append(f"dígito verificador corrigido em {len(correcoes)} AIH(s) (ex.: {correcoes[0][0]} -> "
                       f"{correcoes[0][1]}); lista completa em {mapa}")
    for a in alertas:
        print("AVISO:", a)
    if erros:
        for e in erros:
            print("ERRO:", e)
        print(f"\n{len(erros)} erro(s): arquivo NÃO gerado.")
        return 1

    with open(saida, "wb") as f:
        f.write(sisaih01.gerar_arquivo(aihs).encode("ascii"))
    mais_recente = max(a["dt_saida"][:6] for a in aihs)
    if mais_recente > ap:
        print(f"AVISO: há saídas em {mais_recente[4:]}/{mais_recente[:4]}, depois da apresentação {ap[4:]}/{ap[:4]}")
    print(f"\n{len(aihs)} AIHs gravadas em {saida} ({len(alertas)} aviso(s)).")
    print(f">>> APRESENTAÇÃO GRAVADA NO ARQUIVO: {ap[4:]}/{ap[:4]} – abra esta mesma apresentação no SISAIH01 "
          "antes de importar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
