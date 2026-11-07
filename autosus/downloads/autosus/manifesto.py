"""Registro (manifesto.json) do que ja foi baixado."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


class Manifesto:
    def __init__(self, caminho: Path, **padrao):
        self.caminho = caminho
        self.dados = {"itens": {}, "historico": [], "notificado_em": None, **padrao}
        if caminho.exists():
            with open(caminho, encoding="utf-8") as f:
                self.dados.update(json.load(f))

    @property
    def itens(self) -> dict:
        return self.dados["itens"]

    def item(self, nome: str) -> dict | None:
        return self.itens.get(nome)

    def registrar(self, nome: str, **info) -> None:
        info["registrado_em"] = dt.datetime.now().isoformat(timespec="seconds")
        anterior = self.itens.get(nome)
        if anterior and anterior.get("arquivo") != info.get("arquivo"):
            self.dados["historico"].append({"nome": nome, **anterior})
        self.itens[nome] = info

    @property
    def notificado(self) -> bool:
        return bool(self.dados.get("notificado_em"))

    def marcar_notificado(self) -> None:
        self.dados["notificado_em"] = dt.datetime.now().isoformat(timespec="seconds")

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2)
        tmp.replace(self.caminho)
