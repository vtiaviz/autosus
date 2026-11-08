from pathlib import Path

import robo
from nucleo import jobs as j

LISTA = [(2510, Path("sisaih01_ver2510.exe")), (2520, Path("sisaih01_ver2520.exe")),
         (2540, Path("sisaih01_ver2540.exe")), (2541, Path("sisaih01_ver2541.exe"))]
CONHECIDAS = {"2520": "09/2026", "2540": "11/2026", "2541": "11/2026"}


def com_estado(monkeypatch, conhecidas):
    monkeypatch.setattr(robo, "ler_estado", lambda: {"instalado": {}, "apresentacao_por_versao": {"SISAIH01": conhecidas}})


def test_versao_conhecida_da_apresentacao(monkeypatch):
    com_estado(monkeypatch, CONHECIDAS)
    assert [v for v, _ in robo.versao_sisaih01_para(LISTA, "11/2026")] == [2540, 2541]
    assert [v for v, _ in robo.versao_sisaih01_para(LISTA, "09/2026")] == [2520]


def test_sem_versao_conhecida_tenta_as_nunca_abertas(monkeypatch):
    com_estado(monkeypatch, CONHECIDAS)
    assert [v for v, _ in robo.versao_sisaih01_para(LISTA, "10/2026")] == [2510]
    com_estado(monkeypatch, {**CONHECIDAS, "2510": "08/2026"})
    assert robo.versao_sisaih01_para(LISTA, "10/2026") == []


LEIAME = """
                    VERSÃO 25.41 -  NÃO OBRIGATÓRIA
        APRESENTAÇÃO PADRAO NA TELA DE LOGIN DESSA VERSÃO : 11/2026.
        COMPETÊNCIA : 10/2026
                    VERSÃO 25.31 -  OBRIGATÓRIA
        APRESENTAÇÃO PADRAO NA TELA DE LOGIN DESSA VERSÃO : 10/2026.
        COMPETÊNCIA : 09/2026
                    VERSÃO 25.30
        APRESENTAÇÃO PADRAO NA TELA DE LOGIN DESSA VERSÃO : 10/2026.
"""


def test_leiame_do_datasus():
    assert robo.ler_leiame_sisaih01(LEIAME) == {"2541": "11/2026", "2531": "10/2026", "2530": "10/2026"}


def test_atualizar_instala_o_sisaih01_da_apresentacao():
    assert j.comandos("atualizar", "202609", {}) == [["instalar", "--competencia", "09/2026"]]
    assert j.comandos("sisaih01", "202609", {})[0][:3] == ["sisaih01", "completo", "09/2026"]


def test_competencia_e_apresentacao_do_sisaih01():
    assert robo.apres_de("09/2026") == "10/2026" and robo.apres_de("12/2026") == "01/2027"
    assert robo.comp_de("10/2026") == "09/2026" and robo.comp_de("01/2027") == "12/2026"


def test_resultado_da_critica_lido_da_tela():
    texto = ("Criticar AIH\nForma de Processamento : NORMAL\nQtd total de AlHs a processar: 60\n"
             "Percentual de Rejeição: 0.00 %\n")
    assert robo.resultado_critica(texto) == {"aihs": 60, "rejeicao": 0.0, "forma": "NORMAL"}
    assert robo.resultado_critica("Percentual de Rejeição: 3,45 %")["rejeicao"] == 3.45
    assert robo.resultado_critica("tela sem o rótulo")["rejeicao"] is None
