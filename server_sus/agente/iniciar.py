# -*- coding: utf-8 -*-
"""Inicia o agente do AutoSUS dentro da VM (atalho na pasta Inicializar).

Antes de iniciar, copia da pasta compartilhada a versão mais nova do agente, para que as
atualizações feitas pelo 'robo.bat preparar' no host passem a valer no próximo login.
"""
import os
import runpy
import shutil
import sys
import time

LOCAL = os.path.dirname(os.path.abspath(__file__))
COMPARTILHAMENTO = os.environ.get("AUTOSUS_COMPARTILHAMENTO", "AIH")
ORIGEM = r"\\VBOXSVR\%s\_robo\agente" % COMPARTILHAMENTO

for tentativa in range(30):          # a pasta compartilhada pode demorar a ficar disponível no login
    if os.path.isdir(ORIGEM):
        break
    time.sleep(5)

for nome in ("agente.py", "iniciar.py"):
    origem = os.path.join(ORIGEM, nome)
    destino = os.path.join(LOCAL, nome)
    try:
        if os.path.exists(origem) and (not os.path.exists(destino) or os.path.getmtime(origem) > os.path.getmtime(destino)):
            shutil.copy2(origem, destino)
    except OSError:
        pass

sys.path.insert(0, LOCAL)
runpy.run_path(os.path.join(LOCAL, "agente.py"), run_name="__main__")
