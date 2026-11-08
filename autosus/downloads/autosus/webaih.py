"""Download do arquivo de importacao do SISAIH01 gerado pelo WebAIH (Exportar SISAIH01)."""
from __future__ import annotations

import http.cookiejar
import logging
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

from .comum import (BAIXADO, ERRO, JA_EXISTE, PENDENTE, SIMULADO, Resultado,
                    formatar_tamanho, guardar_anterior, sha256)
from .manifesto import Manifesto

log = logging.getLogger("autosus.webaih")

MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
TAM_REGISTRO = 1800


class ErroWebAIH(Exception):
    pass


class Sessao:
    def __init__(self, base: str, timeout: int):
        self.base = base.rstrip("/") + "/"
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.opener.addheaders = [("User-Agent", "AutoSUS")]

    def pedir(self, caminho: str, dados: dict | None = None):
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        return self.opener.open(self.base + caminho.lstrip("/"), data=corpo, timeout=self.timeout)


def _texto(resp) -> str:
    return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")


def _competencia_de(rotulo: str) -> str | None:
    """'08 / 2026', 'Agosto / 2026', 'ago/2026' -> '202608'."""
    m = re.search(r"([A-Za-zçÇ]+|\d{1,2})\s*/\s*(\d{2,4})", unescape(rotulo))
    if not m:
        return None
    mes_txt, ano = m.group(1), int(m.group(2))
    mes = int(mes_txt) if mes_txt.isdigit() else MESES.get(mes_txt[:3].lower())
    if not mes or not 1 <= mes <= 12:
        return None
    if ano < 100:
        ano += 2000
    return f"{ano:04d}{mes:02d}"


def _codigos_competencia(html: str) -> dict[str, str]:
    """AAAAMM -> cod_competencia, a partir dos <option> da tela de competencias."""
    out = {}
    for valor, rotulo in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', html, re.IGNORECASE):
        comp = _competencia_de(rotulo)
        if comp:
            out.setdefault(comp, valor)
    return out


def _validar_sisaih01(conteudo: bytes) -> int:
    linhas = conteudo.split(b"\r\n")
    if linhas and linhas[-1] == b"":
        linhas.pop()
    if not linhas or any(len(l) != TAM_REGISTRO for l in linhas):
        raise ErroWebAIH("o arquivo recebido nao esta no layout SISAIH01 (1800 posicoes por linha)")
    return len(linhas)


def baixar_webaih(cfg: dict, competencia: str, pasta: Path, manifesto: Manifesto, cred: dict,
                  pasta_logs: Path, simular: bool) -> Resultado:
    nome = cfg.get("nome", "WEBAIH")
    if not cred.get("usuario") or not cred.get("senha"):
        return Resultado(nome, ERRO, detalhe="WEBAIH_USUARIO/WEBAIH_SENHA nao preenchidos no .env")
    log.info("%s: acessando %s", nome, cfg["url"])
    s = Sessao(cfg["url"], int(cfg.get("timeout_segundos", 90)))
    try:
        resp = s.pedir("admin/acesso/logar", {"login": cred["usuario"], "senha": cred["senha"]})
        if "/acesso" in resp.geturl():
            raise ErroWebAIH("login recusado: confira WEBAIH_USUARIO e WEBAIH_SENHA no .env")
        resp.read()
        html = _texto(s.pedir("admin/formularios"))
        codigos = _codigos_competencia(html)
        if competencia not in codigos:
            disp = ", ".join(sorted(codigos)) or "nenhuma"
            log.info("  competencia %s nao cadastrada no WebAIH (disponiveis: %s)", competencia, disp)
            return Resultado(nome, PENDENTE, detalhe="competencia ainda nao cadastrada no WebAIH")
        cod = codigos[competencia]
        if simular:
            return Resultado(nome, SIMULADO, f"competencia {competencia} (cod {cod})")

        resp = s.pedir(f"admin/exportar/{cod}", {"acao": "baixar", "apresentacao": cfg.get("apresentacao", "")})
        disp = resp.headers.get("Content-Disposition", "")
        if "attachment" not in disp.lower():
            pagina = _texto(resp)
            pasta_logs.mkdir(parents=True, exist_ok=True)
            arq = pasta_logs / f"webaih_{competencia}_{time.strftime('%Y%m%d_%H%M%S')}.html"
            arq.write_text(pagina, encoding="utf-8")
            m = re.search(r"(\d+)\s*AIH\(s\) com erro", pagina)
            alerta = re.search(r'class="alert alert-danger"[^>]*>(.*?)</div>', pagina, re.S)
            texto_alerta = " ".join(unescape(re.sub(r"<[^>]+>", " ", alerta.group(1))).split()) if alerta else ""
            if texto_alerta:
                det = f"WebAIH: {texto_alerta} (pagina em logs\\{arq.name})"
            elif m:
                det = f"{m.group(1)} AIH(s) com erro no WebAIH: corrija la (relatorio em logs\\{arq.name})"
            elif "Não há formulários" in pagina or "N&atilde;o h&aacute; formul" in pagina:
                det = "nenhum formulario nesta competencia"
            else:
                det = f"o WebAIH nao gerou o arquivo (pagina salva em logs\\{arq.name})"
            log.info("  %s", det)
            return Resultado(nome, PENDENTE, detalhe=det)

        conteudo = resp.read()
        qtd = _validar_sisaih01(conteudo)
        m = re.search(r'filename="?([^";]+)"?', disp)
        arquivo = m.group(1) if m else f"{competencia}_SISAIH01.txt"
    except ErroWebAIH as e:
        log.error("%s: %s", nome, e)
        return Resultado(nome, ERRO, detalhe=str(e))
    except OSError as e:
        log.error("%s: %s", nome, e)
        return Resultado(nome, ERRO, detalhe=f"WebAIH indisponivel: {e}")

    destino = pasta / arquivo
    registro = manifesto.item(nome)
    if destino.exists() and destino.read_bytes() == conteudo:
        log.info("  %s sem alteracoes (%d AIHs)", arquivo, qtd)
        return Resultado(nome, JA_EXISTE, arquivo, detalhe=f"{qtd} AIHs", tamanho=len(conteudo))
    pasta.mkdir(parents=True, exist_ok=True)
    revisao_nova = destino.exists() or bool(registro)
    if destino.exists():
        antigo = guardar_anterior(destino)
        log.info("  producao mudou no WebAIH; versao anterior guardada como %s", antigo.name)
    tmp = destino.with_name(destino.name + ".part")
    tmp.write_bytes(conteudo)
    tmp.replace(destino)
    manifesto.registrar(nome, arquivo=arquivo, tamanho=len(conteudo), sha256=sha256(destino),
                        aihs=qtd, origem=cfg["url"])
    log.info("  baixado %s (%d AIHs, %s)", arquivo, qtd, formatar_tamanho(len(conteudo)))
    return Resultado(nome, BAIXADO, arquivo, detalhe=f"{qtd} AIHs", revisao_nova=revisao_nova,
                     tamanho=len(conteudo))
