"""Server_SUS - API HTTP usada pelo AutoSUS: VM, snapshots, agente, arquivos e jobs de processamento.

Só expõe ações conhecidas, como o agente. Toda rota, menos /saude, exige o cabeçalho
"Authorization: Bearer <SERVER_SUS_TOKEN>" (token no server_sus\\.env).

Rodar: server_sus\\api.bat  (escuta em 127.0.0.1:8765)
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import secrets
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from nucleo import arquivos
from nucleo.config import PASTA, carregar_config, ler_estado, variavel_env
from nucleo.fila import Fila
from nucleo.jobs import Jobs
from nucleo.vbox import LIMITE_DISCO_GB, VBox, espaco_disco_vm, tirar_snapshot

VERSAO = "0.2.0"
log = logging.getLogger("robo")


def configurar_logs() -> None:
    pasta = PASTA / "logs"
    pasta.mkdir(exist_ok=True)
    fh = logging.FileHandler(pasta / f"api_{dt.date.today():%Y-%m-%d}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(fh)
    raiz.addHandler(logging.StreamHandler(sys.stdout))


configurar_logs()
cfg = carregar_config()
vbox = VBox(cfg)
fila = Fila(cfg)
trava_vm = threading.Lock()          # uma operação na VM por vez (ligar, desligar, snapshot)


def disco_da_vm_cheio() -> str | None:
    """Com o disco da VM cheio a VirtualBox pausa a VM no meio do processamento: melhor nem começar."""
    try:
        disco, livre = espaco_disco_vm(vbox)
    except RuntimeError as e:
        return f"não foi possível ler a VM: {e}"
    if livre < LIMITE_DISCO_GB:
        return (f"só {livre} GB livres no disco {disco}, onde a VM grava (mínimo {LIMITE_DISCO_GB} GB); "
                f"libere espaço ou apague snapshots antigos")
    return None


jobs = Jobs(Path(os.environ["SERVER_SUS_JOBS"]) if os.environ.get("SERVER_SUS_JOBS") else None,
            raiz_fila=fila.raiz, verificar=disco_da_vm_cheio)

app = FastAPI(title="Server_SUS", version=VERSAO,
              description="Controle da VM dos sistemas do SUS e do agente que opera os programas.")


# ------------------------------------------------------------------ autenticação

_bearer = HTTPBearer(auto_error=False)


def exigir_token(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    esperado = variavel_env("SERVER_SUS_TOKEN")
    if not esperado:
        raise HTTPException(503, "SERVER_SUS_TOKEN não configurado no server_sus\\.env")
    if cred is None or not secrets.compare_digest(cred.credentials, esperado):
        raise HTTPException(401, "token inválido", headers={"WWW-Authenticate": "Bearer"})


protegido = [Depends(exigir_token)]


# ------------------------------------------------------------------ modelos

class Agente(BaseModel):
    vivo: bool
    ultimo_sinal_segundos: float | None = None
    versao: str | None = None
    python: str | None = None
    usuario: str | None = None
    tarefas_na_fila: list[str] = []


class Vm(BaseModel):
    nome: str
    estado: str
    memoria_mb: int | None = None
    cpus: int | None = None
    espaco_livre_host_gb: float
    disco_vm: str
    espaco_livre_disco_vm_gb: float
    snapshots: list[str]
    versoes_instaladas: dict[str, str]


class NovoJob(BaseModel):
    competencia: str = Field(..., pattern=r"^20\d{2}(0[1-9]|1[0-2])$", description="AAAAMM, ex.: 202608")
    etapas: list[str] = Field(..., min_length=1, examples=[["iniciar", "atualizar", "sisaih01", "fpo", "sihd"]],
                              description="iniciar, atualizar, sisaih01, fpo, sihd, transmissor_testar "
                                          "ou restaurar:<snapshot>, na ordem em que devem rodar")
    sihd_manual: bool = Field(False, description="para nas AIHs bloqueadas (senão libera todas)")
    versao_sihd: int | None = None
    sihd_a_partir_de: str | None = Field(None, pattern=r"^[a-z_]{1,30}$")
    sem_snapshot: bool = Field(False, description="não tira snapshot antes de SISAIH01, FPO e SIHD")
    confirmar_envio: bool = Field(False, description="obrigatório (true) para a etapa transmissor_enviar, "
                                                     "que transmite o .DTS ao DATASUS")


class NovoSnapshot(BaseModel):
    nome: str | None = Field(None, pattern=r"^[\w.-]{1,60}$",
                             description="padrão: antes_AAAAMMDD_HHMM")
    descricao: str = "AutoSUS - snapshot pela API"


# ------------------------------------------------------------------ utilidades

def _int(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _erro_vbox(e: RuntimeError) -> HTTPException:
    log.error("API: %s", e)
    return HTTPException(409, str(e))


def sem_job_rodando() -> None:
    em_andamento = [j["id"] for j in jobs.listar() if j["situacao"] == "executando"]
    if em_andamento:
        raise HTTPException(409, f"há um job em andamento ({em_andamento[0]}); cancele ou espere terminar")


def ler_agente() -> Agente:
    b = fila.batimento()
    pendentes = sorted(p.stem for p in (fila.raiz / "fila").glob("*.json"))
    if not b:
        return Agente(vivo=False, tarefas_na_fila=pendentes)
    return Agente(vivo=fila.agente_vivo(), ultimo_sinal_segundos=round(b["_idade"], 1), versao=b.get("versao"),
                  python=b.get("python"), usuario=b.get("usuario"), tarefas_na_fila=pendentes)


def ler_vm() -> Vm:
    info = vbox.info()
    disco, livre = espaco_disco_vm(vbox)
    return Vm(nome=cfg["vm"], estado=info.get("VMState", "?"), memoria_mb=_int(info.get("memory")),
              cpus=_int(info.get("cpus")),
              espaco_livre_host_gb=round(shutil.disk_usage("C:\\").free / 2**30, 1),
              disco_vm=disco, espaco_livre_disco_vm_gb=livre,
              snapshots=vbox.snapshots(), versoes_instaladas=ler_estado().get("instalado", {}))


# ------------------------------------------------------------------ rotas

@app.get("/saude")
def saude() -> dict:
    """Sem token: só diz que a API está no ar."""
    return {"ok": True, "versao": VERSAO}


@app.get("/vm", dependencies=protegido)
def vm() -> Vm:
    try:
        return ler_vm()
    except RuntimeError as e:
        raise _erro_vbox(e) from e


@app.post("/vm/ligar", dependencies=protegido)
def vm_ligar() -> dict:
    """Liga (ou retoma) a VM e volta na hora. Acompanhe GET /agente até "vivo": true."""
    with trava_vm:
        try:
            estado = vbox.estado()
            if estado == "paused":
                log.warning("API: VM pausada; retomando")
                vbox.retomar()
            elif estado != "running":
                log.info("API: ligando a VM %s (estado: %s)", cfg["vm"], estado)
                vbox.ligar(cfg.get("abrir_vm", "gui"))
            return {"estado_anterior": estado, "estado": vbox.estado()}
        except RuntimeError as e:
            raise _erro_vbox(e) from e


@app.post("/vm/desligar", dependencies=protegido)
def vm_desligar() -> dict:
    """Desligamento normal (botão ACPI): o Windows da VM fecha os programas e desliga."""
    sem_job_rodando()
    with trava_vm:
        try:
            estado = vbox.estado()
            if estado == "running":
                log.info("API: desligando a VM %s (ACPI)", cfg["vm"])
                vbox.desligar()
            return {"estado_anterior": estado, "estado": vbox.estado()}
        except RuntimeError as e:
            raise _erro_vbox(e) from e


@app.get("/vm/snapshots", dependencies=protegido)
def snapshots() -> list[dict]:
    try:
        nomes = vbox.snapshots()
    except RuntimeError as e:
        raise _erro_vbox(e) from e
    registro = ler_estado().get("snapshots", {})
    return [{"nome": n, "versoes_instaladas": (registro.get(n) or {}).get("instalado", {})} for n in nomes]


@app.post("/vm/snapshots", dependencies=protegido, status_code=201)
def snapshot_novo(pedido: NovoSnapshot) -> dict:
    nome = pedido.nome or f"antes_{dt.datetime.now():%Y%m%d_%H%M}"
    sem_job_rodando()
    with trava_vm:
        try:
            if nome in vbox.snapshots():
                raise HTTPException(409, f"já existe um snapshot chamado {nome}")
            tirar_snapshot(vbox, nome, pedido.descricao)
        except RuntimeError as e:
            raise _erro_vbox(e) from e
    return {"nome": nome}


@app.get("/vm/print", dependencies=protegido, response_class=FileResponse)
def vm_print() -> FileResponse:
    """Print da tela da VM (PNG), para o AutoSUS mostrar o que está acontecendo."""
    destino = Path(tempfile.gettempdir()) / f"server_sus_print_{secrets.token_hex(4)}.png"
    try:
        vbox.print_tela(destino)
    except RuntimeError as e:
        raise _erro_vbox(e) from e
    return FileResponse(destino, media_type="image/png", background=BackgroundTask(destino.unlink, missing_ok=True))


@app.get("/agente", dependencies=protegido)
def agente() -> Agente:
    return ler_agente()


@app.post("/agente/ping", dependencies=protegido)
def agente_ping() -> dict:
    """Pede um ping ao agente e espera até 60 s pela resposta."""
    if not fila.agente_vivo():
        raise HTTPException(409, "agente sem sinal; ligue a VM (POST /vm/ligar) e aguarde")
    id_ = fila.pedir("ping")
    r = fila.esperar(id_, 60)
    if not r:
        raise HTTPException(504, "o agente não respondeu em 60 s")
    return {"ok": bool(r.get("ok")), "tarefa": id_, "dados": r.get("dados")}


# ------------------------------------------------------------------ arquivos por competência

def _competencia(aaaamm: str) -> str:
    try:
        return arquivos.validar_competencia(aaaamm)
    except arquivos.ArquivoRecusado as e:
        raise HTTPException(422, str(e)) from e


@app.get("/competencias/{aaaamm}/arquivos", dependencies=protegido)
def entrada(aaaamm: str) -> dict:
    """Arquivos de entrada da competência: o mais recente de cada item necessário, ou null se falta."""
    return arquivos.situacao_entrada(_competencia(aaaamm))


@app.post("/competencias/{aaaamm}/arquivos", dependencies=protegido, status_code=201)
def enviar_arquivo(aaaamm: str, arquivo: UploadFile = File(...),
                   sha256: str | None = Form(None, pattern=r"^[0-9a-fA-F]{64}$")) -> dict:
    """Recebe um arquivo da competência (ou um instalador) e confere o SHA-256, se informado.
    situacao: novo, ja_existe (igual ao que já estava) ou substituido (o anterior fica com _anterior_)."""
    try:
        r = arquivos.gravar(arquivo.filename or "", _competencia(aaaamm), arquivo.file, sha256)
    except arquivos.ArquivoRecusado as e:
        raise HTTPException(422, str(e)) from e
    log.info("API: arquivo %s (%s) %s", r["nome"], aaaamm, r["situacao"])
    return r


@app.get("/competencias/{aaaamm}/saidas", dependencies=protegido)
def saidas(aaaamm: str) -> dict:
    """Arquivos gerados para a apresentação (AIH .Zip, .VTP, .DTS, resumo do SIHD)."""
    comp = _competencia(aaaamm)
    return {"competencia": comp, "apresentacao": arquivos.apresentacao(comp), "arquivos": arquivos.listar_saidas(comp)}


# ------------------------------------------------------------------ jobs de processamento

@app.post("/jobs", dependencies=protegido, status_code=201)
def novo_job(pedido: NovoJob) -> dict:
    """Coloca um processamento na fila. Os jobs rodam um por vez; acompanhe com GET /jobs/{id}."""
    opcoes = pedido.model_dump(exclude={"competencia", "etapas"}, exclude_none=True)
    try:
        return jobs.criar(pedido.competencia, pedido.etapas, opcoes)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/jobs", dependencies=protegido)
def listar_jobs(limite: int = 20) -> list[dict]:
    return [{k: j.get(k) for k in ("id", "competencia", "etapas", "situacao", "criado", "inicio", "fim", "mensagem")}
            for j in jobs.listar()[:max(1, min(limite, 200))]]


@app.get("/jobs/{id_}", dependencies=protegido)
def ver_job(id_: str) -> dict:
    job = jobs.obter(id_)
    if not job:
        raise HTTPException(404, "job não encontrado")
    return job


@app.get("/jobs/{id_}/log", dependencies=protegido)
def log_job(id_: str, desde: int = 0) -> dict:
    """Saída do robô a partir do byte 'desde'; use o 'proximo' devolvido na chamada seguinte."""
    if not jobs.obter(id_):
        raise HTTPException(404, "job não encontrado")
    texto, proximo = jobs.log(id_, desde)
    return {"texto": texto, "proximo": proximo}


@app.post("/jobs/{id_}/cancelar", dependencies=protegido)
def cancelar_job(id_: str) -> dict:
    """Cancela: se estiver na fila, sai dela; se estiver rodando, o agente para no próximo passo
    (a tela aberta na VM fica como está)."""
    job = jobs.cancelar(id_)
    if not job:
        raise HTTPException(404, "job não encontrado")
    return job


@app.get("/jobs/{id_}/imagens/{nome}", dependencies=protegido, response_class=FileResponse)
def imagem_job(id_: str, nome: str) -> FileResponse:
    """Um print que o robô guardou durante o job (só os citados no log dele)."""
    job = jobs.obter(id_)
    if not job or nome not in job.get("imagens", []):
        raise HTTPException(404, "imagem não encontrada")
    arq = PASTA / "logs" / nome
    if not arq.is_file():
        raise HTTPException(404, "imagem não existe mais")
    return FileResponse(arq, media_type="image/png")
