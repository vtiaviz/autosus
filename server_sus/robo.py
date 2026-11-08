"""AutoSUS - coordenador do robô de processamento (roda no host, fora da VM).

Comandos (robo.bat <comando>):
  status                     estado da VM e do agente
  preparar                   copia o agente para a pasta compartilhada da VM
  iniciar                    liga a VM (se desligada) e espera o agente responder
  ping                       testa a comunicação com o agente
  snapshot [nome]            tira um snapshot da VM (padrão: antes_AAAAMMDD_HHMM)
  snapshots                  lista os snapshots, o tamanho da pasta deles e o espaço livre
  apagar_snapshot <nome...> --confirmar   apaga pontos de retorno (libera disco; a VM atual não muda)
  restaurar <nome> --confirmar   desliga a VM e volta ao snapshot (perde o que foi feito depois dele)
  versoes                    instaladores baixados e a apresentação de cada versão já conhecida
  instalar [SISAIH01 SIHD2] [--versao NNNN] [--pasta "C:\\..."]
                             instala sem telas a maior versão baixada (ou a versão indicada); --pasta
                             procura os instaladores também nessa pasta
  pacotes                    baixa o pywinauto e o pillow (no host) e instala na VM, sem internet na VM
  pacotes --reinstalar pillow  reinstala à força um pacote danificado na VM
  inspecionar [titulo]       grava a árvore de controles das janelas abertas na VM (mapeamento)
  sisaih01 abrir [MM/AAAA]   abre o SISAIH01 (na apresentação indicada), faz login e grava a inspeção
  sisaih01 menus             grava o menu completo do SISAIH01 (com o programa já aberto)
  sisaih01 telas             abre as telas de excluir/importar/consistir/apurar/exportar/relatório,
                             grava os controles e fecha cada uma SEM executar nada
  sisaih01 excluir MM/AAAA --confirmar [--sem-snapshot]
                             apaga a produção da apresentação aberta (snapshot antes; --sem-snapshot
                             reaproveita um snapshot antes_excluir_AAAAMM_* que já exista)
  sisaih01 importar [arquivo]            importa a produção (confere a apresentação do arquivo); sem
                             arquivo, usa o baixado do WebAIH: <downloads>/AAAA-MM/SIH/AAAAMM_SISAIH01_*.txt
  sisaih01 consistir | apurar            roda a consistência / a prévia e grava o histórico
  sisaih01 exportar                      exporta para o SIHD (Secretaria) -> pasta processamento/saida/AAAAMM
  sisaih01 completo MM/AAAA [arquivo] --confirmar [--sem-snapshot]
                             tudo em sequência: abrir, excluir, importar, consistir (para se houver
                             AIH rejeitada), apurar e exportar
  fpo inspecionar            abre o FPO na VM (sem digitar nada) e grava as telas que ele mostrar
  fpo abrir                  abre o FPO, faz o login (FPO_USUARIO/FPO_SENHA do .env) e grava o menu
  fpo fechar                 fecha o FPO (ex.: antes de 'instalar FPO')
  fpo telas                  abre as telas de competência/importações/valores/exportação e fecha SEM executar
  fpo competencia MM/AAAA    altera a competência do FPO (não faz nada se já estiver nela)
  fpo importar_sia MM/AAAA [--pasta X]     descompacta na VM só o BDSIA mais recente (a, b...) e importa
  fpo importar_cnes MM/AAAA [--pasta X]    descompacta TXTPROC_* e TERCEIROSBRASIL* e importa
  fpo valores MM/AAAA        valores vigentes: valores do MS (MAC/FAEC) + 100% Prof. nas eletivas, grava
  fpo exportar MM/AAAA       gera Valores_AAAAMM.VTP -> saida/<apresentação>/
  fpo completo MM/AAAA [--pasta X] [--sem-snapshot]   tudo em sequência (snapshot antes): instala a
                             atualização baixada se for nova, abre (atualiza o banco), competência,
                             SIA, SCNES/Terceiros, valores vigentes e exportar
                             --pasta: onde procurar os arquivos (padrão: <downloads>/AAAA-MM)
  sihd inspecionar           abre o SIHD2 na VM (sem digitar nada) e grava as telas que ele mostrar
  sihd menus                 grava o menu completo do SIHD2 (já aberto e logado)
  sihd importar_cnes MM/AAAA [--pasta X]   importa CNES + Terceiros + importadores + fornecedores + valores (.VTP)
  sihd importar_tabelas      importa as tabelas nacionais (Sim; backup: Não) e espera terminar
  sihd importar_aih MM/AAAA [--pasta X]    copia o DSIHD* para a pasta do SIHD2 e importa o .Zip do SISAIH01
  sihd bloqueadas            percorre Gerenciar Informações e lista as AIHs com pendência (não libera nada)
  sihd liberar <AIH...> --confirmar   libera SÓ as AIHs informadas, Salvar e Sair
  sihd criticar | apurar     Processamento > Criticar / Apurar Valores, espera terminar
  sihd encerrar MM/AAAA --confirmar   encerra a competência e guarda o .DTS em saida/<apresentação>/
  sihd coletar MM/AAAA       só traz o .DTS que o encerramento deixou na VM (não processa nada)
  sihd completo MM/AAAA [--pasta X] [--manual|--auto] [--confirmar] [--a-partir-de ETAPA] [--versao NNNN]
                             SIHD inteiro: instala (se nova), abre/Release, competência, CNES, tabelas, AIH,
                             bloqueadas (--manual: para e lista | --auto: libera todas), crítica, apuração e,
                             com --confirmar, encerramento (.DTS). Snapshot antes (--sem-snapshot evita)
  sihd telas [filtro]        abre as telas de importação/gerenciar/criticar/apurar/encerrar e fecha SEM
                             executar (perguntas ao abrir são respondidas com Não)
  sihd competencia MM/AAAA   Configuração > Abrir Competência (descrição MM/AAAA) e Salvar
  sihd abrir                 abre o SIHD2, faz o login (SIHD_USUARIO/SIHD_SENHA do .env) e, se for a primeira
                             vez da versão, executa o Release (Instalar, Sim, Sair)
  rede [status|ligar|desligar]   conecta/desconecta o cabo de rede virtual da VM (internet só para transmitir)
  transmissor inspecionar    abre o Transmissor na VM (sem digitar nada) e grava as telas
  transmissor procurar       procura onde o Transmissor está instalado na VM (atalhos e pastas)
  transmissor preparar MM/AAAA   preenche tipo, competência, IBGE, CPF, senha e o .DTS e PARA (não envia)
  transmissor testar         liga a rede da VM, clica em Testar Conexão, tira print e desliga a rede
  transmissor enviar --confirmar   liga a rede, clica em Transmitir, tira print do resultado e desliga a rede
  resolucao [LxA]            fixa a resolução da tela da VM (padrão do config_robo.yaml)
  print                      salva um print da tela da VM em logs\\
  desligar                   desliga a VM pelo botão de energia (ACPI)

A comunicação com o agente é por arquivos na pasta compartilhada:
  <compartilhada>\\_robo\\fila\\<id>.json        tarefa pedida pelo host
  <compartilhada>\\_robo\\resultados\\<id>.json  resposta do agente
  <compartilhada>\\_robo\\agente.vivo            batimento do agente (a cada 10 s)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
DOWNLOADS = RAIZ / "autosus" / "downloads"     # downloader do AutoSUS: config.yaml e pacote autosus
sys.path.insert(0, str(DOWNLOADS))
log = logging.getLogger("robo")

from nucleo.config import (ESTADO, carregar_config, credenciais, gravar_estado, ler_estado,  # noqa: E402
                            variavel_env)
from nucleo.fila import Fila  # noqa: E402
from nucleo.vbox import LIMITE_DISCO_GB, VBox, disco_da_vm, tirar_snapshot  # noqa: E402


# ------------------------------------------------------------------ configuração e logs

def configurar_logs() -> Path:
    pasta = PASTA / "logs"
    pasta.mkdir(exist_ok=True)
    arq = pasta / f"robo_{dt.date.today():%Y-%m-%d}.log"
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    fh = logging.FileHandler(arq, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
    raiz.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(message)s"))
    raiz.addHandler(sh)
    return pasta


# ------------------------------------------------------------------ utilidades

def pasta_downloads(cfg: dict) -> Path:
    from autosus.comum import resolver_destino
    return resolver_destino(cfg["_autosus"]["pasta_destino"])


def maior_versao(pasta: Path, padrao: str) -> Path | None:
    rx = re.compile(padrao, re.IGNORECASE)
    candidatos = [(int(m.group("versao")), p) for p in pasta.glob("*") if (m := rx.match(p.name))]
    return max(candidatos)[1] if candidatos else None


def ajustar_resolucao(cfg: dict, vbox: VBox, fila: "Fila | None" = None) -> None:
    """Resolução fixa: as telas do DATASUS não cabem em 640x480 e o robô precisa de um tamanho estável.
    Pede ao Windows da VM (pelo agente), que é o que persiste; o aviso pela VirtualBox é só reforço."""
    res = str(cfg.get("resolucao") or "")
    if "x" not in res:
        return
    largura, altura = (int(v) for v in res.lower().split("x"))
    try:
        vbox.resolucao(largura, altura)
    except RuntimeError:
        pass
    if fila and fila.agente_vivo():
        id_ = fila.pedir("resolucao", largura=largura, altura=altura)
        r = fila.esperar(id_, 30)
        if r and r.get("ok"):
            log.info("Resolução da VM: %s", r["dados"]["resolucao"])
            return
    log.info("Resolução da VM pedida: %dx%d", largura, altura)


def salvar_print(vbox: VBox, pasta_logs: Path, rotulo: str) -> Path | None:
    destino = pasta_logs / f"tela_{rotulo}_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        vbox.print_tela(destino)
        log.info("  print da tela: %s", destino)
        return destino
    except RuntimeError as e:
        log.warning("  não foi possível tirar o print: %s", e)
        return None


# ------------------------------------------------------------------ comandos

def trazer_arquivos(fila: Fila, resposta: dict, pasta_logs: Path) -> None:
    """Copia para processamento\\logs os arquivos que o agente gerou (inspeções, logs de instalação)."""
    producao = set((resposta.get("dados") or {}).get("exportados") or [])   # dados de pacientes: vão para saida\
    for nome in resposta.get("arquivos") or []:
        origem = fila.raiz / "resultados" / nome
        if origem.exists() and nome not in producao:
            shutil.copy2(origem, pasta_logs / nome)
            log.info("  arquivo: %s", pasta_logs / nome)


def executar(fila: Fila, vbox: "VBox", pasta_logs: Path, tipo: str, limite: float, rotulo: str, **parametros):
    """Envia uma tarefa, espera, traz os arquivos e tira um print no final."""
    if not fila.agente_vivo():
        log.error("Agente sem sinal. Rode 'robo.bat iniciar'.")
        return None
    # com o disco cheio a VirtualBox pausa a VM no meio da gravação (já corrompeu o AIH.vbox uma vez):
    # confere o disco onde estão os arquivos da VM (snapshots e disco de trabalho)
    try:
        disco_vm = disco_da_vm(vbox.info())
    except RuntimeError:
        disco_vm = "C:\\"
    livre = shutil.disk_usage(disco_vm).free / 2**30
    if livre < 3:
        log.error("Só %.1f GB livres em %s (onde ficam os arquivos da VM): não vou mandar tarefas para a VM. "
                  "Libere espaço primeiro.", livre, disco_vm)
        return None
    id_ = fila.pedir(tipo, **parametros)
    r = fila.esperar(id_, limite)
    salvar_print(vbox, pasta_logs, rotulo)
    if not r:
        log.error("Sem resposta do agente em %d s.", limite)
        return None
    trazer_arquivos(fila, r, pasta_logs)
    if r.get("erro"):
        log.error("Erro no agente: %s", r["erro"])
        if r.get("traceback"):
            log.error("Detalhe:\n%s", "\n".join(r["traceback"].strip().splitlines()[-12:]))
    return r


def espaco_livre(vbox: "VBox | None" = None) -> None:
    """A VirtualBox pausa a VM sozinha quando o disco onde ela grava enche; vale conferir o C: e,
    se for outro, o disco da VM (pasta de snapshots)."""
    discos = ["C:\\" if sys.platform == "win32" else "/"]
    if vbox:
        try:
            disco = disco_da_vm(vbox.info())
            if disco.upper() not in (d.upper() for d in discos):
                discos.append(disco)
        except RuntimeError:
            pass
    for disco in discos:
        livre = shutil.disk_usage(disco).free / 2**30
        nivel = log.warning if livre < LIMITE_DISCO_GB else log.info
        nivel("Espaço livre no disco %s: %.1f GB%s", disco, livre,
              " (pouco: a VirtualBox pausa a VM quando o disco enche)" if livre < LIMITE_DISCO_GB else "")


def tamanho_pasta(pasta: Path) -> float:
    try:
        return sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file()) / 2**30
    except OSError:
        return 0.0


def cmd_status(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    info = vbox.info()
    log.info("VM %s: %s | memória %s MB | CPUs %s", cfg["vm"], info.get("VMState"), info.get("memory"), info.get("cpus"))
    espaco_livre(vbox)
    log.info("Snapshots: %s", ", ".join(vbox.snapshots()) or "nenhum")
    b = fila.batimento()
    if b:
        log.info("Agente: último sinal há %.0f s | versão %s | Python %s | usuário %s",
                 b["_idade"], b.get("versao"), b.get("python"), b.get("usuario"))
    else:
        log.info("Agente: nunca respondeu (rode 'robo.bat preparar' e instale o agente na VM)")
    pend = list((fila.raiz / "fila").glob("*.json"))
    if pend:
        log.info("Tarefas na fila: %s", ", ".join(p.stem for p in pend))
    return 0


def cmd_preparar(cfg, vbox, fila: Fila, pasta_logs, args) -> int:
    for arq in (PASTA / "agente").iterdir():
        if arq.is_file():
            shutil.copy2(arq, fila.raiz / "agente" / arq.name)
    log.info("Agente copiado para %s", fila.raiz / "agente")
    if fila.agente_vivo():
        r = executar(fila, vbox, pasta_logs, "reiniciar", 60, "reiniciar")
        if r:
            time.sleep(15)
            b = fila.batimento()
            log.info("Agente reiniciado: versão %s", b.get("versao") if b else "?")
    log.info("Na primeira vez, dentro da VM, rode: \\\\VBOXSVR\\%s\\_robo\\agente\\instalar_agente.bat",
             cfg["nome_compartilhamento"])
    return 0


def cmd_iniciar(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    estado = vbox.estado()
    inicio = time.time()
    if estado == "paused":
        log.warning("A VM estava PAUSADA; retomando. Se ela pausar de novo, confira o espaço em disco do host.")
        espaco_livre(vbox)
        vbox.retomar()
    elif estado != "running":
        log.info("Ligando a VM %s (estado atual: %s)...", cfg["vm"], estado)
        vbox.ligar(cfg.get("abrir_vm", "gui"))
    limite = int(cfg["tempo_limite"]["iniciar_vm_segundos"])
    fim = time.time() + limite
    while time.time() < fim:
        b = fila.batimento()
        # com a VM recém-ligada, só vale um batimento gravado depois deste comando
        novo = b and (estado == "running" or time.time() - b["_idade"] > inicio)
        if novo and fila.agente_vivo() and vbox.estado() == "running":
            log.info("Agente respondendo (versão %s).", b.get("versao"))
            ajustar_resolucao(cfg, vbox, fila)
            return 0
        time.sleep(5)
    log.error("O agente não respondeu em %d s.", limite)
    salvar_print(vbox, pasta_logs, "iniciar")
    return 1


def cmd_ping(cfg, vbox, fila: Fila, pasta_logs, args) -> int:
    if not fila.agente_vivo():
        log.error("Agente sem sinal. Rode 'robo.bat iniciar'.")
        return 1
    id_ = fila.pedir("ping")
    r = fila.esperar(id_, 60)
    if not r:
        log.error("Sem resposta do agente.")
        return 1
    log.info("Resposta: %s", json.dumps(r.get("dados"), ensure_ascii=False))
    return 0 if r.get("ok") else 1


def cmd_snapshot(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    nome = args.extra[0] if args.extra else f"antes_{dt.datetime.now():%Y%m%d_%H%M}"
    try:
        tirar_snapshot(vbox, nome, "AutoSUS - snapshot automático")
    except RuntimeError as e:
        log.error("%s", e)
        return 1
    return 0


def instaladores(origem: Path, padrao: str) -> list[tuple[int, Path]]:
    rx = re.compile(padrao, re.IGNORECASE)
    return sorted((int(m.group("versao")), p) for p in origem.glob("*") if (m := rx.match(p.name)))


def ler_leiame_sisaih01(texto: str) -> dict[str, str]:
    """sisaih01_leiame.txt do DATASUS -> {versão: apresentação}. Cada versão traz
    'VERSÃO 25.41' e, logo abaixo, 'APRESENTAÇÃO PADRAO NA TELA DE LOGIN DESSA VERSÃO : 11/2026'."""
    blocos = re.split(r"VERS[ÃA]O\s+(\d{2})\.(\d{2})\b", texto, flags=re.IGNORECASE)
    versoes = {}
    for maior, menor, corpo in zip(blocos[1::3], blocos[2::3], blocos[3::3]):
        m = re.search(r"APRESENTA[ÇC][ÃA]O\s+PADR[ÃA]O\s+NA\s+TELA\s+DE\s+LOGIN.*?:\s*((?:0[1-9]|1[0-2])/\d{4})",
                      corpo, flags=re.IGNORECASE)
        if m:
            versoes.setdefault(maior + menor, m.group(1))     # o leiame vem do mais novo para o mais antigo
    return versoes


def item_sisaih01_ftp(cfg) -> dict:
    """Onde o downloader do AutoSUS busca o SISAIH01 (autosus/downloads/config.yaml)."""
    for item in cfg["_autosus"].get("programas") or []:
        if item["nome"].upper() == "SISAIH01":
            return item
    raise RuntimeError("SISAIH01 não está em programas no config.yaml do AutoSUS")


def atualizar_versoes_sisaih01(cfg) -> dict[str, str]:
    """Lê o sisaih01_leiame.txt no FTP do DATASUS e anota a apresentação de cada versão em
    estado_vm.json. O que o robô já viu na tela de login vale mais que o leiame."""
    from autosus.fonte_ftp import _com_tentativas
    item = item_sisaih01_ftp(cfg)
    partes = []

    def baixar(ftp):
        ftp.cwd(item["pasta"])
        ftp.retrbinary("RETR sisaih01_leiame.txt", partes.append)

    _com_tentativas(item["host"], {**(cfg["_autosus"].get("ftp") or {}), "tentativas": 2}, baixar)
    do_leiame = ler_leiame_sisaih01(b"".join(partes).decode("cp1252", errors="replace"))
    if not do_leiame:
        raise RuntimeError("sisaih01_leiame.txt sem versões reconhecíveis")
    estado = ler_estado()
    conhecidas = estado.setdefault("apresentacao_por_versao", {}).setdefault("SISAIH01", {})
    for versao, apres in do_leiame.items():
        conhecidas.setdefault(versao, apres)
    gravar_estado(estado)
    return do_leiame


def baixar_sisaih01(cfg, versao: str) -> bool:
    """Baixa sisaih01_ver<versao>.exe do FTP para a pasta de programas do AutoSUS (o mesmo do --versao)."""
    from autosus.fonte_ftp import verificar_programa
    from autosus.manifesto import Manifesto
    pasta = pasta_downloads(cfg) / "programas"
    r = verificar_programa(item_sisaih01_ftp(cfg), pasta, Manifesto(pasta / "manifesto.json"),
                           cfg["_autosus"].get("ftp") or {}, False, versao)
    log.info("SISAIH01 %s: %s %s", versao, r.status, r.detalhe or r.arquivo or "")
    return r.status in ("baixado", "ja_existe")


def versao_sisaih01_para(lista: list[tuple[int, Path]], apres: str) -> list[tuple[int, Path]]:
    """Instaladores do SISAIH01 que servem para a apresentação MM/AAAA.

    Cada versão do SISAIH01 só abre uma apresentação (ex.: 2520 = 09/2026, 2541 = 11/2026), então a
    mais nova nem sempre serve. Usa as versões já conhecidas (estado_vm.json); se nenhuma é dessa
    apresentação, tenta as que ainda não foram abertas nenhuma vez (o abrir confere e anota)."""
    conhecidas = ler_estado().get("apresentacao_por_versao", {}).get("SISAIH01", {})
    certas = [x for x in lista if conhecidas.get(str(x[0])) == apres]
    return certas or [x for x in lista if str(x[0]) not in conhecidas]


def cmd_instalar(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    versao = None
    pasta_extra = None
    apres = None
    extra = list(args.extra)
    if "--versao" in extra:
        i = extra.index("--versao")
        versao = int(extra[i + 1])
        del extra[i:i + 2]
    if "--apresentacao" in extra:                # SISAIH01: a versão dessa apresentação, não a mais nova
        i = extra.index("--apresentacao")
        apres = extra[i + 1]
        del extra[i:i + 2]
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", apres):
            log.error("Apresentação inválida: %s (use MM/AAAA)", apres)
            return 2
    if "--pasta" in extra:                       # instaladores guardados em outra pasta (ex.: Produção 08-2026)
        i = extra.index("--pasta")
        pasta_extra = Path(extra[i + 1])
        del extra[i:i + 2]
        if not pasta_extra.is_dir():
            log.error("Pasta não encontrada: %s", pasta_extra)
            return 2
    nomes = [n.upper() for n in extra] or list(cfg["programas"])
    if versao and len(nomes) != 1:
        log.error("Com --versao, indique um programa só (ex.: instalar SISAIH01 --versao 2520).")
        return 2
    origem = pasta_downloads(cfg) / "programas"
    itens = []
    for nome in nomes:
        prog = cfg["programas"].get(nome)
        if not prog:
            log.error("Programa desconhecido: %s (opções: %s)", nome, ", ".join(cfg["programas"]))
            return 2
        lista = instaladores(origem, prog["padrao"]) if origem.is_dir() else []
        if pasta_extra:
            lista = sorted(lista + instaladores(pasta_extra, prog["padrao"]))
        if versao:
            lista = [x for x in lista if x[0] == versao]
        elif apres and nome == "SISAIH01":
            try:
                do_leiame = atualizar_versoes_sisaih01(cfg)
            except Exception as e:                   # sem FTP: segue com as versões já conhecidas
                log.warning("SISAIH01: não consegui ler o sisaih01_leiame.txt no FTP (%s)", e)
                do_leiame = {}
            conhecidas = ler_estado().get("apresentacao_por_versao", {}).get("SISAIH01", {})
            baixadas = {str(v) for v, _ in lista}
            # a maior versão dessa apresentação no leiame (ex.: 2531 para 10/2026); baixa se faltar
            certas = sorted((v for v, a in conhecidas.items() if a == apres and v in do_leiame), key=int)
            if certas and certas[-1] not in baixadas:
                log.info("SISAIH01: a versão da apresentação %s é a %s; baixando do FTP do DATASUS...", apres, certas[-1])
                if baixar_sisaih01(cfg, certas[-1]):
                    lista = instaladores(origem, prog["padrao"])
                    if pasta_extra:
                        lista = sorted(lista + instaladores(pasta_extra, prog["padrao"]))
            servem = versao_sisaih01_para(lista, apres)
            if not servem:
                # não instala a mais nova no lugar: o sisaih01 completo para logo, com a mesma explicação
                log.warning("SISAIH01: nenhum instalador baixado é da apresentação %s (baixados: %s). Baixe a "
                            "versão do SISAIH01 dessa apresentação e coloque em %s. O SISAIH01 da VM "
                            "fica como está.", apres,
                            ", ".join(f"{v} = {conhecidas.get(str(v), '?')}" for v, _ in lista) or "nenhum", origem)
                continue
            if conhecidas.get(str(servem[-1][0])) != apres:
                log.warning("SISAIH01: a versão %d ainda não foi aberta; o abrir confere se ela é da apresentação %s.",
                            servem[-1][0], apres)
            lista = servem
        if not lista:
            log.error("%s: instalador %s não encontrado em %s.", nome, f"da versão {versao}" if versao else "", origem)
            return 1
        arq = lista[-1][1]
        shutil.copy2(arq, fila.raiz / "entrada" / arq.name)
        log.info("%s: %s copiado para a VM", nome, arq.name)
        itens.append({"programa": nome, "arquivo": f"entrada/{arq.name}", "executavel": prog["executavel"]})
    if not itens:
        log.error("Nada para instalar.")
        return 1

    if not fila.agente_vivo():
        log.error("Agente sem sinal. Rode 'robo.bat iniciar'.")
        return 1
    limite = int(cfg["tempo_limite"]["instalacao_segundos"])
    id_ = fila.pedir("instalar", itens=itens, tempo_limite=limite)
    r = fila.esperar(id_, limite * len(itens) + 120)
    salvar_print(vbox, pasta_logs, "instalar")
    if not r:
        log.error("Sem resposta do agente no tempo limite.")
        return 1
    trazer_arquivos(fila, {"arquivos": [i.get("log_instalador") for i in r.get("dados", {}).get("itens", [])
                                        if i.get("log_instalador")]}, pasta_logs)
    estado = ler_estado()
    for item in r.get("dados", {}).get("itens", []):
        log.info("%s: %s", item["programa"], item["situacao"])
        if item.get("codigo_saida") == 0:
            m = re.search(r"(\d{4})", item["instalador"])
            estado["instalado"][item["programa"]] = m.group(1) if m else item["instalador"]
            gravar_estado(estado)
        for k in ("executavel_ok", "executavel_data", "codigo_saida", "log_instalador"):
            if k in item:
                log.info("    %s: %s", k, item[k])
        if item.get("janelas_abertas"):
            log.info("    janelas abertas depois da instalação: %s", "; ".join(item["janelas_abertas"]))
    if r.get("erro"):
        log.error("Erro: %s", r["erro"])
    return 0 if r.get("ok") else 1


def cmd_resolucao(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    if args.extra:
        cfg["resolucao"] = args.extra[0]
    ajustar_resolucao(cfg, vbox, fila)
    return 0


# pywinauto: comandar as janelas; pillow: tirar print de uma janela específica
PACOTES_VM = ["pywinauto", "pillow"]


def cmd_pacotes(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    b = fila.batimento()
    if not b or b["_idade"] > 40:
        log.error("Agente sem sinal. Rode 'robo.bat iniciar'.")
        return 1
    maior, menor = b["python"].split(".")[:2]
    destino = fila.raiz / "pacotes"
    destino.mkdir(exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "download", *PACOTES_VM, "--only-binary=:all:", "--platform", "win_amd64",
           "--python-version", f"{maior}.{menor}", "--implementation", "cp", "--abi", f"cp{maior}{menor}",
           "-d", str(destino)]
    log.info("Baixando pacotes para o Python %s.%s da VM...", maior, menor)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.error("pip download falhou:\n%s", r.stdout[-2000:] + r.stderr[-2000:])
        return 1
    vc = destino / "vc_redist.x64.exe"
    if not vc.exists():
        import urllib.request
        log.info("Baixando o Visual C++ 2015-2022 (x64), necessário para o pywin32 na VM...")
        req = urllib.request.Request("https://aka.ms/vs/17/release/vc_redist.x64.exe", headers={"User-Agent": "AutoSUS"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(vc.with_suffix(".part"), "wb") as f:
            shutil.copyfileobj(resp, f)
        vc.with_suffix(".part").replace(vc)
    log.info("Pacotes: %s", ", ".join(p.name for p in destino.iterdir()))
    resp = executar(fila, vbox, pasta_logs, "instalar_pacotes", 900, "pacotes", pacotes=PACOTES_VM,
                    reinstalar=[x for x in args.extra if x not in ("--reinstalar",)] if "--reinstalar" in args.extra else None)
    if resp:
        log.info(resp.get("dados", {}).get("saida", "")[-1500:])
    return 0 if resp and resp.get("ok") else 1


def cmd_inspecionar(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    resp = executar(fila, vbox, pasta_logs, "inspecionar", 180, "inspecionar",
                    titulo=" ".join(args.extra) or None)
    if resp:
        log.info("Janelas inspecionadas: %s", resp.get("dados", {}).get("janelas"))
    return 0 if resp and resp.get("ok") else 1


def ler_producao(arquivo: Path) -> dict:
    """Confere o arquivo de importação do SISAIH01: registros de 1800 posições, apresentação (pos. 12-17)."""
    dados = arquivo.read_bytes()
    linhas = [l for l in dados.replace(b"\r\n", b"\n").split(b"\n") if l.strip()]
    tamanhos = {len(l) for l in linhas}
    if not linhas or tamanhos != {1800}:
        raise ValueError(f"{arquivo.name}: esperado registros de 1800 posições, achado {sorted(tamanhos)[:5]}")
    apres = {l[11:17].decode("ascii", "replace") for l in linhas}
    return {"aihs": len(linhas), "apresentacoes": sorted(f"{a[4:6]}/{a[:4]}" for a in apres)}


def mostrar_resposta(resp: dict | None) -> int:
    if not resp:
        return 1
    dados = resp.get("dados", {})
    for e in dados.get("eventos", []):
        log.info("  - %s", e)
    if "rejeitadas" in dados:
        nivel = log.warning if dados["rejeitadas"] else log.info
        nivel("  RESULTADO: %d rejeitada(s) de %d AIH", dados["rejeitadas"], dados["total_aih"])
    hist = dados.get("historico")
    if hist:
        log.info("  histórico (linhas que não são 'OK'):")
        for linha in hist:
            log.info("    %s", linha)
    return 0 if resp.get("ok") else 1


def sessao_sisaih01() -> str | None:
    return ler_estado().get("sisaih01_sessao")


def _opcao(extra: list, nome: str):
    if nome in extra:
        i = extra.index(nome)
        if i + 1 < len(extra):
            return extra[i + 1]
    return None


def insumos_fpo(cfg, comp: str, pasta_extra: str | None) -> tuple[list[Path], list[Path]]:
    """Arquivos do SIA (BDSIA*.exe, ou os .DBF já descompactados) e os zips do SCNES/Terceiros Brasil."""
    base = Path(pasta_extra) if pasta_extra else pasta_downloads(cfg) / f"{comp[:4]}-{comp[4:]}"
    if not base.is_dir():
        raise FileNotFoundError(f"pasta não encontrada: {base}")
    todos = [f for f in base.rglob("*") if f.is_file()]
    exes = [f for f in todos if re.fullmatch(rf"BDSIA{comp}[a-z]?\.exe", f.name, re.IGNORECASE)]
    # só o mais recente: a letra mais alta (a, b, c...) e, em empate, o de data mais nova
    sia = sorted(exes, key=lambda f: (f.stem[-1].lower() if f.stem[-1].isalpha() else "", f.stat().st_mtime))[-1:]
    if not sia:
        pa = [f for f in todos if f.name.upper() == "S_PA.DBF"]
        if pa:
            sia = sorted(f for f in pa[0].parent.iterdir() if f.suffix.upper() in (".DBF", ".DBT"))
    cnes = sorted(f for f in todos if re.fullmatch(rf"(TXTPROC_\d+|TERCEIROSBRASIL\d*)_{comp}\.zip", f.name, re.IGNORECASE))
    return sia, cnes


def enviar_para_vm(fila: "Fila", subpasta: str, arquivos: list[Path]) -> str:
    destino = fila.raiz / "entrada" / subpasta
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for f in arquivos:
        shutil.copy2(f, destino / f.name)
    return subpasta.replace("\\", "/")


def competencia_arg(texto: str | None) -> tuple[int, int] | None:
    m = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{4})", texto or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def cmd_fpo(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    acao = (args.extra or ["inspecionar"])[0]
    prog = cfg["programas"]["FPO"]
    resto = [a for a in args.extra[1:] if not a.startswith("--")]
    pasta_extra = _opcao(args.extra, "--pasta")
    if pasta_extra in resto:
        resto.remove(pasta_extra)
    if acao in ("competencia", "importar_sia", "importar_cnes", "valores", "exportar", "completo"):
        mc = competencia_arg(resto[0] if resto else None)
        if not mc:
            log.error("Informe a competência: robo.bat fpo %s MM/AAAA", acao)
            return 2
        mes, ano = mc
        comp = f"{ano}{mes:02d}"
        apres = f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
        base = {"executavel": prog["executavel"]}
        if acao == "completo":
            return fpo_completo(cfg, vbox, fila, pasta_logs, args, mes, ano)
        if acao == "competencia":
            return mostrar_resposta(executar(fila, vbox, pasta_logs, "fpo_competencia", 1900, "fpo_competencia",
                                             mes=mes, ano=ano, **base))
        if acao in ("importar_sia", "importar_cnes"):
            try:
                sia, cnes = insumos_fpo(cfg, comp, pasta_extra)
            except FileNotFoundError as e:
                log.error("%s", e)
                return 1
            lista = sia if acao == "importar_sia" else cnes
            if not lista:
                log.error("Não achei os arquivos %s da competência %s (use --pasta \"C:\\...\")",
                          "do SIA (BDSIA*.exe ou S_PA.DBF)" if acao == "importar_sia" else
                          "TXTPROC_*/TERCEIROSBRASIL*", comp)
                return 1
            log.info("Arquivos: %s", ", ".join(f.name for f in lista))
            sub = enviar_para_vm(fila, f"fpo_{comp}/{'sia' if acao == 'importar_sia' else 'cnes'}", lista)
            resp = executar(fila, vbox, pasta_logs, f"fpo_{acao}", 4 * 3600 + 300, f"fpo_{acao}", pasta=sub, **base)
            shutil.rmtree(fila.raiz / "entrada" / f"fpo_{comp}", ignore_errors=True)
            return mostrar_resposta(resp)
        if acao == "valores":
            return mostrar_resposta(executar(fila, vbox, pasta_logs, "fpo_valores", 3700, "fpo_valores",
                                             mes=mes, ano=ano, **base))
        if acao == "exportar":
            nome = f"Valores_{comp}.VTP"
            resp = executar(fila, vbox, pasta_logs, "fpo_exportar", 1900, "fpo_exportar", arquivo=nome, **base)
            if resp and resp.get("ok"):
                destino = PASTA / "saida" / apres
                destino.mkdir(parents=True, exist_ok=True)
                for n in resp["dados"].get("exportados", []):
                    origem = fila.raiz / "resultados" / n
                    if origem.exists():
                        shutil.move(str(origem), destino / n)
                        log.info("Valores para o SIHD: %s", destino / n)
            return mostrar_resposta(resp)
    if acao == "inspecionar":
        resp = executar(fila, vbox, pasta_logs, "programa_inspecionar", 180, "fpo_inspecionar",
                        executavel=prog["executavel"], prefixo="fpo", esperar=10)
        if resp:
            d = resp.get("dados", {})
            for k in ("executavel", "versao_arquivo", "data_arquivo", "situacao"):
                if d.get(k):
                    log.info("  %s: %s", k, d[k])
            for t in d.get("janelas", []):
                log.info("  janela: %s", t)
        return 0 if resp and resp.get("ok") else 1
    if acao == "abrir":
        cred = credenciais("FPO", "mestre", "A")
        resp = executar(fila, vbox, pasta_logs, "fpo_abrir", 2000, "fpo_abrir", executavel=prog["executavel"], **cred)
        if resp:
            d = resp.get("dados", {})
            for e in d.get("eventos", []):
                log.info("  - %s", e)
            if d.get("barra_status"):
                log.info("  barra de status: %s", " | ".join(d["barra_status"]))
        return mostrar_resposta(resp) if resp and not resp.get("ok") else (0 if resp else 1)
    if acao == "fechar":
        return mostrar_resposta(executar(fila, vbox, pasta_logs, "fpo_fechar", 120, "fpo_fechar",
                                         executavel=prog["executavel"]))
    if acao == "telas":
        telas = [["MANUTENÇÃO", "ALTERAR COMPETÊNCIA"],
                 ["MANUTENÇÃO", "IMPORTAR TABELAS NACIONAIS DO SIA"],
                 ["MANUTENÇÃO", "IMPORTAR TERCEIROS BRASIL"],
                 ["MANUTENÇÃO", "VALORES VIGENTES"],
                 ["MANUTENÇÃO", "EXPORTAR VALORES"]]
        resp = executar(fila, vbox, pasta_logs, "fpo_mapear_telas", 600, "fpo_telas",
                        executavel=prog["executavel"], telas=telas)
        if resp:
            for linha in resp.get("dados", {}).get("resumo", []):
                log.info("  - %s", linha)
        return mostrar_resposta(resp) if resp and not resp.get("ok") else (0 if resp else 1)
    log.error("Ação desconhecida: %s (disponíveis: inspecionar, abrir, telas, competencia, importar_sia, "
              "importar_cnes, valores, exportar, completo)", acao)
    return 2


def insumos_sihd_cnes(cfg, comp: str, pasta_extra: str | None) -> tuple[list[Path], list[str]]:
    """Arquivos da importação do CNES no SIHD: Valores_AAAAMM.VTP (do FPO), TXTPROC_*, TERCEIROSBRASIL*,
    IMPORT_* e FORNEC_* da competência. Devolve (arquivos, faltando)."""
    base = Path(pasta_extra) if pasta_extra else pasta_downloads(cfg) / f"{comp[:4]}-{comp[4:]}"
    todos = [f for f in base.rglob("*") if f.is_file()] if base.is_dir() else []
    ano, mes = int(comp[:4]), int(comp[4:])
    apres = f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
    achados, faltando = [], []
    vtp = PASTA / "saida" / apres / f"Valores_{comp}.VTP"
    (achados.append(vtp) if vtp.exists() else faltando.append(f"Valores_{comp}.VTP (rode 'fpo exportar')"))
    for rotulo, rx in (("TXTPROC", rf"TXTPROC_\d+_{comp}\.zip"), ("TERCEIROSBRASIL", rf"TERCEIROSBRASIL\d*_{comp}\.zip"),
                       ("IMPORT", rf"IMPORT_{comp}\.zip"), ("FORNEC", rf"FORNEC_{comp}\.zip")):
        f = sorted(x for x in todos if re.fullmatch(rx, x.name, re.IGNORECASE))
        (achados.append(f[-1]) if f else faltando.append(f"{rotulo}_*_{comp}.ZIP"))
    return achados, faltando


def cmd_rede(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    acao = (args.extra or ["status"])[0]
    est = vbox.rede_estado()
    if est["tipo"] in ("none", "null", ""):
        log.error("A VM não tem placa de rede configurada (placa 1: %s). Configure NAT na VirtualBox.", est["tipo"])
        return 1
    if acao in ("ligar", "desligar"):
        vbox.rede(acao == "ligar")
        time.sleep(2)
        est = vbox.rede_estado()
    log.info("Rede da VM: placa 1 = %s, cabo %s", est["tipo"], "CONECTADO" if est["cabo"] == "on" else "desconectado")
    return 0


def cmd_transmissor(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    acao = (args.extra or ["inspecionar"])[0]
    prog = cfg["programas"]["TRANSMISSOR"]
    if acao == "inspecionar":
        resp = executar(fila, vbox, pasta_logs, "programa_inspecionar", 180, "transmissor_inspecionar",
                        executavel=prog["executavel"], prefixo="transmissor", esperar=10, titulo="TRANSMISSOR DATASUS")
        if resp:
            d = resp.get("dados", {})
            for k in ("executavel", "aberto_por", "processo", "versao_arquivo", "data_arquivo", "situacao"):
                if d.get(k):
                    log.info("  %s: %s", k, d[k])
            for t in d.get("janelas", []):
                log.info("  janela: %s", t)
        return 0 if resp and resp.get("ok") else mostrar_resposta(resp)
    if acao == "preparar":
        mc = competencia_arg(args.extra[1] if len(args.extra) > 1 else None)
        if not mc:
            log.error("Uso: robo.bat transmissor preparar MM/AAAA")
            return 2
        mes, ano = mc
        comp, apres = f"{ano}{mes:02d}", f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
        cpf, senha = variavel_env("SECRETARIO_CPF"), variavel_env("SECRETARIO_SENHA")
        if not cpf or not senha:
            log.error("Coloque SECRETARIO_CPF e SECRETARIO_SENHA no C:\\AutoSUS\\server_sus\\.env")
            return 2
        dts = sorted((PASTA / "saida" / apres).glob(f"*{comp}.DTS")) + sorted((PASTA / "saida" / apres).glob(f"*{comp}.dts"))
        if not dts:
            log.error("Não achei o .DTS da competência %s em %s (rode 'sihd encerrar' ou 'sihd coletar')",
                      comp, PASTA / "saida" / apres)
            return 1
        log.info("Arquivo: %s", dts[0])
        sub = enviar_para_vm(fila, f"transmissor_{comp}", [dts[0]])
        resp = executar(fila, vbox, pasta_logs, "transmissor_preparar", 600, "transmissor_preparar",
                        pasta=sub, executavel=prog["executavel"], competencia=f"{mes:02d}/{ano}",
                        tipo_arquivo=variavel_env("TIPO_ARQUIVO", "SIHD"), ibge=variavel_env("IBGE", "150175"),
                        cpf=cpf, senha=senha)
        shutil.rmtree(fila.raiz / "entrada" / f"transmissor_{comp}", ignore_errors=True)
        cod = mostrar_resposta(resp)
        if cod == 0:
            log.info("Confira o print logs\\transmissor_preparado.png. Para testar a conexão: robo.bat transmissor "
                     "testar | para enviar: robo.bat transmissor enviar --confirmar")
        return cod
    if acao in ("testar", "enviar"):
        if acao == "enviar" and "--confirmar" not in args.extra:
            log.error("O envio vai para o DATASUS. Confira o print do 'preparar' e repita com --confirmar.")
            return 2
        est = vbox.rede_estado()
        if est["tipo"] in ("none", "null", ""):
            log.error("A VM não tem placa de rede (configure NAT com o cabo desconectado).")
            return 1
        log.info("Ligando a rede da VM só para %s...", "o teste" if acao == "testar" else "a transmissão")
        vbox.rede(True)
        try:
            time.sleep(8)                                # a VM pega endereço (DHCP do NAT)
            resp = executar(fila, vbox, pasta_logs, "transmissor_botao", 1900, f"transmissor_{acao}",
                            botao="testar" if acao == "testar" else "transmitir")
        finally:
            vbox.rede(False)
            log.info("Rede da VM desligada de novo (%s).", vbox.rede_estado()["cabo"])
        cod = mostrar_resposta(resp)
        if resp and resp.get("ok"):
            log.info("Confira os prints em logs\\transmissor_%s*.png (o resultado aparece na mensagem do Transmissor).",
                     "testar" if acao == "testar" else "transmitir")
        return cod
    if acao == "procurar":
        resp = executar(fila, vbox, pasta_logs, "procurar_programa", 300, "transmissor_procurar", termo="transmiss")
        for a in (resp or {}).get("dados", {}).get("achados", []):
            log.info("  %s", " | ".join("%s: %s" % kv for kv in a.items() if kv[1]))
        return 0 if resp and resp.get("ok") else mostrar_resposta(resp)
    log.error("Ação desconhecida: %s (disponíveis: inspecionar, procurar)", acao)
    return 2


def cmd_sihd(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    acao = (args.extra or ["inspecionar"])[0]
    prog = cfg["programas"]["SIHD2"]
    if acao == "completo":
        return sihd_completo(cfg, vbox, fila, pasta_logs, args)
    if acao == "importar_tabelas":
        return mostrar_resposta(executar(fila, vbox, pasta_logs, "sihd_importar_tabelas", 4 * 3600 + 300,
                                         "sihd_importar_tabelas"))
    if acao in ("criticar", "apurar"):
        resp = executar(fila, vbox, pasta_logs, f"sihd_{acao}", 4 * 3600 + 300, f"sihd_{acao}")
        cod = mostrar_resposta(resp)
        for linha in (resp or {}).get("dados", {}).get("mensagens", []):
            log.info("    %s", linha)
        return cod
    if acao in ("encerrar", "coletar"):
        mc = competencia_arg(args.extra[1] if len(args.extra) > 1 else None)
        if acao == "coletar" and mc:
            mes, ano = mc
            apres = f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
            resp = executar(fila, vbox, pasta_logs, "sihd_coletar", 600, "sihd_coletar")
            if resp and resp.get("ok"):
                destino = PASTA / "saida" / apres
                destino.mkdir(parents=True, exist_ok=True)
                for g in resp["dados"].get("gerados", []):
                    origem = fila.raiz / "resultados" / g["arquivo"]
                    if origem.exists():
                        shutil.move(str(origem), destino / g["arquivo"])
                        log.info("Coletado: %s (%d bytes, %s)", destino / g["arquivo"], g["bytes"], g["data"])
            return mostrar_resposta(resp)
        if not mc or "--confirmar" not in args.extra:
            log.error("Uso: robo.bat sihd encerrar MM/AAAA --confirmar  (encerra a competência no SIHD e gera o .DTS)")
            return 2
        mes, ano = mc
        apres = f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
        resp = executar(fila, vbox, pasta_logs, "sihd_encerrar", 4 * 3600 + 300, "sihd_encerrar")
        if resp and resp.get("ok"):
            destino = PASTA / "saida" / apres
            destino.mkdir(parents=True, exist_ok=True)
            for g in resp["dados"].get("gerados", []):
                origem = fila.raiz / "resultados" / g["arquivo"]
                if origem.exists():
                    shutil.move(str(origem), destino / g["arquivo"])
                    log.info("Gerado: %s (%d bytes)", destino / g["arquivo"], g["bytes"])
        cod = mostrar_resposta(resp)
        for linha in (resp or {}).get("dados", {}).get("mensagens", []):
            log.info("    %s", linha)
        return cod
    if acao == "bloqueadas":
        resp = executar(fila, vbox, pasta_logs, "sihd_bloqueadas", 3 * 3600 + 900, "sihd_bloqueadas")
        cod = mostrar_resposta(resp)
        d = (resp or {}).get("dados", {})
        pend = d.get("pendentes", [])
        if resp and resp.get("ok"):
            log.info("AIHs bloqueadas com pendência para liberar: %d de %d", len(pend), d.get("total", 0))
            for r in pend:
                log.info("  %s | %s | %s | %s", r["aih"], r["motivo"] or "-", r["bloqueio_liberacao"] or "-", r["valor"])
            if d.get("liberadas"):
                log.info("AIHs já liberadas: %s", ", ".join(r["aih"] for r in d["liberadas"]))
            if pend:
                log.info("Para liberar (só as que você aprovar): robo.bat sihd liberar <AIH> [<AIH> ...] --confirmar")
        return cod
    if acao == "liberar":
        aihs = [a for a in args.extra[1:] if a != "--confirmar"]
        if not aihs or "--confirmar" not in args.extra:
            log.error("Uso: robo.bat sihd liberar <número da AIH> [...] --confirmar  (libera só as AIHs informadas)")
            return 2
        resp = executar(fila, vbox, pasta_logs, "sihd_liberar", 3 * 3600 + 900, "sihd_liberar", aihs=aihs)
        return mostrar_resposta(resp)
    if acao == "importar_aih":
        mc = competencia_arg(args.extra[1] if len(args.extra) > 1 else None)
        if not mc:
            log.error("Informe a competência: robo.bat sihd importar_aih MM/AAAA [--pasta X]")
            return 2
        mes, ano = mc
        comp, apres = f"{ano}{mes:02d}", f"{ano + (mes == 12)}{mes % 12 + 1:02d}"
        zips = sorted((PASTA / "saida" / apres).glob(f"{apres}AIH*.zip")) + \
            sorted((PASTA / "saida" / apres).glob(f"{apres}AIH*.Zip"))
        base = Path(_opcao(args.extra, "--pasta") or pasta_downloads(cfg) / f"{comp[:4]}-{comp[4:]}")
        dsihd = sorted(f for f in base.rglob("*") if re.fullmatch(rf"DSIHD\d+_\d+_{comp}\.zip", f.name, re.IGNORECASE)) \
            if base.is_dir() else []
        if not zips:
            log.error("Não achei o arquivo do SISAIH01 em %s (rode 'sisaih01 exportar')", PASTA / "saida" / apres)
            return 1
        if not dsihd:
            log.error("Não achei o DSIHD*_%s.ZIP em %s (use --pasta)", comp, base)
            return 1
        arquivos = [sorted(set(zips))[-1], dsihd[-1]]
        log.info("Arquivos: %s", ", ".join(f.name for f in arquivos))
        sub = enviar_para_vm(fila, f"sihd_{comp}/aih", arquivos)
        resp = executar(fila, vbox, pasta_logs, "sihd_importar_aih", 4 * 3600 + 300, "sihd_importar_aih",
                        pasta=sub, executavel=prog["executavel"])
        shutil.rmtree(fila.raiz / "entrada" / f"sihd_{comp}", ignore_errors=True)
        cod = mostrar_resposta(resp)
        for linha in (resp or {}).get("dados", {}).get("mensagens", []):
            log.info("    %s", linha)
        return cod
    if acao == "importar_cnes":
        mc = competencia_arg(args.extra[1] if len(args.extra) > 1 else None)
        if not mc:
            log.error("Informe a competência: robo.bat sihd importar_cnes MM/AAAA [--pasta X]")
            return 2
        comp = f"{mc[1]}{mc[0]:02d}"
        arquivos, faltando = insumos_sihd_cnes(cfg, comp, _opcao(args.extra, "--pasta"))
        if faltando:
            log.error("Faltam arquivos para importar o CNES: %s", ", ".join(faltando))
            return 1
        log.info("Arquivos: %s", ", ".join(f.name for f in arquivos))
        sub = enviar_para_vm(fila, f"sihd_{comp}/cnes", arquivos)
        resp = executar(fila, vbox, pasta_logs, "sihd_importar_cnes", 3 * 3600 + 300, "sihd_importar_cnes", pasta=sub)
        shutil.rmtree(fila.raiz / "entrada" / f"sihd_{comp}", ignore_errors=True)
        cod = mostrar_resposta(resp)
        for linha in (resp or {}).get("dados", {}).get("mensagens", []):
            log.info("    %s", linha)
        return cod
    if acao == "inspecionar":
        resp = executar(fila, vbox, pasta_logs, "programa_inspecionar", 180, "sihd_inspecionar",
                        executavel=prog["executavel"], prefixo="sihd", esperar=15)
        if resp:
            d = resp.get("dados", {})
            for k in ("executavel", "versao_arquivo", "data_arquivo", "situacao"):
                if d.get(k):
                    log.info("  %s: %s", k, d[k])
            for t in d.get("janelas", []):
                log.info("  janela: %s", t)
        return 0 if resp and resp.get("ok") else 1
    if acao == "abrir":
        cred = credenciais("SIHD", "", "")
        if not cred["usuario"] or not cred["senha"]:
            log.error("Coloque SIHD_USUARIO e SIHD_SENHA no C:\\AutoSUS\\server_sus\\.env")
            return 2
        resp = executar(fila, vbox, pasta_logs, "sihd_abrir", 2000, "sihd_abrir", executavel=prog["executavel"], **cred)
        return mostrar_resposta(resp)
    if acao == "competencia":
        mc = competencia_arg(args.extra[1] if len(args.extra) > 1 else None)
        if not mc:
            log.error("Informe a competência: robo.bat sihd competencia MM/AAAA")
            return 2
        return mostrar_resposta(executar(fila, vbox, pasta_logs, "sihd_competencia", 900, "sihd_competencia",
                                         mes=mc[0], ano=mc[1]))
    if acao == "telas":
        telas = [["PRODUÇÃO", ["IMPORTAR ARQUIVOS", "IMPORTAR DADOS DO CNES"]],
                 ["PRODUÇÃO", ["IMPORTAR ARQUIVOS", "IMPORTAR TABELAS NACIONAIS"]],
                 ["PRODUÇÃO", ["IMPORTAR ARQUIVOS", "IMPORTAR MOVIMENTO DE AIH"]],
                 ["CONTROLE E AVALIAÇÃO", ["GERENCIAR INFORMAÇÕES"]],
                 ["PROCESSAMENTO", ["CRITICAR"]],
                 ["PROCESSAMENTO", ["APURAR VALORES"]],
                 ["PROCESSAMENTO", ["ENCERRAR COMPETÊNCIA"]]]
        filtro = " ".join(args.extra[1:]).upper()
        if filtro:                                   # ex.: robo.bat sihd telas gerenciar
            telas = [t for t in telas if filtro in " ".join([t[0]] + t[1]).upper()]
            if not telas:
                log.error("Nenhuma tela com %r", filtro)
                return 2
        resp = executar(fila, vbox, pasta_logs, "sihd_mapear_telas", 900, "sihd_telas", telas=telas)
        if resp:
            for linha in resp.get("dados", {}).get("resumo", []):
                log.info("  - %s", linha)
        return 0 if resp and resp.get("ok") else mostrar_resposta(resp)
    if acao == "menus":
        resp = executar(fila, vbox, pasta_logs, "barra_menus", 300, "sihd_menus",
                        titulo="Sistema de Informação Hospitalar - ", prefixo="sihd")
        return 0 if resp and resp.get("ok") else mostrar_resposta(resp)
    log.error("Ação desconhecida: %s (disponíveis: inspecionar, abrir, menus)", acao)
    return 2


ETAPAS_SIHD = ["instalar", "abrir", "competencia", "importar_cnes", "importar_tabelas", "importar_aih",
               "bloqueadas", "criticar", "apurar", "encerrar"]


def sihd_completo(cfg, vbox: "VBox", fila: "Fila", pasta_logs, args) -> int:
    """SIHD do começo ao fim, parando onde há decisão:
      --manual (padrão): para nas AIHs bloqueadas e lista; você libera com 'sihd liberar' e continua com
                         --a-partir-de criticar
      --auto:            libera automaticamente TODAS as AIHs bloqueadas com pendência e segue
      --confirmar:       encerra a competência no fim; sem ele, para antes do encerramento
      --a-partir-de X:   retoma a partir da etapa X (%s)
      --versao NNNN:     versão do SIHD2 a instalar (padrão: a maior baixada)""" % ", ".join(ETAPAS_SIHD)
    extra = list(args.extra)
    resto = [a for a in extra[1:] if not a.startswith("--")]
    for op in ("--pasta", "--a-partir-de", "--versao"):
        v = _opcao(extra, op)
        if v in resto:
            resto.remove(v)
    mc = competencia_arg(resto[0] if resto else None)
    if not mc:
        log.error("Uso: robo.bat sihd completo MM/AAAA [--pasta X] [--manual|--auto] [--confirmar] "
                  "[--a-partir-de ETAPA] [--versao NNNN] [--sem-snapshot]")
        return 2
    if "--auto" in extra and "--manual" in extra:
        log.error("Use --auto OU --manual.")
        return 2
    modo = "auto" if "--auto" in extra else "manual"
    mes, ano = mc
    comp_txt = f"{mes:02d}/{ano}"
    pasta = ["--pasta", _opcao(extra, "--pasta")] if _opcao(extra, "--pasta") else []
    inicio_em = _opcao(extra, "--a-partir-de") or ETAPAS_SIHD[0]
    if inicio_em not in ETAPAS_SIHD:
        log.error("Etapa desconhecida: %s (etapas: %s)", inicio_em, ", ".join(ETAPAS_SIHD))
        return 2
    etapas = ETAPAS_SIHD[ETAPAS_SIHD.index(inicio_em):]
    if inicio_em not in ("instalar", "abrir"):
        etapas = ["abrir"] + etapas            # ao retomar, garante o SIHD aberto e logado (se já estiver, só confere)

    def retomar(etapa, confirmar=None):
        conf = "--confirmar" in extra if confirmar is None else confirmar
        return "robo.bat sihd completo %s --a-partir-de %s%s%s%s" % (
            comp_txt, etapa, " --" + modo, " --confirmar" if conf else "", f' --pasta "{pasta[1]}"' if pasta else "")
    log.info("SIHD %s | AIHs bloqueadas: %s | encerramento: %s | etapas: %s", comp_txt,
             "liberação AUTOMÁTICA" if modo == "auto" else "liberação MANUAL (para e lista)",
             "sim (--confirmar)" if "--confirmar" in extra else "não (para antes)", ", ".join(etapas))
    sub = lambda e: argparse.Namespace(**{**vars(args), "extra": e})
    if "--sem-snapshot" not in extra and inicio_em == ETAPAS_SIHD[0]:
        try:
            tirar_snapshot(vbox, f"antes_sihd_{ano}{mes:02d}_{dt.datetime.now():%Y%m%d_%H%M}",
                           f"AutoSUS - antes do SIHD {comp_txt}")
        except RuntimeError as e:
            log.error("Snapshot não criado, SIHD cancelado: %s", e)
            return 1
    for etapa in etapas:
        log.info("========== SIHD: %s ==========", etapa)
        if etapa == "instalar":
            origem = pasta_downloads(cfg) / "programas"
            lista = instaladores(origem, cfg["programas"]["SIHD2"]["padrao"]) if origem.is_dir() else []
            if pasta:
                lista = sorted(lista + instaladores(Path(pasta[1]), cfg["programas"]["SIHD2"]["padrao"]))
            versao = _opcao(extra, "--versao")
            if versao:
                lista = [x for x in lista if x[0] == int(versao)]
            instalada = ler_estado().get("instalado", {}).get("SIHD2")
            if not lista:
                log.warning("Nenhum instalador do SIHD2%s encontrado: segue com o instalado (%s)",
                            f" {versao}" if versao else "", instalada or "?")
                continue
            if str(lista[-1][0]).zfill(4) == str(instalada or "").zfill(4):
                log.info("SIHD2 %s já instalado", instalada)
                continue
            cod = cmd_instalar(cfg, vbox, fila, pasta_logs, sub(["SIHD2", "--versao", str(lista[-1][0])] + pasta))
        elif etapa == "abrir":
            cod = cmd_sihd(cfg, vbox, fila, pasta_logs, sub(["abrir"]))
        elif etapa in ("competencia", "importar_cnes", "importar_aih"):
            cod = cmd_sihd(cfg, vbox, fila, pasta_logs, sub([etapa, comp_txt] + pasta))
        elif etapa in ("importar_tabelas", "criticar", "apurar"):
            cod = cmd_sihd(cfg, vbox, fila, pasta_logs, sub([etapa]))
        elif etapa == "bloqueadas":
            resp = executar(fila, vbox, pasta_logs, "sihd_bloqueadas", 3 * 3600 + 900, "sihd_bloqueadas")
            cod = mostrar_resposta(resp)
            if cod == 0:
                pend = resp["dados"].get("pendentes", [])
                log.info("AIHs bloqueadas com pendência: %d de %d", len(pend), resp["dados"].get("total", 0))
                for r in pend:
                    log.info("  %s | %s | %s | %s", r["aih"], r["motivo"] or "-", r["bloqueio_liberacao"] or "-", r["valor"])
                if pend and modo == "manual":
                    log.warning("PAROU para você decidir as liberações. Libere as aprovadas com:\n"
                                "  robo.bat sihd liberar <AIH> [<AIH> ...] --confirmar\n"
                                "e continue com:\n  %s", retomar("bloqueadas"))
                    return 3
                if pend:
                    log.info("--auto: liberando automaticamente %d AIH(s)", len(pend))
                    cod = cmd_sihd(cfg, vbox, fila, pasta_logs, sub(["liberar"] + [r["aih"] for r in pend] + ["--confirmar"]))
                    if cod == 0:
                        conf = executar(fila, vbox, pasta_logs, "sihd_bloqueadas", 3 * 3600 + 900, "sihd_bloqueadas")
                        resto_pend = (conf or {}).get("dados", {}).get("pendentes", [])
                        if not conf or not conf.get("ok") or resto_pend:
                            log.error("Depois da liberação automática ainda há %d AIH(s) pendente(s): %s",
                                      len(resto_pend), ", ".join(r["aih"] for r in resto_pend))
                            return 1
                        log.info("Liberação conferida: nenhuma AIH pendente.")
        elif etapa == "encerrar":
            if "--confirmar" not in extra:
                log.warning("PAROU antes do encerramento (falta --confirmar). Para encerrar e gerar o .DTS:\n"
                            "  %s", retomar("encerrar", True))
                return 3
            cod = cmd_sihd(cfg, vbox, fila, pasta_logs, sub(["encerrar", comp_txt, "--confirmar"]))
        if cod != 0:
            log.error("PAROU na etapa %s. Depois de resolver, continue com:\n  %s", etapa, retomar(etapa))
            return cod
    log.info("SIHD concluído: competência %s encerrada; .DTS em saida/. Próximo: robo.bat transmissor preparar %s",
             comp_txt, comp_txt)
    return 0


def fpo_completo(cfg, vbox: "VBox", fila: "Fila", pasta_logs, args, mes: int, ano: int) -> int:
    """Na ordem do procedimento: 1) instalar a atualização baixada (se for nova) 2) abrir/atualizar o banco
    3) competência 4) importar SIA 5) importar TXT do SCNES e Terceiros Brasil 6) valores vigentes 7) exportar."""
    comp_txt = f"{mes:02d}/{ano}"
    sub = lambda extra: argparse.Namespace(**{**vars(args), "extra": extra})
    if "--sem-snapshot" not in args.extra:
        try:
            tirar_snapshot(vbox, f"antes_fpo_{ano}{mes:02d}_{dt.datetime.now():%Y%m%d_%H%M}",
                           f"AutoSUS - antes do processamento do FPO {comp_txt}")
        except RuntimeError as e:
            log.error("Snapshot não criado, FPO cancelado: %s", e)
            return 1
    # 1) atualização do FPO: instala se a maior versão baixada não é a que o robô instalou
    origem = pasta_downloads(cfg) / "programas"
    baixadas = instaladores(origem, cfg["programas"]["FPO"]["padrao"]) if origem.is_dir() else []
    instalada = ler_estado().get("instalado", {}).get("FPO")
    if baixadas and str(baixadas[-1][0]).zfill(4) != str(instalada or "").zfill(4):
        log.info("========== FPO: atualização %s (instalada pelo robô: %s) ==========",
                 baixadas[-1][1].name, instalada or "desconhecida")
        for extra, func in ((["fechar"], cmd_fpo), (["FPO"], cmd_instalar)):
            cod = func(cfg, vbox, fila, pasta_logs, sub(extra))
            if cod != 0:
                log.error("PAROU na atualização do FPO.")
                return cod
    else:
        log.info("FPO: sem atualização nova (instalada: %s)", instalada or "?")
    pasta = ["--pasta", _opcao(args.extra, "--pasta")] if _opcao(args.extra, "--pasta") else []
    # 2) abrir (no primeiro login depois da atualização o FPO converte o banco) ... 7) exportar
    for nome, extra in [("abrir", ["abrir"]), ("competencia", ["competencia", comp_txt]),
                        ("importar_sia", ["importar_sia", comp_txt] + pasta),
                        ("importar_cnes", ["importar_cnes", comp_txt] + pasta),
                        ("valores", ["valores", comp_txt]), ("exportar", ["exportar", comp_txt])]:
        log.info("========== FPO: %s ==========", nome)
        cod = cmd_fpo(cfg, vbox, fila, pasta_logs, sub(extra))
        if cod != 0:
            log.error("PAROU na etapa %s.", nome)
            return cod
    log.info("FPO concluído: competência %s, Valores_%d%02d.VTP gerado.", comp_txt, ano, mes)
    return 0


def sisaih01_completo(cfg, vbox: "VBox", fila: "Fila", pasta_logs, args) -> int:
    """abrir -> excluir -> importar -> consistir (para se houver rejeitada) -> apurar -> exportar."""
    resto = [a for a in args.extra[1:] if not a.startswith("--")]
    if not resto or not re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", resto[0]):
        log.error("Uso: robo.bat sisaih01 completo MM/AAAA [arquivo] --confirmar [--sem-snapshot]")
        return 2
    if "--confirmar" not in args.extra:
        log.error("O completo apaga a produção da apresentação %s no SISAIH01 antes de importar. "
                  "Repita com --confirmar.", resto[0])
        return 2
    apres, arquivo = resto[0], resto[1:]
    # antes de mexer na VM: a versão instalada precisa ser a dessa apresentação
    estado = ler_estado()
    instalada = estado.get("instalado", {}).get("SISAIH01")
    da_instalada = estado.get("apresentacao_por_versao", {}).get("SISAIH01", {}).get(str(instalada))
    if da_instalada and da_instalada != apres:
        log.error("O SISAIH01 instalado na VM (versão %s) é da apresentação %s, mas a produção é da %s. "
                  "Instale a versão certa: robo.bat instalar SISAIH01 --apresentacao %s "
                  "(ou rode o job com a etapa \"atualizar\").", instalada, da_instalada, apres, apres)
        return 1
    flags = [a for a in args.extra if a in ("--confirmar", "--sem-snapshot")]
    etapas = [("abrir", ["abrir", apres]),
              ("excluir", ["excluir", apres] + flags),
              ("importar", ["importar"] + arquivo),
              ("consistir", ["consistir"]),
              ("apurar", ["apurar"]),
              ("exportar", ["exportar"])]
    for nome, extra in etapas:
        log.info("========== SISAIH01: %s ==========", nome)
        sub = argparse.Namespace(**{**vars(args), "extra": extra})
        if nome == "consistir":
            resp = executar(fila, vbox, pasta_logs, "sisaih01_consistir", 3700, "sisaih01_consistir")
            cod = mostrar_resposta(resp)
            rej = (resp or {}).get("dados", {}).get("rejeitadas")
            if cod == 0 and rej:
                log.warning("PAROU: %d AIH rejeitada(s) na consistência. Corrija no WebAIH (ou veja o relatório "
                            "de consistência no SISAIH01), baixe de novo e repita o completo.", rej)
                return 3
        else:
            cod = cmd_sisaih01(cfg, vbox, fila, pasta_logs, sub)
        if cod != 0:
            log.error("PAROU na etapa %s.", nome)
            return cod
    log.info("SISAIH01 concluído: produção %s importada, consistida, apurada e exportada para o SIHD.", apres)
    return 0


def cmd_sisaih01(cfg, vbox: VBox, fila: Fila, pasta_logs, args) -> int:
    acao = (args.extra or ["abrir"])[0]
    resto = [a for a in args.extra[1:] if not a.startswith("--")]
    sessao = sessao_sisaih01()
    if acao in ("excluir", "importar", "consistir", "apurar", "exportar"):
        if not sessao:
            log.error("Não sei em que apresentação o SISAIH01 está aberto. Rode antes: robo.bat sisaih01 abrir MM/AAAA")
            return 2
        log.info("SISAIH01 aberto na apresentação %s", sessao)
    if acao == "excluir":
        if not resto or resto[0] != sessao:
            log.error("Informe a apresentação a excluir, igual à aberta: robo.bat sisaih01 excluir %s --confirmar", sessao)
            return 2
        if "--confirmar" not in args.extra:
            log.error("A exclusão apaga a produção da apresentação %s no SISAIH01. Repita com --confirmar.", sessao)
            return 2
        prefixo = f"antes_excluir_{sessao[3:]}{sessao[:2]}_"
        if "--sem-snapshot" in args.extra:
            anteriores = [n for n in vbox.snapshots() if n.startswith(prefixo)]
            if not anteriores:
                log.error("--sem-snapshot só vale se já existir um snapshot %s*; não há nenhum.", prefixo)
                return 1
            log.info("Sem snapshot novo; ponto de retorno: %s (para voltar: robo.bat restaurar %s --confirmar)",
                     anteriores[-1], anteriores[-1])
        else:
            try:
                tirar_snapshot(vbox, f"{prefixo}{dt.datetime.now():%Y%m%d_%H%M}",
                               f"AutoSUS - antes de excluir a produção {sessao} no SISAIH01")
            except RuntimeError as e:
                log.error("Snapshot não criado, exclusão cancelada: %s", e)
                return 1
        return mostrar_resposta(executar(fila, vbox, pasta_logs, "sisaih01_excluir", 1900, "sisaih01_excluir",
                                         apresentacao=sessao))
    if acao == "importar":
        if resto:
            arquivo = Path(" ".join(resto)).expanduser()
        else:
            # padrão: o arquivo que o AutoSUS baixou do WebAIH, ex.: 2026-08\SIH\202609_SISAIH01_<CNES>.txt
            mm, aaaa = int(sessao[:2]), int(sessao[3:])
            comp = f"{aaaa if mm > 1 else aaaa - 1}-{(mm - 2) % 12 + 1:02d}"
            pasta = pasta_downloads(cfg) / comp / "SIH"
            achados = sorted(pasta.glob(f"{aaaa}{mm:02d}_SISAIH01_*.txt"))
            if len(achados) != 1:
                log.error("Não achei um único arquivo do WebAIH em %s (%s). Informe o arquivo: "
                          "robo.bat sisaih01 importar \"C:\\...\\arquivo.txt\"",
                          pasta, ", ".join(a.name for a in achados) or "nenhum")
                return 1
            arquivo = achados[0]
            log.info("Arquivo do WebAIH: %s", arquivo)
        if not arquivo.is_file():
            log.error("Arquivo não encontrado: %s", arquivo)
            return 1
        try:
            info = ler_producao(arquivo)
        except ValueError as e:
            log.error("%s", e)
            return 1
        log.info("Arquivo %s: %d AIH, apresentação %s", arquivo.name, info["aihs"], ", ".join(info["apresentacoes"]))
        if info["apresentacoes"] != [sessao]:
            log.error("O arquivo é da apresentação %s e o SISAIH01 está aberto em %s: o SISAIH01 gravaria "
                      "a produção em outra apresentação. Nada foi feito.", ", ".join(info["apresentacoes"]), sessao)
            return 1
        entrada = fila.raiz / "entrada"
        entrada.mkdir(exist_ok=True)
        nome = re.sub(r"[^A-Za-z0-9._-]+", "_", arquivo.name)
        shutil.copy2(arquivo, entrada / nome)
        return mostrar_resposta(executar(fila, vbox, pasta_logs, "sisaih01_importar", 3700, "sisaih01_importar",
                                         arquivo=nome))
    if acao in ("consistir", "apurar"):
        return mostrar_resposta(executar(fila, vbox, pasta_logs, f"sisaih01_{acao}", 3700, f"sisaih01_{acao}"))
    if acao == "exportar":
        resp = executar(fila, vbox, pasta_logs, "sisaih01_exportar", 1900, "sisaih01_exportar")
        if resp and resp.get("ok"):
            destino = PASTA / "saida" / f"{sessao[3:]}{sessao[:2]}"
            destino.mkdir(parents=True, exist_ok=True)
            for nome in resp["dados"].get("exportados", []):
                origem = fila.raiz / "resultados" / nome
                if origem.exists():
                    shutil.copy2(origem, destino / nome)
                    origem.unlink()                  # não deixa a produção na pasta compartilhada
                    log.info("Arquivo para o SIHD: %s", destino / nome)
        return mostrar_resposta(resp)
    if acao == "completo":
        return sisaih01_completo(cfg, vbox, fila, pasta_logs, args)
    if acao == "menus":
        resp = executar(fila, vbox, pasta_logs, "sisaih01_menus", 180, "sisaih01_menus")
        return 0 if resp and resp.get("ok") else 1
    if acao == "telas":
        telas = [["MANUTENÇÃO", ["EXCLUIR PRODUÇÃO"]],
                 ["MANUTENÇÃO", ["IMPORTAR", "PRODUÇÃO"]],
                 ["PROCESSAMENTO", ["CONSISTIR PRODUÇÃO"]],
                 ["PROCESSAMENTO", ["APURAR PRÉVIA"]],
                 ["PROCESSAMENTO", ["EXPORTAR PRODUÇÃO PARA", "SIHD (SECRETARIA)"]],
                 ["RELATÓRIOS", ["GERENCIAIS", "CONSISTÊNCIA", "ERROS"]]]
        resp = executar(fila, vbox, pasta_logs, "sisaih01_mapear_telas", 600, "sisaih01_telas", telas=telas)
        if resp:
            for linha in resp.get("dados", {}).get("resumo", []):
                log.info("  - %s", linha)
        return 0 if resp and resp.get("ok") else 1
    if acao != "abrir":
        log.error("Ação desconhecida: %s (disponíveis: abrir, menus, telas, excluir, importar, consistir, "
                  "apurar, exportar, completo)", acao)
        return 2
    apresentacao = None
    if len(args.extra) > 1:                      # robo.bat sisaih01 abrir 09/2026
        apresentacao = args.extra[1]
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", apresentacao):
            log.error("Apresentação inválida: %s (use MM/AAAA)", apresentacao)
            return 2
    cred = credenciais("SISAIH01", "mestre", "mestre")
    resp = executar(fila, vbox, pasta_logs, "sisaih01_abrir", 1200, "sisaih01",
                    executavel=cfg["programas"]["SISAIH01"]["executavel"], apresentacao=apresentacao, **cred)
    if resp:
        for passo in resp.get("dados", {}).get("passos", []):
            log.info("  - %s", passo)
        apv = resp.get("dados", {}).get("apresentacao_da_versao")
        if resp.get("ok"):
            estado = ler_estado()
            estado["sisaih01_sessao"] = apresentacao or apv
            gravar_estado(estado)
        if apv:
            estado = ler_estado()
            versao = estado["instalado"].get("SISAIH01")
            if versao:
                estado["apresentacao_por_versao"].setdefault("SISAIH01", {})[versao] = apv
                gravar_estado(estado)
                log.info("SISAIH01 versão %s = apresentação %s (registrado em %s)", versao, apv, ESTADO.name)
    return 0 if resp and resp.get("ok") else 1


def cmd_snapshots(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    info = vbox.info()
    log.info("Snapshots da VM %s (do mais antigo ao mais novo):", cfg["vm"])
    for nome in vbox.snapshots():
        log.info("  - %s", nome)
    pasta = Path(info.get("SnapFldr", ""))
    if pasta.is_dir():
        log.info("Pasta dos snapshots: %s (%.1f GB)", pasta, tamanho_pasta(pasta))
    espaco_livre(vbox)
    return 0


def cmd_apagar_snapshot(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    nomes = [a for a in args.extra if a != "--confirmar"]
    if not nomes or "--confirmar" not in args.extra:
        log.error("Uso: robo.bat apagar_snapshot <nome> [<nome> ...] --confirmar  "
                  "(apaga só o ponto de retorno; o estado atual da VM não muda)")
        return 2
    existentes = vbox.snapshots()
    faltando = [n for n in nomes if n not in existentes]
    if faltando:
        log.error("Snapshot não existe: %s. Disponíveis: %s", ", ".join(faltando), ", ".join(existentes))
        return 1
    if vbox.estado() in ("running", "paused"):
        log.warning("A VM está ligada: apagar snapshot com ela ligada pode falhar. Se falhar, desligue-a "
                    "(ou restaure um snapshot) e repita.")
    falhas = []
    for nome in nomes:
        log.info("Apagando o snapshot %s (pode demorar alguns minutos)...", nome)
        try:
            vbox.apagar_snapshot(nome)
            estado = ler_estado()
            estado.get("snapshots", {}).pop(nome, None)
            gravar_estado(estado)
        except RuntimeError as e:
            log.error("  não apagou: %s", str(e).strip().splitlines()[-1] if str(e).strip() else e)
            falhas.append(nome)
    espaco_livre(vbox)
    if falhas:
        log.error("Não apagados: %s", " ".join(falhas))
        return 1
    return 0


def cmd_restaurar(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    nomes = [a for a in args.extra if a != "--confirmar"]
    if not nomes:
        log.error("Indique o snapshot: robo.bat restaurar <nome> --confirmar")
        return 2
    nome = nomes[0]
    if nome not in vbox.snapshots():
        log.error("Snapshot %s não existe. Disponíveis: %s", nome, ", ".join(vbox.snapshots()) or "nenhum")
        return 1
    if "--confirmar" not in args.extra:
        log.error("Restaurar descarta tudo o que foi feito na VM depois do snapshot %s. "
                  "Para seguir, repita com --confirmar.", nome)
        return 2
    estado = vbox.estado()
    if estado in ("running", "paused"):
        if estado == "paused":
            vbox.retomar()
        log.info("Desligando a VM...")
        vbox.desligar()
        fim = time.time() + 120
        while time.time() < fim and vbox.estado() not in ("poweroff", "saved", "aborted"):
            time.sleep(3)
        if vbox.estado() not in ("poweroff", "saved", "aborted"):
            log.warning("A VM não desligou pelo botão de energia; desligando à força.")
            vbox.desligar_forcado()
            time.sleep(5)
    vbox.restaurar(nome)
    estado_vm = ler_estado()
    # depois de restaurar, vale o que estava instalado quando o snapshot foi tirado (se o robô anotou)
    anotado = estado_vm.get("snapshots", {}).get(nome, {})
    estado_vm["instalado"] = dict(anotado.get("instalado", {}))
    estado_vm["sisaih01_sessao"] = anotado.get("sisaih01_sessao")
    gravar_estado(estado_vm)
    log.info("VM %s restaurada para o snapshot %s.", cfg["vm"], nome)
    log.info("Se o snapshot é anterior ao agente, ligue a VM e rode de novo o instalar_agente.bat dentro dela.")
    return 0


def cmd_versoes(cfg, vbox, fila, pasta_logs, args) -> int:
    origem = pasta_downloads(cfg) / "programas"
    estado = ler_estado()
    for nome, prog in cfg["programas"].items():
        conhecidas = estado["apresentacao_por_versao"].get(nome, {})
        lista = instaladores(origem, prog["padrao"])
        log.info("%s (instalada na VM: %s):", nome, estado["instalado"].get(nome, "?"))
        for versao, arq in lista:
            data = dt.datetime.fromtimestamp(arq.stat().st_mtime).strftime("%d/%m/%Y")
            log.info("    %s  baixado em %s  apresentação %s", arq.name, data, conhecidas.get(str(versao), "?"))
        if not lista:
            log.info("    nenhum instalador em %s", origem)
    return 0


def cmd_print(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    return 0 if salvar_print(vbox, pasta_logs, "manual") else 1


def cmd_desligar(cfg, vbox: VBox, fila, pasta_logs, args) -> int:
    estado = vbox.estado()
    inicio = time.time()
    if estado == "paused":
        log.info("A VM estava pausada; retomando antes de desligar.")
        vbox.retomar()
        time.sleep(5)
    elif estado != "running":
        log.info("A VM já está desligada (%s).", estado)
        return 0
    vbox.desligar()
    log.info("Sinal de desligar enviado à VM %s.", cfg["vm"])
    return 0


COMANDOS = {"status": cmd_status, "preparar": cmd_preparar, "iniciar": cmd_iniciar, "ping": cmd_ping,
            "snapshot": cmd_snapshot, "instalar": cmd_instalar, "resolucao": cmd_resolucao, "pacotes": cmd_pacotes,
            "inspecionar": cmd_inspecionar, "sisaih01": cmd_sisaih01, "fpo": cmd_fpo, "sihd": cmd_sihd, "transmissor": cmd_transmissor, "rede": cmd_rede, "print": cmd_print,
            "snapshots": cmd_snapshots, "apagar_snapshot": cmd_apagar_snapshot, "restaurar": cmd_restaurar, "versoes": cmd_versoes, "desligar": cmd_desligar}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="robo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=list(COMANDOS))
    ap.add_argument("extra", nargs=argparse.REMAINDER)   # aceita --confirmar, --versao, --pasta...
    args = ap.parse_args(argv)
    pasta_logs = configurar_logs()
    cfg = carregar_config()
    vbox = VBox(cfg)
    fila = Fila(cfg)
    log.info("===== robo %s %s =====", args.comando, " ".join(args.extra))
    try:
        return COMANDOS[args.comando](cfg, vbox, fila, pasta_logs, args)
    except RuntimeError as e:
        log.error(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
