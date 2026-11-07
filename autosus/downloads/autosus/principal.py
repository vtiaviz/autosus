"""Ponto de entrada: autosus.bat [AAAAMM] [opcoes]."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .comum import (BAIXADO, ERRO, OK, PENDENTE, Resultado, competencia_padrao, formatar_tamanho,
                    resolver_destino, validar_competencia)
from .manifesto import Manifesto

BASE = Path(__file__).resolve().parent.parent
log = logging.getLogger("autosus")


def configurar_logs(pasta_logs: Path, manter_dias: int) -> Path:
    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_logs / f"autosus_{dt.date.today():%Y-%m-%d}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    fh = logging.FileHandler(arquivo, encoding="utf-8")
    fh.setFormatter(fmt)
    raiz.addHandler(fh)
    if sys.stdout is not None:      # pythonw (agendamento) nao tem console
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(message)s"))
        raiz.addHandler(sh)
    limite = dt.datetime.now() - dt.timedelta(days=manter_dias)
    for antigo in pasta_logs.glob("autosus_*.log"):
        if dt.datetime.fromtimestamp(antigo.stat().st_mtime) < limite:
            antigo.unlink(missing_ok=True)
    return arquivo


def carregar_config(caminho: Path) -> dict:
    import yaml
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")
    except ImportError:
        pass


def executar_item(nome: str, funcao, *args) -> Resultado:
    """Um erro inesperado num arquivo nao interrompe os demais."""
    try:
        return funcao(*args)
    except Exception as e:
        log.exception("%s: erro inesperado", nome)
        return Resultado(nome, ERRO, detalhe=f"erro inesperado: {e}")


def montar_resumo(competencia: str, resultados: list[Resultado], destino: Path) -> str:
    linhas = [f"AutoSUS - competencia {competencia[4:]}/{competencia[:4]}",
              f"Pasta: {destino}", ""]
    linhas += [r.linha() for r in resultados]
    total = sum(r.tamanho for r in resultados if r.status == BAIXADO)
    linhas += ["", f"Baixados nesta execucao: {sum(r.status == BAIXADO for r in resultados)} "
                   f"({formatar_tamanho(total)})"]
    return "\n".join(linhas)


def gravar_json(destino: Path, competencia: str, raiz: Path, simulado: bool, resultados: list[Resultado],
                cfg: dict, man_comp: Manifesto, man_prog: Manifesto) -> None:
    """Resultado da execucao para o AutoSUS: um item por arquivo/programa, com o que o manifesto sabe."""
    programas = {i["nome"] for i in (cfg.get("programas") or []) + (cfg.get("programas_http") or [])}
    itens = []
    for r in resultados:
        tipo = "programa" if r.nome in programas else "arquivo"
        reg = (man_prog if tipo == "programa" else man_comp).item(r.nome) or {}
        itens.append({"nome": r.nome, "tipo": tipo, "situacao": r.status, "arquivo": r.arquivo or reg.get("arquivo", ""),
                      "detalhe": r.detalhe, "revisao_nova": r.revisao_nova,
                      "tamanho": r.tamanho or reg.get("tamanho") or 0, "sha256": reg.get("sha256"),
                      "versao": reg.get("versao") or ""})
    dados = {"competencia": competencia, "pasta": str(raiz), "simulado": simulado,
             "gerado_em": dt.datetime.now().isoformat(timespec="seconds"), "itens": itens}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autosus", description="Download mensal dos arquivos SIH/SIA/CNES.")
    ap.add_argument("competencia", nargs="?", help="AAAAMM (padrao: mes anterior)")
    ap.add_argument("--somente", help="itens separados por virgula, ex.: FORNEC,TXTPROC")
    ap.add_argument("--simular", action="store_true", help="so mostra o que baixaria")
    ap.add_argument("--versao", action="append", default=[], metavar="PROGRAMA=NNNN",
                    help="baixa uma versao especifica de um programa, ex.: --versao SISAIH01=2520")
    ap.add_argument("--mostrar-navegador", action="store_true", help="abre o navegador visivel no portal CNES")
    ap.add_argument("--diagnostico-cnes", action="store_true", help="lista os campos da tela de login do CNES")
    ap.add_argument("--testar-aviso", action="store_true", help="envia notificacao e e-mail de teste")
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--json", metavar="ARQUIVO", help="grava o resultado (itens e situacao) em JSON, para o AutoSUS")
    args = ap.parse_args(argv)

    carregar_env()
    cfg = carregar_config(Path(args.config))
    configurar_logs(BASE / "logs", int((cfg.get("logs") or {}).get("manter_dias", 365)))
    log.info("===== AutoSUS %s - inicio =====", __version__)

    cfg_aviso = cfg.get("aviso") or {}
    if args.testar_aviso:
        from .aviso import avisar
        ok = avisar(cfg_aviso, "AutoSUS - teste", "Se voce recebeu isto, os avisos funcionam.",
                    "Mensagem de teste do AutoSUS. Os avisos estao configurados corretamente.")
        return 0 if ok else 1

    if args.diagnostico_cnes:
        from .portal_cnes import diagnosticar
        diagnosticar(cfg["cnes_portal"], BASE / "logs")
        return 0

    try:
        competencia = validar_competencia(args.competencia) if args.competencia else competencia_padrao()
    except ValueError as e:
        log.error(str(e))
        return 2
    somente = {s.strip().upper() for s in args.somente.split(",")} if args.somente else None
    quer = lambda nome: somente is None or nome.upper() in somente

    uf, municipio = str(cfg["uf"]), str(cfg["municipio"])
    raiz = resolver_destino(cfg["pasta_destino"])
    pasta_comp = raiz / f"{competencia[:4]}-{competencia[4:]}"
    pasta_prog = raiz / "programas"
    log.info("Competencia %s | destino %s%s", competencia, raiz, " | SIMULACAO" if args.simular else "")

    man_comp = Manifesto(pasta_comp / "manifesto.json", competencia=competencia)
    man_prog = Manifesto(pasta_prog / "manifesto.json")
    cfg_ftp = cfg.get("ftp") or {}
    resultados: list[Resultado] = []

    from .fonte_ftp import verificar_competencia, verificar_programa
    versoes = {}
    for v in args.versao:
        nome, _, num = v.partition("=")
        if not num.isdigit():
            log.error("--versao invalido: %s (use PROGRAMA=NNNN, ex.: SISAIH01=2520)", v)
            return 2
        versoes[nome.strip().upper()] = num
    if versoes:                       # so os programas pedidos, na versao pedida
        somente = set(versoes)
    for item in cfg.get("programas") or []:
        if quer(item["nome"]):
            resultados.append(executar_item(item["nome"], verificar_programa, item, pasta_prog, man_prog,
                                            cfg_ftp, args.simular, versoes.get(item["nome"].upper())))
    for item in cfg.get("arquivos_competencia") or []:
        if quer(item["nome"]):
            resultados.append(executar_item(item["nome"], verificar_competencia, item, competencia, uf,
                                            municipio, pasta_comp / item.get("grupo", ""), man_comp,
                                            cfg_ftp, args.simular))
    from .fonte_http import verificar_programa_http
    for item in cfg.get("programas_http") or []:
        if quer(item["nome"]):
            resultados.append(executar_item(item["nome"], verificar_programa_http, item, pasta_prog, man_prog,
                                            cfg.get("http") or {}, args.simular, BASE / "logs"))
    portal = cfg.get("cnes_portal") or {}
    if portal.get("ativo", True) and quer(portal.get("nome", "TXTPROC")):
        from .portal_cnes import baixar_txtproc
        cred = {"usuario": os.getenv("CNES_USUARIO", "").strip(), "senha": os.getenv("CNES_SENHA", ""),
                "cpf": "".join(ch for ch in os.getenv("CNES_CPF", "") if ch.isdigit())}
        resultados.append(executar_item(portal.get("nome", "TXTPROC"), baixar_txtproc, portal, competencia,
                                        municipio, pasta_comp / portal.get("grupo", ""), man_comp, cred,
                                        BASE / "logs", args.simular, args.mostrar_navegador))

    webaih = cfg.get("webaih") or {}
    if webaih.get("ativo", False) and quer(webaih.get("nome", "WEBAIH")):
        from .webaih import baixar_webaih
        cred_w = {"usuario": os.getenv("WEBAIH_USUARIO", "").strip(), "senha": os.getenv("WEBAIH_SENHA", "")}
        resultados.append(executar_item(webaih.get("nome", "WEBAIH"), baixar_webaih, webaih, competencia,
                                        pasta_comp / webaih.get("grupo", "SIH"), man_comp, cred_w,
                                        BASE / "logs", args.simular))

    resumo = montar_resumo(competencia, resultados, raiz)
    log.info("\n%s", resumo)
    # o AutoSUS (api) le estado\AAAAMM.json para mostrar as atualizacoes, venha a execucao de onde vier
    # (tarefa agendada, autosus.bat ou o proprio AutoSUS); a simulacao so grava com --json
    json_destino = Path(args.json) if args.json else (None if args.simular else BASE / "estado" / f"{competencia}.json")
    if json_destino:
        gravar_json(json_destino, competencia, raiz, args.simular, resultados, cfg, man_comp, man_prog)

    if not args.simular:
        # salva o manifesto mesmo que algo tenha dado errado acima
        man_comp.salvar()
        man_prog.salvar()
        # Aviso so na execucao completa (sem --somente), quando todos os itens estao ok
        completo = somente is None and resultados and all(r.status in OK for r in resultados)
        revisoes = [r for r in resultados if r.status == BAIXADO and r.revisao_nova]
        if completo and not man_comp.notificado:
            from .aviso import avisar
            if avisar(cfg_aviso, f"AutoSUS: competencia {competencia[4:]}/{competencia[:4]} completa",
                      f"Todos os {len(resultados)} arquivos foram baixados.", resumo) or not cfg_aviso.get("email", True):
                man_comp.marcar_notificado()
                man_comp.salvar()
        elif man_comp.notificado and revisoes:
            from .aviso import avisar
            nomes = ", ".join(r.arquivo for r in revisoes)
            avisar(cfg_aviso, f"AutoSUS: nova revisao {competencia[4:]}/{competencia[:4]}",
                   f"Arquivos atualizados: {nomes}", resumo)
        elif not completo:
            faltam = [r.nome for r in resultados if r.status not in OK]
            log.info("Faltam: %s. Nova verificacao na proxima execucao.", ", ".join(faltam) or "-")

    log.info("===== fim =====")
    return 1 if any(r.status == ERRO for r in resultados) else 0
