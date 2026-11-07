"""Arquivos de entrada (por competência) e saídas do processamento no Server_SUS.

As entradas ficam na mesma pasta que o robô já lê (a pasta do downloader do AutoSUS, em
config.yaml > pasta_destino):
  <pasta>/programas/               instaladores (sisaih01_ver, SIHD2_, FPOMAG_Atualiza_, Transmissor)
  <pasta>/AAAA-MM/SIH/             DSIHD017, FORNEC, IMPORT, TERCEIROS, TXTPROC e produção do WebAIH
  <pasta>/AAAA-MM/SIA/             BDSIA
As saídas ficam em server_sus/saida/<apresentação AAAAMM>/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

from .config import DOWNLOADS, PASTA

# Nome do arquivo -> onde ele fica. Qualquer outro nome é recusado.
REGRAS = [
    (r"^sisaih01_ver\d{4}\.exe$", "programas"),
    (r"^SIHD2_\d{4}\.exe$", "programas"),
    (r"^FPOMAG_Atualiza_\d{4}\.exe$", "programas"),
    (r"^Transmissor\d+\.exe$", "programas"),
    (r"^BDSIA(?P<comp>\d{6})[a-z]?\.exe$", "SIA"),
    (r"^DSIHD017_\d+_(?P<comp>\d{6})[a-z]?\.zip$", "SIH"),
    (r"^FORNEC_(?P<comp>\d{6})[a-z]?\.zip$", "SIH"),
    (r"^IMPORT_(?P<comp>\d{6})[a-z]?\.zip$", "SIH"),
    (r"^TERCEIROSBRASIL\d+_(?P<comp>\d{6})[a-z]?\.zip$", "SIH"),
    (r"^TXTPROC_\d+_(?P<comp>\d{6})[a-z]?\.zip$", "SIH"),
    (r"^(?P<apres>\d{6})_SISAIH01_\d+\.txt$", "SIH"),          # produção do WebAIH (nome = apresentação)
]

# O que o processamento de uma competência precisa (os mesmos itens do teste_completo.ps1)
NECESSARIOS = [
    ("Produção do WebAIH", "SIH", r"^{apres}_SISAIH01_\d+\.txt$"),
    ("DSIHD (SIHD)", "SIH", r"^DSIHD017_\d+_{comp}[a-z]?\.zip$"),
    ("Fornecedores (CNES)", "SIH", r"^FORNEC_{comp}[a-z]?\.zip$"),
    ("Importadores (CNES)", "SIH", r"^IMPORT_{comp}[a-z]?\.zip$"),
    ("Terceiros Brasil (CNES)", "SIH", r"^TERCEIROSBRASIL\d+_{comp}[a-z]?\.zip$"),
    ("TXTPROC (portal CNES)", "SIH", r"^TXTPROC_\d+_{comp}[a-z]?\.zip$"),
    ("BDSIA (SIA)", "SIA", r"^BDSIA{comp}[a-z]?\.exe$"),
]


class ArquivoRecusado(ValueError):
    pass


def validar_competencia(aaaamm: str) -> str:
    if not re.fullmatch(r"20\d{2}(0[1-9]|1[0-2])", aaaamm or ""):
        raise ArquivoRecusado(f"competência inválida: {aaaamm!r} (use AAAAMM)")
    return aaaamm


def apresentacao(aaaamm: str) -> str:
    """Competência + 1 mês (AAAAMM), a regra do SISAIH01/WebAIH."""
    ano, mes = int(aaaamm[:4]), int(aaaamm[4:])
    return f"{ano + mes // 12}{mes % 12 + 1:02d}"


def pasta_entrada() -> Path:
    import yaml
    if str(DOWNLOADS) not in sys.path:
        sys.path.insert(0, str(DOWNLOADS))
    from autosus.comum import resolver_destino
    with open(DOWNLOADS / "config.yaml", encoding="utf-8") as f:
        return resolver_destino(yaml.safe_load(f)["pasta_destino"])


def pasta_saida(aaaamm: str) -> Path:
    return PASTA / "saida" / apresentacao(aaaamm)


def destino(nome: str, aaaamm: str, base: Path) -> Path:
    """Onde guardar o arquivo; recusa nomes desconhecidos ou de outra competência."""
    if Path(nome).name != nome:
        raise ArquivoRecusado("o nome do arquivo não pode ter pasta")
    for padrao, grupo in REGRAS:
        m = re.match(padrao, nome, re.IGNORECASE)
        if not m:
            continue
        if grupo == "programas":
            return base / "programas" / nome
        comp = m.groupdict().get("comp")
        if comp and comp != aaaamm:
            raise ArquivoRecusado(f"{nome} é da competência {comp}, não de {aaaamm}")
        apres = m.groupdict().get("apres")
        if apres and apres != apresentacao(aaaamm):
            raise ArquivoRecusado(f"{nome} é da apresentação {apres}; a competência {aaaamm} "
                                  f"apresenta em {apresentacao(aaaamm)}")
        return base / f"{aaaamm[:4]}-{aaaamm[4:]}" / grupo / nome
    raise ArquivoRecusado(f"arquivo não reconhecido: {nome}")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def gravar(nome: str, aaaamm: str, fluxo, sha_esperado: str | None, base: Path | None = None) -> dict:
    """Grava o arquivo recebido conferindo o SHA-256. Se já existe igual, não muda nada; se existe
    diferente, o anterior fica guardado com _anterior_<data> no nome (como faz o downloader)."""
    base = base or pasta_entrada()
    alvo = destino(nome, aaaamm, base)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_name(alvo.name + ".recebendo")
    h, tamanho = hashlib.sha256(), 0
    with open(tmp, "wb") as f:
        for bloco in iter(lambda: fluxo.read(1 << 20), b""):
            h.update(bloco)
            tamanho += len(bloco)
            f.write(bloco)
    recebido = h.hexdigest()
    if sha_esperado and recebido.lower() != sha_esperado.lower():
        tmp.unlink()
        raise ArquivoRecusado(f"SHA-256 não confere: recebido {recebido}, esperado {sha_esperado}")
    if alvo.exists():
        if sha256(alvo) == recebido:
            tmp.unlink()
            return {"nome": nome, "caminho": str(alvo), "sha256": recebido, "tamanho": tamanho, "situacao": "ja_existe"}
        carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        alvo.rename(alvo.with_name(f"{alvo.stem}_anterior_{carimbo}{alvo.suffix}"))
        situacao = "substituido"
    else:
        situacao = "novo"
    tmp.replace(alvo)
    return {"nome": nome, "caminho": str(alvo), "sha256": recebido, "tamanho": tamanho, "situacao": situacao}


def _info(p: Path) -> dict:
    st = p.stat()
    return {"nome": p.name, "tamanho": st.st_size,
            "modificado": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


def situacao_entrada(aaaamm: str, base: Path | None = None) -> dict:
    """Itens necessários da competência: o arquivo mais recente de cada um, ou o que falta."""
    base = base or pasta_entrada()
    pasta_comp = base / f"{aaaamm[:4]}-{aaaamm[4:]}"
    itens = []
    for rotulo, grupo, padrao in NECESSARIOS:
        rx = re.compile(padrao.format(comp=aaaamm, apres=apresentacao(aaaamm)), re.IGNORECASE)
        pasta = pasta_comp / grupo
        achados = sorted((p for p in pasta.glob("*") if p.is_file() and rx.match(p.name)),
                         key=lambda p: p.stat().st_mtime) if pasta.is_dir() else []
        itens.append({"item": rotulo, "arquivo": _info(achados[-1]) if achados else None})
    programas = base / "programas"
    lista = sorted((_info(p) for p in programas.glob("*.exe")), key=lambda i: i["nome"]) if programas.is_dir() else []
    return {"competencia": aaaamm, "apresentacao": apresentacao(aaaamm),
            "completo": all(i["arquivo"] for i in itens), "itens": itens, "programas": lista}


def listar_saidas(aaaamm: str) -> list[dict]:
    pasta = pasta_saida(aaaamm)
    if not pasta.is_dir():
        return []
    return [_info(p) | {"sha256": sha256(p)} for p in sorted(pasta.iterdir()) if p.is_file() and not p.name.startswith(".")]
