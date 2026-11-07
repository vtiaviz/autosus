"""Tipos e funcoes compartilhadas."""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Situacoes possiveis de cada item
BAIXADO = "baixado"
JA_EXISTE = "ja_existe"
PENDENTE = "pendente"      # ainda nao publicado
SIMULADO = "simulado"      # --simular: baixaria
ERRO = "erro"

OK = {BAIXADO, JA_EXISTE}


@dataclass
class Resultado:
    nome: str
    status: str
    arquivo: str = ""
    detalhe: str = ""
    revisao_nova: bool = False   # letra nova ou versao nova em relacao ao ultimo download
    tamanho: int = 0

    def linha(self) -> str:
        rotulo = {
            BAIXADO: "BAIXADO",
            JA_EXISTE: "ja existe",
            PENDENTE: "PENDENTE",
            SIMULADO: "baixaria",
            ERRO: "ERRO",
        }.get(self.status, self.status)
        extra = " (NOVA REVISAO/VERSAO)" if self.revisao_nova else ""
        txt = f"{self.nome:<10} {rotulo:<10} {self.arquivo}{extra}"
        if self.detalhe:
            txt += f"  - {self.detalhe}"
        return txt


def competencia_padrao(hoje: dt.date | None = None) -> str:
    """Mes anterior ao atual, no formato AAAAMM."""
    hoje = hoje or dt.date.today()
    primeiro = hoje.replace(day=1)
    anterior = primeiro - dt.timedelta(days=1)
    return f"{anterior.year:04d}{anterior.month:02d}"


def validar_competencia(valor: str) -> str:
    if not re.fullmatch(r"\d{6}", valor or ""):
        raise ValueError(f"Competencia invalida: {valor!r}. Use AAAAMM, ex.: 202502")
    mes = int(valor[4:])
    if not 1 <= mes <= 12:
        raise ValueError(f"Mes invalido na competencia {valor}")
    return valor


def montar_padrao(padrao: str, **valores: str) -> re.Pattern:
    """Troca {competencia}, {uf}, {municipio} sem mexer em quantificadores como \\d{4}."""
    for chave, valor in valores.items():
        padrao = padrao.replace("{" + chave + "}", re.escape(valor))
    return re.compile(padrao, re.IGNORECASE)


def chave_letra(letra: str | None) -> tuple:
    """Ordem: sem letra < a < b < ... < z."""
    letra = (letra or "").lower()
    return (len(letra), letra)


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def validar_arquivo(caminho: Path) -> None:
    """Testa a integridade de ZIPs. Levanta ValueError se estiver corrompido.

    Alguns ZIPs do DATASUS (ex.: DSIHD017) sao protegidos por senha: neles so da
    para conferir a estrutura do arquivo (indice e cabecalhos), nao o conteudo.
    """
    if not (caminho.suffix.lower() == ".zip" or caminho.name.lower().endswith(".zip.part")):
        return
    try:
        with zipfile.ZipFile(caminho) as z:
            itens = z.infolist()
            if not itens:
                raise ValueError("ZIP vazio")
            for info in itens:
                if info.flag_bits & 0x1:      # criptografado: so a estrutura e conferida
                    continue
                with z.open(info) as f:       # le tudo; o zipfile confere o CRC no fim
                    while f.read(1 << 20):
                        pass
    except ValueError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, NotImplementedError) as e:
        raise ValueError(f"ZIP invalido: {e}") from e


def guardar_anterior(caminho: Path) -> Path | None:
    """Renomeia um arquivo existente para nao sobrescreve-lo."""
    if not caminho.exists():
        return None
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    novo = caminho.with_name(f"{caminho.stem}_anterior_{carimbo}{caminho.suffix}")
    caminho.rename(novo)
    return novo


def pasta_area_de_trabalho() -> Path:
    """Caminho real da Area de Trabalho no Windows (inclusive OneDrive)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_DESKTOPDIRECTORY = 0x10
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:
            pass
    return Path(os.path.expanduser("~")) / "Desktop"


def resolver_destino(texto: str) -> Path:
    if texto.startswith("AREA_DE_TRABALHO"):
        resto = texto[len("AREA_DE_TRABALHO"):].lstrip("/\\")
        return pasta_area_de_trabalho() / resto
    return Path(os.path.expandvars(os.path.expanduser(texto)))


def formatar_tamanho(n: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024
    return str(n)
