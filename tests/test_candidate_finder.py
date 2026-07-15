from src.candidate_finder import buscar_candidaturas, eleicao_mais_recente


def test_buscar_candidaturas_encontra_multiplas_para_numero_ambiguo():
    candidaturas = buscar_candidaturas(15900)
    assert len(candidaturas) > 1, "numero 15900 deve aparecer em varios municipios de SP"
    municipios = {c.municipio for c in candidaturas}
    assert "SÃO PAULO" in municipios


def test_candidaturas_tem_campos_obrigatorios_preenchidos():
    candidaturas = buscar_candidaturas(15900)
    for c in candidaturas:
        assert c.numero == 15900
        assert c.uf == "SP"
        assert c.ano_eleicao == 2024
        assert c.total_votos >= 0
        assert c.partido_sigla


def test_eleicao_mais_recente_filtra_por_ano_e_turno_maximos():
    candidaturas = buscar_candidaturas(15900)
    mais_recentes = eleicao_mais_recente(candidaturas)
    assert mais_recentes, "deveria haver ao menos uma candidatura na eleicao mais recente"
    ano_max = max(c.ano_eleicao for c in candidaturas)
    assert all(c.ano_eleicao == ano_max for c in mais_recentes)


def test_numero_inexistente_retorna_lista_vazia():
    candidaturas = buscar_candidaturas(999999)
    assert candidaturas == []
