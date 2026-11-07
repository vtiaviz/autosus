"""Server_SUS - API HTTP usada pelo AutoSUS (etapa 2: VM, snapshots e agente).

Só expõe ações conhecidas, como o agente. Toda rota, menos /saude, exige o cabeçalho
"Authorization: Bearer <SERVER_SUS_TOKEN>" (token no server_sus\\.env).

Rodar: server_sus\\api.bat  (escuta em 127.0.0.1:8765)
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from nucleo.config import PASTA, carregar_config, ler_estado, variavel_env
from nucleo.fila import Fila
from nucleo.vbox import VBox, tirar_snapshot

VERSAO = "0.1.0"
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
    snapshots: list[str]
    versoes_instaladas: dict[str, str]


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


def ler_agente() -> Agente:
    b = fila.batimento()
    pendentes = sorted(p.stem for p in (fila.raiz / "fila").glob("*.json"))
    if not b:
        return Agente(vivo=False, tarefas_na_fila=pendentes)
    return Agente(vivo=fila.agente_vivo(), ultimo_sinal_segundos=round(b["_idade"], 1), versao=b.get("versao"),
                  python=b.get("python"), usuario=b.get("usuario"), tarefas_na_fila=pendentes)


def ler_vm() -> Vm:
    info = vbox.info()
    return Vm(nome=cfg["vm"], estado=info.get("VMState", "?"), memoria_mb=_int(info.get("memory")),
              cpus=_int(info.get("cpus")),
              espaco_livre_host_gb=round(shutil.disk_usage("C:\\").free / 2**30, 1),
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
