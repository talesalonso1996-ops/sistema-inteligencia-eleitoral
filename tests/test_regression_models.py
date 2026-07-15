from conftest import VARIAVEIS_DEMOGRAFICAS

from src.regression_models import regressao_logistica_bom_desempenho


def test_regressao_logistica_pseudo_r2_entre_0_e_1(base_territorio_sp):
    modelo, issues = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert 0 <= modelo.pseudo_r2_mcfadden <= 1


def test_regressao_logistica_odds_ratio_sempre_positivo(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert (modelo.coeficientes["odds_ratio"] > 0).all()


def test_regressao_logistica_matriz_confusao_soma_bate(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo.matriz_confusao.values.sum() == modelo.n_positivos + modelo.n_negativos


def test_regressao_logistica_classes_aproximadamente_balanceadas(base_territorio_sp):
    """O limiar default (mediana do proprio candidato) deve gerar uma
    divisao proxima de 50/50 entre territorios de boa/fraca votacao."""
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    total = modelo.n_positivos + modelo.n_negativos
    assert abs(modelo.n_positivos - modelo.n_negativos) <= max(2, total * 0.1)


def test_regressao_logistica_amostra_insuficiente_retorna_none():
    import pandas as pd

    df_pequeno = pd.DataFrame({
        "pct_votos_validos_territorio": [1.0, 2.0, 3.0],
        "renda_media_responsavel": [100, 200, 300],
    })
    modelo, issues = regressao_logistica_bom_desempenho(
        df_pequeno, "pct_votos_validos_territorio", ["renda_media_responsavel"]
    )
    assert modelo is None
    assert len(issues) > 0
