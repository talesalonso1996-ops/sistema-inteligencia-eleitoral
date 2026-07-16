from conftest import VARIAVEIS_DEMOGRAFICAS

from src.maslow_analysis import gerar_analise_maslow, gerar_narrativa_maslow, mapear_coeficientes_para_tiers
from src.regression_models import regressao_logistica_bom_desempenho
from src.utils import indicators_config


def test_config_todas_variaveis_classificadas():
    """Toda variavel de VARIAVEIS_DEMOGRAFICAS deve aparecer em pelo menos
    um lugar do config (mapeada num tier, pendente de decisao, ou sem
    correspondencia teorica) - nunca invisivel/esquecida."""
    cfg = indicators_config()["piramide_maslow"]
    classificadas = set()
    for tier in cfg["tiers"].values():
        classificadas |= {v["nome"] for v in tier.get("variaveis", [])}
    classificadas |= {v["nome"] for v in cfg.get("variaveis_pendentes_decisao", [])}
    classificadas |= {v["nome"] for v in cfg.get("variaveis_sem_correspondencia_teorica", [])}

    faltando = set(VARIAVEIS_DEMOGRAFICAS) - classificadas
    assert not faltando, f"variaveis sem classificacao no config: {faltando}"


def test_tiers_sem_proxy_tem_motivo_documentado():
    cfg = indicators_config()["piramide_maslow"]
    sem_proxy = [t for t in cfg["tiers"].values() if t["status"] == "sem_proxy"]
    assert len(sem_proxy) >= 1
    assert all(t.get("motivo_sem_proxy", "").strip() for t in sem_proxy)


def test_renda_mapeada_em_fisiologico_e_seguranca():
    cfg = indicators_config()["piramide_maslow"]
    tiers_com_renda = {
        tier_key for tier_key, tier in cfg["tiers"].items()
        if any(v["nome"] == "renda_media_responsavel" for v in tier.get("variaveis", []))
    }
    assert {"fisiologico", "seguranca"}.issubset(tiers_com_renda)


def test_raca_mapeada_em_seguranca_com_rationale():
    """Decisao explicita do cliente: pct_preta_parda mapeada em Seguranca,
    com justificativa documentada (nao um mapeamento silencioso)."""
    cfg = indicators_config()["piramide_maslow"]
    variaveis_seguranca = {v["nome"]: v for v in cfg["tiers"]["seguranca"]["variaveis"]}
    assert "pct_preta_parda" in variaveis_seguranca
    assert variaveis_seguranca["pct_preta_parda"]["rationale"].strip()


def test_gerar_analise_maslow_sem_nenhum_modelo():
    resultado = gerar_analise_maslow(None, None, None)
    assert resultado.fonte_efeito == "indisponivel"
    assert resultado.tiers_mapeados.empty
    assert resultado.narrativa  # deve ter uma mensagem explicando a indisponibilidade


def test_gerar_analise_maslow_usa_logistico_quando_disponivel(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo is not None, "modelo logistico deveria convergir com os dados reais de teste"
    resultado = gerar_analise_maslow(modelo)
    assert resultado.fonte_efeito == "regressao_logistica"
    assert not resultado.tiers_mapeados.empty


def test_narrativa_conta_bate_com_tiers_mapeados(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    resultado = gerar_analise_maslow(modelo)
    n_tiers_mapeados = resultado.tiers_mapeados.query("status == 'mapeado'")["tier"].nunique()
    assert len(resultado.narrativa) == n_tiers_mapeados


def test_mapear_coeficientes_marca_variavel_sem_correspondencia(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    tiers_df = mapear_coeficientes_para_tiers(modelo.coeficientes, "odds_ratio", "odds_ratio")
    linha_idade = tiers_df[tiers_df["variavel"] == "idade_media_aprox"]
    assert not linha_idade.empty
    assert (linha_idade["status"] == "sem_correspondencia").all()
    assert linha_idade["tier"].isna().all()


def test_gerar_narrativa_maslow_vazia_quando_sem_tiers_mapeados():
    import pandas as pd

    vazio = pd.DataFrame(columns=["tier", "label", "status", "interpretacao"])
    assert gerar_narrativa_maslow(vazio, ["fisiologico", "seguranca"]) == []
