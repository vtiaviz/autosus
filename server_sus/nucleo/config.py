"""Configuração, estado da VM e credenciais do Server_SUS (usado pelo robo.py e pela API)."""
from __future__ import annotations

import json
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent          # C:\AutoSUS\server_sus
DOWNLOADS = PASTA.parent / "autosus" / "downloads"      # downloader do AutoSUS: config.yaml


def carregar_config() -> dict:
    import yaml
    with open(PASTA / "config_robo.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(DOWNLOADS / "config.yaml", encoding="utf-8") as f:
        cfg["_autosus"] = yaml.safe_load(f)
    return cfg


ESTADO = PASTA / "estado_vm.json"


def ler_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"instalado": {}, "apresentacao_por_versao": {}}


def gravar_estado(estado: dict) -> None:
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def credenciais(prefixo: str, padrao_usuario: str, padrao_senha: str) -> dict:
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(PASTA / ".env")
    except ImportError:
        pass
    return {"usuario": os.getenv(f"{prefixo}_USUARIO", padrao_usuario),
            "senha": os.getenv(f"{prefixo}_SENHA", padrao_senha)}


def variavel_env(nome: str, padrao: str = "") -> str:
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(PASTA / ".env")
    except ImportError:
        pass
    return (os.getenv(nome) or padrao).strip()
