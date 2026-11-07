import io

import pytest

from nucleo import arquivos as a


def test_apresentacao_vira_o_ano():
    assert a.apresentacao("202608") == "202609"
    assert a.apresentacao("202612") == "202701"


@pytest.mark.parametrize("nome,esperado", [
    ("SIHD2_2350.exe", "programas/SIHD2_2350.exe"),
    ("sisaih01_ver2541.exe", "programas/sisaih01_ver2541.exe"),
    ("BDSIA202608a.exe", "2026-08/SIA/BDSIA202608a.exe"),
    ("FORNEC_202608.ZIP", "2026-08/SIH/FORNEC_202608.ZIP"),
    ("TXTPROC_150175_202608.ZIP", "2026-08/SIH/TXTPROC_150175_202608.ZIP"),
    ("202609_SISAIH01_2312166.txt", "2026-08/SIH/202609_SISAIH01_2312166.txt"),
])
def test_destino(tmp_path, nome, esperado):
    assert a.destino(nome, "202608", tmp_path) == tmp_path / esperado


@pytest.mark.parametrize("nome", ["FORNEC_202607.ZIP", "202608_SISAIH01_2312166.txt", "virus.exe",
                                  "..\\SIHD2_2350.exe", "sub/FORNEC_202608.ZIP"])
def test_destino_recusa(tmp_path, nome):
    with pytest.raises(a.ArquivoRecusado):
        a.destino(nome, "202608", tmp_path)


def test_gravar_novo_igual_e_substituido(tmp_path):
    r = a.gravar("FORNEC_202608.ZIP", "202608", io.BytesIO(b"um"), None, tmp_path)
    assert r["situacao"] == "novo"
    r = a.gravar("FORNEC_202608.ZIP", "202608", io.BytesIO(b"um"), r["sha256"], tmp_path)
    assert r["situacao"] == "ja_existe"
    r = a.gravar("FORNEC_202608.ZIP", "202608", io.BytesIO(b"dois"), None, tmp_path)
    assert r["situacao"] == "substituido"
    pasta = tmp_path / "2026-08" / "SIH"
    assert (pasta / "FORNEC_202608.ZIP").read_bytes() == b"dois"
    assert len(list(pasta.glob("FORNEC_202608_anterior_*.ZIP"))) == 1
    assert not list(pasta.glob("*.recebendo"))


def test_gravar_sha_errado_nao_deixa_arquivo(tmp_path):
    with pytest.raises(a.ArquivoRecusado):
        a.gravar("FORNEC_202608.ZIP", "202608", io.BytesIO(b"um"), "0" * 64, tmp_path)
    assert not list(tmp_path.rglob("FORNEC*"))


def test_situacao_entrada(tmp_path):
    a.gravar("FORNEC_202608.ZIP", "202608", io.BytesIO(b"x"), None, tmp_path)
    a.gravar("SIHD2_2350.exe", "202608", io.BytesIO(b"x"), None, tmp_path)
    s = a.situacao_entrada("202608", tmp_path)
    assert not s["completo"]
    itens = {i["item"]: i["arquivo"] for i in s["itens"]}
    assert itens["Fornecedores (CNES)"]["nome"] == "FORNEC_202608.ZIP"
    assert itens["BDSIA (SIA)"] is None
    assert [p["nome"] for p in s["programas"]] == ["SIHD2_2350.exe"]
