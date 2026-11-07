"""Download do TXTPROC no portal do gestor do CNES (login com usuario, senha e CPF)."""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
from pathlib import Path
from urllib.parse import urljoin

from .comum import (BAIXADO, ERRO, JA_EXISTE, PENDENTE, SIMULADO, Resultado,
                    guardar_anterior, sha256, validar_arquivo)
from .manifesto import Manifesto

log = logging.getLogger("autosus.cnes")

COMBO = 'select[name="ComboCompetencia"]'

# Lista os campos de formulario e links de todas as frames (para diagnostico e deteccao)
_JS_CAMPOS = """() => Array.from(document.querySelectorAll('input, select, button')).map((e, i) => ({
  i, tag: e.tagName.toLowerCase(), type: (e.type || '').toLowerCase(), name: e.name || '',
  id: e.id || '', value: (e.type === 'password') ? '' : (e.value || '').slice(0, 40),
  visivel: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
}))"""


class ErroPortal(Exception):
    pass


def _todas_frames(page):
    return [page.main_frame] + [f for f in page.frames if f != page.main_frame]


def _achar(page, seletor: str):
    """Procura o seletor na pagina e em todas as frames."""
    for frame in _todas_frames(page):
        loc = frame.locator(seletor)
        try:
            if loc.count() > 0:
                return frame, loc.first
        except Exception:
            continue
    return None, None


def _seletor_campo(campo: dict) -> str:
    if campo["name"]:
        return f'{campo["tag"]}[name="{campo["name"]}"]'
    if campo["id"]:
        return f'#{campo["id"]}'
    return f'{campo["tag"]}[type="{campo["type"]}"]'


def _detectar_login(page, seletores: dict) -> tuple:
    """Descobre os campos usuario/senha/cpf/entrar. Seletores do config.yaml tem prioridade."""
    for frame in _todas_frames(page):
        try:
            campos = frame.evaluate(_JS_CAMPOS)
        except Exception:
            continue
        visiveis = [c for c in campos if c["visivel"]]
        rotulo = lambda c: (c["name"] + " " + c["id"]).lower()
        digitaveis = [c for c in visiveis if c["tag"] == "input"
                      and c["type"] in ("text", "tel", "number", "password", "")]
        # O CPF pode ser campo de texto ou de senha (no portal CNES e "password")
        cpf = next((c for c in digitaveis if "cpf" in rotulo(c)), None)
        senha = next((c for c in digitaveis if c is not cpf and c["type"] == "password"
                      and re.search(r"senha|pass|pwd", rotulo(c))), None) \
            or next((c for c in digitaveis if c is not cpf and c["type"] == "password"), None)
        if not senha and not seletores.get("senha"):
            continue
        textos = [c for c in digitaveis if c["type"] != "password" and c is not cpf]
        usuario = next((c for c in textos if re.search(r"usu|login|user|nome", rotulo(c))), None)
        restantes = [c for c in textos if c is not usuario]
        if usuario is None and restantes:
            usuario = restantes.pop(0)
        if cpf is None and restantes:
            cpf = restantes.pop(0)
        entrar = next((c for c in visiveis if c["type"] in ("submit", "image")
                       or (c["tag"] == "button" and c["type"] != "reset")), None)
        sel = {
            "usuario": seletores.get("usuario") or (usuario and _seletor_campo(usuario)),
            "senha": seletores.get("senha") or (senha and _seletor_campo(senha)),
            "cpf": seletores.get("cpf") or (cpf and _seletor_campo(cpf)),
            "entrar": seletores.get("entrar") or (entrar and _seletor_campo(entrar)),
        }
        return frame, sel
    raise ErroPortal("formulario de login nao encontrado na pagina")


def _salvar_diagnostico(page, pasta_logs: Path, motivo: str, nivel: int = logging.ERROR) -> None:
    carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_logs.mkdir(parents=True, exist_ok=True)
    try:
        png = pasta_logs / f"cnes_{carimbo}.png"
        page.screenshot(path=str(png), full_page=True)
        html = pasta_logs / f"cnes_{carimbo}.html"
        partes = []
        for frame in _todas_frames(page):
            try:
                partes.append(f"<!-- frame: {frame.url} -->\n{frame.content()}")
            except Exception:
                pass
        html.write_text("\n\n".join(partes), encoding="utf-8")
        log.log(nivel, "  %s. Captura salva em %s e %s", motivo, png.name, html.name)
    except Exception as e:
        log.error("  %s (nao foi possivel salvar captura: %s)", motivo, e)


def _login(page, cfg: dict, cred: dict) -> None:
    frame, sel = _detectar_login(page, cfg.get("seletores") or {})
    log.info("  campos de login: %s", {k: v for k, v in sel.items()})
    faltando = [k for k in ("usuario", "senha", "cpf") if not sel.get(k)]
    if faltando:
        raise ErroPortal(f"nao identifiquei os campos {faltando}; rode --diagnostico-cnes "
                         "e preencha cnes_portal.seletores no config.yaml")
    frame.fill(sel["usuario"], cred["usuario"])
    frame.fill(sel["cpf"], cred["cpf"])
    frame.fill(sel["senha"], cred["senha"])
    if sel.get("entrar"):
        frame.click(sel["entrar"])
    else:
        frame.press(sel["senha"], "Enter")
    page.wait_for_load_state("load")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


def _link_txtproc(page, nome_base: str):
    regex = re.compile(re.escape(nome_base), re.IGNORECASE)
    for frame in _todas_frames(page):
        loc = frame.locator("a", has_text=regex)
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def _selecionar(frame, combo, competencia: str, enviar: bool) -> None:
    """Escolhe a competencia; espera a pagina recarregar se o combo/formulario navegar."""
    try:
        with frame.expect_navigation(timeout=15000):
            combo.select_option(competencia)
            if enviar:
                combo.evaluate("s => s.form && s.form.submit()")
    except Exception:
        pass   # sem navegacao (pagina atualiza sem recarregar)
    try:
        frame.page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass


def _esperar_link(page, nome_base: str, segundos: int):
    import time
    fim = time.monotonic() + segundos
    while True:
        link = _link_txtproc(page, nome_base)
        if link is not None or time.monotonic() > fim:
            return link
        page.wait_for_timeout(500)


def baixar_txtproc(cfg: dict, competencia: str, municipio: str, pasta_local: Path, manifesto: Manifesto,
                   cred: dict, pasta_logs: Path, simular: bool, mostrar_navegador: bool = False) -> Resultado:
    nome_item = cfg.get("nome", "TXTPROC")
    nome_base = cfg["arquivo"].replace("{municipio}", municipio).replace("{competencia}", competencia)
    registro = manifesto.item(nome_item)
    if registro and (pasta_local / registro["arquivo"]).exists():
        log.info("%s: %s ja existe localmente", nome_item, registro["arquivo"])
        return Resultado(nome_item, JA_EXISTE, registro["arquivo"], tamanho=registro.get("tamanho", 0))

    faltando = [k for k in ("usuario", "senha", "cpf") if not cred.get(k)]
    if faltando:
        return Resultado(nome_item, ERRO, detalhe=f"preencha no .env: {', '.join('CNES_' + k.upper() for k in faltando)}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return Resultado(nome_item, ERRO, detalhe="Playwright nao instalado (rode instalar.bat)")

    log.info("%s: acessando o portal do CNES", nome_item)
    timeout_ms = int(cfg.get("timeout_segundos", 90)) * 1000
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=not (mostrar_navegador or cfg.get("mostrar_navegador")),
                                       executable_path=os.getenv("AUTOSUS_CHROMIUM") or None)
        contexto = navegador.new_context(accept_downloads=True, ignore_https_errors=True)
        page = contexto.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(cfg["url"], wait_until="load")
            _login(page, cfg, cred)

            frame_combo, combo = _achar(page, COMBO)
            if combo is None:
                _salvar_diagnostico(page, pasta_logs, "combo de competencia nao apareceu apos o login "
                                    "(usuario/senha/CPF incorretos?)")
                return Resultado(nome_item, ERRO, detalhe="login falhou ou pagina mudou; veja a captura na pasta logs")

            valores = combo.locator("option").evaluate_all("os => os.map(o => o.value)")
            if competencia not in valores:
                log.info("  competencia %s ainda nao disponivel (ultimas: %s)", competencia, valores[:3])
                return Resultado(nome_item, PENDENTE, detalhe="competencia ainda nao disponivel no portal")

            # O combo do portal apenas navega para ...?VComp=AAAAMM; vamos direto para essa pagina
            url_comp = cfg.get("url_competencia")
            if url_comp:
                page.goto(urljoin(page.url, url_comp.replace("{competencia}", competencia)), wait_until="load")
                link = _esperar_link(page, nome_base, segundos=10)
            else:
                link = None
            if link is None:
                frame_combo, combo = _achar(page, COMBO)
                if combo is not None:
                    _selecionar(frame_combo, combo, competencia, enviar=False)
                    link = _esperar_link(page, nome_base, segundos=15)
            if link is None:   # o combo nao enviou sozinho: envia o formulario
                frame_combo, combo = _achar(page, COMBO)
                if combo is not None:
                    _selecionar(frame_combo, combo, competencia, enviar=True)
                    link = _esperar_link(page, nome_base, segundos=15)
            if link is None:
                _salvar_diagnostico(page, pasta_logs, f"link {nome_base} nao encontrado")
                return Resultado(nome_item, PENDENTE, detalhe="link do arquivo nao apareceu")

            nome_arquivo = re.sub(r"\s+", "", link.inner_text()) or f"{nome_base}.ZIP"
            href = link.get_attribute("href") or ""
            log.info("  encontrado %s", nome_arquivo)
            if simular:
                return Resultado(nome_item, SIMULADO, nome_arquivo, "baixaria")

            destino = pasta_local / nome_arquivo
            pasta_local.mkdir(parents=True, exist_ok=True)
            parcial = destino.with_name(destino.name + ".part")

            resposta = contexto.request.get(urljoin(page.url, href), timeout=600000)
            corpo = resposta.body() if resposta.ok else b""
            if corpo[:2] == b"PK":
                parcial.write_bytes(corpo)
            else:   # plano B: clicar no link como uma pessoa faria
                log.info("  download direto falhou (HTTP %s); tentando pelo clique", resposta.status)
                with page.expect_download(timeout=600000) as info:
                    link.click()
                info.value.save_as(str(parcial))

            validar_arquivo(parcial)
            if destino.exists():
                guardar_anterior(destino)
            parcial.replace(destino)
            tamanho = destino.stat().st_size
            manifesto.registrar(nome_item, arquivo=nome_arquivo, tamanho=tamanho, sha256=sha256(destino),
                                origem=cfg["url"], versao="")
            log.info("  baixado %s (%d bytes)", nome_arquivo, tamanho)
            return Resultado(nome_item, BAIXADO, nome_arquivo, tamanho=tamanho)
        except ErroPortal as e:
            _salvar_diagnostico(page, pasta_logs, str(e))
            return Resultado(nome_item, ERRO, detalhe=str(e))
        except Exception as e:
            _salvar_diagnostico(page, pasta_logs, f"erro inesperado: {e}")
            return Resultado(nome_item, ERRO, detalhe=str(e).splitlines()[0][:200])
        finally:
            contexto.close()
            navegador.close()


def diagnosticar(cfg: dict, pasta_logs: Path) -> None:
    """Abre o portal com janela, lista os campos e salva captura + HTML."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=False)
        page = navegador.new_page()
        page.goto(cfg["url"], wait_until="load")
        for frame in _todas_frames(page):
            log.info("Frame: %s", frame.url)
            for c in frame.evaluate(_JS_CAMPOS):
                log.info("  %s", c)
        _salvar_diagnostico(page, pasta_logs, "diagnostico concluido", logging.INFO)
        input("Confira o navegador aberto e pressione Enter para fechar...")
        navegador.close()
