import os
import time

import pytest
from fastapi.testclient import TestClient

H = {"Authorization": "Bearer segredo-de-teste"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVER_SUS_JOBS", str(tmp_path / "jobs"))
    monkeypatch.setenv("SERVER_SUS_TOKEN", "segredo-de-teste")
    from api import app as modulo
    from nucleo import arquivos
    monkeypatch.setattr(modulo, "variavel_env", lambda nome, padrao="": os.environ.get(nome, padrao))
    monkeypatch.setattr(arquivos, "pasta_entrada", lambda: tmp_path / "entrada")
    return TestClient(modulo.app), modulo


def test_saude_sem_token(cliente):
    c, _ = cliente
    assert c.get("/saude").json()["ok"] is True


@pytest.mark.parametrize("cab", [{}, {"Authorization": "Bearer errado"}])
def test_rotas_exigem_token(cliente, cab):
    c, _ = cliente
    assert c.get("/jobs", headers=cab).status_code == 401
    r = c.post("/competencias/202608/arquivos", headers=cab, files={"arquivo": ("FORNEC_202608.ZIP", b"x")})
    assert r.status_code == 401


def test_upload_e_situacao(cliente):
    c, _ = cliente
    r = c.post("/competencias/202608/arquivos", headers=H, files={"arquivo": ("FORNEC_202608.ZIP", b"x")})
    assert r.status_code == 201 and r.json()["situacao"] == "novo"
    r = c.post("/competencias/202608/arquivos", headers=H, files={"arquivo": ("FORNEC_202608.ZIP", b"x")},
               data={"sha256": r.json()["sha256"]})
    assert r.json()["situacao"] == "ja_existe"
    r = c.post("/competencias/202608/arquivos", headers=H, files={"arquivo": ("FORNEC_202607.ZIP", b"x")})
    assert r.status_code == 422
    s = c.get("/competencias/202608/arquivos", headers=H).json()
    assert s["apresentacao"] == "202609" and not s["completo"]
    assert c.get("/competencias/202613/arquivos", headers=H).status_code == 422


def test_jobs_pela_api(cliente, tmp_path):
    c, modulo = cliente
    from nucleo.jobs import Jobs
    chamadas = []

    def robo(args, ao_ler, parar, ao_iniciar):
        chamadas.append(args)
        ao_ler("ok")
        return 0
    modulo.jobs = Jobs(tmp_path / "jobs2", executor=robo)
    assert c.post("/jobs", headers=H, json={"competencia": "202608", "etapas": ["transmitir"]}).status_code == 422
    r = c.post("/jobs", headers=H, json={"competencia": "202608", "etapas": ["iniciar", "transmissor_testar"]})
    assert r.status_code == 201
    id_ = r.json()["id"]
    for _ in range(100):
        job = c.get(f"/jobs/{id_}", headers=H).json()
        if job["situacao"] == "concluido":
            break
        time.sleep(0.05)
    assert job["situacao"] == "concluido"
    assert chamadas[-1] == ["transmissor", "testar"]
    assert c.get(f"/jobs/{id_}/log", headers=H).json()["texto"].count("ok") == 4
    assert c.get("/jobs", headers=H).json()[0]["id"] == id_
    assert c.get("/jobs/nao_existe", headers=H).status_code == 404
