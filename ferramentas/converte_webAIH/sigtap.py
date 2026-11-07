"""
Leitura das regras do SIGTAP (Tabela Unificada do SUS) direto do zip mensal do DATASUS
(TabelaUnificada_AAAAMM_*.zip), sem precisar descompactar.

Regras usadas pelo conversor:

* Média de permanência (TB_PROCEDIMENTO.QT_DIAS_PERMANENCIA) -> crítica de permanência a menor.
  O SISAIH01 critica quando permanência < média // 2 (divisão inteira): ex. "1 menor que 3 (Media: 6)".
* Compatibilidade CID x procedimento (RL_PROCEDIMENTO_CID):
    ST_PRINCIPAL = 'S' -> CIDs aceitos como principal do procedimento;
    ST_PRINCIPAL = 'N' -> CIDs secundários vinculados ao procedimento (só 32 procedimentos:
                          diálise, fístula AV, parto de alto risco, transplantes).
* Atributo complementar 043 "Exige registro de CID de causas associadas" (RL_PROCEDIMENTO_DETALHE).

A regra "CID principal de lesão (S00-T98) exige causa externa (V01-Y98) no 1º CID secundário"
NÃO está nas tabelas do SIGTAP: é norma da Portaria SAS/MS nº 1.324/2014, embutida no SISAIH01.
"""
from __future__ import annotations

import io
import os
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Procedimento:
    codigo: str
    nome: str
    sexo: str
    media_permanencia: int
    idade_min_meses: int
    idade_max_meses: int


@dataclass
class Sigtap:
    competencia: str = ""
    procedimentos: dict[str, Procedimento] = field(default_factory=dict)
    cid_principal: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    cid_secundario: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    detalhes: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    cids: dict[str, str] = field(default_factory=dict)

    def media(self, proc: str) -> int | None:
        p = self.procedimentos.get(proc)
        return p.media_permanencia if p and p.media_permanencia > 0 else None


def _abrir(origem: str):
    """Devolve uma função que abre um arquivo da tabela, seja de um .zip ou de uma pasta."""
    if os.path.isdir(origem):
        return lambda nome: open(os.path.join(origem, nome), encoding="latin-1")
    z = zipfile.ZipFile(origem)
    nomes = {os.path.basename(n).lower(): n for n in z.namelist()}
    return lambda nome: io.TextIOWrapper(z.open(nomes[nome.lower()]), encoding="latin-1")


def carregar(origem: str) -> Sigtap:
    abrir = _abrir(origem)
    s = Sigtap()
    with abrir("tb_procedimento.txt") as f:
        for l in f:
            if len(l) < 330:
                continue
            cod = l[0:10]
            s.procedimentos[cod] = Procedimento(
                codigo=cod,
                nome=l[10:260].rstrip(),
                sexo=l[261],
                media_permanencia=int(l[266:270] or 0),
                idade_min_meses=int(l[274:278] or 0),
                idade_max_meses=int(l[278:282] or 0),
            )
            s.competencia = l[324:330]
    with abrir("rl_procedimento_cid.txt") as f:
        for l in f:
            if len(l) < 15:
                continue
            alvo = s.cid_principal if l[14] == "S" else s.cid_secundario
            alvo[l[0:10]].add(l[10:14].strip())
    with abrir("rl_procedimento_detalhe.txt") as f:
        for l in f:
            if len(l) >= 13:
                s.detalhes[l[0:10]].add(l[10:13])
    with abrir("tb_cid.txt") as f:
        for l in f:
            if len(l) >= 104:
                s.cids[l[0:4].strip()] = l[4:104].rstrip()
    return s


def _casa(cid: str, lista: set[str]) -> bool:
    """CID da AIH (3 ou 4 caracteres) contra a lista do SIGTAP (que mistura categorias e subcategorias)."""
    cid = cid.strip()
    return cid in lista or cid[:3] in lista


def eh_lesao(cid: str) -> bool:
    return cid[:1] in ("S", "T")


def eh_causa_externa(cid: str) -> bool:
    return cid[:1] in ("V", "W", "X", "Y")


def criticas_cid(aih: dict, s: Sigtap | None) -> list[str]:
    """Críticas de CID principal/secundário para uma AIH no formato do sisaih01.py."""
    n, out = aih["numero_aih"], []
    principal = aih["cid_principal"].strip()
    secs = [d["cid"].strip() for d in aih.get("diagnosticos_secundarios", []) if d.get("cid", "").strip()]
    proc = aih["proc_realizado"]

    # Portaria SAS/MS 1.324/2014, art. 3º, § 2º
    if eh_lesao(principal) and not (secs and eh_causa_externa(secs[0])):
        motivo = "sem CID secundário" if not secs else f"1º CID secundário é {secs[0]}"
        out.append(f"{n}: CID principal {principal} é lesão (S00–T98) e {motivo}; o 1º CID secundário tem que "
                   "ser a causa externa (V01–Y98) – SERÁ REJEITADA (CAMPO OBRIGATÓRIO: CID Secundário)")

    if s is None:
        return out
    if s.cid_principal.get(proc) and not _casa(principal, s.cid_principal[proc]):
        out.append(f"{n}: CID principal {principal} não é compatível com o procedimento {proc} no SIGTAP {s.competencia}")
    if s.cid_secundario.get(proc) and not any(_casa(c, s.cid_secundario[proc]) for c in secs):
        ex = ", ".join(sorted(s.cid_secundario[proc])[:5])
        out.append(f"{n}: o procedimento {proc} tem CIDs secundários vinculados no SIGTAP (ex.: {ex}) e a AIH "
                   "não informa nenhum deles")
    if "043" in s.detalhes.get(proc, set()) and not secs:
        out.append(f"{n}: o procedimento {proc} exige registro de CID de causas associadas (atributo 043 do SIGTAP)")
    return out


def lesoes_que_exigem_causa_externa(s: Sigtap) -> list[tuple[str, str]]:
    """Lista dos CIDs do SIGTAP que, como principal, obrigam causa externa no 1º secundário."""
    return sorted((c, nome) for c, nome in s.cids.items() if eh_lesao(c))
