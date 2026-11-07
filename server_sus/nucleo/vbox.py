"""VirtualBox: comandos VBoxManage na VM e snapshots com conferência de espaço."""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from .config import gravar_estado, ler_estado

log = logging.getLogger("robo")

LIMITE_DISCO_GB = 10       # abaixo disso no disco da VM, avisa (robo) ou não começa job (API)


class VBox:
    def __init__(self, cfg: dict):
        self.exe = cfg["vboxmanage"]
        self.vm = cfg["vm"]

    def _rodar(self, *args: str, verificar: bool = True) -> str:
        r = subprocess.run([self.exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if verificar and r.returncode != 0:
            raise RuntimeError(f"VBoxManage {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
        return r.stdout

    def info(self) -> dict:
        out = self._rodar("showvminfo", self.vm, "--machinereadable")
        dados = {}
        for linha in out.splitlines():
            if "=" in linha:
                k, v = linha.split("=", 1)
                dados[k.strip('"')] = v.strip('"')
        return dados

    def estado(self) -> str:
        return self.info().get("VMState", "?")

    def ligar(self, tipo: str) -> None:
        # logo depois de restaurar/desligar, a VirtualBox ainda pode estar soltando a sessão da VM
        # ("already locked by a session"): espera e tenta de novo por até 2 minutos
        fim = time.time() + 120
        while True:
            try:
                self._rodar("startvm", self.vm, "--type", tipo)
                return
            except RuntimeError as e:
                texto = str(e)
                if time.time() > fim or not ("already locked" in texto or "INVALID_OBJECT_STATE" in texto):
                    raise
                log.info("  a VirtualBox ainda está liberando a VM; tentando ligar de novo em 5 s...")
                time.sleep(5)

    def snapshot(self, nome: str, descricao: str) -> None:
        self._rodar("snapshot", self.vm, "take", nome, "--description", descricao)

    def rede_estado(self) -> dict:
        """Placa 1 da VM: tipo (nat, bridged...) e se o cabo virtual está conectado."""
        info = self.info()
        return {"tipo": info.get("nic1", "none"), "cabo": info.get("cableconnected1", "off")}

    def rede(self, ligar: bool) -> None:
        """Conecta/desconecta o cabo virtual da placa 1 (a VM continua ligada)."""
        self._rodar("controlvm", self.vm, "setlinkstate1", "on" if ligar else "off")

    def apagar_snapshot(self, nome: str) -> None:
        self._rodar("snapshot", self.vm, "delete", nome)

    def restaurar(self, nome: str) -> None:
        self._rodar("snapshot", self.vm, "restore", nome)

    def desligar_forcado(self) -> None:
        self._rodar("controlvm", self.vm, "poweroff")

    def snapshots(self) -> list[str]:
        return [v for k, v in self.info().items() if k.startswith("SnapshotName")]

    def print_tela(self, destino: Path) -> None:
        self._rodar("controlvm", self.vm, "screenshotpng", str(destino))

    def resolucao(self, largura: int, altura: int) -> None:
        self._rodar("controlvm", self.vm, "setvideomodehint", str(largura), str(altura), "32")

    def retomar(self) -> None:
        self._rodar("controlvm", self.vm, "resume")

    def desligar(self) -> None:
        self._rodar("controlvm", self.vm, "acpipowerbutton")


def disco_da_vm(info: dict) -> str:
    """Disco onde a VM grava (pasta de snapshots, onde ficam o estado salvo e o disco de trabalho)."""
    for chave in ("SnapFldr", "CfgFile"):
        ancora = Path(info.get(chave) or "").anchor
        if ancora:
            return ancora
    return "C:\\"


def tirar_snapshot(vbox: "VBox", nome: str, descricao: str) -> None:
    """Snapshot com a VM ligada grava a memória inteira (.sav) no disco do host: confere o espaço antes."""
    info = vbox.info()
    precisa = int(info.get("memory") or 4096) / 1024 * 1.3 + 2           # memória + 30% + 2 GB de folga
    livre = shutil.disk_usage(disco_da_vm(info)).free / 2**30
    if livre < precisa:
        raise RuntimeError(f"pouco espaço no disco do host para o snapshot: {livre:.1f} GB livres, precisa de "
                           f"~{precisa:.0f} GB. Apague snapshots antigos (robo.bat snapshots / apagar_snapshot) "
                           f"ou libere espaço.")
    try:
        vbox.snapshot(nome, descricao)
    except RuntimeError:
        if vbox.estado() == "paused":                    # a VirtualBox pausa a VM quando o disco enche
            try:
                vbox.retomar()
                log.warning("A VM tinha pausado com a falha do snapshot e foi retomada.")
            except RuntimeError:
                log.error("A VM ficou pausada; depois de liberar espaço rode: robo.bat iniciar")
        raise
    estado = ler_estado()
    estado.setdefault("snapshots", {})[nome] = {"instalado": dict(estado.get("instalado", {})),
                                                 "sisaih01_sessao": estado.get("sisaih01_sessao")}
    gravar_estado(estado)
    log.info("Snapshot criado: %s (para voltar: robo.bat restaurar %s --confirmar)", nome, nome)


def espaco_disco_vm(vbox: VBox) -> tuple[str, float]:
    """Disco onde a VM grava (disco virtual e snapshots) e o espaço livre nele, em GB."""
    disco = disco_da_vm(vbox.info())
    return disco, round(shutil.disk_usage(disco).free / 2**30, 1)
