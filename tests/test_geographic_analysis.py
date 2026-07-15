import pytest

from src.candidate_finder import votos_da_candidatura
from src.geographic_analysis import (
    agregar_votos_por_bairro,
    atribuir_setor_e_bairro,
    carregar_coordenadas_locais,
    juntar_votos_com_coordenadas,
    uf_tem_malha_completa,
)
from src.utils import parse_tse_broken_decimal


def test_parse_tse_broken_decimal_latitude_santos():
    # Exemplo real do arquivo legado: latitude de Santos exportada com a
    # virgula decimal corrompida pelo Excel.
    assert parse_tse_broken_decimal("-239.669.088", integer_digits=2) == pytest.approx(-23.9669088)


def test_parse_tse_broken_decimal_longitude_santos():
    assert parse_tse_broken_decimal("-463.529.031", integer_digits=2) == pytest.approx(-46.3529031)


def test_parse_tse_broken_decimal_valor_ausente():
    assert parse_tse_broken_decimal("-1", integer_digits=2) is None
    assert parse_tse_broken_decimal(None, integer_digits=2) is None


def test_uf_com_malha_completa_sp():
    assert uf_tem_malha_completa("SP") is True


def test_uf_sem_malha_completa_retorna_false_e_nao_quebra():
    assert uf_tem_malha_completa("XX") is False


def test_join_espacial_atribui_setor_para_maioria_dos_locais(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro(pontos, candidatura_sp)

    com_setor = enriquecido["CD_SETOR"].notna().sum()
    assert com_setor / len(enriquecido) > 0.9, "mais de 90% dos locais devem cair em algum setor"


def test_agregar_votos_por_bairro_soma_bate(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, _ = atribuir_setor_e_bairro(pontos, candidatura_sp)
    bairros_agg = agregar_votos_por_bairro(enriquecido)

    assert int(bairros_agg["votos_candidato"].sum()) == int(enriquecido["votos_candidato"].sum())
