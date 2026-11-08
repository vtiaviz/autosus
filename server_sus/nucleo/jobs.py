"""Jobs de processamento: uma fila de etapas executadas uma por vez pelo robo.py.

Cada etapa vira um ou mais comandos do robo.py, rodados como processo separado (o mesmo código
que o robo.bat e o teste_completo.ps1 usam). O job fica em server_sus/jobs/<id>/:
  job.json    pedido, situação, passos e resultado
  saida.log   tudo o que o robo.py escreveu
Situações: na_fila, executando, concluido, falhou, aguardando_decisao, cancelado, interrompido.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from .arquivos import apresentacao, pasta_saida
from .config import PASTA

log = logging.getLogger("robo")

ORDEM = ["iniciar", "atualizar", "sisaih01", "fpo", "sihd", "transmissor_testar", "transmissor_enviar"]
# a única etapa que manda algo para fora: só roda com "confirmar_envio": true no pedido
ENVIO = "transmissor_enviar"
FINAIS = {"concluido", "falhou", "aguardando_decisao", "cancelado", "interrompido"}
COD_DECISAO = 3          # robo.py sihd completo --manual: AIHs bloqueadas esperando decisão


def _mm_aaaa(aaaamm: str) -> str:
    return f"{aaaamm[4:]}/{aaaamm[:4]}"


def comandos(etapa: str, comp: str, opcoes: dict) -> list[list[str]]:
    """Comandos do robo.py de uma etapa. comp = competência AAAAMM."""
    sem_snap = ["--sem-snapshot"] if opcoes.get("sem_snapshot") else []
    if etapa.startswith("restaurar:"):
        nome = etapa.split(":", 1)[1]
        return [["restaurar", nome, "--confirmar"], ["iniciar"], ["preparar"]]
    if etapa == "iniciar":
        return [["iniciar"], ["preparar"]]
    if etapa == "atualizar":
        return [["instalar"]]
    if etapa == "sisaih01":
        return [["sisaih01", "completo", _mm_aaaa(apresentacao(comp)), "--confirmar", *sem_snap]]
    if etapa == "fpo":
        return [["fpo", "completo", _mm_aaaa(comp), *sem_snap]]
    if etapa == "sihd":
        sihd = ["sihd", "completo", _mm_aaaa(comp), "--confirmar", "--manual" if opcoes.get("sihd_manual") else "--auto"]
        if opcoes.get("versao_sihd"):
            sihd += ["--versao", str(opcoes["versao_sihd"])]
        if opcoes.get("sihd_a_partir_de"):
            sihd += ["--a-partir-de", opcoes["sihd_a_partir_de"]]
        return [sihd + sem_snap]
    if etapa == "transmissor_testar":
        return [["transmissor", "preparar", _mm_aaaa(comp)], ["transmissor", "testar"]]
    if etapa == ENVIO:
        if opcoes.get("confirmar_envio") is not True:
            raise ValueError("a transmissão para o DATASUS exige \"confirmar_envio\": true")
        return [["transmissor", "preparar", _mm_aaaa(comp)], ["transmissor", "enviar", "--confirmar"]]
    raise ValueError(f"etapa desconhecida: {etapa}")


def esperados(etapa: str, comp: str) -> list[str]:
    """Arquivos que a etapa deixa em saida/<apresentação>/ (conferidos no fim do job)."""
    return {"sisaih01": [f"{apresentacao(comp)}AIH*.Zip"],
            "fpo": [f"Valores_{comp}.VTP"],
            "sihd": [f"*{comp}.DTS", f"SIH{comp[2:]}.txt"]}.get(etapa, [])


def validar_etapas(etapas: list[str]) -> list[str]:
    if not etapas:
        raise ValueError("informe ao menos uma etapa")
    for e in etapas:
        if e.startswith("restaurar:"):
            if not re.fullmatch(r"restaurar:[\w.-]{1,60}", e):
                raise ValueError(f"nome de snapshot inválido em {e!r}")
        elif e not in ORDEM:
            raise ValueError(f"etapa desconhecida: {e!r} (opções: {', '.join(ORDEM)} ou restaurar:<snapshot>)")
    return etapas


def rodar_robo(args: list[str], ao_ler: Callable[[str], None], parar: threading.Event,
               ao_iniciar: Callable[[subprocess.Popen], None]) -> int:
    """Roda 'python robo.py <args>' e repassa cada linha. Devolve o código de saída."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([sys.executable, str(PASTA / "robo.py"), *args], cwd=PASTA, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ao_iniciar(proc)
    for linha in proc.stdout:
        ao_ler(linha.rstrip("\n"))
        if parar.is_set():
            break
    if parar.is_set() and proc.poll() is None:
        proc.terminate()
    return proc.wait()


class Jobs:
    def __init__(self, pasta: Path | None = None, executor=rodar_robo, raiz_fila: Path | None = None,
                 verificar: Callable[[], str | None] | None = None):
        self.pasta = pasta or PASTA / "jobs"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self.raiz_fila = raiz_fila            # <compartilhada>/_robo, para cancelar e ler o progresso
        self.verificar = verificar            # antes de cada passo: devolve um motivo para não seguir
        self._trava = threading.Lock()
        self._novo = threading.Event()
        self._parar_atual = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._tarefa_agente: str | None = None
        self._atual: str | None = None
        self._recuperar()
        threading.Thread(target=self._trabalhar, name="jobs", daemon=True).start()

    # ---------------------------------------------------------------- persistência

    def _arq(self, id_: str) -> Path:
        return self.pasta / id_ / "job.json"

    def _ler(self, id_: str) -> dict:
        return ler_json(self._arq(id_))

    def _gravar(self, job: dict) -> None:
        # no Windows, trocar o arquivo falha enquanto outra thread o lê: tenta de novo por até 2 s
        arq = self._arq(job["id"])
        tmp = arq.with_name(f"job.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        for _ in range(100):
            try:
                tmp.replace(arq)
                return
            except PermissionError:
                time.sleep(0.02)
        tmp.replace(arq)

    def _recuperar(self) -> None:
        """Jobs que estavam rodando quando a API caiu não são retomados sozinhos."""
        for arq in self.pasta.glob("*/job.json"):
            job = ler_json(arq)
            if job["situacao"] in ("executando", "na_fila"):
                job["situacao"] = "interrompido"
                job["mensagem"] = "a API do Server_SUS foi reiniciada durante o job"
                job["fim"] = agora()
                self._gravar(job)

    # ---------------------------------------------------------------- consulta

    def listar(self) -> list[dict]:
        jobs = [ler_json(a) for a in self.pasta.glob("*/job.json")]
        return sorted(jobs, key=lambda j: j.get("ordem", 0), reverse=True)

    def obter(self, id_: str) -> dict | None:
        if not re.fullmatch(r"[\w-]+", id_) or not self._arq(id_).exists():
            return None
        job = self._ler(id_)
        if job["situacao"] == "executando" and id_ == self._atual:
            job["progresso_agente"] = self._progresso_agente()
        return job

    def log(self, id_: str, desde: int = 0) -> tuple[str, int]:
        arq = self.pasta / id_ / "saida.log"
        if not arq.exists():
            return "", 0
        with open(arq, "rb") as f:
            f.seek(max(0, desde))
            dados = f.read()
        return dados.decode("utf-8", errors="replace"), desde + len(dados)

    def _progresso_agente(self) -> str | None:
        if not (self.raiz_fila and self._tarefa_agente):
            return None
        try:
            return (self.raiz_fila / "andamento" / f"{self._tarefa_agente}.progresso").read_text(encoding="utf-8").strip()
        except OSError:
            return None

    # ---------------------------------------------------------------- pedidos

    def criar(self, competencia: str, etapas: list[str], opcoes: dict | None = None) -> dict:
        opcoes = opcoes or {}
        validar_etapas(etapas)
        id_ = f"{dt.datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        passos = [{"etapa": e, "args": a, "situacao": "pendente"} for e in etapas for a in comandos(e, competencia, opcoes)]
        job = {"id": id_, "competencia": competencia, "apresentacao": apresentacao(competencia), "etapas": etapas,
               "opcoes": opcoes, "situacao": "na_fila", "criado": agora(), "ordem": time.time_ns(),
               "inicio": None, "fim": None,
               "passo_atual": None, "passos": passos, "mensagem": None, "conferencia": None, "imagens": []}
        (self.pasta / id_).mkdir()
        self._gravar(job)
        log.info("job criado: %s (%s, etapas %s)", id_, competencia, ", ".join(etapas))
        self._novo.set()
        return job

    def cancelar(self, id_: str) -> dict | None:
        with self._trava:
            job = self.obter(id_)
            if not job or job["situacao"] in FINAIS:
                return job
            if job["situacao"] == "na_fila":
                job.update(situacao="cancelado", fim=agora(), mensagem="cancelado antes de começar")
                self._gravar(job)
                return job
        if id_ == self._atual:
            self._parar_atual.set()
            if self.raiz_fila and self._tarefa_agente:     # o agente larga a tarefa no próximo passo
                (self.raiz_fila / "cancelar").mkdir(parents=True, exist_ok=True)
                (self.raiz_fila / "cancelar" / self._tarefa_agente).write_text("cancelar", encoding="utf-8")
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        return self.obter(id_)

    # ---------------------------------------------------------------- execução

    def _proximo(self) -> dict | None:
        fila = [j for j in self.listar() if j["situacao"] == "na_fila"]
        return min(fila, key=lambda j: j.get("ordem", 0)) if fila else None     # o mais antigo primeiro

    def _trabalhar(self) -> None:
        while True:
            job = self._proximo()
            if not job:
                self._novo.wait(5)
                self._novo.clear()
                continue
            try:
                self._executar(job)
            except Exception as e:                       # nunca derruba o trabalhador
                log.exception("job %s: erro inesperado", job["id"])
                job.update(situacao="falhou", fim=agora(), mensagem=f"erro inesperado: {e}")
                self._gravar(job)
            finally:
                self._atual = self._tarefa_agente = None

    def _executar(self, job: dict) -> None:
        self._atual = job["id"]
        self._parar_atual.clear()
        job.update(situacao="executando", inicio=agora())
        self._gravar(job)
        arq_log = self.pasta / job["id"] / "saida.log"
        log.info("job %s: começou", job["id"])
        with open(arq_log, "a", encoding="utf-8") as saida:
            def ao_ler(linha: str) -> None:
                saida.write(linha + "\n")
                saida.flush()
                m = re.search(r"tarefa enviada: (\S+)", linha)
                if m:
                    self._tarefa_agente = m.group(1)
                # prints que o robô guardou em server_sus/logs: o AutoSUS mostra (resultado do Transmissor etc.)
                img = re.search(r"(?:print da tela|arquivo): .*?([\w.-]+\.png)\s*$", linha)
                if img and img.group(1) not in job.setdefault("imagens", []):
                    job["imagens"].append(img.group(1))

            def ao_iniciar(proc) -> None:
                self._proc = proc

            for i, passo in enumerate(job["passos"]):
                with self._trava:
                    if self._parar_atual.is_set():
                        return self._fechar(job, "cancelado", "cancelado pelo usuário")
                    job["passo_atual"] = i
                    passo.update(situacao="executando", inicio=agora())
                    self._gravar(job)
                problema = self.verificar() if self.verificar else None
                if problema:
                    passo["situacao"] = "falhou"
                    saida.write(f"\n*** {problema}\n")
                    return self._fechar(job, "falhou", problema)
                saida.write(f"\n===== {agora()}  robo {' '.join(passo['args'])} =====\n")
                self._tarefa_agente = None
                codigo = self.executor(passo["args"], ao_ler, self._parar_atual, ao_iniciar)
                passo.update(fim=agora(), codigo=codigo)
                if self._parar_atual.is_set():
                    passo["situacao"] = "cancelado"
                    return self._fechar(job, "cancelado", "cancelado pelo usuário")
                if codigo == COD_DECISAO and passo["etapa"] == "sihd":
                    passo["situacao"] = "aguardando_decisao"
                    return self._fechar(job, "aguardando_decisao",
                                        "AIHs bloqueadas no SIHD2 esperando decisão (veja o log)")
                if codigo != 0:
                    passo["situacao"] = "falhou"
                    return self._fechar(job, "falhou", f"robo {' '.join(passo['args'][:2])} terminou com código {codigo}")
                passo["situacao"] = "concluido"
                self._gravar(job)
        conf = self._conferir(job)
        job["conferencia"] = conf
        faltou = [c["padrao"] for c in conf if not c["novo"]]
        if faltou:
            return self._fechar(job, "falhou", "o job terminou, mas não gerou: " + ", ".join(faltou))
        return self._fechar(job, "concluido", None)

    def _conferir(self, job: dict) -> list[dict]:
        """Cada saída esperada precisa existir e ter sido gerada depois do início do job."""
        pasta = pasta_saida(job["competencia"])
        inicio = dt.datetime.fromisoformat(job["inicio"]).timestamp()
        resultado = []
        for etapa in job["etapas"]:
            for padrao in esperados(etapa, job["competencia"]):
                achados = sorted((p for p in pasta.glob("*") if fnmatch.fnmatch(p.name.lower(), padrao.lower())),
                                 key=lambda p: p.stat().st_mtime) if pasta.is_dir() else []
                ultimo = achados[-1] if achados else None
                resultado.append({"etapa": etapa, "padrao": padrao, "arquivo": ultimo.name if ultimo else None,
                                  "novo": bool(ultimo and ultimo.stat().st_mtime >= inicio - 1)})
        return resultado

    def _fechar(self, job: dict, situacao: str, mensagem: str | None) -> None:
        job.update(situacao=situacao, mensagem=mensagem, fim=agora())
        self._gravar(job)
        log.info("job %s: %s%s", job["id"], situacao, f" ({mensagem})" if mensagem else "")


def ler_json(arq: Path) -> dict:
    """Lê o job.json; se ele estiver sendo trocado naquele instante, tenta de novo por até 2 s."""
    for _ in range(100):
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except (PermissionError, ValueError):
            time.sleep(0.02)
    return json.loads(arq.read_text(encoding="utf-8"))


def agora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")
