"""Limpeza e padronizacao de dados brutos (secao 4/17 do briefing).

Cobre principalmente a correcao de campos numericos do arquivo legado
DADOS_SANTOS_ELEITORAL.csv, que foi exportado do Excel com a virgula
decimal transformada incorretamente em separador de milhar (ex.: latitude
"-239.669.088" deveria ser -23.9669088). O arquivo nacional
eleitorado_local_votacao_2024.csv nao tem esse problema (coordenadas ja
vem no formato correto, ex. "-11.5164129").
"""
from __future__ import annotations

import pandas as pd

from .utils import get_logger, parse_tse_broken_decimal

logger = get_logger(__name__)


def limpar_coordenadas_legado_santos(df: pd.DataFrame) -> pd.DataFrame:
    """Corrige NR_LATITUDE/NR_LONGITUDE do arquivo legado (exportacao Excel
    com formatacao numerica corrompida). Latitudes no Brasil tem 1-2 digitos
    inteiros (0 a -34); longitudes tem 2 digitos inteiros (28 a 74)."""
    out = df.copy()
    out["NR_LATITUDE"] = out["NR_LATITUDE"].apply(
        lambda v: parse_tse_broken_decimal(v, integer_digits=2)
    )
    out["NR_LONGITUDE"] = out["NR_LONGITUDE"].apply(
        lambda v: parse_tse_broken_decimal(v, integer_digits=2)
    )
    n_invalidas = int(out["NR_LATITUDE"].isna().sum() + out["NR_LONGITUDE"].isna().sum())
    if n_invalidas:
        logger.warning("%s coordenadas nao puderam ser corrigidas/parseadas", n_invalidas)
    return out


def padronizar_colunas_texto(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Remove espacos extras e normaliza caixa alta em colunas de texto
    (nomes de municipio, candidato, bairro etc.), evitando divergencias
    de agrupamento por diferencas triviais de formatacao."""
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().str.upper()
    return out


def remover_linhas_sem_secao_ou_zona(df: pd.DataFrame) -> pd.DataFrame:
    """Remove registros sem identificacao valida de zona/secao - nao ha
    como agregar territorialmente esses casos (secao 17: nao inventar
    valores ausentes)."""
    antes = len(df)
    out = df.dropna(subset=["NR_ZONA", "NR_SECAO"])
    removidas = antes - len(out)
    if removidas:
        logger.warning("%s linhas removidas por falta de NR_ZONA/NR_SECAO", removidas)
    return out


def coagir_numericos(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
