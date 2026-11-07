"""Verificacao e download nos FTPs do DATASUS."""
from __future__ import annotations

import ftplib
import logging
import time
from pathlib import Path
from typing import Callable

from .comum import (BAIXADO, ERRO, JA_EXISTE, PENDENTE, SIMULADO, Resultado,
                    chave_letra, formatar_tamanho, guardar_anterior, montar_padrao,
                    sha256, validar_arquivo)
from .manifesto import Manifesto

log = logging.getLogger("autosus.ftp")


class FalhaFTP(Exception):
    pass


def _conectar(host: str, timeout: int) -> ftplib.FTP:
    nome, _, porta = host.partition(":")      # aceita "host" ou "host:porta"
    ftp = ftplib.FTP(timeout=timeout, encoding="latin-1")
    ftp.connect(nome, int(porta or 21))
    ftp.login()            # anonimo
    ftp.set_pasv(True)
    return ftp


def _com_tentativas(host: str, cfg_ftp: dict, operacao: Callable[[ftplib.FTP], object]):
    tentativas = int(cfg_ftp.get("tentativas", 3))
    timeout = int(cfg_ftp.get("timeout_segundos", 120))
    ultimo_erro: Exception | None = None
    for n in range(1, tentativas + 1):
        ftp = None
        try:
            ftp = _conectar(host, timeout)
            return operacao(ftp)
        except (ftplib.error_temp, ftplib.error_reply, ftplib.error_proto, OSError, EOFError) as e:
            ultimo_erro = e
            espera = 10 * 2 ** (n - 1)
            log.warning("%s: falha na tentativa %d/%d (%s)", host, n, tentativas, e)
            if n < tentativas:
                log.info("Nova tentativa em %ds...", espera)
                time.sleep(espera)
        finally:
            if ftp is not None:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
    raise FalhaFTP(f"{host}: {ultimo_erro}")


def _listar(ftp: ftplib.FTP, pasta: str) -> list[str]:
    ftp.cwd(pasta)
    try:
        nomes = ftp.nlst()
    except ftplib.error_perm as e:          # pasta vazia em alguns servidores
        if str(e).startswith("550"):
            return []
        raise
    return [n.replace("\\", "/").rsplit("/", 1)[-1] for n in nomes]


def _info_remota(ftp: ftplib.FTP, nome: str) -> tuple[int | None, str | None]:
    ftp.voidcmd("TYPE I")
    try:
        tamanho = ftp.size(nome)
    except ftplib.all_errors:
        tamanho = None
    try:
        mdtm = ftp.voidcmd(f"MDTM {nome}").split()[-1]
    except ftplib.all_errors:
        mdtm = None
    return tamanho, mdtm


def _baixar(ftp: ftplib.FTP, nome: str, destino: Path, tamanho_esperado: int | None) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    inicio = time.monotonic()
    with open(parcial, "wb") as f:
        ftp.retrbinary(f"RETR {nome}", f.write, blocksize=1 << 16)
    obtido = parcial.stat().st_size
    if tamanho_esperado is not None and obtido != tamanho_esperado:
        parcial.unlink(missing_ok=True)
        raise OSError(f"tamanho incompleto: {obtido} de {tamanho_esperado} bytes")
    try:
        validar_arquivo(parcial)
    except ValueError:
        parcial.unlink(missing_ok=True)
        raise
    parcial.replace(destino)
    log.info("  baixado %s (%s em %.0fs)", destino.name, formatar_tamanho(obtido),
             time.monotonic() - inicio)
    return obtido


def _sincronizar(*, nome_item: str, host: str, pasta: str, padrao, chave, local_dir: Path,
                 manifesto: Manifesto, cfg_ftp: dict, simular: bool, rotulo_versao: Callable,
                 filtro: Callable | None = None) -> Resultado:
    """Lista a pasta, escolhe o maior candidato e baixa se for novo."""
    url = f"ftp://{host}{pasta}"
    log.info("%s: verificando %s", nome_item, url)

    def operacao(ftp: ftplib.FTP) -> Resultado:
        nomes = _listar(ftp, pasta)
        candidatos = [(n, m) for n in nomes if (m := padrao.match(n))]
        if filtro is not None:
            todos = sorted(rotulo_versao(m) for _, m in candidatos)
            candidatos = [(n, m) for n, m in candidatos if filtro(m)]
            if not candidatos:
                log.info("  versao pedida nao encontrada; versoes no servidor: %s", ", ".join(todos) or "nenhuma")
                return Resultado(nome_item, ERRO, detalhe="versao pedida nao existe no servidor "
                                 f"(disponiveis: {', '.join(todos) or 'nenhuma'})")
        if not candidatos:
            log.info("  nenhum arquivo encontrado para o padrao %s", padrao.pattern)
            return Resultado(nome_item, PENDENTE, detalhe="ainda nao publicado")
        escolhido, match = max(candidatos, key=lambda c: chave(c[1]))
        log.info("  %d candidato(s); escolhido: %s", len(candidatos), escolhido)
        tamanho_remoto, mdtm = _info_remota(ftp, escolhido)

        registro = manifesto.item(nome_item)
        if filtro is not None:            # versao antiga pedida: nao mexe no registro da versao atual
            registro = manifesto.item(f"{nome_item}_{rotulo_versao(match)}")
            nome_reg = f"{nome_item}_{rotulo_versao(match)}"
        else:
            nome_reg = nome_item
        revisao_nova = bool(registro) and registro.get("arquivo", "").lower() != escolhido.lower()
        destino = local_dir / escolhido

        # Mesmo nome mas data de modificacao remota diferente da registrada = conteudo novo
        mudou_no_servidor = bool(registro and registro.get("arquivo") == escolhido and mdtm
                                 and registro.get("mdtm") and registro["mdtm"] != mdtm)
        igual = (destino.exists()
                 and (tamanho_remoto is None or destino.stat().st_size == tamanho_remoto)
                 and not mudou_no_servidor)
        if igual:
            if not registro or registro.get("arquivo") != escolhido:
                manifesto.registrar(nome_reg, arquivo=escolhido, tamanho=destino.stat().st_size,
                                    sha256=sha256(destino), mdtm=mdtm, origem=f"{url}/{escolhido}",
                                    versao=rotulo_versao(match))
            log.info("  %s ja existe localmente", escolhido)
            return Resultado(nome_item, JA_EXISTE, escolhido, tamanho=destino.stat().st_size)

        if simular:
            det = formatar_tamanho(tamanho_remoto) if tamanho_remoto else ""
            return Resultado(nome_item, SIMULADO, escolhido, det, revisao_nova)

        if destino.exists():   # mesmo nome, conteudo diferente: guarda o antigo
            antigo = guardar_anterior(destino)
            log.info("  conteudo remoto mudou; copia anterior guardada como %s", antigo.name)
            revisao_nova = True
        obtido = _baixar(ftp, escolhido, destino, tamanho_remoto)
        manifesto.registrar(nome_reg, arquivo=escolhido, tamanho=obtido, sha256=sha256(destino),
                            mdtm=mdtm, origem=f"{url}/{escolhido}", versao=rotulo_versao(match))
        return Resultado(nome_item, BAIXADO, escolhido, revisao_nova=revisao_nova, tamanho=obtido)

    try:
        return _com_tentativas(host, cfg_ftp, operacao)
    except (FalhaFTP, ftplib.error_perm, ValueError) as e:
        log.error("%s: %s", nome_item, e)
        return Resultado(nome_item, ERRO, detalhe=str(e))


def verificar_programa(item: dict, pasta_programas: Path, manifesto: Manifesto,
                       cfg_ftp: dict, simular: bool, versao: str | None = None) -> Resultado:
    """Baixa a maior versao; com 'versao', baixa exatamente aquela (ex.: para reprocessar
    uma competencia antiga com a versao da epoca)."""
    padrao = montar_padrao(item["padrao"])
    filtro = (lambda m: int(m.group("versao")) == int(versao)) if versao else None
    return _sincronizar(
        nome_item=item["nome"], host=item["host"], pasta=item["pasta"], padrao=padrao,
        chave=lambda m: int(m.group("versao")), local_dir=pasta_programas, manifesto=manifesto,
        cfg_ftp=cfg_ftp, simular=simular, rotulo_versao=lambda m: m.group("versao"), filtro=filtro)


def verificar_competencia(item: dict, competencia: str, uf: str, municipio: str, pasta_local: Path,
                          manifesto: Manifesto, cfg_ftp: dict, simular: bool) -> Resultado:
    padrao = montar_padrao(item["padrao"], competencia=competencia, uf=uf, municipio=municipio)
    return _sincronizar(
        nome_item=item["nome"], host=item["host"], pasta=item["pasta"], padrao=padrao,
        chave=lambda m: chave_letra(m.group("letra")), local_dir=pasta_local, manifesto=manifesto,
        cfg_ftp=cfg_ftp, simular=simular, rotulo_versao=lambda m: (m.group("letra") or "").lower())
