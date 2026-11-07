"""Programas publicados em paginas web (ex.: Transmissor): acha o link da maior versao e baixa."""
from __future__ import annotations

import logging
import re
import time
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from .comum import (BAIXADO, ERRO, JA_EXISTE, PENDENTE, SIMULADO, Resultado,
                    formatar_tamanho, guardar_anterior, sha256)
from .manifesto import Manifesto

log = logging.getLogger("autosus.http")

AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoSUS"


def _abrir(url: str, timeout: int, metodo: str = "GET"):
    req = urllib.request.Request(url, method=metodo, headers={"User-Agent": AGENTE})
    return urllib.request.urlopen(req, timeout=timeout)


def _links(html: str, base: str) -> list[str]:
    hrefs = re.findall(r"""href\s*=\s*["']?([^"' >]+)""", html, re.IGNORECASE)
    return [urljoin(base, unescape(h.strip())) for h in hrefs]


def _com_tentativas(cfg: dict, operacao):
    tentativas = int(cfg.get("tentativas", 3))
    ultimo = None
    for n in range(1, tentativas + 1):
        try:
            return operacao()
        except OSError as e:          # inclui URLError, HTTPError, timeout
            ultimo = e
            log.warning("  falha na tentativa %d/%d (%s)", n, tentativas, e)
            if n < tentativas:
                time.sleep(10 * 2 ** (n - 1))
    raise OSError(str(ultimo))


def verificar_programa_http(item: dict, pasta_programas: Path, manifesto: Manifesto, cfg: dict,
                            simular: bool, pasta_logs: Path) -> Resultado:
    """item: nome, pagina (URL da pagina de download), padrao (regex aplicado ao nome do
    arquivo do link, com o grupo 'versao'). Opcional: links_extras (URLs conhecidas, usadas
    tambem como candidatos caso a pagina mude)."""
    nome = item["nome"]
    timeout = int(cfg.get("timeout_segundos", 120))
    padrao = re.compile(item["padrao"], re.IGNORECASE)
    log.info("%s: verificando %s", nome, item["pagina"])

    def listar():
        with _abrir(item["pagina"], timeout) as r:
            bruto = r.read()
            charset = r.headers.get_content_charset() or "latin-1"
        return bruto.decode(charset, errors="replace")

    candidatos = {}
    try:
        html = _com_tentativas(cfg, listar)
        for url in _links(html, item["pagina"]):
            m = padrao.match(url.rsplit("/", 1)[-1].split("?", 1)[0])
            if m:
                candidatos[url] = int(m.group("versao"))
    except OSError as e:
        log.warning("  pagina indisponivel: %s", e)
        html = ""
    for url in item.get("links_extras") or []:
        m = padrao.match(url.rsplit("/", 1)[-1])
        if m:
            candidatos.setdefault(url, int(m.group("versao")))

    if not candidatos:
        if html:
            pasta_logs.mkdir(parents=True, exist_ok=True)
            arq = pasta_logs / f"{nome.lower()}_pagina_{time.strftime('%Y%m%d_%H%M%S')}.html"
            arq.write_text(html, encoding="utf-8")
            log.error("  nenhum link encontrado para %s; pagina salva em %s", padrao.pattern, arq)
            return Resultado(nome, ERRO, detalhe=f"link nao encontrado na pagina (veja {arq.name})")
        return Resultado(nome, ERRO, detalhe="pagina de download indisponivel")

    url, versao = max(candidatos.items(), key=lambda c: c[1])
    arquivo = url.rsplit("/", 1)[-1].split("?", 1)[0]
    destino = pasta_programas / arquivo
    registro = manifesto.item(nome)
    revisao_nova = bool(registro) and registro.get("arquivo", "").lower() != arquivo.lower()
    log.info("  %d candidato(s); escolhido: %s", len(candidatos), arquivo)

    if destino.exists():
        if not registro or registro.get("arquivo") != arquivo:
            manifesto.registrar(nome, arquivo=arquivo, tamanho=destino.stat().st_size,
                                sha256=sha256(destino), origem=url, versao=str(versao))
        log.info("  %s ja existe localmente", arquivo)
        return Resultado(nome, JA_EXISTE, arquivo, tamanho=destino.stat().st_size)
    if simular:
        return Resultado(nome, SIMULADO, arquivo, revisao_nova=revisao_nova)

    def baixar():
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".part")
        inicio = time.monotonic()
        with _abrir(url, timeout) as r, open(parcial, "wb") as f:
            esperado = r.headers.get("Content-Length")
            while bloco := r.read(1 << 16):
                f.write(bloco)
        obtido = parcial.stat().st_size
        if esperado and obtido != int(esperado):
            parcial.unlink(missing_ok=True)
            raise OSError(f"tamanho incompleto: {obtido} de {esperado} bytes")
        with open(parcial, "rb") as f:
            if f.read(2) != b"MZ":
                parcial.unlink(missing_ok=True)
                raise OSError("o arquivo baixado nao e um executavel do Windows")
        guardar_anterior(destino)
        parcial.replace(destino)
        log.info("  baixado %s (%s em %.0fs)", arquivo, formatar_tamanho(obtido), time.monotonic() - inicio)
        return obtido

    try:
        obtido = _com_tentativas(cfg, baixar)
    except OSError as e:
        log.error("%s: %s", nome, e)
        return Resultado(nome, ERRO, arquivo, detalhe=str(e))
    manifesto.registrar(nome, arquivo=arquivo, tamanho=obtido, sha256=sha256(destino), origem=url,
                        versao=str(versao))
    return Resultado(nome, BAIXADO, arquivo, revisao_nova=revisao_nova, tamanho=obtido)
