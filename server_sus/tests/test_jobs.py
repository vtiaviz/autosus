import os
import time

import pytest

from nucleo import jobs as j

TAREFA = "20261107_000000_ping_abc123"


class Robo:
    """Faz o papel do robo.py: devolve o código configurado e grava as saídas que cada etapa gera."""

    def __init__(self, saida, codigos=None, demora=0.0):
        self.saida, self.codigos, self.demora, self.chamadas = saida, codigos or {}, demora, []

    def __call__(self, args, ao_ler, parar, ao_iniciar):
        self.chamadas.append(args)
        ao_ler(f"robo {' '.join(args)}")
        ao_ler(f"tarefa enviada: {TAREFA}")
        fim = time.time() + self.demora
        while time.time() < fim:
            if parar.is_set():
                return 1
            time.sleep(0.01)
        if args[:2] == ["sisaih01", "completo"]:
            (self.saida / "202609AIH2312166.Zip").write_text("x")
        if args[:2] == ["fpo", "completo"]:
            (self.saida / "Valores_202608.VTP").write_text("x")
        if args[:2] == ["sihd", "completo"]:
            (self.saida / "HM15017501N202608.DTS").write_text("x")
            (self.saida / "SIH2608.txt").write_text("x")
        return self.codigos.get(args[0], 0)


def esperar(jobs, id_, limite=10):
    fim = time.time() + limite
    while time.time() < fim:
        job = jobs.obter(id_)
        if job["situacao"] in j.FINAIS:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job não terminou: {jobs.obter(id_)['situacao']}")


@pytest.fixture
def saida(tmp_path, monkeypatch):
    pasta = tmp_path / "saida"
    pasta.mkdir()
    monkeypatch.setattr(j, "pasta_saida", lambda comp: pasta)
    return pasta


def test_comandos_seguem_o_teste_completo():
    assert j.comandos("sisaih01", "202608", {}) == [["sisaih01", "completo", "09/2026", "--confirmar"]]
    assert j.comandos("fpo", "202608", {"sem_snapshot": True}) == [["fpo", "completo", "08/2026", "--sem-snapshot"]]
    assert j.comandos("sihd", "202608", {"versao_sihd": 2340}) == [
        ["sihd", "completo", "08/2026", "--confirmar", "--auto", "--versao", "2340"]]
    assert j.comandos("sihd", "202608", {"sihd_manual": True})[0][4] == "--manual"
    assert j.comandos("restaurar:antes_sihd_202608", "202608", {})[0] == ["restaurar", "antes_sihd_202608", "--confirmar"]
    assert j.comandos("transmissor_testar", "202608", {}) == [["transmissor", "preparar", "08/2026"],
                                                              ["transmissor", "testar"]]


@pytest.mark.parametrize("etapas", [[], ["transmitir"], ["restaurar:a b"], ["restaurar:../x"]])
def test_etapas_invalidas(etapas):
    with pytest.raises(ValueError):
        j.validar_etapas(etapas)


def test_job_completo_confere_as_saidas(tmp_path, saida):
    jobs = j.Jobs(tmp_path / "jobs", executor=Robo(saida))
    job = jobs.criar("202608", ["iniciar", "sisaih01", "fpo", "sihd"], {})
    fim = esperar(jobs, job["id"])
    assert fim["situacao"] == "concluido", fim["mensagem"]
    assert [p["situacao"] for p in fim["passos"]] == ["concluido"] * 5
    assert all(c["novo"] for c in fim["conferencia"])
    texto, proximo = jobs.log(job["id"])
    assert "robo sihd completo 08/2026" in texto and proximo > 0
    assert jobs.log(job["id"], proximo) == ("", proximo)


def test_job_falha_e_para(tmp_path, saida):
    robo = Robo(saida, codigos={"fpo": 1})
    jobs = j.Jobs(tmp_path / "jobs", executor=robo)
    fim = esperar(jobs, jobs.criar("202608", ["sisaih01", "fpo", "sihd"], {})["id"])
    assert fim["situacao"] == "falhou"
    assert [p["situacao"] for p in fim["passos"]] == ["concluido", "falhou", "pendente"]
    assert [c[0] for c in robo.chamadas] == ["sisaih01", "fpo"]


def test_sihd_com_bloqueadas_aguarda_decisao(tmp_path, saida):
    jobs = j.Jobs(tmp_path / "jobs", executor=Robo(saida, codigos={"sihd": 3}))
    fim = esperar(jobs, jobs.criar("202608", ["sihd"], {"sihd_manual": True})["id"])
    assert fim["situacao"] == "aguardando_decisao"


def test_conferencia_acusa_saida_antiga(tmp_path, saida):
    antigo = saida / "Valores_202608.VTP"
    antigo.write_text("antigo")
    os.utime(antigo, (0, 0))
    jobs = j.Jobs(tmp_path / "jobs", executor=lambda args, ao_ler, parar, ao_iniciar: 0)
    fim = esperar(jobs, jobs.criar("202608", ["fpo"], {})["id"])
    assert fim["situacao"] == "falhou" and "Valores_202608.VTP" in fim["mensagem"]


def test_cancelar_job_rodando_avisa_o_agente(tmp_path, saida):
    raiz_fila = tmp_path / "_robo"
    robo = Robo(saida, demora=5)
    jobs = j.Jobs(tmp_path / "jobs", executor=robo, raiz_fila=raiz_fila)
    job = jobs.criar("202608", ["sisaih01", "fpo"], {})
    fim = time.time() + 5
    while not robo.chamadas and time.time() < fim:
        time.sleep(0.02)
    time.sleep(0.1)
    jobs.cancelar(job["id"])
    final = esperar(jobs, job["id"])
    assert final["situacao"] == "cancelado"
    assert (raiz_fila / "cancelar" / TAREFA).exists()
    assert len(robo.chamadas) == 1


def test_cancelar_na_fila(tmp_path, saida):
    robo = Robo(saida, demora=1)
    jobs = j.Jobs(tmp_path / "jobs", executor=robo)
    primeiro = jobs.criar("202608", ["fpo"], {})
    segundo = jobs.criar("202608", ["sisaih01"], {})
    assert jobs.cancelar(segundo["id"])["situacao"] == "cancelado"
    assert esperar(jobs, primeiro["id"])["situacao"] == "concluido"
    assert [c[0] for c in robo.chamadas] == ["fpo"]


def test_api_reiniciada_marca_interrompido(tmp_path):
    # um job.json que ficou "executando" quando a API caiu
    pasta = tmp_path / "jobs" / "20261107_000000_abcdef"
    pasta.mkdir(parents=True)
    (pasta / "job.json").write_text('{"id": "20261107_000000_abcdef", "situacao": "executando", "passos": []}',
                                    encoding="utf-8")
    jobs = j.Jobs(tmp_path / "jobs", executor=lambda *a: 0)
    assert jobs.obter("20261107_000000_abcdef")["situacao"] == "interrompido"


def test_verificacao_impede_o_passo(tmp_path, saida):
    robo = Robo(saida)
    jobs = j.Jobs(tmp_path / "jobs", executor=robo, verificar=lambda: "só 0.0 GB livres no disco D:\\")
    fim = esperar(jobs, jobs.criar("202608", ["fpo"], {})["id"])
    assert fim["situacao"] == "falhou" and "D:" in fim["mensagem"]
    assert robo.chamadas == []


def test_envio_exige_confirmacao():
    with pytest.raises(ValueError):
        j.comandos("transmissor_enviar", "202608", {})
    assert j.comandos("transmissor_enviar", "202608", {"confirmar_envio": True})[-1] == [
        "transmissor", "enviar", "--confirmar"]


def test_job_guarda_os_prints(tmp_path, saida):
    def robo(args, ao_ler, parar, ao_iniciar):
        ao_ler(r"  print da tela: C:\AutoSUS\server_sus\logs\tela_x_20261107.png")
        ao_ler(r"  arquivo: C:\AutoSUS\server_sus\logs\transmissor_testar_msg1.png")
        return 0
    jobs = j.Jobs(tmp_path / "jobs", executor=robo)
    fim = esperar(jobs, jobs.criar("202608", ["transmissor_testar"], {})["id"])
    assert fim["imagens"] == ["tela_x_20261107.png", "transmissor_testar_msg1.png"]
