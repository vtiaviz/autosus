r"""Fila de tarefas para o agente da VM, pela pasta compartilhada (\\VBOXSVR\<nome>\_robo)."""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
import uuid
from pathlib import Path

log = logging.getLogger("robo")


class Fila:
    def __init__(self, cfg: dict):
        self.raiz = Path(cfg["pasta_compartilhada"]) / "_robo"
        for sub in ("fila", "andamento", "resultados", "entrada", "logs", "agente", "cancelar"):
            (self.raiz / sub).mkdir(parents=True, exist_ok=True)

    def batimento(self) -> dict | None:
        arq = self.raiz / "agente.vivo"
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
            dados["_idade"] = time.time() - arq.stat().st_mtime
            return dados
        except (OSError, ValueError):
            return None

    def agente_vivo(self, limite: float = 40) -> bool:
        b = self.batimento()
        return bool(b and b["_idade"] < limite)

    def pedir(self, tipo: str, **parametros) -> str:
        id_ = f"{dt.datetime.now():%Y%m%d_%H%M%S}_{tipo}_{uuid.uuid4().hex[:6]}"
        tarefa = {"id": id_, "tipo": tipo, "parametros": parametros,
                  "pedido_em": dt.datetime.now().isoformat(timespec="seconds")}
        tmp = self.raiz / "fila" / f"{id_}.tmp"
        tmp.write_text(json.dumps(tarefa, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(tmp.with_suffix(".json"))
        log.info("tarefa enviada: %s", id_)
        return id_

    def esperar(self, id_: str, limite: float) -> dict | None:
        try:
            return self._esperar(id_, limite)
        except KeyboardInterrupt:
            # Ctrl+C: avisa o agente para largar a tarefa (ele confere entre um passo e outro)
            (self.raiz / "cancelar").mkdir(exist_ok=True)
            (self.raiz / "cancelar" / id_).write_text("cancelar", encoding="utf-8")
            log.warning("Cancelamento pedido ao agente para a tarefa %s. Ele para no próximo passo; "
                        "a tela que estiver aberta na VM fica como está.", id_)
            raise

    def _esperar(self, id_: str, limite: float) -> dict | None:
        arq = self.raiz / "resultados" / f"{id_}.json"
        fim = time.time() + limite
        ultimo_aviso = 0.0
        while time.time() < fim:
            if arq.exists():
                try:
                    return json.loads(arq.read_text(encoding="utf-8"))
                except ValueError:
                    pass                      # ainda sendo gravado
            if time.time() - ultimo_aviso > 60:
                andamento = (self.raiz / "andamento" / f"{id_}.json").exists()
                try:
                    progresso = (self.raiz / "andamento" / f"{id_}.progresso").read_text(encoding="utf-8").strip()
                except OSError:
                    progresso = ""
                log.info("  aguardando o agente (%s)...", progresso or ("executando" if andamento else "na fila"))
                ultimo_aviso = time.time()
            time.sleep(2)
        return None
