# -*- coding: utf-8 -*-
"""AutoSUS - agente do robô (roda DENTRO da VM, na sessão do usuário logado).

Fica observando a pasta compartilhada \\\\VBOXSVR\\<compartilhamento>\\_robo\\fila. Para cada
tarefa .json executa a ação pedida e grava a resposta em _robo\\resultados. Só executa os
tipos de tarefa conhecidos abaixo (não roda comandos arbitrários).

Usa apenas a biblioteca padrão do Python (as etapas com telas virão com o pywinauto).
"""
import ctypes
import datetime as dt
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

VERSAO = "1.22.6"
COMPARTILHAMENTO = os.environ.get("AUTOSUS_COMPARTILHAMENTO", "AIH")
RAIZ = os.environ.get("AUTOSUS_RAIZ", r"\\VBOXSVR\%s\_robo" % COMPARTILHAMENTO)
INTERVALO = 3          # segundos entre verificações da fila
BATIMENTO = 10         # segundos entre batimentos


def caminho(*partes):
    return os.path.join(RAIZ, *partes)


def agora():
    return dt.datetime.now().isoformat(timespec="seconds")


def registrar(msg):
    linha = "%s %s" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(caminho("logs", "agente_%s.log" % dt.date.today().strftime("%Y%m%d")), "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass
    print(linha)


def gravar_json(destino, dados):
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, destino)


def bater():
    gravar_json(caminho("agente.vivo"), {
        "hora": agora(), "versao": VERSAO, "python": platform.python_version(),
        "usuario": getpass.getuser(), "maquina": platform.node(),
        "windows": platform.version(), "pid": os.getpid(),
    })


# ------------------------------------------------------------------ janelas abertas (Win32, sem dependências)

def janelas_visiveis():
    user32 = ctypes.windll.user32
    titulos = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visitar(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value and buf.value not in ("Program Manager",):
                    titulos.append(buf.value)
        return True

    user32.EnumWindows(visitar, 0)
    return titulos


# ------------------------------------------------------------------ resolução da tela (dentro do Windows)

class _DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort),
                ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort),
                ("dmFields", ctypes.c_ulong), ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
                ("dmDisplayOrientation", ctypes.c_ulong), ("dmDisplayFixedOutput", ctypes.c_ulong),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
                ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_ulong), ("dmPelsWidth", ctypes.c_ulong),
                ("dmPelsHeight", ctypes.c_ulong), ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
                ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong), ("dmMediaType", ctypes.c_ulong),
                ("dmDitherType", ctypes.c_ulong), ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
                ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong)]


def garantir_resolucao(largura=1366, altura=768):
    """As telas do DATASUS não cabem em 640x480; fixa a resolução antes de operar os programas."""
    user32 = ctypes.windll.user32
    dm = _DEVMODEW()
    dm.dmSize = ctypes.sizeof(_DEVMODEW)
    if not user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):    # ENUM_CURRENT_SETTINGS
        return "resolução atual não lida"
    atual = "%dx%d" % (dm.dmPelsWidth, dm.dmPelsHeight)
    if (dm.dmPelsWidth, dm.dmPelsHeight) == (largura, altura):
        return atual
    # só modos que o driver de vídeo da VM oferece; se o pedido não existir, o maior que caiba nele
    modos, i, m = set(), 0, _DEVMODEW()
    m.dmSize = ctypes.sizeof(_DEVMODEW)
    while user32.EnumDisplaySettingsW(None, i, ctypes.byref(m)):
        modos.add((m.dmPelsWidth, m.dmPelsHeight))
        i += 1
    if (largura, altura) not in modos and modos:
        cabem = [md for md in modos if md[0] <= largura and md[1] <= altura] or list(modos)
        largura, altura = max(cabem, key=lambda md: md[0] * md[1])
        if (dm.dmPelsWidth, dm.dmPelsHeight) == (largura, altura):
            return atual + " (maior modo disponível)"
    dm.dmPelsWidth, dm.dmPelsHeight = largura, altura
    dm.dmFields = 0x80000 | 0x100000                                    # DM_PELSWIDTH | DM_PELSHEIGHT
    r = user32.ChangeDisplaySettingsW(ctypes.byref(dm), 1)              # CDS_UPDATEREGISTRY
    time.sleep(2)
    return "%s -> %dx%d (código %s)" % (atual, largura, altura, r)


# ------------------------------------------------------------------ tarefas

def tarefa_ping(p):
    return {"ok": True, "dados": {"agente": VERSAO, "python": platform.python_version(),
                                  "usuario": getpass.getuser(), "maquina": platform.node(),
                                  "janelas": janelas_visiveis()}}


def achar_executavel(candidatos):
    """Primeiro caminho que existe (o config pode listar mais de um, ex.: Program Files e Program Files (x86))."""
    if not candidatos:
        return None
    for c in ([candidatos] if isinstance(candidatos, str) else candidatos):
        if os.path.exists(c):
            return c
    return None


def versao_arquivo(exe):
    try:
        import win32api
        info = win32api.GetFileVersionInfo(exe, "\\")
        ms, ls = info["FileVersionMS"], info["FileVersionLS"]
        return "%d.%d.%d.%d" % (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)
    except Exception:
        return None


def instalar_um(item, limite, pasta_res):
    """Instalador Inno Setup em modo silencioso (sem telas)."""
    origem = caminho(*item["arquivo"].split("/"))
    nome = os.path.basename(origem)
    local = os.path.join(tempfile.gettempdir(), "autosus_" + nome)
    shutil.copy2(origem, local)
    log_inst = os.path.join(pasta_res, "instalador_%s_%s.log" % (item["programa"], dt.datetime.now().strftime("%H%M%S")))
    cmd = [local, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/LOG=" + log_inst]
    registrar("  instalando %s: %s" % (item["programa"], " ".join(cmd)))
    antes = set(janelas_visiveis())
    inicio = time.time()
    proc = subprocess.Popen(cmd)
    situacao = None
    while time.time() - inicio < limite:
        codigo = proc.poll()
        if codigo is not None:
            situacao = "instalado" if codigo == 0 else "instalador terminou com código %s" % codigo
            break
        time.sleep(2)
    res = {"programa": item["programa"], "instalador": nome, "segundos": round(time.time() - inicio)}
    if situacao is None:
        # Não mata o processo: pode estar esperando uma janela (ex.: release do SIHD)
        situacao = "AINDA EM EXECUÇÃO após %d s (provavelmente esperando uma janela)" % limite
        res["codigo_saida"] = None
    else:
        res["codigo_saida"] = proc.returncode
    res["situacao"] = situacao
    res["janelas_abertas"] = [t for t in janelas_visiveis() if t not in antes]
    exe = achar_executavel(item.get("executavel"))
    if item.get("executavel"):
        res["executavel_ok"] = bool(exe)
        if exe:
            res["executavel"] = exe
            res["executavel_data"] = dt.datetime.fromtimestamp(os.path.getmtime(exe)).isoformat(timespec="seconds")
    res["log_instalador"] = os.path.basename(log_inst)
    try:
        os.remove(local)
    except OSError:
        pass
    return res


def tarefa_instalar(p, pasta_res):
    limite = int(p.get("tempo_limite", 900))
    itens = [instalar_um(item, limite, pasta_res) for item in p["itens"]]
    ok = all(i["codigo_saida"] == 0 and i.get("executavel_ok", True) for i in itens)
    return {"ok": ok, "dados": {"itens": itens}}


def preparar_pywin32():
    """Ajuda o Windows a achar as DLLs do pywin32 (win32ui precisa da mfc140u.dll da pasta pythonwin)."""
    import site
    pastas = []
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        for sub in ("pywin32_system32", "pythonwin", os.path.join("win32", "lib")):
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                pastas.append(d)
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(d)
                    except OSError:
                        pass
                if d not in sys.path:
                    sys.path.append(d)
    os.environ["PATH"] = os.pathsep.join(pastas + [os.environ.get("PATH", "")])


def instalar_vcredist(origem):
    """Visual C++ 2015-2022 (x64): o pywin32/pywinauto precisa da mfc140u.dll e da msvcp140.dll."""
    exe = os.path.join(origem, "vc_redist.x64.exe")
    if not os.path.exists(exe):
        return "vc_redist.x64.exe não enviado"
    local = os.path.join(tempfile.gettempdir(), "autosus_vc_redist.x64.exe")
    shutil.copy2(exe, local)
    r = subprocess.run([local, "/install", "/quiet", "/norestart"], timeout=900)
    significado = {0: "instalado", 1638: "já havia versão igual ou mais nova", 3010: "instalado (pede reinício)"}
    return "Visual C++: código %s (%s)" % (r.returncode, significado.get(r.returncode, "verificar"))


def tarefa_instalar_pacotes(p, pasta_res):
    """pip install offline, a partir dos pacotes copiados pelo host para _robo/pacotes."""
    origem = caminho("pacotes")
    vc = instalar_vcredist(origem)
    registrar("  " + vc)
    python = sys.executable.replace("pythonw.exe", "python.exe")
    base = [python, "-m", "pip", "install", "--no-index", "--find-links", origem]
    comandos = []
    if p.get("reinstalar"):
        # pacote danificado (ex.: arquivo .py com bytes nulos): apaga e instala de novo, sem mexer nas dependências
        comandos.append(base + ["--force-reinstall", "--no-deps", "--no-cache-dir"] + list(p["reinstalar"]))
    comandos.append(base + ["--upgrade"] + list(p.get("pacotes", ["pywinauto"])))
    saida, ok = "", True
    for cmd in comandos:
        registrar("  " + " ".join(cmd))
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        saida += r.stdout.decode("utf-8", errors="replace")
        ok = ok and r.returncode == 0
    if ok:
        # confere se os pacotes carregam (pega arquivo danificado na hora, e não no meio de uma tarefa)
        teste = subprocess.run([python, "-c", "import PIL.ImageGrab, pywinauto; print('pacotes ok')"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        saida += "\n" + teste.stdout.decode("utf-8", errors="replace")
        ok = teste.returncode == 0
    if ok:
        # pacotes como o pywin32 só são carregados por um Python novo: reinicia o agente
        iniciar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iniciar.py")
        subprocess.Popen([sys.executable, iniciar], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    return {"ok": ok, "dados": {"codigo": 0 if ok else 1, "saida": vc + "\n" + saida[-3000:]}, "_sair": ok}


def _arvore_menu(itens, nivel=0):
    linhas = []
    for item in itens or []:
        linhas.append("%s- %s" % ("    " * nivel, item.get("text", "")))
        sub = item.get("menu_items") or {}
        linhas += _arvore_menu(sub.get("menu_items", []) if isinstance(sub, dict) else sub, nivel + 1)
    return linhas


def inspecionar_janelas(destino, titulo=None, profundidade=6):
    """Grava a árvore de controles (classe, texto, nomes do pywinauto) das janelas visíveis."""
    preparar_pywin32()
    from pywinauto import Application, Desktop
    partes = []
    for w in Desktop(backend="win32").windows(visible_only=True):
        t = w.window_text()
        if not t or t == "Program Manager" or (titulo and not re.search(titulo, t, re.IGNORECASE)):
            continue
        partes.append("=" * 100)
        partes.append("JANELA: %r  classe=%s  handle=%s  ret=%s" % (t, w.class_name(), w.handle, w.rectangle()))
        try:
            menu = w.menu_items()
            if menu:
                partes.append("MENU:")
                partes += _arvore_menu(menu, 1)
        except Exception as e:
            partes.append("(menu não lido: %s)" % e)
        try:
            for tb in w.descendants(class_name="TToolBar"):
                textos = [texto_botao(tb, i) for i in range(tb.button_count())]
                if any(textos):
                    partes.append("BARRA %s: %s" % (tb.rectangle(), " | ".join(textos)))
        except Exception as e:
            partes.append("(barras não lidas: %s)" % e)
        tmp = destino + ".parte"
        try:
            app = Application(backend="win32").connect(handle=w.handle)
            app.window(handle=w.handle).print_control_identifiers(depth=profundidade, filename=tmp)
            with open(tmp, "rb") as f:
                bruto = f.read()
            try:
                partes.append(bruto.decode("utf-8"))
            except UnicodeDecodeError:
                partes.append(bruto.decode("mbcs", errors="replace"))
        except Exception as e:
            partes.append("(controles não lidos: %s)" % e)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
    return len([p for p in partes if p.startswith("JANELA:")])


def tarefa_inspecionar(p, pasta_res):
    nome = "inspecao_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    qtd = inspecionar_janelas(os.path.join(pasta_res, nome), p.get("titulo"), int(p.get("profundidade", 6)))
    return {"ok": True, "dados": {"janelas": qtd}, "arquivos": [nome]}


def preencher_campo(controle, valor, senha=False):
    """Escreve direto no controle (WM_SETTEXT), sem depender do foco do teclado, e confere.

    - Respeita o limite de caracteres do campo (o usuário do SISAIH01 aceita 5: 'mestre' vira 'MESTR')
      e não diferencia maiúsculas (o campo converte para maiúsculas).
    - Campo de senha: o Windows não deixa outro programa ler o texto, então aceita vazio/asteriscos.
    """
    limite = controle.send_message(0x00D5, 0, 0) or len(valor)          # EM_GETLIMITTEXT
    esperado = valor[:limite].upper()

    def conferido():
        lido = controle.window_text()
        return lido.upper() == esperado or (senha and lido in ("", "*" * len(esperado)))

    controle.set_edit_text(valor[:limite])
    if conferido():
        return
    controle.set_edit_text("")                   # plano B: limpar, clicar no próprio campo e digitar
    controle.click_input()
    time.sleep(0.3)
    controle.type_keys("{END}+{HOME}{DEL}", set_foreground=False)
    controle.type_keys(valor[:limite], with_spaces=True, set_foreground=False)
    if not conferido():
        raise RuntimeError("o campo %s não aceitou o valor (ficou %r)" % (controle.class_name(),
                           "" if senha else controle.window_text()))


class ErroVersao(RuntimeError):
    def __init__(self, msg, apresentacao_da_versao):
        RuntimeError.__init__(self, msg)
        self.apresentacao_da_versao = apresentacao_da_versao


def preencher_login(login, usuario, senha, apresentacao=None):
    """Tela 'SISAIH01 - Autenticação': usuário (TEdit), senha e apresentação (TMaskEdit, nessa ordem)."""
    campo_usuario = login.child_window(class_name="TEdit").wrapper_object()
    mascaras = sorted(login.wrapper_object().descendants(class_name="TMaskEdit"),
                      key=lambda c: c.rectangle().top)
    if len(mascaras) < 2:
        raise RuntimeError("tela de login diferente do esperado (campos de senha/apresentação não achados)")
    campo_senha, campo_apresentacao = mascaras[0], mascaras[1]
    da_versao = campo_apresentacao.window_text().strip()
    # A apresentação que o SISAIH01 sugere é a da versão instalada (ex.: versão de outubro -> 11/2026).
    # Se o arquivo for de outra apresentação, a versão instalada é a errada: para aqui.
    if apresentacao and da_versao and da_versao != apresentacao:
        raise ErroVersao("a versão instalada do SISAIH01 é da apresentação %s, mas foi pedida %s: "
                         "instale a versão do SISAIH01 dessa apresentação" % (da_versao, apresentacao), da_versao)
    preencher_campo(campo_usuario, usuario)
    preencher_campo(campo_senha, senha, senha=True)
    if apresentacao:                             # MM/AAAA: tem de ser a mesma apresentação do arquivo
        preencher_campo(campo_apresentacao, apresentacao)
    if campo_usuario.window_text().upper() != usuario[:len(campo_usuario.window_text())].upper() \
            or not campo_usuario.window_text():
        raise RuntimeError("o campo de usuário ficou com %r" % campo_usuario.window_text())
    return da_versao, campo_apresentacao.window_text()


def atualizar_banco_sisaih01(app):
    """Tela 'Atualização do Banco de Dados': Atualizar, confirmar o SUCESSO e Fechar."""
    from pywinauto import Desktop
    passos = []
    tela = app.window(title="Atualização do Banco de Dados")
    tela["&Atualizar"].click()
    passos.append("atualização do banco iniciada")
    fim = time.time() + 900
    while time.time() < fim:
        for w in Desktop(backend="win32").windows(visible_only=True):
            t = w.window_text()
            if t.upper() == "SUCESSO":
                w.set_focus()
                w.type_keys("{ENTER}")
                passos.append("atualização do banco concluída (SUCESSO)")
                time.sleep(1)
                try:
                    memo = tela["Edit"].window_text().strip().replace("\r", "")
                    passos.append("mensagens: " + " | ".join(l for l in memo.split("\n") if l.strip() and not l.startswith("---"))[:800])
                except Exception:
                    pass
                tela["&Fechar"].click()
                return passos
            if t.upper() in ("ERRO", "ATENÇÃO", "AVISO") or t.lower().startswith("erro"):
                raise RuntimeError("janela inesperada durante a atualização do banco: %r" % t)
        time.sleep(2)
    raise RuntimeError("a atualização do banco não terminou em 15 minutos")


def fechar_sisaih01(principal, limite=60):
    """Fecha o SISAIH01 pelo X e confirma só perguntas de saída ('Deseja sair/encerrar/finalizar?')."""
    return _fechar_programa(principal, r"(sair|encerrar|finalizar|fechar)", limite)


def _fechar_programa(principal, padrao_sair, limite=60):
    pid = principal.process_id()
    principal.close()
    eventos = []
    fim = time.time() + limite
    while time.time() < fim:
        vivas = [w for w in janelas_handles().values() if w.process_id() == pid]
        if not vivas:
            return "SISAIH01 que já estava aberto foi fechado" + (" (%s)" % "; ".join(eventos) if eventos else "")
        for d in dialogos_abertos(pid):
            tratar_dialogo(d, [(padrao_sair, "Sim")], eventos)
        time.sleep(1)
    raise RuntimeError("o SISAIH01 aberto não fechou (%s)" % "; ".join(eventos))


def tarefa_sisaih01_abrir(p, pasta_res):
    """Abre o SISAIH01 e faz o login. Para em qualquer tela inesperada e devolve a inspeção."""
    preparar_pywin32()
    from pywinauto import Application, Desktop
    from pywinauto.timings import TimeoutError as Tempo
    exe = p.get("executavel", r"C:\DATASUS\SISAIH01\SISAIH01.EXE")
    arquivos = []
    apresentacao_da_versao = None
    passos = ["resolução: " + garantir_resolucao()]
    try:
        # já aberto (sessão anterior): fecha e entra de novo, para ter certeza da apresentação usada
        principal = [w for w in Desktop(backend="win32").windows(visible_only=True)
                     if w.window_text().startswith("SISAIH01 - Programa")]
        if principal:
            passos.append(fechar_sisaih01(principal[0]))
        aberta = [w for w in Desktop(backend="win32").windows(visible_only=True)
                  if w.window_text() == "SISAIH01 - Autenticação"]
        if aberta:                               # login de uma tentativa anterior ainda aberto: reaproveita
            app = Application(backend="win32").connect(handle=aberta[0].handle)
            passos.append("tela de login já estava aberta")
        else:
            app = Application(backend="win32").start(exe, work_dir=os.path.dirname(exe))
        login = app.window(title="SISAIH01 - Autenticação")
        login.wait("visible", timeout=60)
        passos.append("tela de login aberta")
        try:
            da_versao, apres = preencher_login(login, p.get("usuario", "mestre"), p.get("senha", "mestre"),
                                               p.get("apresentacao"))
        except ErroVersao as e:
            apresentacao_da_versao = e.apresentacao_da_versao
            raise
        apresentacao_da_versao = da_versao
        passos.append("apresentação da versão instalada: %s | usada no login: %s" % (da_versao, apres))
        login.child_window(title="&Entrar", class_name="TBitBtn").click()
        passos.append("login enviado")
        # depois do login: janela principal ou atualização do banco (sempre que a versão é nova)
        fim = time.time() + 90
        while time.time() < fim:
            titulos = [w.window_text() for w in Desktop(backend="win32").windows(visible_only=True)]
            if any("Atualização do Banco" in t for t in titulos):
                if not p.get("atualizar_banco", True):
                    passos.append("o SISAIH01 pediu atualização do banco (não executada)")
                    break
                passos += atualizar_banco_sisaih01(app)
                fim = time.time() + 90
                continue
            if any(t.startswith("SISAIH01 - Programa") for t in titulos):
                passos.append("janela principal aberta")
                break
            time.sleep(2)
        else:
            passos.append("nenhuma das janelas esperadas apareceu em 90 s")
    except Tempo:
        passos.append("a tela de login não apareceu em 60 s")
    except RuntimeError as e:
        passos.append("PAROU: %s" % e)
    nome = "inspecao_sisaih01_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    inspecionar_janelas(os.path.join(pasta_res, nome), None, 6)
    arquivos.append(nome)
    return {"ok": "janela principal aberta" in passos,
            "dados": {"passos": passos, "apresentacao_da_versao": apresentacao_da_versao}, "arquivos": arquivos}


def texto_botao(barra, i):
    for ler in (lambda: barra.button(i).info.text, lambda: barra.get_button(i).text, lambda: barra.button(i).text()):
        try:
            t = ler()
            if t is not None:
                return str(t)
        except Exception:
            continue
    return ""


def _itens_popup(menu, nivel=1):
    linhas = []
    for item in menu.items():
        texto = item.text()
        if not texto:
            continue
        linhas.append("%s- %s%s" % ("    " * nivel, texto, "" if item.is_enabled() else "  (desabilitado)"))
        sub = item.sub_menu()
        if sub:
            linhas += _itens_popup(sub, nivel + 1)
    return linhas


def mapear_menu_barra(janela, barra):
    """Clica em cada botão da barra-menu, lê o menu que abre (com submenus) e fecha com ESC."""
    from pywinauto import Desktop
    linhas = []
    for i in range(barra.button_count()):
        # Os botões desta barra são desenhados pelo programa: o texto (CADASTRO, PRODUÇÃO...) não
        # fica no botão. Identifica pela ordem e pela posição; o conteúdo do menu mostra qual é.
        texto = texto_botao(barra, i).strip()
        try:
            ret = barra.get_button_rect(i)
            pos = "x=%d..%d" % (ret.left, ret.right)
        except Exception:
            pos = ""
        linhas.append("[botão %d] %s %s" % (i, texto, pos))
        barra.button(i).click_input()
        popup = None
        fim = time.time() + 5
        while time.time() < fim and popup is None:
            for w in Desktop(backend="win32").windows(class_name="#32768", visible_only=True):
                popup = w
            time.sleep(0.3)
        if popup is None:
            linhas.append("    (nenhum menu abriu)")
            continue
        try:
            linhas += _itens_popup(popup.menu())
        except Exception as e:
            linhas.append("    (menu não lido: %s)" % e)
        for _ in range(3):
            janela.type_keys("{ESC}", set_foreground=False)
            time.sleep(0.2)
    return linhas


def tarefa_sisaih01_menus(p, pasta_res):
    """Mapeia o menu do SISAIH01 (que é uma barra de botões com menus suspensos)."""
    preparar_pywin32()
    from pywinauto import Application, Desktop
    principal = [w for w in Desktop(backend="win32").windows(visible_only=True)
                 if w.window_text().startswith("SISAIH01 - Programa")]
    if not principal:
        raise RuntimeError("o SISAIH01 não está aberto (rode 'robo.bat sisaih01 abrir')")
    app = Application(backend="win32").connect(handle=principal[0].handle)
    janela = app.window(handle=principal[0].handle)
    janela.set_focus()
    barras = [b for b in janela.wrapper_object().descendants(class_name="TToolBar") if b.button_count()]
    barra = max(barras, key=lambda b: b.button_count())
    linhas = ["MENU DO SISAIH01 (barra %s)" % barra.rectangle()] + mapear_menu_barra(janela, barra)
    nome = "menus_sisaih01_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    return {"ok": True, "dados": {"linhas": len(linhas)}, "arquivos": [nome]}


def tarefa_barra_menus(p, pasta_res):
    """Mapeia o menu de um programa que usa barra de botões com menus suspensos (SISAIH01, SIHD2)."""
    preparar_pywin32()
    from pywinauto import Application, Desktop
    alvo = [w for w in Desktop(backend="win32").windows(visible_only=True)
            if w.window_text().startswith(p["titulo"]) and not w.window_text().endswith("Descentralizado")]
    if not alvo:
        raise RuntimeError("janela %r não encontrada" % p["titulo"])
    app = Application(backend="win32").connect(handle=alvo[0].handle)
    janela = app.window(handle=alvo[0].handle)
    janela.set_focus()
    barras = [b for b in janela.wrapper_object().descendants(class_name="TToolBar") if b.button_count()]
    if not barras:
        raise RuntimeError("nenhuma barra de menu (TToolBar) na janela")
    linhas = []
    for barra in sorted(barras, key=lambda b: -b.button_count()):
        linhas.append("BARRA %s com %d botões" % (barra.rectangle(), barra.button_count()))
        linhas += mapear_menu_barra(janela, barra)
    nome = "menus_%s_%s.txt" % (p.get("prefixo", "programa"), dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    return {"ok": True, "dados": {"linhas": len(linhas)}, "arquivos": [nome]}


# ------------------------------------------------------------------ SISAIH01: menus e telas

# botões da barra-menu do SISAIH01 (pela ordem; os nomes são desenhados e não podem ser lidos)
SISAIH01_MENU = {"CADASTRO": 0, "PRODUÇÃO": 1, "PROCESSAMENTO": 2, "RELATÓRIOS": 3, "CONSULTA": 4, "MANUTENÇÃO": 5}


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").replace("&", "")).strip().upper()


def sisaih01_principal():
    preparar_pywin32()
    from pywinauto import Application, Desktop
    jan = [w for w in Desktop(backend="win32").windows(visible_only=True)
           if w.window_text().startswith("SISAIH01 - Programa")]
    if not jan:
        raise RuntimeError("o SISAIH01 não está aberto (rode 'robo.bat sisaih01 abrir')")
    app = Application(backend="win32").connect(handle=jan[0].handle)
    return app, app.window(handle=jan[0].handle)


def janelas_handles(principal=None):
    """Janelas de topo visíveis + formulários abertos dentro da principal (caso o programa use MDI)."""
    from pywinauto import Desktop
    jan = {w.handle: w for w in Desktop(backend="win32").windows(visible_only=True)
           if w.class_name() != "#32768" and w.window_text()}
    if principal is not None:
        try:
            for c in principal.wrapper_object().descendants():
                if c.class_name().startswith(("TFrm", "TForm")) and c.is_visible():
                    jan[c.handle] = c
        except Exception:
            pass
    return jan


class MenuNaoAbriu(RuntimeError):
    pass


def escolher_menu(janela, menu, caminho, tentativas=4):
    """Clica no botão da barra (ex.: 'MANUTENÇÃO', ou o número do botão) e segue o caminho no menu
    suspenso (ex.: ['IMPORTAR', 'PRODUÇÃO']). Compara os textos sem '&' e sem diferenciar maiúsculas.
    Se o menu não abrir (ex.: logo depois de uma tela pesada fechar, o programa ainda ocupado), fecha
    o que tiver ficado aberto com ESC, espera o programa responder e tenta de novo."""
    for n in range(1, tentativas + 1):
        try:
            return _escolher_menu(janela, menu, caminho)
        except MenuNaoAbriu as e:
            if n == tentativas:
                raise
            avisar("%s; tentando de novo (%d/%d)" % (e, n + 1, tentativas))
            for _ in range(3):
                try:
                    janela.type_keys("{ESC}", set_foreground=True)
                except Exception:
                    pass
                time.sleep(0.4)
            try:
                hwnd = janela.handle
            except Exception:
                hwnd = None
            fim = time.time() + 60
            while hwnd and time.time() < fim and not responde(hwnd, 2000):
                time.sleep(2)
            time.sleep(3 * n)


def _escolher_menu(janela, menu, caminho):
    from pywinauto import Desktop
    janela.set_focus()
    try:
        base = janela.wrapper_object()
    except Exception:
        base = janela
    barra = max((b for b in base.descendants(class_name="TToolBar") if b.button_count()),
                key=lambda b: b.button_count())
    indice = menu if isinstance(menu, int) else SISAIH01_MENU[_norm(menu)]
    menu = str(menu)
    barra.button(indice).click_input()
    usados = set()
    for nivel, texto in enumerate(caminho):
        popup = None
        fim = time.time() + 5
        while time.time() < fim and popup is None:
            for w in Desktop(backend="win32").windows(class_name="#32768", visible_only=True):
                if w.handle not in usados:
                    popup = w
                    break
            time.sleep(0.3)
        if popup is None:
            raise MenuNaoAbriu("o menu %s não abriu" % " > ".join([menu] + caminho[:nivel]))
        itens = popup.menu().items()
        alvo = [i for i in itens if _norm(i.text()).startswith(_norm(texto))]
        if not alvo:
            janela.type_keys("{ESC}{ESC}{ESC}", set_foreground=False)
            raise RuntimeError("item %r não encontrado no menu (itens: %s)"
                               % (texto, ", ".join(_norm(i.text()) for i in itens if i.text())))
        usados.add(popup.handle)
        alvo[0].click_input()
        time.sleep(0.6)


def esperar_janela_nova(antes, limite=15, ignorar=(), principal=None):
    fim = time.time() + limite
    while time.time() < fim:
        novas = [w for h, w in janelas_handles(principal).items()
                 if h not in antes and w.window_text() not in ignorar]
        if novas:
            return novas[0]
        time.sleep(0.5)
    return None


def fechar_sem_executar(janela):
    """Fecha uma tela sem disparar a ação dela: ESC; depois Fechar/Sair/Cancelar/Não; por último WM_CLOSE."""
    for _ in range(2):
        if not janela.is_visible():
            return "fechada com ESC"
        try:
            janela.type_keys("{ESC}", set_foreground=True)
        except Exception:
            pass
        time.sleep(0.8)
    if not janela.is_visible():
        return "fechada com ESC"
    for b in janela.descendants():
        nome = _norm(b.window_text())
        if nome in ("FECHAR", "SAIR", "CANCELAR", "NÃO", "NAO", "NO", "CANCEL"):
            b.click()
            time.sleep(0.8)
            if not janela.is_visible():
                return "fechada pelo botão %s" % nome
    janela.close()
    return "fechada pelo X"


def controles_da_janela(w, profundidade=8):
    from pywinauto import Application
    tmp = os.path.join(tempfile.gettempdir(), "controles_%s.txt" % w.handle)
    try:
        app = Application(backend="win32").connect(handle=w.top_level_parent().handle)
        app.window(handle=w.handle).print_control_identifiers(depth=profundidade, filename=tmp)
        with open(tmp, "rb") as f:
            bruto = f.read()
        try:
            return bruto.decode("utf-8")
        except UnicodeDecodeError:
            return bruto.decode("mbcs", errors="replace")
    except Exception as e:
        return "(controles não lidos: %s)" % e
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def print_janela(w, destino):
    """Imagem só da janela (precisa do Pillow; sem ele, segue sem a imagem)."""
    try:
        w.set_focus()
        time.sleep(0.4)
        w.capture_as_image().save(destino)
        return True
    except Exception as e:
        registrar("  sem print da janela: %s" % e)
        return False


def tarefa_sisaih01_mapear_telas(p, pasta_res):
    """Abre cada tela pedida pelo menu, grava os controles e fecha SEM executar nada."""
    app, janela = sisaih01_principal()
    nome = "telas_sisaih01_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(pasta_res, nome)
    partes, resumo, arquivos = [], [], [nome]
    for n, (menu, caminho) in enumerate(p["telas"], 1):
        rotulo = " > ".join([menu] + caminho)
        antes = set(janelas_handles(janela))
        try:
            escolher_menu(janela, menu, caminho)
            nova = esperar_janela_nova(antes, principal=janela)
            if nova is None:
                resumo.append("%s: nenhuma tela abriu" % rotulo)
                continue
            time.sleep(1.5)                       # deixa a tela terminar de carregar
            titulo, classe = nova.window_text(), nova.class_name()
            img = "tela%d_%s.png" % (n, re.sub(r"[^A-Za-z0-9]+", "_", classe))
            if print_janela(nova, os.path.join(pasta_res, img)):
                arquivos.append(img)
            partes.append("#" * 100 + "\nTELA: %s  ret=%s\n%s" % (rotulo, nova.rectangle(), controles_da_janela(nova)))
            # mensagens que a tela abriu por cima dela (ex.: "Confirma a exclusão?")
            for extra in [w for h, w in janelas_handles(janela).items() if h not in antes and h != nova.handle]:
                partes.append("-- janela extra %r --\n%s" % (extra.window_text(), controles_da_janela(extra)))
                fechar_sem_executar(extra)
            como = fechar_sem_executar(nova)
            resumo.append("%s: %r classe=%s (%s)" % (rotulo, titulo, classe, como))
        except Exception as e:
            resumo.append("%s: ERRO %s" % (rotulo, e))
        time.sleep(1)
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(resumo) + "\n\n" + "\n".join(partes))
    return {"ok": True, "dados": {"resumo": resumo}, "arquivos": arquivos}


# ------------------------------------------------------------------ SISAIH01: operações

# Botões desenhados (sem janela própria) nas telas de Consistir e Apurar: posição a partir do canto
# superior esquerdo da janela, medida nos prints das telas (tela3/tela4).
POS_BOTOES = {
    "TFrmConsistirProducao": {"Consistir": (65, 564), "Fechar": (700, 564)},
    "TFrmApurarPrevia2": {"Apurar": (60, 503), "Fechar": (736, 503)},
}
CLASSES_DIALOGO = ("#32770", "TMessageForm")
BM_CLICK = 0x00F5


class ParadaParaDecisao(RuntimeError):
    """O programa fez uma pergunta que o robô não está autorizado a responder sozinho."""


def _user32():
    return ctypes.windll.user32


def responde(hwnd, ms=1500):
    """True se o programa está processando mensagens (não está ocupado/travado)."""
    r = ctypes.c_size_t()
    return bool(_user32().SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, ms, ctypes.byref(r)))   # WM_NULL


def ler_texto(hwnd, ms=2000):
    """Texto de um controle sem travar se o programa estiver ocupado (None = não respondeu)."""
    u = _user32()
    r = ctypes.c_size_t()
    if not u.SendMessageTimeoutW(hwnd, 0x000E, 0, 0, 0x0002, ms, ctypes.byref(r)):   # WM_GETTEXTLENGTH
        return None
    buf = ctypes.create_unicode_buffer(r.value + 1)
    if not u.SendMessageTimeoutW(hwnd, 0x000D, r.value + 1, buf, 0x0002, ms, ctypes.byref(r)):   # WM_GETTEXT
        return None
    return buf.value


def botao(tela, titulo):
    """Botão (com janela própria) da tela pelo texto, ex.: '&Excluir'."""
    for c in tela.descendants():
        if c.window_text() == titulo:
            return c
    raise RuntimeError("botão %r não encontrado na tela %s" % (titulo, tela.window_text()))


def clicar_botao(botao):
    botao.set_focus() if botao.top_level_parent().is_enabled() else None
    _user32().PostMessageW(botao.handle, BM_CLICK, 0, 0)


def clicar_posicao(janela, rotulo):
    from pywinauto import mouse
    x, y = POS_BOTOES[janela.class_name()][rotulo]
    r = janela.rectangle()
    janela.set_focus()
    time.sleep(0.3)
    mouse.click(coords=(r.left + x, r.top + y))


def ler_area_transferencia():
    import win32clipboard
    for _ in range(5):
        try:
            win32clipboard.OpenClipboard()
            try:
                return win32clipboard.GetClipboardData(13)          # CF_UNICODETEXT
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.3)
    return ""


def texto_dialogo(d):
    """Mensagem de uma caixa de diálogo. MessageBox e TMessageForm (Delphi) copiam o texto com Ctrl+C."""
    import win32clipboard
    estaticos = [ler_texto(c.handle) or "" for c in d.children() if c.class_name() in ("Static", "TLabel")]
    texto = " ".join(t.strip() for t in estaticos if t.strip())
    if texto:
        return texto
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
        d.set_focus()
        d.type_keys("^c", set_foreground=False)
        time.sleep(0.4)
        bruto = ler_area_transferencia() or ""
        # formato do Ctrl+C: ---\nTítulo\n---\nMensagem\n---\nBotões\n---
        partes = [x.strip() for x in bruto.replace("\r", "").split("---") if x.strip()]
        return partes[1] if len(partes) >= 3 else bruto.strip()
    except Exception as e:
        return "(texto não lido: %s)" % e


def dialogos_abertos(pid, ignorar=()):
    from pywinauto import Desktop
    return [w for w in Desktop(backend="win32").windows(visible_only=True, process=pid)
            if w.class_name() in CLASSES_DIALOGO and w.handle not in ignorar]


def botoes_dialogo(d):
    return {_norm(c.window_text()): c for c in d.children()
            if c.class_name() in ("Button", "TButton", "TBitBtn") and c.window_text()}


_SEM_BOTOES = {}


def tratar_dialogo(d, regras, eventos):
    """OK sozinho: lê e confirma. Pergunta: só responde se uma regra autorizar; senão para."""
    botoes = botoes_dialogo(d)
    if not botoes:
        # caixa acabou de abrir e os botões ainda não existem: tenta de novo na próxima volta
        _SEM_BOTOES[d.handle] = _SEM_BOTOES.get(d.handle, 0) + 1
        if _SEM_BOTOES[d.handle] < 20:
            time.sleep(0.5)
            return
    texto = texto_dialogo(d)
    titulo = d.window_text()
    if set(botoes) <= {"OK", "FECHAR"} and botoes:
        eventos.append("[%s] %s -> OK" % (titulo, texto))
        clicar_botao(list(botoes.values())[0])
        return
    for padrao, resposta in regras:
        if texto and re.search(padrao, texto, re.IGNORECASE | re.DOTALL):
            sinonimos = {"SIM": ("SIM", "YES"), "YES": ("YES", "SIM"), "NÃO": ("NÃO", "NAO", "NO"),
                         "NAO": ("NÃO", "NAO", "NO"), "NO": ("NO", "NÃO", "NAO")}
            alvo = next((botoes[n] for n in sinonimos.get(_norm(resposta), (_norm(resposta),)) if n in botoes), None)
            if alvo is None:
                break
            eventos.append("[%s] %s -> %s" % (titulo, texto, resposta))
            clicar_botao(alvo)
            return
    eventos.append("[%s] %s -> SEM RESPOSTA AUTOMÁTICA (botões: %s)" % (titulo, texto, ", ".join(botoes)))
    raise ParadaParaDecisao("o programa perguntou: %r (botões: %s). Nada foi respondido; a pergunta "
                            "continua aberta na VM." % (texto, ", ".join(botoes)))


def acompanhar(tela, pid, regras, eventos, limite, memo=None, quieto=10, terminou=None, principal=None):
    """Espera o processamento terminar, respondendo às caixas de mensagem conforme as regras.
    Considera concluído quando o programa responde, não há caixa aberta e o histórico (memo) ficou
    'quieto' segundos sem mudar — ou quando terminou(eventos) disser que sim."""
    inicio = time.time()
    fim = inicio + limite
    ultimo, desde, ultimo_aviso = None, time.time(), 0
    while time.time() < fim:
        checar_cancelamento()
        if time.time() - ultimo_aviso > 50:
            titulo = tela.window_text()[:60] if _user32().IsWindow(tela.handle) else "tela fechada"
            avisar("%s: processando há %d min" % (titulo, (time.time() - inicio) // 60))
            ultimo_aviso = time.time()
        dialogos = dialogos_abertos(pid)
        if dialogos:
            for d in dialogos:
                tratar_dialogo(d, regras, eventos)
            desde = time.time()
            time.sleep(1)
            continue
        if terminou and terminou(eventos):
            return True
        alvo = tela.handle if _user32().IsWindow(tela.handle) else (principal.handle if principal is not None else None)
        if alvo is None:
            return True                                   # a tela fechou e não há janela principal para olhar
        if responde(alvo):
            atual = ler_texto(memo.handle) if memo is not None else None
            if atual != ultimo:
                ultimo, desde = atual, time.time()
            elif time.time() - desde >= quieto:
                return True
        else:
            desde = time.time()
        time.sleep(1)
    raise RuntimeError("o processamento não terminou em %d minutos" % (limite // 60))


def abrir_tela(janela, menu, caminho, classe, limite=20):
    """Abre a tela pelo menu. No Delphi do SISAIH01 uma tela aberta pode ficar ESCONDIDA atrás da
    janela principal e travar o menu: reaproveita a tela se já estiver aberta e fecha outras telas
    (sem executar nada) antes de usar o menu."""
    pid = janela.process_id()
    caixas = dialogos_abertos(pid)
    if caixas:
        raise ParadaParaDecisao("há uma mensagem do SISAIH01 aberta antes de começar: %r"
                                % texto_dialogo(caixas[0]))
    principal = janela.wrapper_object().handle
    for w in list(janelas_handles(janela).values()):
        if w.handle == principal or w.process_id() != pid:
            continue
        if w.class_name() == classe:
            w.set_focus()
            time.sleep(0.5)
            return w
        if w.class_name().startswith(("TFrm", "TForm")):
            fechar_sem_executar(w)
            time.sleep(0.5)
    antes = set(janelas_handles(janela))
    escolher_menu(janela, menu, caminho)
    fim = time.time() + limite
    while time.time() < fim:
        for h, w in janelas_handles(janela).items():
            if w.class_name() == classe:
                time.sleep(1)
                return w
        time.sleep(0.5)
    novas = [w.window_text() for h, w in janelas_handles(janela).items() if h not in antes]
    raise RuntimeError("a tela %s não abriu (janelas novas: %s)" % (classe, novas))


def apresentacao_na_tela(janela):
    """Procura MM/AAAA nos textos da barra de status da janela principal (se houver)."""
    achadas = set()
    for c in janela.wrapper_object().descendants():
        if c.class_name() in ("TStatusBar", "msctls_statusbar32"):
            try:
                textos = c.texts()
            except Exception:
                textos = [c.window_text()]
            for t in textos:
                # painel "APRES.: 09 / 2026" (a data do dia, 02/11/2026, fica em outro painel e é ignorada)
                achadas.update(re.findall(r"APRES\w*\.?\s*:?\s*(0[1-9]|1[0-2])\s*/\s*(\d{4})", t or "", re.IGNORECASE))
    return sorted("%s/%s" % a for a in achadas)


def relatorio(pasta_res, acao, linhas):
    nome = "sisaih01_%s_%s.txt" % (acao, dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    return nome


def operacao_sisaih01(acao, pasta_res, corpo):
    """Executa corpo(janela, pid, eventos, arquivos) e, dando certo ou não, grava eventos e print."""
    app, janela = sisaih01_principal()
    pid = janela.process_id()
    eventos, arquivos, dados = [], [], {}
    ok, erro = False, None
    try:
        dados = corpo(janela, pid, eventos, arquivos) or {}
        ok = True
    except Exception as e:
        erro = "%s: %s" % (type(e).__name__, e)
        eventos.append("PAROU: " + erro)
        img = "erro_%s.png" % acao
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(os.path.join(pasta_res, img))
            arquivos.append(img)
        except Exception:
            pass
    arquivos.insert(0, relatorio(pasta_res, acao, eventos + ["", "dados: " + json.dumps(dados, ensure_ascii=False)]))
    dados["eventos"] = eventos
    if erro:
        dados["erro"] = erro
    return {"ok": ok, "dados": dados, "arquivos": arquivos}


def tarefa_sisaih01_excluir(p, pasta_res):
    apresentacao = p["apresentacao"]                      # MM/AAAA, já conferida pelo host
    if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{4}", apresentacao or ""):
        raise RuntimeError("apresentação inválida: %r" % apresentacao)

    def corpo(janela, pid, eventos, arquivos):
        na_tela = apresentacao_na_tela(janela)
        eventos.append("apresentação na barra de status: %s" % (", ".join(na_tela) or "não mostrada"))
        if na_tela and apresentacao not in na_tela:
            raise RuntimeError("o SISAIH01 está aberto na apresentação %s, e não %s" % (na_tela, apresentacao))
        tela = abrir_tela(janela, "MANUTENÇÃO", ["EXCLUIR PRODUÇÃO"], "TFrmExcluirProducao")
        campo = tela.descendants(class_name="TMaskEdit")[0]
        campo.set_focus()
        campo.type_keys("{HOME}" + apresentacao.replace("/", ""), set_foreground=False)
        time.sleep(0.5)
        lido = campo.window_text()
        if lido != apresentacao:
            raise RuntimeError("o campo de apresentação ficou %r (esperado %s)" % (lido, apresentacao))
        eventos.append("apresentação digitada: %s" % lido)
        clicar_botao(botao(tela, "&Excluir"))
        eventos.append("clicou em Excluir")
        # só confirma pergunta de exclusão que cite a apresentação certa (ou nenhuma)
        mm, aaaa = apresentacao.split("/")
        regras = [(r"^(?!.*\d{2}/\d{4})(?=.*(exclu|apag|remov)).*$", "Sim"),
                  (r"(exclu|apag|remov).*%s/%s|%s/%s.*(exclu|apag|remov)" % (mm, aaaa, mm, aaaa), "Sim")]
        acompanhar(tela, pid, regras, eventos, 1800, quieto=8)
        img = "sisaih01_excluir.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_botao(botao(tela, "&Fechar"))
        return {"apresentacao": apresentacao}
    return operacao_sisaih01("excluir", pasta_res, corpo)


def _campo_nome_arquivo(caixa):
    """Campo 'Nome:' da caixa Abrir/Salvar (estilo antigo: Edit 1152; novo: Edit dentro do combo 1148)."""
    for e in caixa.descendants(class_name="Edit"):
        if not e.is_visible():
            continue
        ids = [e.control_id()]
        pai = e.parent()
        for _ in range(2):
            if pai is None:
                break
            ids.append(pai.control_id())
            pai = pai.parent()
        if 1152 in ids[:1] or 1148 in ids[1:]:
            return e
    return None


def escolher_arquivo_dialogo(pid, caminho_arquivo, eventos, salvar=False, limite=15):
    """Preenche a caixa padrão do Windows (Abrir/Salvar como) e confirma. Devolve (sugerido, destino)."""
    fim = time.time() + limite
    caixa, campo = None, None
    while time.time() < fim and campo is None:
        for d in dialogos_abertos(pid):
            if d.class_name() == "#32770":
                campo = _campo_nome_arquivo(d)
                if campo is not None:
                    caixa = d
                    break
        time.sleep(0.5)
    if campo is None:
        raise RuntimeError("a caixa de escolher arquivo não abriu")
    sugerido = ler_texto(campo.handle) or ""
    destino = caminho_arquivo(sugerido) if callable(caminho_arquivo) else caminho_arquivo
    eventos.append("caixa %r: sugerido %r -> %s" % (caixa.window_text(), sugerido, destino))
    campo.set_edit_text(destino)
    time.sleep(0.3)
    ok = [b for b in caixa.children() if b.class_name() == "Button" and b.control_id() == 1]   # IDOK
    if not ok:
        raise RuntimeError("botão Abrir/Salvar não achado")
    clicar_botao(ok[0])
    fim = time.time() + 5
    while time.time() < fim:
        time.sleep(0.7)
        if not (_user32().IsWindow(caixa.handle) and _user32().IsWindowVisible(caixa.handle)):
            return sugerido, destino
        for d in dialogos_abertos(pid, ignorar=(caixa.handle,)):
            t = texto_dialogo(d)
            b = botoes_dialogo(d)
            if salvar and re.search(r"(já existe|substituir|replace)", t, re.IGNORECASE) and ("SIM" in b or "YES" in b):
                eventos.append("substituir arquivo existente: Sim")       # pasta de saída do robô
                clicar_botao(b.get("SIM") or b.get("YES"))
            else:
                raise RuntimeError("a caixa de arquivo respondeu: %r" % t)
    raise RuntimeError("a caixa de escolher arquivo não fechou (caminho recusado?)")


def tarefa_sisaih01_importar(p, pasta_res):
    origem = caminho("entrada", p["arquivo"])
    if not os.path.isfile(origem):
        raise RuntimeError("arquivo não encontrado: %s" % origem)
    local_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entrada")
    os.makedirs(local_dir, exist_ok=True)
    local = os.path.join(local_dir, p["arquivo"])
    shutil.copy2(origem, local)                             # o SISAIH01 lê melhor de pasta local

    def corpo(janela, pid, eventos, arquivos):
        eventos.append("arquivo: %s (%d bytes)" % (local, os.path.getsize(local)))
        tela = abrir_tela(janela, "MANUTENÇÃO", ["IMPORTAR", "PRODUÇÃO"], "TFrmImportaProducao")
        campo = tela.descendants(class_name="TEdit")[0]
        if campo.has_style(0x0800):                         # ES_READONLY: só pela caixa "Abrir"
            procurar = [b for b in tela.descendants(class_name="TBitBtn") if not b.window_text()]
            clicar_botao(procurar[0])
            escolher_arquivo_dialogo(pid, local, eventos)
        else:
            campo.set_edit_text(local)
        time.sleep(0.5)
        if (ler_texto(campo.handle) or "").lower() != local.lower():
            raise RuntimeError("o campo Arquivo ficou %r" % ler_texto(campo.handle))
        clicar_botao(botao(tela, "Importar"))
        eventos.append("clicou em Importar")
        regras = [(r"(confirma|deseja).*(importa)", "Sim")]
        acompanhar(tela, pid, regras, eventos, 3600, quieto=10)
        img = "sisaih01_importar.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_botao(botao(tela, "&Fechar"))
        return {"arquivo": p["arquivo"]}
    return operacao_sisaih01("importar", pasta_res, corpo)


def _processar_com_historico(acao, menu, caminho_menu, classe, botao, pasta_res, regras, limite):
    def corpo(janela, pid, eventos, arquivos):
        tela = abrir_tela(janela, menu, caminho_menu, classe)
        memo = tela.descendants(class_name="TRichEdit")[0]
        inicial = ler_texto(memo.handle) or ""
        clicar_posicao(tela, botao)
        eventos.append("clicou em %s" % botao)
        # espera o histórico começar a mudar (confirma que o clique pegou)
        fim = time.time() + 60
        while time.time() < fim:
            if dialogos_abertos(pid) or (responde(memo.handle, 500) and (ler_texto(memo.handle) or "") != inicial):
                break
            time.sleep(1)
        else:
            raise RuntimeError("o %s não começou (o histórico não mudou em 60 s)" % botao)
        acompanhar(tela, pid, regras, eventos, limite, memo=memo, quieto=15)
        historico = (ler_texto(memo.handle) or "").replace("\r", "")
        nome_hist = "sisaih01_%s_historico.txt" % acao
        with open(os.path.join(pasta_res, nome_hist), "w", encoding="utf-8") as f:
            f.write(historico)
        arquivos.append(nome_hist)
        img = "sisaih01_%s.png" % acao
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_posicao(tela, "Fechar")
        time.sleep(1)
        if re.search(r"n[ãa]o existe aih", historico, re.IGNORECASE):
            raise RuntimeError("não há produção nesta apresentação (importe o arquivo antes de %s)" % acao)
        linhas = [l.strip() for l in historico.split("\n") if l.strip()]
        dados = {"historico": [l for l in linhas if not re.search(r"\s(OK)$", l)][-40:]}
        m = re.search(r"Total:\s*(\d+)\s*rejeitadas?\s*de\s*(\d+)", historico, re.IGNORECASE)
        if m:
            dados["rejeitadas"], dados["total_aih"] = int(m.group(1)), int(m.group(2))
        return dados
    return operacao_sisaih01(acao, pasta_res, corpo)


def tarefa_sisaih01_consistir(p, pasta_res):
    return _processar_com_historico("consistir", "PROCESSAMENTO", ["CONSISTIR PRODUÇÃO"],
                                    "TFrmConsistirProducao", "Consistir", pasta_res, [], 3600)


def tarefa_sisaih01_apurar(p, pasta_res):
    return _processar_com_historico("apurar", "PROCESSAMENTO", ["APURAR PRÉVIA"],
                                    "TFrmApurarPrevia2", "Apurar", pasta_res, [], 3600)


def tarefa_sisaih01_exportar(p, pasta_res):
    saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
    os.makedirs(saida, exist_ok=True)
    for antigo in os.listdir(saida):
        os.remove(os.path.join(saida, antigo))

    def corpo(janela, pid, eventos, arquivos):
        tela = abrir_tela(janela, "PROCESSAMENTO", ["EXPORTAR PRODUÇÃO PARA", "SIHD (SECRETARIA)"],
                          "TFrmExportaProducao")
        campo = tela.descendants(class_name="TEdit")[0]
        procurar = [b for b in tela.descendants(class_name="TBitBtn") if not b.window_text()]
        clicar_botao(procurar[0])
        sugerido, destino = escolher_arquivo_dialogo(
            pid, lambda nome: os.path.join(saida, os.path.basename(nome) or "exportacao_sihd"), eventos, salvar=True)
        time.sleep(0.5)
        eventos.append("campo Arquivo: %s" % ler_texto(campo.handle))
        clicar_botao(botao(tela, "&Exportar"))
        eventos.append("clicou em Exportar")
        regras = [(r"protocolo", "Não")]
        acompanhar(tela, pid, regras, eventos, 1800, quieto=10)
        img = "sisaih01_exportar.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        gerados = sorted(os.listdir(saida))
        if not gerados:
            raise RuntimeError("a exportação terminou sem gerar arquivo em %s" % saida)
        for nome in gerados:
            shutil.copy2(os.path.join(saida, nome), os.path.join(pasta_res, nome))
            arquivos.append(nome)
        clicar_botao(botao(tela, "&Fechar"))
        return {"exportados": gerados, "sugerido": sugerido}
    return operacao_sisaih01("exportar", pasta_res, corpo)


# ------------------------------------------------------------------ programas em geral: abrir e inspecionar

def janelas_do_processo(pid):
    """Janelas visíveis do processo, inclusive as sem título (ex.: tela de login do FPO)."""
    from pywinauto import Desktop
    out = []
    for w in Desktop(backend="win32").windows(visible_only=True, process=pid):
        r = w.rectangle()
        if w.class_name() == "TApplication" or r.width() < 20 or r.height() < 20:
            continue
        out.append(w)
    return out


def pid_do_executavel(exe):
    import win32process, win32api, win32con
    from pywinauto import Desktop
    nome_exe = os.path.basename(exe).lower()
    for w in Desktop(backend="win32").windows(visible_only=True):
        try:
            h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, w.process_id())
            if os.path.basename(win32process.GetModuleFileNameEx(h, 0)).lower() == nome_exe:
                return w.process_id()
        except Exception:
            continue
    return None


def gravar_telas(pid, pasta_res, prefixo, extra=None):
    """Grava imagem, menu e controles de cada janela do processo. Devolve (arquivos, títulos)."""
    arquivos, partes, titulos = [], [], []
    for i, w in enumerate(janelas_do_processo(pid), 1):
        titulos.append("%s [%s]" % (w.window_text() or "(sem título)", w.class_name()))
        img = "%s_janela%d.png" % (prefixo, i)
        if print_janela(w, os.path.join(pasta_res, img)):
            arquivos.append(img)
        menu = ""
        try:
            itens = w.menu_items()
            if itens:
                menu = "MENU:\n" + "\n".join(_arvore_menu(itens, 1)) + "\n"
        except Exception:
            pass
        partes.append("#" * 100 + "\nJANELA %d: %r classe=%s ret=%s\n%s%s" % (
            i, w.window_text(), w.class_name(), w.rectangle(), menu, controles_da_janela(w)))
    nome = "inspecao_%s_%s.txt" % (prefixo, dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write((json.dumps(extra, ensure_ascii=False) + "\n" if extra else "") + "\n".join(partes))
    return [nome] + arquivos, titulos


def tarefa_programa_inspecionar(p, pasta_res):
    """Abre o programa (se ainda não estiver aberto), espera e grava as telas que ele mostrar.
    NÃO digita nem clica em nada: serve para mapear a tela de login e as primeiras perguntas."""
    preparar_pywin32()
    from pywinauto import Application
    exe = achar_executavel(p["executavel"])
    if not exe:
        raise RuntimeError("programa não instalado (procurei em: %s)" % "; ".join(
            [p["executavel"]] if isinstance(p["executavel"], str) else p["executavel"]))
    dados = {"executavel": exe, "versao_arquivo": versao_arquivo(exe),
             "data_arquivo": dt.datetime.fromtimestamp(os.path.getmtime(exe)).isoformat(timespec="seconds")}
    def por_titulo():
        # programas Java: o .exe só lança o java/javaw; a janela é de outro processo -> acha pelo título
        from pywinauto import Desktop
        for w in Desktop(backend="win32").windows(visible_only=True):
            if p.get("titulo") and p["titulo"].lower() in titulo_janela(w).lower():
                return w.process_id()
        return None

    pid = por_titulo() or pid_do_executavel(exe)
    if pid:
        dados["situacao"] = "já estava aberto"
    else:
        if p.get("titulo"):
            # programa Java: abre pelo próprio atalho da Área de Trabalho/menu Iniciar (igual ao duplo clique)
            atalho = achar_atalho(exe)
            alvo = atalho or exe
            atual = os.getcwd()
            try:
                os.chdir(os.path.dirname(exe))
                os.startfile(alvo)
            finally:
                os.chdir(atual)
            dados["aberto_por"] = alvo
            pid = None
        else:
            pid = Application(backend="win32").start(exe, work_dir=os.path.dirname(exe)).process
        dados["situacao"] = "aberto agora"
        fim = time.time() + float(p.get("esperar", 8)) + (80 if p.get("titulo") else 0)
        time.sleep(float(p.get("esperar", 8)))
        while p.get("titulo") and time.time() < fim and not por_titulo():
            time.sleep(1)
        pid = por_titulo() or pid
    if not pid:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        procs = sorted({l.split('","')[0].strip('"') for l in r.stdout.decode("mbcs", "replace").splitlines()
                        if re.search(r"java|trans", l, re.IGNORECASE)})
        raise RuntimeError("a janela %r não apareceu em %d s (aberto por %s; processos java/trans rodando: %s; "
                           "PATH tem java: %s)" % (p.get("titulo"), float(p.get("esperar", 8)) + 80,
                                                  dados.get("aberto_por"), ", ".join(procs) or "nenhum",
                                                  "sim" if "java" in os.environ.get("PATH", "").lower() else "não"))
    dados["processo"] = _exe_do_processo(pid)
    arquivos, dados["janelas"] = gravar_telas(pid, pasta_res, p.get("prefixo", "programa"), dados)
    return {"ok": True, "dados": dados, "arquivos": arquivos}


# ------------------------------------------------------------------ FPO

def fpo_principal(pid):
    for w in janelas_do_processo(pid):
        if w.class_name() == "TF_GAMENU":
            return w
    return None


def item_menu_padrao(janela, caminho):
    """Item do menu comum do Windows (TMainMenu) pelo caminho de textos, ex.: ['MANUTENÇÃO', 'ALTERAR']."""
    menu = janela.menu()
    item = None
    for nivel, texto in enumerate(caminho):
        itens = menu.items()
        alvo = [i for i in itens if _norm(i.text()).startswith(_norm(texto))]
        if not alvo:
            raise RuntimeError("item %r não encontrado no menu (itens: %s)"
                               % (texto, ", ".join(_norm(i.text()) for i in itens if i.text())))
        item = alvo[0]
        if nivel < len(caminho) - 1:
            menu = item.sub_menu()
    return item


def abrir_por_menu_padrao(pid, janela, caminho, limite=20, classe=None, eventos=None):
    """Escolhe o item do menu (sem clicar: manda o comando do item) e devolve a tela que abriu."""
    antes = {w.handle for w in janelas_do_processo(pid)}
    item = item_menu_padrao(janela, caminho)
    if not item.is_enabled():
        raise RuntimeError("o item %s está desabilitado" % " > ".join(caminho))
    item.select()
    fim = time.time() + limite
    while time.time() < fim:
        for w in janelas_do_processo(pid):
            if w.handle not in antes and w.class_name() not in CLASSES_DIALOGO and (classe is None or w.class_name() == classe):
                time.sleep(1.5)
                return w
        caixas = [d for d in dialogos_abertos(pid) if d.handle not in antes]
        if caixas and classe is None:
            return caixas[0]
        for d in caixas:                       # esperando uma tela específica: mensagem só com OK é confirmada
            tratar_dialogo(d, [], eventos if eventos is not None else [])
        time.sleep(0.5)
    return None


def tarefa_fpo_mapear_telas(p, pasta_res):
    """Abre cada tela do FPO pelo menu, grava imagem e controles e fecha SEM executar nada."""
    preparar_pywin32()
    exe = achar_executavel(p["executavel"])
    pid = pid_do_executavel(exe) if exe else None
    principal = fpo_principal(pid) if pid else None
    if principal is None or len(principal.menu_items()) <= 2:
        raise RuntimeError("o FPO não está aberto com login feito (rode 'robo.bat fpo abrir')")
    resumo, partes, arquivos = [], [], []
    nome = "telas_fpo_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    for n, caminho in enumerate(p["telas"], 1):
        rotulo = " > ".join(caminho)
        try:
            tela = abrir_por_menu_padrao(pid, principal, caminho)
            if tela is None:
                resumo.append("%s: nenhuma tela abriu" % rotulo)
                continue
            titulo, classe = tela.window_text(), tela.class_name()
            img = "fpo_tela%d_%s.png" % (n, re.sub(r"[^A-Za-z0-9]+", "_", classe))
            if print_janela(tela, os.path.join(pasta_res, img)):
                arquivos.append(img)
            texto = texto_dialogo(tela) if classe in CLASSES_DIALOGO else ""
            partes.append("#" * 100 + "\nTELA: %s  %r classe=%s ret=%s %s\n%s" % (
                rotulo, titulo, classe, tela.rectangle(), ("mensagem: %r" % texto) if texto else "",
                controles_da_janela(tela)))
            como = fechar_sem_executar(tela)
            for d in dialogos_abertos(pid):              # pergunta ao fechar ("deseja sair?"): não responde Sim
                partes.append("-- mensagem ao fechar: %r" % texto_dialogo(d))
                como += "; " + fechar_sem_executar(d)
            resumo.append("%s: %r classe=%s (%s)" % (rotulo, titulo, classe, como))
        except Exception as e:
            resumo.append("%s: ERRO %s" % (rotulo, e))
        time.sleep(1)
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(resumo) + "\n\n" + "\n".join(partes))
    return {"ok": True, "dados": {"resumo": resumo}, "arquivos": [nome] + arquivos}


# ------------------------------------------------------------------ FPO: operações

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO",
         "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
PASTA_AGENTE = os.path.dirname(os.path.abspath(__file__))


def fpo_contexto(p):
    preparar_pywin32()
    exe = achar_executavel(p["executavel"])
    pid = pid_do_executavel(exe) if exe else None
    principal = fpo_principal(pid) if pid else None
    if principal is None or len(principal.menu_items()) <= 2:
        raise RuntimeError("o FPO não está aberto com login feito (rode 'robo.bat fpo abrir')")
    return pid, principal


def fpo_tela(pid, principal, caminho, classe, eventos=None):
    """Reaproveita a tela se já estiver aberta; fecha outras telas do FPO (sem executar) e abre pelo menu.
    Mensagens já abertas só com OK (ex.: 'após atualizar para a versão 03.05, é obrigatório atualizar o
    BDSIA') são confirmadas; uma pergunta aberta faz parar."""
    eventos = eventos if eventos is not None else []
    for _ in range(10):
        caixas = dialogos_abertos(pid)
        if not caixas:
            break
        for d in caixas:
            tratar_dialogo(d, [], eventos)
        time.sleep(1)
    for w in janelas_do_processo(pid):
        if w.handle == principal.handle:
            continue
        if w.class_name() == classe:
            w.set_focus()
            return w
        fechar_sem_executar(w)
    tela = abrir_por_menu_padrao(pid, principal, caminho, classe=classe, eventos=eventos)
    if tela is None:
        raise RuntimeError("a tela %s não abriu" % " > ".join(caminho))
    return tela


def botao_por_texto(tela, texto):
    """Botão pelo texto. Lê o texto direto do Windows (não trava se o programa estiver ocupado)."""
    alvo = _norm(texto)
    for c in tela.descendants():
        if c.class_name() in ("TBitBtn", "TButton", "Button", "TSpeedButton") and _norm(titulo_janela(c)) == alvo:
            return c
    raise RuntimeError("botão %r não encontrado em %r" % (texto, titulo_janela(tela)))


def operacao_fpo(acao, p, pasta_res, corpo):
    pid, principal = fpo_contexto(p)
    eventos, arquivos, dados = [], [], {}
    ok, erro = False, None
    try:
        dados = corpo(pid, principal, eventos, arquivos) or {}
        ok = True
    except Exception as e:
        erro = "%s: %s" % (type(e).__name__, e)
        eventos.append("PAROU: " + erro)
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(os.path.join(pasta_res, "erro_fpo_%s.png" % acao))
            arquivos.append("erro_fpo_%s.png" % acao)
        except Exception:
            pass
    arquivos.insert(0, relatorio(pasta_res, "fpo_" + acao, eventos + ["", "dados: " + json.dumps(dados, ensure_ascii=False)]))
    dados["eventos"] = eventos
    if erro:
        dados["erro"] = erro
    return {"ok": ok, "dados": dados, "arquivos": arquivos}


def ler_competencia_fpo(pid, principal, eventos=None):
    tela = fpo_tela(pid, principal, ["MANUTENÇÃO", "ALTERAR COMPETÊNCIA"], "TFALT_CMP", eventos)
    combo = tela.descendants(class_name="TComboBox")[0] if tela.descendants(class_name="TComboBox") else \
        [c for c in tela.descendants() if c.class_name() == "ComboBox" or "Combo" in c.class_name()][0]
    ano = [c for c in tela.descendants() if c.class_name() in ("TEdit", "TMaskEdit", "Edit")
           and c.parent().handle == tela.handle][0]
    return tela, combo, ano, _norm(ler_texto(combo.handle) or ""), (ler_texto(ano.handle) or "").strip()


def tarefa_fpo_competencia(p, pasta_res):
    mes, ano = int(p["mes"]), int(p["ano"])

    def corpo(pid, principal, eventos, arquivos):
        tela, combo, campo_ano, mes_atual, ano_atual = ler_competencia_fpo(pid, principal, eventos)
        eventos.append("competência atual: %s/%s" % (mes_atual, ano_atual))
        if mes_atual == MESES[mes - 1] and ano_atual == str(ano):
            eventos.append("já está em %s/%d: nada a fazer" % (MESES[mes - 1], ano))
            clicar_botao(botao_por_texto(tela, "&Saida"))
            return {"competencia": "%02d/%d" % (mes, ano), "alterada": False}
        combo.select(mes - 1)
        campo_ano.set_edit_text(str(ano))
        time.sleep(0.5)
        if _norm(ler_texto(combo.handle)) != MESES[mes - 1] or (ler_texto(campo_ano.handle) or "").strip() != str(ano):
            raise RuntimeError("os campos ficaram %r/%r" % (ler_texto(combo.handle), ler_texto(campo_ano.handle)))
        eventos.append("nova competência digitada: %s/%d (copia tabela SIA: mantida como estava)" % (MESES[mes - 1], ano))
        clicar_botao(botao_por_texto(tela, "&Grava"))
        eventos.append("clicou em Grava")
        regras = [(r"compet", "Sim")]
        acompanhar(tela, pid, regras, eventos, 1800, quieto=10, principal=principal)
        if _user32().IsWindow(tela.handle) and tela.is_visible():
            clicar_botao(botao_por_texto(tela, "&Saida"))
            time.sleep(1)
        # confere reabrindo a tela
        tela, combo, campo_ano, mes_atual, ano_atual = ler_competencia_fpo(pid, principal, eventos)
        clicar_botao(botao_por_texto(tela, "&Saida"))
        if mes_atual != MESES[mes - 1] or ano_atual != str(ano):
            raise RuntimeError("depois de gravar, a competência continua %s/%s" % (mes_atual, ano_atual))
        eventos.append("conferido: competência %s/%s" % (mes_atual, ano_atual))
        return {"competencia": "%02d/%d" % (mes, ano), "alterada": True}
    return operacao_fpo("competencia", p, pasta_res, corpo)


def navegar_pasta(tela, pasta, eventos):
    """Tela com DriveComboBox + DirectoryListBox + FileListBox (Delphi): vai até a pasta indicada."""
    listas = sorted([c for c in tela.descendants() if c.class_name() in ("ListBox", "TDirectoryListBox", "TFileListBox")],
                    key=lambda c: c.rectangle().top)
    if len(listas) < 2:
        raise RuntimeError("listas de pasta/arquivos não encontradas na tela")
    pastas, arquivos_lb = listas[0], listas[1]
    unidade, *partes = [x for x in os.path.normpath(pasta).split(os.sep) if x]
    if not unidade.upper().startswith("C:"):
        raise RuntimeError("só sei navegar no disco C: (%s)" % pasta)

    def abrir(i):
        pastas.set_focus()
        pastas.select(i)
        time.sleep(0.2)
        pastas.type_keys("{ENTER}", set_foreground=False)
        time.sleep(0.8)

    textos = pastas.item_texts()
    if not textos:
        raise RuntimeError("não consegui ler a lista de pastas")
    abrir(0)                                            # raiz "C:\"
    for parte in partes:
        textos = pastas.item_texts()
        idx = [i for i, t in enumerate(textos) if t.strip().lower() == parte.lower()]
        if not idx:
            raise RuntimeError("pasta %r não aparece na lista (%s)" % (parte, ", ".join(textos[:15])))
        abrir(idx[-1])
    nomes = [t.strip() for t in arquivos_lb.item_texts()]
    eventos.append("pasta escolhida: %s (%d arquivo(s) listados)" % (pasta, len(nomes)))
    return nomes


def fim_pelo_botao(botao, tela=None):
    """'terminou' para acompanhar(): o botão fica desabilitado durante o processamento e volta no fim.
    Algumas telas (importação do SIA) deixam o botão desabilitado: aí o fim é a mensagem final com OK,
    depois de a barra chegar ao fim, seguida de 10 s com o programa respondendo e sem nova mensagem."""
    estado = {"desabilitou": False, "desde": None, "eventos": None, "msg": None}

    def terminou(eventos):
        if estado["eventos"] is None:
            estado["eventos"] = len(eventos)
        if len(eventos) > estado["eventos"]:
            if eventos[-1].endswith("-> OK"):
                estado["msg"] = time.time()
            estado["eventos"] = len(eventos)
        if estado["msg"] and tela is not None:
            alvo = tela.handle if _user32().IsWindow(tela.handle) else None
            if alvo is None or (responde(alvo) and time.time() - estado["msg"] >= 10):
                return True
        if not _user32().IsWindow(botao.handle):
            return False
        habilitado = bool(_user32().IsWindowEnabled(botao.handle))
        if not habilitado:
            estado["desabilitou"], estado["desde"] = True, None
            return False
        if not estado["desabilitou"]:
            return False
        estado["desde"] = estado["desde"] or time.time()
        return time.time() - estado["desde"] >= 8          # habilitado de novo, e firme por 8 s
    return terminou


def preparar_pasta_local(nome):
    """Pasta de trabalho vazia. Se a anterior estiver presa (o programa ainda está com arquivos dela
    abertos), usa uma pasta nova com data/hora e tenta limpar as antigas sem insistir."""
    base = os.path.join(PASTA_AGENTE, "fpo")
    destino = os.path.join(base, nome)
    for antiga in [d for d in os.listdir(base) if d.startswith(nome + "_")] if os.path.isdir(base) else []:
        shutil.rmtree(os.path.join(base, antiga), ignore_errors=True)
    if os.path.isdir(destino):
        try:
            shutil.rmtree(destino)
        except OSError:
            destino = os.path.join(base, "%s_%s" % (nome, dt.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(destino)
    return destino


def tarefa_fpo_importar_sia(p, pasta_res):
    origem = caminho("entrada", *p["pasta"].split("/"))

    def corpo(pid, principal, eventos, arquivos):
        destino = preparar_pasta_local("sia")
        exes = sorted(f for f in os.listdir(origem) if f.lower().endswith(".exe"))
        for f in os.listdir(origem):
            if not f.lower().endswith(".exe"):
                shutil.copy2(os.path.join(origem, f), destino)
        for f in exes:                                     # BDSIA*a.exe e depois b.exe (7-Zip autoextraível)
            local = os.path.join(tempfile.gettempdir(), "autosus_" + f)   # da rede o Windows pede confirmação
            shutil.copy2(os.path.join(origem, f), local)
            r = subprocess.run([local, "-y", "-o" + destino], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=600,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            eventos.append("%s descompactado (código %s)" % (f, r.returncode))
            if r.returncode != 0:
                raise RuntimeError("falha ao descompactar %s: %s" % (f, r.stdout[-500:]))
        dbfs = sorted(f for f in os.listdir(destino) if f.lower().endswith(".dbf"))
        eventos.append("%d arquivo(s) .DBF em %s" % (len(dbfs), destino))
        if not dbfs:
            raise RuntimeError("nenhum .DBF do SIA para importar")
        tela = fpo_tela(pid, principal, ["MANUTENÇÃO", "IMPORTAR TABELAS NACIONAIS DO SIA"], "TFImp_SIA", eventos)
        listados = navegar_pasta(tela, destino, eventos)
        if not any(n.upper() == "S_PA.DBF" for n in listados):
            raise RuntimeError("a lista de arquivos da tela não mostra S_PA.DBF (pasta errada?)")
        botao = botao_por_texto(tela, "&Importa")
        clicar_botao(botao)
        eventos.append("clicou em Importa")
        # a importação do SIA demora (mais de 1 hora): o fim é o botão Importa voltar a ficar habilitado
        acompanhar(tela, pid, [(r"importa", "Sim")], eventos, 4 * 3600, quieto=10 ** 9, principal=principal,
                   terminou=fim_pelo_botao(botao, tela))
        eventos.append("importação do SIA concluída")
        img = "fpo_importar_sia.png"
        if _user32().IsWindow(tela.handle) and print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        if _user32().IsWindow(tela.handle) and tela.is_visible():
            clicar_botao(botao_por_texto(tela, "&Saida"))
        return {"dbf": len(dbfs)}
    return operacao_fpo("importar_sia", p, pasta_res, corpo)


def tarefa_fpo_importar_cnes(p, pasta_res):
    import zipfile
    origem = caminho("entrada", *p["pasta"].split("/"))

    def corpo(pid, principal, eventos, arquivos):
        destino = preparar_pasta_local("cnes")
        for f in sorted(os.listdir(origem)):
            if f.lower().endswith(".zip"):
                with zipfile.ZipFile(os.path.join(origem, f)) as z:
                    z.extractall(destino)
                    eventos.append("%s descompactado (%d arquivo(s))" % (f, len(z.namelist())))
        txts = [f for f in os.listdir(destino) if f.lower().endswith(".txt")]
        if not txts:
            raise RuntimeError("nenhum .txt do SCNES/Terceiros para importar")
        tela = fpo_tela(pid, principal, ["MANUTENÇÃO", "IMPORTAR TERCEIROS BRASIL"], "TFImp_SCNES", eventos)
        listados = navegar_pasta(tela, destino, eventos)
        if not listados:
            raise RuntimeError("a lista de arquivos da tela ficou vazia (pasta errada?)")
        botao = botao_por_texto(tela, "&Importa")
        if not botao.is_enabled():
            time.sleep(2)
        if not botao.is_enabled():
            raise RuntimeError("o botão Importa continua desabilitado depois de escolher a pasta")
        clicar_botao(botao)
        eventos.append("clicou em Importa")
        acompanhar(tela, pid, [(r"importa", "Sim")], eventos, 4 * 3600, quieto=10 ** 9, principal=principal,
                   terminou=fim_pelo_botao(botao, tela))
        eventos.append("importação do SCNES/Terceiros concluída")
        img = "fpo_importar_cnes.png"
        if _user32().IsWindow(tela.handle) and print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        if _user32().IsWindow(tela.handle) and tela.is_visible():
            clicar_botao(botao_por_texto(tela, "&Saida"))
        return {"txt": len(txts)}
    return operacao_fpo("importar_cnes", p, pasta_res, corpo)


def marcar(caixa, valor, eventos):
    if bool(caixa.get_check_state()) != valor:
        clicar_botao(caixa)
        time.sleep(0.4)
    eventos.append("%s: %s" % (caixa.window_text(), "marcado" if valor else "desmarcado"))


def tarefa_fpo_valores(p, pasta_res):
    mes, ano = int(p["mes"]), int(p["ano"])
    comp_tela = "%s/%d" % (MESES_ABREV[mes - 1], ano)
    regras = [(r"valor vigente igual ao valor de refer", "Sim"),
              (r"aplica[cç][aã]o dos percentuais", "Sim")]

    def corpo(pid, principal, eventos, arquivos):
        tela = fpo_tela(pid, principal, ["MANUTENÇÃO", "VALORES VIGENTES"], "TF_cad_val", eventos)
        titulo = tela.window_text()
        m = re.search(r"BDSIA:\s*(\d{6})", titulo)
        eventos.append("tela: %s" % re.sub(r"\s+", " ", titulo))
        if not m or m.group(1) != "%d%02d" % (ano, mes):
            raise RuntimeError("o BDSIA do FPO é %s, e não %d%02d (importe o SIA antes)"
                               % (m.group(1) if m else "?", ano, mes))
        combo = [c for c in tela.descendants() if "Combo" in c.class_name()
                 and re.fullmatch(r"[A-Z]{3}/\d{4}", _norm(ler_texto(c.handle) or ""))][0]
        if _norm(ler_texto(combo.handle)) != comp_tela:
            raise RuntimeError("a tela está na competência %s, e não %s" % (ler_texto(combo.handle), comp_tela))
        clicar_botao(botao_por_texto(tela, "Procura"))
        eventos.append("clicou em Procura (%s)" % comp_tela)
        acompanhar(tela, pid, regras, eventos, 1800, quieto=8)
        caixas = {_norm(c.window_text()): c for c in tela.descendants() if c.class_name() in ("TCheckBox", "CheckBox", "Button")
                  and _norm(c.window_text()) in ("ATENÇÃO BÁSICA", "FINANCIAMENTO MAC", "FINANCIAMENTO FAEC")}
        if len(caixas) != 3:
            raise RuntimeError("caixas Atenção Básica/MAC/FAEC não encontradas")
        marcar(caixas["ATENÇÃO BÁSICA"], False, eventos)
        marcar(caixas["FINANCIAMENTO MAC"], True, eventos)
        marcar(caixas["FINANCIAMENTO FAEC"], True, eventos)
        grupo = caixas["FINANCIAMENTO MAC"].parent()
        seta = [c for c in grupo.children() if c.class_name() == "TBitBtn" and not c.window_text()]
        if len(seta) != 1:
            raise RuntimeError("botão (seta) de atualizar com os valores do MS não encontrado")
        clicar_botao(seta[0])
        eventos.append("clicou em Atualizar tabela local com Valores do MS")
        acompanhar(tela, pid, regras, eventos, 1800, quieto=8)
        # Complemento federal: 0 / 0 / 100 para todos os procedimentos eletivos
        antes = {w.handle for w in janelas_do_processo(pid)}
        clicar_botao(botao_por_texto(tela, "Aplicar %"))
        fim, perc = time.time() + 20, None
        while time.time() < fim and perc is None:
            perc = next((w for w in janelas_do_processo(pid) if w.handle not in antes
                         and "PERCENTUA" in _norm(w.window_text())), None)
            time.sleep(0.5)
        if perc is None:
            raise RuntimeError("a tela 'Informe Percentuais para o Valor Federal' não abriu")
        edits = sorted([c for c in perc.descendants() if c.class_name() in ("TEdit", "Edit") and c.is_visible()],
                       key=lambda c: c.rectangle().left)
        if len(edits) < 3:
            raise RuntimeError("campos de percentual não encontrados (%d)" % len(edits))
        for campo, valor in zip(edits[:3], ("0", "0", "100")):
            campo.set_edit_text(valor)
        radio = [c for c in perc.descendants() if "TODOS OS PROCEDIMENTOS" in _norm(c.window_text())]
        if not radio:
            raise RuntimeError("opção 'Todos os procedimentos Eletivos' não encontrada")
        if not radio[0].get_check_state():
            clicar_botao(radio[0])
        eventos.append("percentuais: Amb %s, Hosp %s, Prof %s; todos os procedimentos eletivos"
                       % tuple(ler_texto(e.handle) for e in edits[:3]))
        img = "fpo_percentuais.png"
        if print_janela(perc, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_botao(botao_por_texto(perc, "Aplicar"))
        acompanhar(tela, pid, regras, eventos, 1800, quieto=8)
        # O FPO ainda pode estar "aplicando incremento na programação" depois de 'Percentuais aplicados!'
        # (com a VM lenta, minutos): espera a mensagem 'Valores gravados!' em vez de só alguns segundos
        # de silêncio; se ela não vier, tenta o Gravar mais uma vez.
        gravou = lambda ev: any("GRAVADOS" in _norm(e) for e in ev)   # noqa: E731
        for tentativa in (1, 2):
            clicar_botao(botao_por_texto(tela, "Gravar"))
            eventos.append("clicou em Gravar" + (" (de novo)" if tentativa == 2 else ""))
            acompanhar(tela, pid, regras, eventos, 1800, quieto=600, terminou=gravou)
            if gravou(eventos):
                break
        if not gravou(eventos):
            raise RuntimeError("não apareceu a mensagem 'Valores gravados!'")
        clicar_botao(botao_por_texto(tela, "Fechar"))
        return {"competencia": comp_tela}
    return operacao_fpo("valores", p, pasta_res, corpo)


def tarefa_fpo_exportar(p, pasta_res):
    nome = p["arquivo"]                                    # Valores_AAAAMM.VTP

    def corpo(pid, principal, eventos, arquivos):
        saida = preparar_pasta_local("saida")
        destino = os.path.join(saida, nome)
        tela = fpo_tela(pid, principal, ["MANUTENÇÃO", "EXPORTAR VALORES"], "TFrmExportarValores", eventos)
        campo = [c for c in tela.descendants() if c.class_name() in ("TEdit", "Edit")][0]
        if campo.has_style(0x0800):                         # só leitura: usa a caixa "Salvar como"
            procurar = [b for b in tela.descendants() if b.class_name() == "TBitBtn" and not b.window_text()]
            clicar_botao(procurar[0])
            escolher_arquivo_dialogo(pid, destino, eventos, salvar=True)
        else:
            campo.set_edit_text(destino)
        time.sleep(0.5)
        eventos.append("campo Arquivo: %s" % ler_texto(campo.handle))
        clicar_botao(botao_por_texto(tela, "&Exportar"))
        eventos.append("clicou em Exportar")
        acompanhar(tela, pid, [], eventos, 1800, quieto=10, principal=principal)
        img = "fpo_exportar.png"
        if _user32().IsWindow(tela.handle) and print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        gerados = sorted(os.listdir(saida))
        if not gerados:
            raise RuntimeError("a exportação terminou sem gerar arquivo em %s" % saida)
        for g in gerados:
            shutil.copy2(os.path.join(saida, g), os.path.join(pasta_res, g))
            arquivos.append(g)
        if _user32().IsWindow(tela.handle) and tela.is_visible():
            clicar_botao(botao_por_texto(tela, "&Fechar"))
        return {"exportados": gerados}
    return operacao_fpo("exportar", p, pasta_res, corpo)


def tarefa_fpo_fechar(p, pasta_res):
    """Fecha o FPO (antes de instalar a atualização). Só confirma perguntas de saída."""
    preparar_pywin32()
    exe = achar_executavel(p["executavel"])
    pid = pid_do_executavel(exe) if exe else None
    if not pid:
        return {"ok": True, "dados": {"eventos": ["o FPO não estava aberto"]}}
    eventos = []
    for w in janelas_do_processo(pid):                     # telas abertas: fecha sem executar
        if w.class_name() != "TF_GAMENU":
            fechar_sem_executar(w)
    principal = fpo_principal(pid)
    if principal is not None:
        eventos.append(_fechar_programa(principal, r"(sair|encerrar|finalizar|fechar)").replace("SISAIH01", "FPO"))
    return {"ok": True, "dados": {"eventos": eventos}}


def tarefa_fpo_abrir(p, pasta_res):
    """Abre o FPO e faz o login; em caso de parada devolve o que registrou até ali (mensagens e imagens)."""
    estado = {"eventos": [], "registro": [], "imagens": []}
    try:
        return _fpo_abrir(p, pasta_res, estado)
    except Exception as e:
        arquivos = []
        if estado["registro"]:
            nome = "fpo_mensagens_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
                f.write("\n".join(estado["eventos"]) + "\n\n" + "\n".join(estado["registro"]))
            arquivos = [nome] + estado["imagens"]
        erro = "%s: %s" % (type(e).__name__, e)
        return {"ok": False, "dados": {"eventos": estado["eventos"] + ["PAROU: " + erro], "erro": erro},
                "arquivos": arquivos}


def _fpo_abrir(p, pasta_res, estado):
    """Abre o FPO e faz o login (Usuário/Senha na tela de abertura). Para em qualquer mensagem."""
    preparar_pywin32()
    from pywinauto import Application
    exe = achar_executavel(p["executavel"])
    if not exe:
        raise RuntimeError("FPO não instalado")
    eventos = estado["eventos"]
    pid = pid_do_executavel(exe)
    if not pid:
        pid = Application(backend="win32").start(exe, work_dir=os.path.dirname(exe)).process
        eventos.append("FPO aberto")
    fim = time.time() + 60
    login = None
    while time.time() < fim and login is None:
        for w in janelas_do_processo(pid):
            campos = [c for c in w.descendants() if c.class_name() in ("TEdit", "TMaskEdit", "Edit") and c.is_visible()]
            if len(campos) == 2 and w.class_name() != "TF_GAMENU":
                login = (w, sorted(campos, key=lambda c: c.rectangle().left))
                break
        principal = fpo_principal(pid)
        if login is None and principal is not None and len(principal.menu_items()) > 2:
            eventos.append("FPO já estava com login feito")
            break
        time.sleep(1)
    if login:
        tela, (campo_usuario, campo_senha) = login
        preencher_campo(campo_usuario, p.get("usuario", "mestre"))
        preencher_campo(campo_senha, p.get("senha", "A"), senha=True)
        campo_senha.set_focus()
        campo_senha.type_keys("{ENTER}", set_foreground=False)
        eventos.append("login enviado (usuário %s)" % p.get("usuario", "mestre"))
    tela_login = login[0].handle if login else None
    # registra (imagem + controles + texto) cada janela/mensagem nova que o FPO mostrar, antes de agir
    vistos, registro, imagens = set(), estado["registro"], estado["imagens"]

    def registrar_novas():
        for w in janelas_do_processo(pid):
            if w.handle in vistos or w.class_name() == "TF_GAMENU" or w.handle == tela_login:
                continue
            vistos.add(w.handle)
            n = len(vistos)
            img = "fpo_msg%d.png" % n
            if print_janela(w, os.path.join(pasta_res, img)):
                imagens.append(img)
            texto = texto_dialogo(w) if w.class_name() in CLASSES_DIALOGO else ""
            registro.append("#" * 80 + "\nJANELA %d: %r classe=%s %s\n%s" % (
                n, w.window_text(), w.class_name(), ("texto: %r" % texto) if texto else "", controles_da_janela(w, 4)))
    principal = fpo_principal(pid)
    if principal is None or len(principal.menu_items()) <= 2 or login:
        # Depois de uma atualização do FPO, o primeiro login atualiza o banco ("Aguarde... Atualização do
        # Banco de Dados") e mostra a tela "Backup e Restore do banco". O robô não clica em nada nela:
        # espera o FPO terminar sozinho, registrando o que aparece; se ficar parado, devolve para decisão.
        inicio = time.time()
        fim, ultimo_texto, desde = inicio + 1800, None, time.time()
        while time.time() < fim:
            checar_cancelamento()
            registrar_novas()
            principal = fpo_principal(pid)
            caixas = dialogos_abertos(pid)
            if caixas:
                for d in caixas:
                    tratar_dialogo(d, [], eventos)          # só OK; pergunta = para
                desde = time.time()
                continue
            outras = [w for w in janelas_do_processo(pid) if w.class_name() != "TF_GAMENU" and w.handle != tela_login]
            login_aberto = tela_login is not None and _user32().IsWindow(tela_login) and _user32().IsWindowVisible(tela_login)
            if principal is not None and len(principal.menu_items()) > 2 and not login_aberto and not outras:
                break
            texto = " | ".join("%s: %s" % (w.window_text(), " ".join(
                (ler_texto(c.handle, 500) or "").split())[-200:]) for w in outras
                for c in w.descendants() if c.class_name() in ("TMemo", "TRichEdit"))
            nomes = ", ".join(w.window_text() or w.class_name() for w in outras)
            if texto != ultimo_texto:
                if texto:
                    eventos.append("andamento: " + texto)
                ultimo_texto, desde = texto, time.time()
            avisar("FPO abrindo há %d min (%s)" % ((time.time() - inicio) // 60, nomes or "aguardando"))
            # tela "Backup e Restore do banco" parada (depois de atualizar o FPO): o procedimento é sair dela
            backup = [w for w in outras if "BACKUP E RESTORE" in _norm(w.window_text())]
            if backup and time.time() - desde > 20 and responde(backup[0].handle):
                sair = [c for c in backup[0].descendants() if c.class_name() in ("TBitBtn", "TButton")
                        and _norm(c.window_text()) in ("SAIDA", "SAÍDA", "SAIR")]
                if sair:
                    clicar_botao(sair[0])
                    eventos.append("tela 'Backup e Restore do banco' parada: clicou em Saída")
                    desde = time.time()
                    time.sleep(3)
                    continue
            if outras and time.time() - desde > 600:
                img = "fpo_abrir_parado.png"
                if print_janela(outras[0], os.path.join(pasta_res, img)):
                    pass
                raise ParadaParaDecisao("o FPO está há 10 min parado na tela %r sem mudar. Nada foi clicado; "
                                        "veja o que ela pede." % nomes)
            time.sleep(3)
        else:
            raise RuntimeError("o FPO não ficou pronto em 30 min")
        eventos.append("FPO pronto (menu completo)")
    arquivos, titulos = gravar_telas(pid, pasta_res, "fpo_logado", {"eventos": eventos})
    if registro:
        nome = "fpo_mensagens_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
            f.write("\n".join(eventos) + "\n\n" + "\n".join(registro))
        arquivos += [nome] + imagens
    principal = fpo_principal(pid)
    status = []
    if principal is not None:
        status = [ler_texto(c.handle) or "" for c in principal.descendants() if c.class_name() == "TPanel"]
    return {"ok": True, "dados": {"eventos": eventos, "janelas": titulos,
                                  "barra_status": [t for t in status if t.strip()]}, "arquivos": arquivos}


# ------------------------------------------------------------------ SIHD2

def titulo_janela(w):
    """Título da janela sem esperar o programa responder (o SIHD fica 'ocupado' durante as importações)."""
    h = w if isinstance(w, int) else w.handle
    buf = ctypes.create_unicode_buffer(512)
    _user32().GetWindowTextW(h, buf, 512)
    return buf.value

def sihd_principal(pid):
    """Janela principal JÁ LOGADA. Antes do login o título é só 'Sistema de Informação Hospitalar -
    Descentralizado'; depois vira '... - (M150175801) SMS ... - Versão 23.40' (com o órgão e a versão)."""
    janelas = janelas_do_processo(pid)
    if any(titulo_janela(w).startswith(("Acesso à Aplicação", "Acesso a Aplica")) for w in janelas):
        return None
    for w in janelas:
        t = titulo_janela(w)
        if t.startswith("Sistema de Informação Hospitalar") and ("(" in t or "VERS" in _norm(t)):
            return w
    return None


def tarefa_sihd_abrir(p, pasta_res):
    """Abre o SIHD2: espera os AVISOS IMPORTANTES, faz o login (Acesso à Aplicação) e, na primeira vez
    depois de instalar, executa o Release (Instalar -> Sim -> Sair). Registra cada tela nova com imagem."""
    estado = {"eventos": [], "registro": [], "imagens": []}
    try:
        dados = _sihd_abrir(p, pasta_res, estado)
        ok, erro = True, None
    except Exception as e:
        dados, ok, erro = {}, False, "%s: %s" % (type(e).__name__, e)
        estado["eventos"].append("PAROU: " + erro)
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(os.path.join(pasta_res, "erro_sihd_abrir.png"))
            estado["imagens"].append("erro_sihd_abrir.png")
        except Exception:
            pass
    nome = "sihd_abrir_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(estado["eventos"]) + "\n\n" + "\n".join(estado["registro"]))
    dados.update({"eventos": estado["eventos"]})
    if erro:
        dados["erro"] = erro
    return {"ok": ok, "dados": dados, "arquivos": [nome] + estado["imagens"]}


_EXE_CACHE = {}


def _exe_do_processo(pid):
    """Nome do executável do processo. Usa QueryFullProcessImageName, que funciona com acesso limitado
    (inclusive para processo aberto 'como administrador'); falhas não ficam guardadas."""
    if _EXE_CACHE.get(pid):
        return _EXE_CACHE[pid]
    nome = ""
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            tam = ctypes.c_ulong(1024)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)):
                nome = os.path.basename(buf.value).lower()
        finally:
            k32.CloseHandle(h)
    if nome:
        _EXE_CACHE[pid] = nome
    return nome


TITULOS_SIHD = ("Sistema de Informação Hospitalar", "Acesso à Aplicação", "AVISOS IMPORTANTES", "Release ",
                "RELEASE", "SIHD", "Configurações - ", "Importação", "Gerenciar", "Criticar", "Apura", "Encerrar")


def janelas_sihd():
    """Janelas visíveis do SIHD2.exe e do ReleaseNNNN.exe (o Release roda em outro processo)."""
    from pywinauto import Desktop
    out = []
    for w in Desktop(backend="win32").windows(visible_only=True):
        try:
            nome = _exe_do_processo(w.process_id())
        except Exception:
            continue
        if nome == "sihd2.exe" or re.fullmatch(r"release\d+\.exe", nome) or \
                (not nome and titulo_janela(w).startswith(TITULOS_SIHD)):
            r = w.rectangle()
            if w.class_name() != "TApplication" and r.width() > 20 and r.height() > 20:
                out.append(w)
    return out


def _sihd_abrir(p, pasta_res, estado):
    preparar_pywin32()
    from pywinauto import Application
    exe = achar_executavel(p["executavel"])
    if not exe:
        raise RuntimeError("SIHD2 não instalado")
    pasta = os.path.dirname(exe)
    eventos, registro, imagens = estado["eventos"], estado["registro"], estado["imagens"]
    if not p.get("usuario") or not p.get("senha"):
        raise RuntimeError("usuário/senha do SIHD não informados (SIHD_USUARIO e SIHD_SENHA no .env)")
    vistos = set()

    def registrar(janelas):
        for w in janelas:
            chave = (w.handle, titulo_janela(w)[:12])
            if chave in vistos or w.class_name() == "TFoAvisos" and any(k[0] == w.handle for k in vistos):
                continue
            vistos.add(chave)
            n = len(vistos)
            img = "sihd_tela%d.png" % n
            if print_janela(w, os.path.join(pasta_res, img)):
                imagens.append(img)
            texto = texto_dialogo(w) if w.class_name() in CLASSES_DIALOGO else ""
            registro.append("#" * 80 + "\nJANELA %d: %r classe=%s processo=%s %s\n%s" % (
                n, titulo_janela(w), w.class_name(), _exe_do_processo(w.process_id()),
                ("texto: %r" % texto) if texto else "", controles_da_janela(w, 4)))

    def vivos():
        return [w for w in janelas_sihd()]

    def iniciar(caminho_exe, motivo):
        Application(backend="win32").start(caminho_exe, work_dir=pasta)
        eventos.append(motivo)
        limite = time.time() + 60                      # espera a primeira janela (não abre duas vezes)
        while time.time() < limite and not janelas_sihd():
            time.sleep(1)

    aberturas, logins = 0, 0
    release = {"iniciado": False, "instalar": False, "sair": False}
    avisos_vistos = {}
    inicio = time.time()
    fim = inicio + 1800
    while time.time() < fim:
        checar_cancelamento()
        janelas = janelas_sihd()
        registrar(janelas)
        avisar("SIHD2 abrindo há %d min (%s)" % ((time.time() - inicio) // 60,
                                                  ", ".join(titulo_janela(w)[:30] for w in janelas) or "nada aberto"))
        if not janelas:
            # nada aberto: abre o SIHD2 (no começo, ou depois que o Release terminou)
            if aberturas >= 4:
                raise RuntimeError("o SIHD2 fechou %d vezes durante a abertura" % aberturas)
            aberturas += 1
            iniciar(exe, "SIHD2 aberto" + (" de novo (depois do Release)" if release["sair"] else ""))
            continue
        caixas = [w for w in janelas if w.class_name() in CLASSES_DIALOGO]
        if caixas:
            for d in caixas:
                texto = _norm(texto_dialogo(d))
                b = botoes_dialogo(d)
                if not b:
                    time.sleep(0.5)
                    continue
                if "SENHA INV" in texto or "ACESSO NEGADO" in texto:
                    eventos.append("[%s] %s -> OK" % (titulo_janela(d), texto_dialogo(d)))
                    if "OK" in b:
                        clicar_botao(b["OK"])
                    raise ParadaParaDecisao("o SIHD recusou a senha. Confira SIHD_USUARIO/SIHD_SENHA no .env "
                                            "(o robô para na primeira recusa para não bloquear o usuário)")
                if "INCOMPAT" in texto and "BANCO DE DADOS" in texto:
                    eventos.append("[%s] %s -> OK" % (titulo_janela(d), texto_dialogo(d)))
                    if "OK" in b:
                        clicar_botao(b["OK"])
                    if release["sair"]:
                        raise RuntimeError("o banco continua incompatível depois do Release")
                    time.sleep(3)
                    for w in janelas_sihd():              # fecha o SIHD2 que sobrou, para rodar o Release
                        if _exe_do_processo(w.process_id()) == "sihd2.exe" and w.class_name() not in CLASSES_DIALOGO:
                            try:
                                w.close()
                            except Exception:
                                pass
                    time.sleep(3)
                    if not any(re.fullmatch(r"release\d+\.exe", _exe_do_processo(w.process_id())) for w in janelas_sihd()):
                        rels = sorted(f for f in os.listdir(pasta) if re.fullmatch(r"Release\d{4}\.exe", f, re.IGNORECASE))
                        if not rels:
                            raise RuntimeError("banco desatualizado e nenhum ReleaseNNNN.exe na pasta do SIHD2")
                        iniciar(os.path.join(pasta, rels[-1]), "banco desatualizado: executando %s" % rels[-1])
                    release["iniciado"] = True
                    break
                if _norm(titulo_janela(d)) == "RELEASE" and "SIM" in b:
                    eventos.append("[RELEASE] %s -> Sim" % texto_dialogo(d))
                    clicar_botao(b["SIM"])
                    continue
                tratar_dialogo(d, [], eventos)        # só OK é confirmado; outra pergunta faz parar
            time.sleep(1)
            continue
        principal = next((w for w in janelas if sihd_titulo_logado(titulo_janela(w))), None)
        login_aberto = any(titulo_janela(w).startswith(("Acesso à Aplicação", "Acesso a Aplica")) for w in janelas)
        if principal is not None and not login_aberto:
            eventos.append("janela principal: %s" % titulo_janela(principal))
            return {"titulo": titulo_janela(principal), "release": release["sair"]}
        acao = False
        for w in janelas:
            titulo = titulo_janela(w)
            if w.class_name() == "TFoAvisos":
                # "AVISOS IMPORTANTES - O SIHD2 iniciará em N segundos": fecha logo (mesmo efeito de esperar)
                avisos_vistos.setdefault(w.handle, time.time())
                if time.time() - avisos_vistos[w.handle] > 2:
                    w.close()
                    eventos.append("AVISOS IMPORTANTES fechado")
                    acao = True
                break
            if titulo.startswith(("Acesso à Aplicação", "Acesso a Aplica")):
                if logins >= 3:
                    raise RuntimeError("a tela de acesso voltou %d vezes" % logins)
                campos = sorted([c for c in w.descendants() if c.class_name() in ("TEdit", "TMaskEdit", "Edit")
                                 and c.is_visible()], key=lambda c: (c.rectangle().top, c.rectangle().left))
                if len(campos) < 2:
                    raise RuntimeError("campos de usuário/senha não encontrados na tela de acesso")
                digitar(campos[0], p["usuario"])
                if (ler_texto(campos[0].handle) or "").strip().upper() != p["usuario"].strip().upper():
                    raise RuntimeError("o campo usuário ficou %r" % ler_texto(campos[0].handle))
                digitar(campos[1], p["senha"])
                clicar_botao(botao_por_texto(w, "OK"))
                logins += 1
                eventos.append("login enviado (usuário %s) em %s" % (p["usuario"], _exe_do_processo(w.process_id())))
                time.sleep(3)
                acao = True
                break
            if titulo.startswith("Release"):
                botoes = {_norm(titulo_janela(c)): c for c in w.descendants()
                          if c.class_name() in ("TBitBtn", "TButton", "Button") and c.is_visible()}
                if not release["instalar"] and "INSTALAR" in botoes and botoes["INSTALAR"].is_enabled():
                    clicar_botao(botoes["INSTALAR"])
                    release["instalar"] = True
                    eventos.append("%s: clicou em Instalar" % titulo)
                    acao = True
                elif release["instalar"] and "SAIR" in botoes and botoes["SAIR"].is_enabled() and responde(w.handle):
                    memo = [ler_texto(c.handle) or "" for c in w.descendants() if c.class_name() in ("TMemo", "TRichEdit")]
                    eventos.append("%s: %s" % (titulo, " ".join(" ".join(memo).split())[-300:]))
                    clicar_botao(botoes["SAIR"])
                    release["sair"] = True
                    eventos.append("%s: concluído, clicou em Sair" % titulo)
                    acao = True
                time.sleep(2)
                break
        time.sleep(1 if acao else 2)
    raise RuntimeError("o SIHD2 não chegou à janela principal em 30 min")


def sihd_qualquer(pid):
    for w in janelas_do_processo(pid):
        if titulo_janela(w).startswith("Sistema de Informação Hospitalar"):
            return w
    return None


def digitar(campo, texto):
    """Digita pelo teclado no campo (apaga antes). Usado em telas de login que ignoram texto colado."""
    campo.set_focus()
    time.sleep(0.2)
    campo.type_keys("{END}+{HOME}{DEL}", set_foreground=False)
    escapado = "".join("{%s}" % c if c in "+^%~(){}[]" else c for c in texto)
    campo.type_keys(escapado, with_spaces=True, set_foreground=False, pause=0.03)
    time.sleep(0.2)


def _processo_vivo(pid):
    import win32api, win32con, win32process
    try:
        h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        return win32process.GetExitCodeProcess(h) == 259          # STILL_ACTIVE
    except Exception:
        return False


# ------------------------------------------------------------------ SIHD2: operações

SIHD_MENU = {"CONFIGURAÇÃO": 0, "MANUTENÇÃO": 1, "PRODUÇÃO": 2, "CONTROLE E AVALIAÇÃO": 3,
             "PROCESSAMENTO": 4, "RELATÓRIOS": 5, "AJUDA": 6}


def sihd_titulo_logado(titulo):
    """Antes do login: 'Sistema de Informação Hospitalar - Descentralizado'. Logado: '... - (M150175801) SMS ...
    - CMPT: 07/2026 - Versão 23.40' ou, com a competência aberta, '... - SMS BREJO GRANDE DO ARAGUAIA'."""
    t = (titulo or "").strip()
    return t.startswith("Sistema de Informação Hospitalar - ") and not t.endswith("Descentralizado")


def sihd_menu_habilitado(espec, indice):
    try:
        barra = max((b for b in espec.wrapper_object().descendants(class_name="TToolBar") if b.button_count()),
                    key=lambda b: b.button_count())
        return bool(barra.button(indice).is_enabled())
    except Exception:
        return False


def sihd_contexto():
    preparar_pywin32()
    from pywinauto import Application
    janelas = janelas_sihd()
    if any(titulo_janela(w).startswith(("Acesso à Aplicação", "Acesso a Aplica")) for w in janelas):
        raise RuntimeError("o SIHD2 está na tela de login (rode 'robo.bat sihd abrir')")
    principal = next((w for w in janelas if sihd_titulo_logado(titulo_janela(w))), None)
    if principal is None:
        from pywinauto import Desktop
        vistas = []
        for w in Desktop(backend="win32").windows(visible_only=True):
            t = titulo_janela(w)
            if t:
                vistas.append("%r [%s, %s, responde=%s]" % (t[:60], w.class_name(), _exe_do_processo(w.process_id()) or "?",
                                                              responde(w.handle, 1000)))
        raise RuntimeError("o SIHD2 não está aberto com login feito (rode 'robo.bat sihd abrir'). Janelas vistas: %s"
                           % "; ".join(vistas[:15]))
    app = Application(backend="win32").connect(handle=principal.handle)
    return principal.process_id(), principal, app.window(handle=principal.handle)


def competencia_sihd(titulo):
    m = re.search(r"CMPT:\s*(\d{2})/(\d{4})", titulo or "")
    return "%s/%s" % (m.group(1), m.group(2)) if m else None


def sihd_tela(pid, principal, espec, menu, caminho, titulo_tela, eventos):
    """Abre uma tela do SIHD pela barra de menus (confirma mensagens só com OK no caminho)."""
    for w in janelas_sihd():
        if titulo_janela(w).startswith(titulo_tela):
            w.set_focus()
            return w
    for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
        tratar_dialogo(d, [], eventos)
    antes = {w.handle for w in janelas_sihd()}
    escolher_menu(espec, SIHD_MENU[_norm(menu)], caminho)
    fim = time.time() + 30
    while time.time() < fim:
        for w in janelas_sihd():
            if w.handle not in antes and titulo_janela(w).startswith(titulo_tela):
                time.sleep(1)
                return w
        time.sleep(0.5)
    novas = [titulo_janela(w) for w in janelas_sihd() if w.handle not in antes]
    raise RuntimeError("a tela %r não abriu (janelas novas: %s)" % (titulo_tela, novas))


def operacao_sihd(acao, pasta_res, corpo):
    eventos, arquivos, dados = [], [], {}
    ok, erro = False, None
    try:
        pid, principal, espec = sihd_contexto()
        dados = corpo(pid, principal, espec, eventos, arquivos) or {}
        ok = True
    except Exception as e:
        erro = "%s: %s" % (type(e).__name__, e)
        eventos.append("PAROU: " + erro)
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(os.path.join(pasta_res, "erro_sihd_%s.png" % acao))
            arquivos.append("erro_sihd_%s.png" % acao)
        except Exception:
            pass
    arquivos.insert(0, relatorio(pasta_res, "sihd_" + acao, eventos + ["", "dados: " + json.dumps(dados, ensure_ascii=False)]))
    dados["eventos"] = eventos
    if erro:
        dados["erro"] = erro
    return {"ok": ok, "dados": dados, "arquivos": arquivos}


def escolher_pasta_dialogo(pasta, eventos, limite=20):
    """Caixa 'Procurar Pasta' do Windows (árvore): Área de Trabalho > Este Computador > (C:) > ... > OK."""
    from pywinauto import Desktop
    fim = time.time() + limite
    caixa = tree = None
    while time.time() < fim and tree is None:
        for d in Desktop(backend="win32").windows(class_name="#32770", visible_only=True):
            arv = d.descendants(class_name="SysTreeView32")
            if arv:
                caixa, tree = d, arv[0]
                break
        time.sleep(0.5)
    if tree is None:
        raise RuntimeError("a caixa 'Procurar Pasta' não abriu")
    unidade, *partes = [x for x in os.path.normpath(pasta).split(os.sep) if x]
    raiz = tree.roots()[0]
    raiz.expand()
    time.sleep(0.5)
    computador = next((c for c in raiz.children() if _norm(c.text()) in ("ESTE COMPUTADOR", "COMPUTADOR", "MEU COMPUTADOR", "THIS PC")), None)
    if computador is None:
        raise RuntimeError("'Este Computador' não aparece na caixa de pastas (%s)" % [c.text() for c in raiz.children()])
    computador.expand()
    time.sleep(0.8)
    atual = next((c for c in computador.children() if "(%s)" % unidade.upper() in c.text().upper()), None)
    if atual is None:
        raise RuntimeError("disco %s não aparece (%s)" % (unidade, [c.text() for c in computador.children()]))
    for parte in partes:
        atual.expand()
        time.sleep(0.6)
        filho = next((c for c in atual.children() if c.text().strip().lower() == parte.lower()), None)
        if filho is None:
            raise RuntimeError("pasta %r não aparece em %r (%s)" % (parte, atual.text(), [c.text() for c in atual.children()][:20]))
        atual = filho
    atual.select()
    atual.ensure_visible()
    time.sleep(0.5)
    eventos.append("caixa 'Procurar Pasta': %s" % pasta)
    ok = [b for b in caixa.children() if b.class_name() == "Button" and b.control_id() == 1]
    if not ok:
        raise RuntimeError("botão OK da caixa de pastas não encontrado")
    clicar_botao(ok[0])
    time.sleep(1.5)


def finalizar_cnes(tela, mensagens, botao_sair, eventos, arquivos, pasta_res, opcoes):
    texto = (ler_texto(mensagens.handle, 5000) or "").replace("\r", "")
    nome = "sihd_importar_cnes_mensagens.txt"
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write(texto)
    arquivos.append(nome)
    img = "sihd_importar_cnes.png"
    if print_janela(tela, os.path.join(pasta_res, img)):
        arquivos.append(img)
    if _user32().IsWindowEnabled(botao_sair.handle):
        clicar_botao(botao_sair)
        eventos.append("clicou em Sair")
    return {"opcoes": opcoes, "mensagens": [l for l in texto.split("\n") if l.strip()][-25:]}


def tarefa_sihd_importar_cnes(p, pasta_res):
    import zipfile
    origem = caminho("entrada", *p["pasta"].split("/"))

    def corpo(pid, principal, espec, eventos, arquivos):
        destino = preparar_pasta_local("sihd_cnes")
        for f in sorted(os.listdir(origem)):
            arq = os.path.join(origem, f)
            if f.lower().endswith(".zip"):
                shutil.copy2(arq, destino)                 # o SIHD usa o zip E o conteúdo: deixa os dois
                with zipfile.ZipFile(arq) as z:
                    z.extractall(destino)
                    eventos.append("%s copiado e descompactado (%d arquivo(s))" % (f, len(z.namelist())))
            else:
                shutil.copy2(arq, destino)                 # Valores_AAAAMM.VTP
                eventos.append("%s copiado" % f)
        tela = sihd_tela(pid, principal, espec, "PRODUÇÃO", ["IMPORTAR ARQUIVOS", "IMPORTAR DADOS DO CNES"],
                         "Importação CNES", eventos)
        caixas = {_norm(titulo_janela(c)): c for c in tela.descendants() if c.class_name() in ("TCheckBox", "CheckBox")}
        edits = sorted([c for c in tela.descendants() if c.class_name() in ("TEdit", "Edit", "TMemo")],
                       key=lambda c: c.rectangle().top)
        diretorio, mensagens = edits[0], edits[-1]
        botao_importar, botao_sair = botao_por_texto(tela, "Importar"), botao_por_texto(tela, "Sair")
        en = lambda b: bool(_user32().IsWindowEnabled(b.handle))

        def esperar_fim(origem_txt):
            # a importação demora e o SIHD fica sem responder em alguns trechos: o fim é o botão Sair
            # voltar a ficar habilitado (ele fica desabilitado durante toda a importação)
            acompanhar(tela, pid, [], eventos, 4 * 3600, quieto=10 ** 9, principal=principal,
                       terminou=fim_pelo_botao(botao_sair, None))
            eventos.append("importação concluída (%s)" % origem_txt)

        if not en(botao_importar) and not en(botao_sair):
            # tela de uma execução anterior com a importação ainda em andamento: só espera terminar
            eventos.append("importação já em andamento na tela aberta: aguardando o fim")
            esperar_fim("execução anterior")
            return finalizar_cnes(tela, mensagens, botao_sair, eventos, arquivos, pasta_res, {})
        # botão "..." (desenhado, sem janela própria: fica logo à direita do campo Diretório) -> árvore de pastas
        liberou = lambda: en(botao_importar) or \
            any(c.is_enabled() for n, c in caixas.items() if not n.startswith("REALIZA"))
        from pywinauto import mouse
        tela.set_focus()
        r_dir = diretorio.rectangle()
        mouse.click(coords=(r_dir.right + 16, (r_dir.top + r_dir.bottom) // 2))
        escolher_pasta_dialogo(destino, eventos)
        time.sleep(2)
        if not liberou():
            raise RuntimeError("as opções de arquivos não liberaram depois de escolher a pasta %s" % destino)
        # os cinco tipos de arquivo foram fornecidos: todos devem ficar marcados (o backup fica como está)
        faltando = []
        for nome_cx, cx in caixas.items():
            if nome_cx.startswith("REALIZA"):
                continue
            if not cx.get_check_state():
                if cx.is_enabled():
                    clicar_botao(cx)
                    time.sleep(0.4)
                    eventos.append("%s estava desmarcado: marcado pelo robô" % titulo_janela(cx))
                if not cx.get_check_state():
                    faltando.append(titulo_janela(cx))
        if faltando:
            raise RuntimeError("opções que não ficaram marcadas (o SIHD não reconheceu o arquivo?): %s; "
                               "nada foi importado" % ", ".join(faltando))
        eventos.append("diretório: %s" % ler_texto(diretorio.handle))
        estado_caixas = {n: ("marcado" if c.get_check_state() else "desmarcado") + ("" if c.is_enabled() else " (bloqueado)")
                         for n, c in caixas.items()}
        eventos.append("opções: " + "; ".join("%s: %s" % kv for kv in estado_caixas.items()))
        img = "sihd_importar_cnes_antes.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_botao(botao_importar)
        eventos.append("clicou em Importar")
        esperar_fim("esta execução")
        return finalizar_cnes(tela, mensagens, botao_sair, eventos, arquivos, pasta_res, estado_caixas)
    return operacao_sihd("importar_cnes", pasta_res, corpo)


def tarefa_sihd_importar_tabelas(p, pasta_res):
    """Produção > Importar Arquivos > Importar Tabelas Nacionais: 'Deseja realmente importar...?' -> Sim;
    pergunta do backup -> Não (como no procedimento); espera o Sair da tela de importação liberar."""
    regras = [(r"deseja realmente importar as tabelas nacionais", "Sim"), (r"backup", "Não")]

    def corpo(pid, principal, espec, eventos, arquivos):
        for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
            tratar_dialogo(d, [], eventos)
        antes = {w.handle for w in janelas_sihd()}
        escolher_menu(espec, SIHD_MENU["PRODUÇÃO"], ["IMPORTAR ARQUIVOS", "IMPORTAR TABELAS NACIONAIS"])
        eventos.append("menu Importar Tabelas Nacionais")
        tela, botao_sair, inicio = None, None, time.time()
        ultimo_aviso = 0
        while time.time() - inicio < 4 * 3600:
            checar_cancelamento()
            janelas = janelas_sihd()
            caixas = [w for w in janelas if w.class_name() in CLASSES_DIALOGO]
            if caixas:
                for d in caixas:
                    tratar_dialogo(d, regras, eventos)
                time.sleep(1)
                continue
            if tela is None:
                tela = next((w for w in janelas if w.handle not in antes
                             and titulo_janela(w).startswith("Importação de Tabelas")), None)
                if tela is not None:
                    eventos.append("tela: %s" % titulo_janela(tela))
                    try:
                        botao_sair = botao_por_texto(tela, "Sair")
                    except RuntimeError:
                        botao_sair = None
                    terminou = fim_pelo_botao(botao_sair, None) if botao_sair else None
            elif terminou is not None and terminou(eventos):
                break
            elif not _user32().IsWindow(tela.handle):
                eventos.append("a tela de importação fechou sozinha")
                break
            if time.time() - ultimo_aviso > 50:
                avisar("Importação de Tabelas Nacionais: processando há %d min" % ((time.time() - inicio) // 60))
                ultimo_aviso = time.time()
            if tela is None and time.time() - inicio > 120:
                raise RuntimeError("a tela 'Importação de Tabelas do Sistema' não abriu")
            time.sleep(2)
        else:
            raise RuntimeError("a importação das tabelas não terminou em 4 horas")
        if tela is not None and _user32().IsWindow(tela.handle):
            memo = [c for c in tela.descendants() if c.class_name() in ("TMemo", "TRichEdit", "TListBox")]
            texto = "\n".join((ler_texto(m.handle, 5000) or "") for m in memo).replace("\r", "")
            if texto.strip():
                nome = "sihd_importar_tabelas_mensagens.txt"
                with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
                    f.write(texto)
                arquivos.append(nome)
            img = "sihd_importar_tabelas.png"
            if print_janela(tela, os.path.join(pasta_res, img)):
                arquivos.append(img)
            if botao_sair is not None and _user32().IsWindowEnabled(botao_sair.handle):
                clicar_botao(botao_sair)
                eventos.append("clicou em Sair")
        eventos.append("importação das tabelas nacionais concluída em %d min" % ((time.time() - inicio) // 60))
        return {}
    return operacao_sihd("importar_tabelas", pasta_res, corpo)


def registrar_janela(w, pasta_res, prefixo, registro, arquivos):
    n = len(registro) + 1
    img = "%s_%d.png" % (prefixo, n)
    if print_janela(w, os.path.join(pasta_res, img)):
        arquivos.append(img)
    texto = texto_dialogo(w) if w.class_name() in CLASSES_DIALOGO else ""
    registro.append("#" * 80 + "\nJANELA %d: %r classe=%s %s\n%s" % (
        n, titulo_janela(w), w.class_name(), ("texto: %r" % texto) if texto else "", controles_da_janela(w, 5)))


def tarefa_sihd_importar_aih(p, pasta_res):
    """Produção > Importar Arquivos > Importar Movimento de AIH > Estabelecimento (arquivos do SISAIH01):
    copia o DSIHD017 para a pasta do SIHD2, escolhe o .Zip exportado pelo SISAIH01, Importar, espera o Sair."""
    origem = caminho("entrada", *p["pasta"].split("/"))
    registro = []

    def corpo(pid, principal, espec, eventos, arquivos):
        exe = achar_executavel(p["executavel"])
        pasta_sihd = os.path.dirname(exe)
        destino = preparar_pasta_local("sihd_aih")
        zip_aih = None
        for f in sorted(os.listdir(origem)):
            if re.match(r"DSIHD\d+_", f, re.IGNORECASE):
                shutil.copy2(os.path.join(origem, f), os.path.join(pasta_sihd, f))
                eventos.append("%s copiado para %s" % (f, pasta_sihd))
            else:
                shutil.copy2(os.path.join(origem, f), destino)
                zip_aih = os.path.join(destino, f)
                eventos.append("arquivo de AIH: %s" % zip_aih)
        if not zip_aih:
            raise RuntimeError("arquivo .Zip do SISAIH01 não recebido")
        regras = []
        antes = {w.handle for w in janelas_sihd()}
        for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
            tratar_dialogo(d, [], eventos)
        escolher_menu(espec, SIHD_MENU["PRODUÇÃO"], ["IMPORTAR ARQUIVOS", "IMPORTAR MOVIMENTO DE AIH"])
        eventos.append("menu Importar Movimento de AIH")
        # 1) Origem dos Dados: opção do estabelecimento (arquivos do SISAIH01)
        origem_tela = None
        fim = time.time() + 30
        while time.time() < fim and origem_tela is None:
            for w in janelas_sihd():
                if w.handle in antes:
                    continue
                if w.class_name() in CLASSES_DIALOGO:
                    registrar_janela(w, pasta_res, "sihd_aih", registro, arquivos)
                    tratar_dialogo(w, regras, eventos)
                elif titulo_janela(w).startswith("Importação - Origem"):
                    origem_tela = w
            time.sleep(0.5)
        if origem_tela is None:
            raise RuntimeError("a tela 'Importação - Origem dos Dados' não abriu")
        registrar_janela(origem_tela, pasta_res, "sihd_aih", registro, arquivos)
        opcoes = [c for c in origem_tela.descendants() if c.class_name() in ("TGroupButton", "TRadioButton")]
        alvo = [c for c in opcoes if re.search(r"SISAIH|ESTABELEC", _norm(titulo_janela(c)))]
        if not alvo:
            raise RuntimeError("opção do estabelecimento/SISAIH01 não encontrada (%s)" % [titulo_janela(c) for c in opcoes])
        eventos.append("origem: %s" % titulo_janela(alvo[0]))
        antes = {w.handle for w in janelas_sihd()}
        clicar_botao(alvo[0])
        # 2) Importação de AIH (Estabelecimento - Arquivos vindos do SISAIH-01)
        tela = None
        fim = time.time() + 30
        while time.time() < fim and tela is None:
            for w in janelas_sihd():
                if w.handle not in antes and titulo_janela(w).startswith("Importação de AIH"):
                    tela = w
            if tela is None and _user32().IsWindow(origem_tela.handle):
                for b in [c for c in origem_tela.descendants() if _norm(titulo_janela(c)) in ("OK", "AVANÇAR", "CONFIRMAR")]:
                    if b.is_enabled():
                        clicar_botao(b)
                        eventos.append("Origem dos Dados: clicou em %s" % titulo_janela(b))
                        break
            time.sleep(1)
        if tela is None:
            raise RuntimeError("a tela 'Importação de AIH' não abriu")
        time.sleep(1)
        registrar_janela(tela, pasta_res, "sihd_aih", registro, arquivos)
        botao_importar, botao_sair = botao_por_texto(tela, "Importar"), botao_por_texto(tela, "Sair")
        # 3) escolher o arquivo: a lista "Arquivos para importar" tem à direita, no alto, o botão "..."
        #    (desenhado, sem janela própria) que abre a caixa "Pasta para ler os Arquivos"
        lista = sorted([c for c in tela.descendants() if c.class_name() in ("TListBox", "ListBox", "TFileListBox")],
                       key=lambda c: c.rectangle().top)
        if not lista:
            raise RuntimeError("lista 'Arquivos para importar' não encontrada")
        from pywinauto import mouse
        tela.set_focus()
        r_l = lista[0].rectangle()
        mouse.click(coords=(r_l.right + 19, r_l.top + 11))
        escolher_arquivo_dialogo(pid, zip_aih, eventos)
        time.sleep(1.5)
        try:
            itens = lista[0].item_texts()
        except Exception:
            itens = []
        eventos.append("arquivos para importar: %s" % (", ".join(itens) or "(lista não lida)"))
        if not _user32().IsWindowEnabled(botao_importar.handle):
            raise RuntimeError("o botão Importar continua desabilitado depois de escolher o arquivo")
        clicar_botao(botao_importar)
        eventos.append("clicou em Importar")
        vistos = {w.handle for w in janelas_sihd()}
        terminou = fim_pelo_botao(botao_sair, None)
        inicio, ultimo = time.time(), 0
        while time.time() - inicio < 4 * 3600:
            checar_cancelamento()
            for w in janelas_sihd():
                if w.handle not in vistos:
                    vistos.add(w.handle)
                    registrar_janela(w, pasta_res, "sihd_aih", registro, arquivos)
            caixas = [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]
            if caixas:
                for d in caixas:
                    tratar_dialogo(d, regras, eventos)
                time.sleep(1)
                continue
            if terminou(eventos):
                break
            if time.time() - ultimo > 50:
                avisar("Importação de AIH: processando há %d min" % ((time.time() - inicio) // 60))
                ultimo = time.time()
            time.sleep(2)
        else:
            raise RuntimeError("a importação de AIH não terminou em 4 horas")
        memo = [c for c in tela.descendants() if c.class_name() in ("TMemo", "TRichEdit", "TListBox")]
        texto = "\n".join((ler_texto(m.handle, 5000) or "") for m in memo).replace("\r", "")
        nome = "sihd_importar_aih_mensagens.txt"
        with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
            f.write(texto)
        arquivos.append(nome)
        img = "sihd_importar_aih.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        if _user32().IsWindowEnabled(botao_sair.handle):
            clicar_botao(botao_sair)
            eventos.append("clicou em Sair")
        return {"mensagens": [l for l in texto.split("\n") if l.strip()][-25:]}

    resultado = operacao_sihd("importar_aih", pasta_res, corpo)
    if registro:
        nome = "sihd_importar_aih_telas_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
            f.write("\n".join(registro))
        resultado["arquivos"].append(nome)
    return resultado


# Botões desenhados (sem janela própria) da tela Gerenciar Informações: posição a partir do canto da janela
# (749 x 514), medida no print da tela. Habilitado = texto preto; desabilitado = texto cinza.
GERENCIAR_BOTOES = {"BLOQUEAR": (90, 182), "LIBERAR": (185, 182), "CANCELAR_REGISTRO": (287, 182),
                    "SALVAR": (352, 496), "CANCELAR": (449, 496), "SAIR": (703, 496)}


def _ponto_gerenciar(tela, nome):
    r = tela.rectangle()
    if abs(r.width() - 749) > 4 or abs(r.height() - 514) > 4:
        raise RuntimeError("a tela Gerenciar Informações está com outro tamanho (%dx%d): posições dos botões "
                           "não conferem" % (r.width(), r.height()))
    x, y = GERENCIAR_BOTOES[nome]
    return r.left + x, r.top + y


def botao_desenhado_habilitado(tela, nome):
    from PIL import ImageGrab
    x, y = _ponto_gerenciar(tela, nome)
    img = ImageGrab.grab(bbox=(x - 28, y - 7, x + 28, y + 7)).convert("RGB")
    escuros = sum(1 for px in img.getdata() if max(px) < 90)
    return escuros > 12


def clicar_desenhado(tela, nome):
    from pywinauto import mouse
    tela.set_focus()
    time.sleep(0.2)
    mouse.click(coords=_ponto_gerenciar(tela, nome))


def _gerenciar_ler_atual(tela):
    """Lê o registro ativo do painel de detalhes (campos com janela própria) e o estado do botão Liberar."""
    painel = [c for c in tela.descendants() if c.class_name() == "TDBCtrlPanel"]
    campos = [c for c in (painel[0].descendants() if painel else tela.descendants())
              if c.class_name() in ("TDBEdit", "Edit", "TEdit")]
    memos = sorted([c for c in (painel[0].descendants() if painel else []) if c.class_name() == "TDBMemo"],
                   key=lambda c: c.rectangle().top)
    textos = {c.handle: (ler_texto(c.handle, 3000) or "").strip() for c in campos}
    aih = next((t for t in textos.values() if re.fullmatch(r"\d{12}-\d", t)), "")
    valor = next((c for c in campos if textos[c.handle].startswith("R$")), None)
    motivo = ""
    if valor is not None:
        vr = valor.rectangle()
        cand = [c for c in campos if c.handle != valor.handle and abs(c.rectangle().top - vr.top) <= 4]
        motivo = " ".join(textos[c.handle] for c in cand)
    datas = sorted({t for t in textos.values() if re.fullmatch(r"\d{2}/\d{2}/\d{4}", t)})
    proc = next((t for t in textos.values() if re.match(r"\d{9}-\d ", t)), "")
    bloqueio = " | ".join(" ".join((ler_texto(m.handle, 3000) or "").split()) for m in memos)
    time.sleep(0.3)                                  # deixa o botão Liberar se redesenhar
    return {"aih": aih, "motivo": motivo, "bloqueio_liberacao": bloqueio.strip(" |"), "procedimento": proc,
            "datas": datas, "valor": textos[valor.handle] if valor is not None else "",
            "liberar_disponivel": botao_desenhado_habilitado(tela, "LIBERAR")}


def _gerenciar_esperar_pronta(tela, grade, eventos, limite=3 * 3600):
    """Na primeira abertura depois de importar o movimento, o SIHD mostra 'Aguarde - Verificando
    Duplicidades e Incompatibilidade...' e deixa a tela desabilitada até terminar. Espera a grade
    ficar habilitada e o botão Sair (desenhado) ficar preto, estável por 5 s."""
    inicio = time.time()
    pronta_desde, avisou = None, False
    while time.time() - inicio < limite:
        checar_cancelamento()
        try:
            ok = grade.is_enabled() and responde(tela.handle, 2000) and botao_desenhado_habilitado(tela, "SAIR")
        except Exception:
            ok = False
        if ok:
            pronta_desde = pronta_desde or time.time()
            if time.time() - pronta_desde >= 5:
                if avisou:
                    eventos.append("Gerenciar Informações liberou a tela depois de %d min de verificação"
                                   % ((time.time() - inicio) // 60))
                return
        else:
            pronta_desde = None
            if not avisou and time.time() - inicio > 3:
                eventos.append("Gerenciar Informações: SIHD verificando duplicidades/incompatibilidades; aguardando")
                avisou = True
            avisar("Gerenciar Informações: aguardando a verificação do SIHD (%d min)" % ((time.time() - inicio) // 60))
        time.sleep(2)
    raise RuntimeError("a tela Gerenciar Informações não ficou disponível em %d horas" % (limite // 3600))


def _gerenciar_percorrer(tela, eventos, ao_ler=None, limite=2000):
    """Vai ao primeiro registro e desce um a um pela grade de AIHs, chamando ao_ler(registro)."""
    grades = sorted([c for c in tela.descendants() if c.class_name() == "TDBGrid"], key=lambda c: c.rectangle().top)
    if not grades:
        raise RuntimeError("grade de AIHs não encontrada em Gerenciar Informações")
    grade = grades[0]
    _gerenciar_esperar_pronta(tela, grade, eventos)
    grade.set_focus()
    grade.type_keys("^{HOME}", set_foreground=False)
    time.sleep(1)
    lidos, anterior = [], None
    for _ in range(limite):
        checar_cancelamento()
        reg = _gerenciar_ler_atual(tela)
        if reg["aih"] and reg["aih"] == anterior:
            break
        lidos.append(reg)
        if ao_ler:
            ao_ler(reg)
        anterior = reg["aih"]
        grade.set_focus()
        grade.type_keys("{DOWN}", set_foreground=False)
        time.sleep(0.6)
    avisar("Gerenciar Informações: %d AIH(s) lidas" % len(lidos))
    return lidos


def tarefa_sihd_bloqueadas(p, pasta_res):
    """Percorre todas as AIHs em Gerenciar Informações e lista as que têm pendência (botão Liberar
    disponível), com o motivo. NÃO libera nem salva nada."""
    def corpo(pid, principal, espec, eventos, arquivos):
        tela = sihd_tela(pid, principal, espec, "CONTROLE E AVALIAÇÃO", ["GERENCIAR INFORMAÇÕES"],
                         "Gerenciar Informações", eventos)
        regs = _gerenciar_percorrer(tela, eventos)
        def situacao(r):
            t = _norm(r["bloqueio_liberacao"])
            if "LIBERAD" in t:
                return "liberada"
            if r["liberar_disponivel"] or "BLOQUEAD" in t:
                return "bloqueada"
            return ""
        for r in regs:
            r["situacao"] = situacao(r)
        pend = [r for r in regs if r["situacao"] == "bloqueada"]
        liberadas = [r for r in regs if r["situacao"] == "liberada"]
        linhas = ["AIH;internação/saída;procedimento;valor;motivo;bloqueio/liberação;liberar disponível"]
        for r in regs:
            linhas.append(";".join([r["aih"], " a ".join(r["datas"]), r["procedimento"], r["valor"], r["motivo"],
                                    r["bloqueio_liberacao"], "SIM" if r["liberar_disponivel"] else "não"]))
        nome = "sihd_aihs_gerenciar_%s.csv" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(pasta_res, nome), "w", encoding="utf-8-sig") as f:
            f.write("\n".join(linhas))
        arquivos.append(nome)
        img = "sihd_gerenciar.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        tela.close()                                   # nada foi alterado: fecha a tela
        eventos.append("%d AIH(s) lidas; %d bloqueada(s) com pendência; %d já liberada(s)"
                       % (len(regs), len(pend), len(liberadas)))
        resumo = lambda r: {"aih": r["aih"], "motivo": r["motivo"], "valor": r["valor"],
                            "bloqueio_liberacao": r["bloqueio_liberacao"].split(" Doc:")[0]}   # sem dados do autorizador
        return {"total": len(regs), "pendentes": [resumo(r) for r in pend], "liberadas": [resumo(r) for r in liberadas]}
    return operacao_sihd("bloqueadas", pasta_res, corpo)


def tarefa_sihd_liberar(p, pasta_res):
    """Libera SOMENTE as AIHs aprovadas pelo usuário (lista de números), clica em Salvar e Sair."""
    aprovadas = {re.sub(r"\D", "", a) for a in p["aihs"]}

    def corpo(pid, principal, espec, eventos, arquivos):
        tela = sihd_tela(pid, principal, espec, "CONTROLE E AVALIAÇÃO", ["GERENCIAR INFORMAÇÕES"],
                         "Gerenciar Informações", eventos)
        liberadas, nao_encontradas = [], set(aprovadas)

        def ao_ler(reg):
            num = re.sub(r"\D", "", reg["aih"])
            if num in aprovadas:
                nao_encontradas.discard(num)
                if reg["liberar_disponivel"]:
                    clicar_desenhado(tela, "LIBERAR")
                    time.sleep(1)
                    for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
                        tratar_dialogo(d, [], eventos)            # só OK; pergunta = para
                    liberadas.append(reg["aih"])
                    eventos.append("liberada: %s (%s)" % (reg["aih"], reg["motivo"] or reg["bloqueio_liberacao"]))
                else:
                    eventos.append("%s: aprovada, mas sem pendência para liberar" % reg["aih"])

        _gerenciar_percorrer(tela, eventos, ao_ler)
        if nao_encontradas:
            eventos.append("AIH(s) aprovada(s) não encontrada(s) na lista: %s" % ", ".join(sorted(nao_encontradas)))
        if liberadas:
            time.sleep(0.5)
            if not botao_desenhado_habilitado(tela, "SALVAR"):
                raise RuntimeError("o botão Salvar não habilitou depois de liberar (nada foi salvo)")
            clicar_desenhado(tela, "SALVAR")
            eventos.append("clicou em Salvar")
            acompanhar(tela, pid, [], eventos, 600, quieto=5, principal=principal)
        img = "sihd_liberar.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        tela.close()
        return {"liberadas": liberadas, "nao_encontradas": sorted(nao_encontradas)}
    return operacao_sihd("liberar", pasta_res, corpo)


def _sihd_executar_tela(pid, principal, espec, eventos, arquivos, pasta_res, menu, caminho, titulo, botao,
                        regras, prefixo, antes_de_executar=None, limite=4 * 3600):
    """Abre a tela pelo menu (respondendo às perguntas pelas regras), clica no botão de executar e espera
    o botão Sair voltar a ficar habilitado. Grava os textos da tela e clica em Sair."""
    registro = []
    for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
        tratar_dialogo(d, [], eventos)
    antes = {w.handle for w in janelas_sihd()}
    escolher_menu(espec, SIHD_MENU[_norm(menu)], caminho)
    eventos.append("menu %s > %s" % (menu, " > ".join(caminho)))
    tela, fim = None, time.time() + 60
    while time.time() < fim and tela is None:
        for w in janelas_sihd():
            if w.handle in antes:
                continue
            if w.class_name() in CLASSES_DIALOGO:
                registrar_janela(w, pasta_res, prefixo, registro, arquivos)
                tratar_dialogo(w, regras, eventos)
            elif titulo_janela(w).startswith(titulo):
                tela = w
        time.sleep(0.5)
    if tela is None:
        raise RuntimeError("a tela %r não abriu" % titulo)
    time.sleep(1)
    registrar_janela(tela, pasta_res, prefixo, registro, arquivos)
    executar_b = botao_por_texto(tela, botao)
    sair_b = None
    for nome_sair in ("Sair", "Fechar"):              # Apura Valores usa "Fechar"
        try:
            sair_b = botao_por_texto(tela, nome_sair)
            break
        except RuntimeError:
            pass
    if sair_b is None:
        raise RuntimeError("botão Sair/Fechar não encontrado em %r" % titulo_janela(tela))
    if antes_de_executar:
        antes_de_executar(tela)
    clicar_botao(executar_b)
    eventos.append("clicou em %s" % botao)
    terminou = fim_pelo_botao(sair_b, None)
    vistos = {w.handle for w in janelas_sihd()}
    inicio, ultimo = time.time(), 0
    while time.time() - inicio < limite:
        checar_cancelamento()
        for w in janelas_sihd():
            if w.handle not in vistos:
                vistos.add(w.handle)
                registrar_janela(w, pasta_res, prefixo, registro, arquivos)
        caixas = [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]
        if caixas:
            for d in caixas:
                tratar_dialogo(d, regras, eventos)
            time.sleep(1)
            continue
        if terminou(eventos):
            break
        if not _user32().IsWindow(tela.handle):
            # o Encerrar Competência fecha a tela (e o SIHD2) sozinho no fim
            eventos.append("a tela %r fechou sozinha (fim do processamento)" % titulo)
            break
        if time.time() - ultimo > 50:
            avisar("%s: processando há %d min" % (titulo, (time.time() - inicio) // 60))
            ultimo = time.time()
        time.sleep(2)
    else:
        raise RuntimeError("%s não terminou em %d horas" % (titulo, limite // 3600))
    eventos.append("%s concluído em %d min" % (titulo, (time.time() - inicio) // 60))
    textos = []
    for c in (tela.descendants() if _user32().IsWindow(tela.handle) else []):
        if c.class_name() in ("TMemo", "TRichEdit", "TListBox", "TDBMemo"):
            t = (ler_texto(c.handle, 5000) or "").replace("\r", "").strip()
            if t:
                textos.append(t)
    nome = "%s_mensagens.txt" % prefixo
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n\n".join(textos))
    arquivos.append(nome)
    img = "%s.png" % prefixo
    if _user32().IsWindow(tela.handle) and print_janela(tela, os.path.join(pasta_res, img)):
        arquivos.append(img)
    for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:
        tratar_dialogo(d, regras, eventos)
    if _user32().IsWindow(tela.handle) and _user32().IsWindowEnabled(sair_b.handle):
        clicar_botao(sair_b)
        eventos.append("clicou em %s" % titulo_janela(sair_b))
    if registro:
        nome = "%s_telas.txt" % prefixo
        with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
            f.write("\n".join(registro))
        arquivos.append(nome)
    linhas = [l for t in textos for l in t.split("\n") if l.strip()]
    time.sleep(2)
    for d in [w for w in janelas_sihd() if w.class_name() in CLASSES_DIALOGO]:   # mensagem final (ex.: SIHD2 OK)
        tratar_dialogo(d, regras, eventos)
    return linhas[-30:]


def tarefa_sihd_criticar(p, pasta_res):
    def corpo(pid, principal, espec, eventos, arquivos):
        return {"mensagens": _sihd_executar_tela(pid, principal, espec, eventos, arquivos, pasta_res, "PROCESSAMENTO",
                                                 ["CRITICAR"], "Criticar", "Criticar", [], "sihd_criticar")}
    return operacao_sihd("criticar", pasta_res, corpo)


def tarefa_sihd_apurar(p, pasta_res):
    def corpo(pid, principal, espec, eventos, arquivos):
        return {"mensagens": _sihd_executar_tela(pid, principal, espec, eventos, arquivos, pasta_res, "PROCESSAMENTO",
                                                 ["APURAR VALORES"], "Apura", "Valorar", [], "sihd_apurar")}
    return operacao_sihd("apurar", pasta_res, corpo)


def tarefa_sihd_coletar(p, pasta_res):
    """Devolve os arquivos que o Encerrar Competência deixou na pasta de saída do robô (sem processar nada)."""
    saida = os.path.join(PASTA_AGENTE, "fpo", "sihd_saida")
    candidatas = [saida] + sorted((os.path.join(PASTA_AGENTE, "fpo", d) for d in os.listdir(os.path.join(PASTA_AGENTE, "fpo"))
                                   if d.startswith("sihd_saida_")), reverse=True)
    gerados, arquivos = [], []
    for pasta in candidatas:
        if os.path.isdir(pasta) and os.listdir(pasta):
            for n in os.listdir(pasta):
                origem = os.path.join(pasta, n)
                if os.path.isfile(origem):
                    shutil.copy2(origem, os.path.join(pasta_res, n))
                    arquivos.append(n)
                    gerados.append({"arquivo": n, "bytes": os.path.getsize(origem),
                                    "data": dt.datetime.fromtimestamp(os.path.getmtime(origem)).isoformat(timespec="seconds")})
            break
    return {"ok": bool(gerados), "dados": {"gerados": gerados, "exportados": arquivos,
            "erro": None if gerados else "nenhum arquivo na pasta de saída do SIHD"}, "arquivos": arquivos}


def tarefa_sihd_encerrar(p, pasta_res):
    """Encerrar Competência (só com --confirmar no host): confirma a pergunta de encerramento, informa a pasta
    de saída nos campos da tela, Executar, espera terminar e devolve os arquivos gerados (.DTS)."""
    regras = [(r"encerr", "Sim")]

    def corpo(pid, principal, espec, eventos, arquivos):
        saida = preparar_pasta_local("sihd_saida")

        def pastas(tela):
            campos = [c for c in tela.descendants() if c.class_name() in ("TEdit", "Edit")]
            for c in campos:
                c.set_edit_text(saida)
            eventos.append("pasta de saída nos %d campo(s): %s" % (len(campos), saida))

        msgs = _sihd_executar_tela(pid, principal, espec, eventos, arquivos, pasta_res, "PROCESSAMENTO",
                                   ["ENCERRAR COMPETÊNCIA"], "Encerrar Compet", "Executar", regras, "sihd_encerrar",
                                   antes_de_executar=pastas)
        gerados = []
        for raiz, _, nomes in os.walk(saida):
            for n in nomes:
                origem = os.path.join(raiz, n)
                shutil.copy2(origem, os.path.join(pasta_res, n))
                arquivos.append(n)
                gerados.append({"arquivo": n, "bytes": os.path.getsize(origem)})
        if not gerados:
            raise RuntimeError("o encerramento terminou sem gerar arquivo em %s" % saida)
        return {"mensagens": msgs, "exportados": [g["arquivo"] for g in gerados], "gerados": gerados}
    return operacao_sihd("encerrar", pasta_res, corpo)


def tarefa_sihd_mapear_telas(p, pasta_res):
    """Abre cada tela pedida pela barra de menus do SIHD, grava imagem/controles e fecha SEM executar.
    Perguntas que aparecerem ao abrir (ex.: 'Deseja encerrar...?') são registradas e respondidas com Não."""
    pid, principal, espec = sihd_contexto()
    resumo, partes, arquivos = [], [], []
    nome = "telas_sihd_%s.txt" % dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    for n, (menu, caminho) in enumerate(p["telas"], 1):
        rotulo = " > ".join([menu] + caminho)
        try:
            antes = {w.handle for w in janelas_sihd()}
            escolher_menu(espec, SIHD_MENU[_norm(menu)], caminho)
            vistas = []
            fim = time.time() + 15
            while time.time() < fim:
                novas = [w for w in janelas_sihd() if w.handle not in antes and w.class_name() != "#32768"]
                if novas:
                    break
                time.sleep(0.5)
            for rodada in range(4):                       # tela + perguntas que ela abrir por cima
                time.sleep(1.5)
                novas = [w for w in janelas_sihd() if w.handle not in antes and w.class_name() != "#32768"
                         and w.handle not in [v.handle for v in vistas]]
                if not novas:
                    break
                for w in novas:
                    vistas.append(w)
                    img = "sihd_tela%d_%d.png" % (n, len(vistas))
                    if print_janela(w, os.path.join(pasta_res, img)):
                        arquivos.append(img)
                    texto = texto_dialogo(w) if w.class_name() in CLASSES_DIALOGO else ""
                    partes.append("#" * 100 + "\nTELA: %s  %r classe=%s ret=%s %s\n%s" % (
                        rotulo, titulo_janela(w), w.class_name(), w.rectangle(),
                        ("mensagem: %r botões: %s" % (texto, ", ".join(botoes_dialogo(w)))) if texto else "",
                        controles_da_janela(w, 6)))
                # fecha de cima para baixo: primeiro as mensagens, depois a tela
                for w in sorted(novas, key=lambda w: 0 if w.class_name() in CLASSES_DIALOGO else 1):
                    if _user32().IsWindow(w.handle) and w.is_visible():
                        fechar_sem_executar(w)
            if not vistas:
                resumo.append("%s: nenhuma tela abriu" % rotulo)
            else:
                resumo.append("%s: %s" % (rotulo, " | ".join("%r [%s]" % (titulo_janela(v) if _user32().IsWindow(v.handle)
                              else "(fechada)", v.class_name()) for v in vistas)))
        except Exception as e:
            resumo.append("%s: ERRO %s" % (rotulo, e))
        time.sleep(1)
    with open(os.path.join(pasta_res, nome), "w", encoding="utf-8") as f:
        f.write("\n".join(resumo) + "\n\n" + "\n".join(partes))
    return {"ok": True, "dados": {"resumo": resumo}, "arquivos": [nome] + arquivos}


def tarefa_sihd_competencia(p, pasta_res):
    mes, ano = int(p["mes"]), int(p["ano"])
    alvo = "%02d/%d" % (mes, ano)

    def corpo(pid, principal, espec, eventos, arquivos):
        atual = competencia_sihd(titulo_janela(principal))
        eventos.append("título do SIHD: %s" % titulo_janela(principal))
        if atual == alvo:
            eventos.append("já está em %s: nada a fazer" % alvo)
            return {"competencia": alvo, "alterada": False}
        if atual is None and sihd_menu_habilitado(espec, SIHD_MENU["PRODUÇÃO"]):
            # com a competência aberta o título perde o 'CMPT:' e os menus Produção/Processamento liberam
            eventos.append("competência já aberta (menus Produção e Processamento habilitados): nada a fazer")
            return {"competencia": alvo, "alterada": False}
        tela = sihd_tela(pid, principal, espec, "CONFIGURAÇÃO", ["ABRIR COMPET"], "Configurações - Abrir Compet", eventos)
        campos = sorted([c for c in tela.descendants() if c.class_name() in ("TDBEdit", "TEdit", "TMaskEdit", "Edit")
                         and c.is_visible()], key=lambda c: (c.rectangle().top // 10, c.rectangle().left))
        if len(campos) < 3:
            raise RuntimeError("campos da tela Abrir Competência não encontrados (%d)" % len(campos))
        processamento, competencia, descricao = campos[0], campos[1], campos[2]
        comp_tela = (ler_texto(competencia.handle) or "").strip()
        eventos.append("tela: processamento %s, competência %s" % ((ler_texto(processamento.handle) or "").strip(), comp_tela))
        if comp_tela != "%d%02d" % (ano, mes):
            raise RuntimeError("a tela sugere a competência %s, e não %d%02d; nada foi gravado" % (comp_tela, ano, mes))
        digitar(descricao, alvo)
        lido = (ler_texto(descricao.handle) or "").strip()
        if lido != alvo:
            raise RuntimeError("a descrição ficou %r (esperado %s)" % (lido, alvo))
        eventos.append("descrição: %s" % lido)
        img = "sihd_abrir_competencia.png"
        if print_janela(tela, os.path.join(pasta_res, img)):
            arquivos.append(img)
        clicar_botao(botao_por_texto(tela, "Salvar"))
        eventos.append("clicou em Salvar")
        acompanhar(tela, pid, [], eventos, 600, quieto=5, principal=principal)
        fim = time.time() + 30
        while time.time() < fim:
            if competencia_sihd(titulo_janela(principal)) == alvo or sihd_menu_habilitado(espec, SIHD_MENU["PRODUÇÃO"]):
                break
            time.sleep(1)
        if not sihd_menu_habilitado(espec, SIHD_MENU["PRODUÇÃO"]):
            raise RuntimeError("depois de salvar, o menu Produção continua desabilitado (título: %s)"
                               % titulo_janela(principal))
        eventos.append("conferido: competência aberta, menus Produção e Processamento habilitados (título: %s)"
                       % titulo_janela(principal))
        return {"competencia": alvo, "alterada": True}
    return operacao_sihd("competencia", pasta_res, corpo)


def achar_atalho(exe):
    """Atalho (.lnk) que abre o executável, na Área de Trabalho ou no menu Iniciar."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        return None
    for base in (os.path.expandvars(r"%UserProfile%\Desktop"), os.path.expandvars(r"%Public%\Desktop"),
                 os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
                 os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs")):
        for raiz, _, nomes in os.walk(base):
            for n in nomes:
                if n.lower().endswith(".lnk"):
                    try:
                        if shell.CreateShortCut(os.path.join(raiz, n)).Targetpath.lower() == exe.lower():
                            return os.path.join(raiz, n)
                    except Exception:
                        continue
    return None


def tarefa_procurar_programa(p, pasta_res):
    """Procura um programa instalado pelo nome: atalhos do menu Iniciar/Área de Trabalho (com o destino)
    e executáveis/jar nas pastas de programas."""
    preparar_pywin32()
    termo = p["termo"].lower()
    achados = []
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        shell = None
    pastas_atalhos = [os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
                      os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
                      os.path.expandvars(r"%Public%\Desktop"), os.path.expandvars(r"%UserProfile%\Desktop")]
    for base in pastas_atalhos:
        for raiz, _, nomes in os.walk(base):
            for n in nomes:
                if termo in n.lower() and n.lower().endswith(".lnk"):
                    caminho_lnk = os.path.join(raiz, n)
                    alvo = args = pasta = ""
                    if shell:
                        try:
                            at = shell.CreateShortCut(caminho_lnk)
                            alvo, args, pasta = at.Targetpath, at.Arguments, at.WorkingDirectory
                        except Exception:
                            pass
                    achados.append({"atalho": caminho_lnk, "alvo": alvo, "argumentos": args, "pasta": pasta})
    for base in (r"C:\Program Files", r"C:\Program Files (x86)", r"C:\Datasus", r"C:\DATASUS", "C:\\"):
        if not os.path.isdir(base):
            continue
        for raiz, dirs, nomes in os.walk(base):
            if raiz.count(os.sep) - base.count(os.sep) > 3 or "windows" in raiz.lower():
                dirs[:] = []
                continue
            for n in nomes:
                # o nome do arquivo OU da pasta contém o termo (ex.: pasta 'Transmissor DATASUS')
                if (termo in n.lower() or termo in raiz.lower()) and n.lower().endswith((".exe", ".jar", ".bat", ".cmd")):
                    achados.append({"arquivo": os.path.join(raiz, n)})
            if base == "C:\\":
                dirs[:] = [d for d in dirs if termo in d.lower()]
    return {"ok": True, "dados": {"achados": achados[:40]}}


# ------------------------------------------------------------------ Transmissor DATASUS (Java)

# Posições medidas no print da janela (643 x 361). Os campos do Java não existem para o Windows: o robô
# clica pela posição, digita pelo teclado e confere copiando o campo para a área de transferência.
TRANSMISSOR_POS = {"tipo": (288, 50), "competencia": (287, 77), "ibge": (287, 102), "cpf": (287, 127),
                   "senha": (287, 153), "arquivo": (308, 228), "procurar": (466, 229),
                   "testar": (87, 338), "transmitir": (222, 338), "comprovante": (406, 338), "sair": (568, 338)}
TRANSMISSOR_TAM = (643, 361)
TITULO_TRANSMISSOR = "TRANSMISSOR DATASUS"


def transmissor_janela(abrir=False, exe=None, limite=90):
    from pywinauto import Desktop
    def achar():
        for w in Desktop(backend="win32").windows(visible_only=True):
            if TITULO_TRANSMISSOR.lower() in titulo_janela(w).lower() and w.class_name() == "SunAwtFrame":
                return w
        return None
    w = achar()
    if w is None and abrir:
        alvo = achar_atalho(exe) or exe
        atual = os.getcwd()
        try:
            os.chdir(os.path.dirname(exe))
            os.startfile(alvo)
        finally:
            os.chdir(atual)
        fim = time.time() + limite
        while time.time() < fim and w is None:
            time.sleep(1)
            w = achar()
        time.sleep(3)                                  # o Java termina de desenhar
    return w


def _tx_ponto(w, nome):
    r = w.rectangle()
    if abs(r.width() - TRANSMISSOR_TAM[0]) > 6 or abs(r.height() - TRANSMISSOR_TAM[1]) > 6:
        raise RuntimeError("a janela do Transmissor está com outro tamanho (%dx%d); as posições não conferem"
                           % (r.width(), r.height()))
    x, y = TRANSMISSOR_POS[nome]
    return r.left + x, r.top + y


def _tx_clicar(w, nome):
    from pywinauto import mouse
    w.set_focus()
    time.sleep(0.3)
    mouse.click(coords=_tx_ponto(w, nome))
    time.sleep(0.4)


def _tx_teclas(texto, escapar=True):
    from pywinauto import keyboard
    if escapar:
        texto = "".join("{%s}" % c if c in "+^%~(){}[]" else c for c in texto)
    keyboard.send_keys(texto, with_spaces=True, pause=0.03)


def _tx_ler_campo(w, nome):
    """Copia o conteúdo do campo (Ctrl+A, Ctrl+C) e lê da área de transferência."""
    import win32clipboard
    try:
        win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.CloseClipboard()
    except Exception:
        pass
    _tx_clicar(w, nome)
    _tx_teclas("^a^c", escapar=False)
    time.sleep(0.4)
    return (ler_area_transferencia() or "").strip()


def _tx_preencher(w, nome, valor, conferir=True, mostrar=None):
    _tx_clicar(w, nome)
    _tx_teclas("^a{BACKSPACE}", escapar=False)
    _tx_teclas(valor)
    time.sleep(0.3)
    if conferir:
        lido = _tx_ler_campo(w, nome)
        if re.sub(r"\D", "", lido) != re.sub(r"\D", "", valor) and lido != valor:
            raise RuntimeError("o campo %s ficou %r" % (nome, mostrar or lido))


def _tx_escuros(w, caixa):
    """Quantos pixels escuros há numa região da janela (para ver se um texto apareceu)."""
    from PIL import ImageGrab
    r = w.rectangle()
    x1, y1, x2, y2 = caixa
    img = ImageGrab.grab(bbox=(r.left + x1, r.top + y1, r.left + x2, r.top + y2)).convert("RGB")
    return sum(1 for px in img.getdata() if max(px) < 90)


def tarefa_transmissor_preparar(p, pasta_res):
    """Preenche o Transmissor (tipo, competência, IBGE, CPF, senha, arquivo .DTS) e PARA: não transmite."""
    eventos, arquivos = [], []
    preparar_pywin32()
    exe = achar_executavel(p["executavel"])
    if not exe:
        raise RuntimeError("Transmissor não instalado")
    origem = caminho("entrada", *p["pasta"].split("/"))
    destino = preparar_pasta_local("transmissor")
    dts = None
    for f in os.listdir(origem):
        shutil.copy2(os.path.join(origem, f), destino)
        if f.upper().endswith(".DTS"):
            dts = os.path.join(destino, f)
    if not dts:
        raise RuntimeError("arquivo .DTS não recebido")
    eventos.append("arquivo: %s (%d bytes)" % (dts, os.path.getsize(dts)))
    w = transmissor_janela(abrir=True, exe=exe)
    if w is None:
        raise RuntimeError("a janela do Transmissor não abriu")
    eventos.append("Transmissor aberto: %s" % titulo_janela(w))
    try:
        # tipo de arquivo: com SIHD selecionado aparece ao lado a opção 'Declaração de não envio - DNE'
        tipo = p.get("tipo_arquivo", "SIHD")
        _tx_clicar(w, "tipo")
        time.sleep(0.5)
        _tx_teclas(tipo)
        time.sleep(0.3)
        _tx_teclas("{ENTER}", escapar=False)
        time.sleep(1)
        if tipo.upper() == "SIHD" and _tx_escuros(w, (340, 40, 600, 60)) < 30:
            raise RuntimeError("não consegui confirmar o tipo SIHD (a opção DNE não apareceu)")
        eventos.append("tipo de arquivo: %s" % tipo)
        _tx_preencher(w, "competencia", p["competencia"].replace("/", ""))
        eventos.append("competência: %s" % p["competencia"])
        _tx_preencher(w, "ibge", p["ibge"])
        eventos.append("IBGE: %s" % p["ibge"])
        _tx_preencher(w, "cpf", p["cpf"], conferir=False)   # campo mascarado (••••): não dá para copiar
        eventos.append("CPF: ***.%s-**" % re.sub(r"\D", "", p["cpf"])[3:6])
        _tx_preencher(w, "senha", p["senha"], conferir=False)
        eventos.append("senha digitada")
        # arquivo: tenta digitar no campo; se não aceitar, usa o botão '...' (caixa do Java: digita o caminho + Enter)
        _tx_preencher(w, "arquivo", dts, conferir=False)
        if _tx_ler_campo(w, "arquivo").lower() != dts.lower():
            antes = {x.handle for x in __import__("pywinauto").Desktop(backend="win32").windows(visible_only=True)}
            _tx_clicar(w, "procurar")
            time.sleep(2)
            _tx_teclas(dts)
            time.sleep(0.3)
            _tx_teclas("{ENTER}", escapar=False)
            time.sleep(2)
            lido = _tx_ler_campo(w, "arquivo")
            if lido.lower() != dts.lower():
                raise RuntimeError("o campo Arquivo ficou %r" % lido)
            eventos.append("arquivo escolhido pelo botão '...'")
        eventos.append("arquivo no campo: %s" % dts)
        eventos.append("PRONTO PARA TRANSMITIR: nada foi enviado")
        ok, erro = True, None
    except Exception as e:
        ok, erro = False, "%s: %s" % (type(e).__name__, e)
        eventos.append("PAROU: " + erro)
    img = "transmissor_preparado.png"
    if print_janela(w, os.path.join(pasta_res, img)):
        arquivos.append(img)
    dados = {"eventos": eventos, "dts": os.path.basename(dts)}
    if erro:
        dados["erro"] = erro
    return {"ok": ok, "dados": dados, "arquivos": arquivos}


def tarefa_transmissor_botao(p, pasta_res):
    """Clica em 'Testar Conexão' ou 'Transmitir' (o host liga a rede antes e desliga depois), espera e
    tira prints da janela e das mensagens do Java para o usuário conferir."""
    from pywinauto import Desktop
    botao = p["botao"]                                     # testar | transmitir
    w = transmissor_janela()
    if w is None:
        raise RuntimeError("o Transmissor não está aberto (rode 'robo.bat transmissor preparar')")
    eventos, arquivos = [], []
    antes = {x.handle for x in Desktop(backend="win32").windows(visible_only=True)}
    _tx_clicar(w, botao)
    eventos.append("clicou em %s" % ("Testar Conexão" if botao == "testar" else "Transmitir"))
    limite = float(p.get("limite", 60 if botao == "testar" else 1800))
    inicio, n = time.time(), 0
    mensagens = []
    while time.time() - inicio < limite:
        checar_cancelamento()
        novas = [x for x in Desktop(backend="win32").windows(visible_only=True)
                 if x.handle not in antes and x.class_name().startswith("SunAwt")]
        if novas:
            for d in novas:
                antes.add(d.handle)
                n += 1
                img = "transmissor_%s_msg%d.png" % (botao, n)
                time.sleep(1)
                if print_janela(d, os.path.join(pasta_res, img)):
                    arquivos.append(img)
                mensagens.append(titulo_janela(d) or "(mensagem sem título)")
                eventos.append("mensagem do Transmissor: %r (print %s)" % (titulo_janela(d), img))
            img = "transmissor_%s.png" % botao
            if print_janela(w, os.path.join(pasta_res, img)):
                arquivos.append(img)
            for d in novas:                               # depois do print, fecha a mensagem (OK = Enter)
                try:
                    d.set_focus()
                    time.sleep(0.3)
                    _tx_teclas("{ENTER}", escapar=False)
                    eventos.append("mensagem fechada (OK)")
                except Exception:
                    pass
            return {"ok": True, "dados": {"eventos": eventos, "mensagens": mensagens}, "arquivos": arquivos}                                         # o resultado vem numa mensagem: o usuário confere pelo print
        avisar("Transmissor (%s): aguardando há %d s" % (botao, time.time() - inicio))
        time.sleep(2)
    else:
        eventos.append("nenhuma mensagem em %d s" % limite)
    img = "transmissor_%s.png" % botao
    if print_janela(w, os.path.join(pasta_res, img)):
        arquivos.append(img)
    return {"ok": True, "dados": {"eventos": eventos, "mensagens": mensagens}, "arquivos": arquivos}


def tarefa_reiniciar(p, pasta_res):
    """Reinicia o agente (para carregar uma versão nova copiada pelo 'robo.bat preparar')."""
    iniciar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iniciar.py")
    subprocess.Popen([sys.executable, iniciar], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    return {"ok": True, "dados": {"mensagem": "reiniciando"}, "_sair": True}


def tarefa_resolucao(p, pasta_res):
    return {"ok": True, "dados": {"resolucao": garantir_resolucao(int(p.get("largura", 1366)), int(p.get("altura", 768)))}}


TAREFAS = {"ping": lambda p, pasta: tarefa_ping(p), "resolucao": tarefa_resolucao, "instalar": tarefa_instalar,
           "instalar_pacotes": tarefa_instalar_pacotes, "inspecionar": tarefa_inspecionar,
           "sisaih01_abrir": tarefa_sisaih01_abrir, "sisaih01_menus": tarefa_sisaih01_menus,
           "sisaih01_mapear_telas": tarefa_sisaih01_mapear_telas,
           "barra_menus": tarefa_barra_menus,
           "programa_inspecionar": tarefa_programa_inspecionar,
           "procurar_programa": tarefa_procurar_programa,
           "transmissor_preparar": tarefa_transmissor_preparar,
           "transmissor_botao": tarefa_transmissor_botao,
           "fpo_abrir": tarefa_fpo_abrir,
           "fpo_fechar": tarefa_fpo_fechar,
           "sihd_abrir": tarefa_sihd_abrir,
           "sihd_competencia": tarefa_sihd_competencia,
           "sihd_mapear_telas": tarefa_sihd_mapear_telas,
           "sihd_importar_cnes": tarefa_sihd_importar_cnes,
           "sihd_importar_tabelas": tarefa_sihd_importar_tabelas,
           "sihd_importar_aih": tarefa_sihd_importar_aih,
           "sihd_bloqueadas": tarefa_sihd_bloqueadas,
           "sihd_liberar": tarefa_sihd_liberar,
           "sihd_criticar": tarefa_sihd_criticar,
           "sihd_apurar": tarefa_sihd_apurar,
           "sihd_encerrar": tarefa_sihd_encerrar,
           "sihd_coletar": tarefa_sihd_coletar,
           "fpo_mapear_telas": tarefa_fpo_mapear_telas,
           "fpo_competencia": tarefa_fpo_competencia,
           "fpo_importar_sia": tarefa_fpo_importar_sia,
           "fpo_importar_cnes": tarefa_fpo_importar_cnes,
           "fpo_valores": tarefa_fpo_valores,
           "fpo_exportar": tarefa_fpo_exportar,
           "sisaih01_excluir": tarefa_sisaih01_excluir,
           "sisaih01_importar": tarefa_sisaih01_importar,
           "sisaih01_consistir": tarefa_sisaih01_consistir,
           "sisaih01_apurar": tarefa_sisaih01_apurar,
           "sisaih01_exportar": tarefa_sisaih01_exportar, "reiniciar": tarefa_reiniciar}


# ------------------------------------------------------------------ laço principal

def atualizar_ambiente():
    """Relê as variáveis de ambiente do Windows (PATH, JAVA_HOME...). O agente começa junto com o Windows;
    programas instalados depois (ex.: Java) mudam o PATH, e sem isto os programas abertos pelo agente não
    enxergariam a mudança (o Explorer enxerga, por isso o duplo clique funciona)."""
    try:
        import winreg
    except ImportError:
        return
    valores = {}
    for raiz, chave in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                        (winreg.HKEY_CURRENT_USER, r"Environment")):
        try:
            with winreg.OpenKey(raiz, chave) as k:
                i = 0
                while True:
                    try:
                        nome, valor, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    if nome.upper() == "PATH" and "PATH" in valores:
                        valores["PATH"] = valores["PATH"] + ";" + str(valor)
                    else:
                        valores[nome.upper()] = str(valor)
        except OSError:
            continue
    for nome, valor in valores.items():
        os.environ[nome] = os.path.expandvars(valor)


TAREFA_ATUAL = {"id": None}


class Cancelada(RuntimeError):
    pass


def checar_cancelamento():
    if TAREFA_ATUAL["id"] and os.path.exists(caminho("cancelar", TAREFA_ATUAL["id"])):
        raise Cancelada("tarefa cancelada pelo usuário (Ctrl+C no robô)")


def avisar(msg):
    """Andamento de tarefa longa, lido pelo host enquanto espera (andamento/<id>.progresso)."""
    if TAREFA_ATUAL["id"]:
        try:
            with open(caminho("andamento", TAREFA_ATUAL["id"] + ".progresso"), "w", encoding="utf-8") as f:
                f.write(msg)
        except OSError:
            pass


def processar(arquivo):
    andamento = caminho("andamento", os.path.basename(arquivo))
    os.replace(arquivo, andamento)
    with open(andamento, encoding="utf-8") as f:
        tarefa = json.load(f)
    id_ = tarefa["id"]
    TAREFA_ATUAL["id"] = id_
    atualizar_ambiente()
    registrar("tarefa %s (%s) iniciada" % (id_, tarefa["tipo"]))
    resposta = {"id": id_, "tipo": tarefa["tipo"], "inicio": agora(), "ok": False}
    try:
        func = TAREFAS.get(tarefa["tipo"])
        if not func:
            raise ValueError("tipo de tarefa desconhecido: %s" % tarefa["tipo"])
        resposta.update(func(tarefa.get("parametros") or {}, caminho("resultados")))
    except Exception as e:
        resposta["erro"] = "%s: %s" % (type(e).__name__, e)
        resposta["traceback"] = traceback.format_exc()
        registrar("  ERRO: %s" % resposta["erro"])
    resposta["fim"] = agora()
    sair = resposta.pop("_sair", False)
    gravar_json(caminho("resultados", id_ + ".json"), resposta)
    os.remove(andamento)
    TAREFA_ATUAL["id"] = None
    for resto in (caminho("andamento", id_ + ".progresso"), caminho("cancelar", id_)):
        try:
            os.remove(resto)
        except OSError:
            pass
    registrar("tarefa %s concluída (ok=%s)" % (id_, resposta.get("ok")))
    if sair:
        registrar("agente encerrando para reiniciar")
        os._exit(0)


def batimentos():
    """Thread separada: o batimento continua durante tarefas demoradas (instalações)."""
    while True:
        try:
            bater()
        except OSError:
            pass
        time.sleep(BATIMENTO)


_MUTEX = []


def unica_instancia():
    """Espera até 20 s: no reinício, a instância anterior ainda pode estar terminando."""
    k32 = ctypes.windll.kernel32
    for _ in range(20):
        h = k32.CreateMutexW(None, False, "AutoSUS_agente")
        if k32.GetLastError() != 183:      # ERROR_ALREADY_EXISTS
            _MUTEX.append(h)
            return True
        k32.CloseHandle(h)
        time.sleep(1)
    return False


def main():
    if not unica_instancia():
        print("o agente já está em execução")
        return
    for sub in ("fila", "andamento", "resultados", "logs"):
        os.makedirs(caminho(sub), exist_ok=True)
    registrar("agente %s iniciado (Python %s, usuário %s, pasta %s)"
              % (VERSAO, platform.python_version(), getpass.getuser(), RAIZ))
    threading.Thread(target=batimentos, daemon=True).start()
    while True:
        try:
            pendentes = sorted(f for f in os.listdir(caminho("fila")) if f.endswith(".json"))
            if pendentes:
                processar(caminho("fila", pendentes[0]))
                continue
        except OSError as e:
            registrar("pasta compartilhada indisponível: %s" % e)
            time.sleep(15)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
