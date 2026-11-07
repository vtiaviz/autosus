"""Avisos: notificacao do Windows e e-mail pelo Gmail."""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage

log = logging.getLogger("autosus.aviso")

_PS_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName('text')
$x.Item(0).AppendChild($t.CreateTextNode($env:AUTOSUS_TITULO)) | Out-Null
$x.Item(1).AppendChild($t.CreateTextNode($env:AUTOSUS_TEXTO)) | Out-Null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($t))
"""


def notificar_windows(titulo: str, texto: str) -> bool:
    if sys.platform != "win32":
        log.info("Notificacao do Windows (simulada): %s - %s", titulo, texto)
        return False
    env = dict(os.environ, AUTOSUS_TITULO=titulo, AUTOSUS_TEXTO=texto[:250])
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS_TOAST],
                       env=env, check=True, capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log.info("Notificacao do Windows enviada")
        return True
    except Exception as e:
        log.warning("Nao foi possivel mostrar a notificacao do Windows: %s", e)
        return False


def enviar_email(cfg_aviso: dict, assunto: str, corpo: str) -> bool:
    usuario = os.getenv("GMAIL_USUARIO", "").strip()
    senha = os.getenv("GMAIL_SENHA_APP", "").replace(" ", "").strip()
    destino = cfg_aviso.get("destinatario") or usuario
    if not usuario or not senha:
        log.warning("E-mail nao enviado: preencha GMAIL_USUARIO e GMAIL_SENHA_APP no .env")
        return False
    msg = EmailMessage()
    msg["From"] = usuario
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(corpo)
    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg_aviso.get("smtp_host", "smtp.gmail.com"),
                              int(cfg_aviso.get("smtp_porta", 465)), context=contexto, timeout=60) as s:
            s.login(usuario, senha)
            s.send_message(msg)
        log.info("E-mail enviado para %s", destino)
        return True
    except Exception as e:
        log.error("Falha ao enviar e-mail: %s", e)
        return False


def avisar(cfg_aviso: dict, titulo: str, texto_curto: str, corpo_email: str) -> bool:
    ok = True
    if cfg_aviso.get("windows", True):
        notificar_windows(titulo, texto_curto)
    if cfg_aviso.get("email", True):
        ok = enviar_email(cfg_aviso, titulo, corpo_email)
    return ok
