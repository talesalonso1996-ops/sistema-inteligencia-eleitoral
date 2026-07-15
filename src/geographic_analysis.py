"""Analise geografica: local de votacao -> setor censitario / bairro
(secao 8 e 9 do briefing).

Fluxo:
1. Coordenadas de cada local de votacao vem do arquivo nacional
   eleitorado_local_votacao_2024.csv (TSE) - chave (CD_MUNICIPIO, NR_ZONA,
   NR_LOCAL_VOTACAO).
2. Os votos por local (agregados a partir de votos_da_candidatura /
   votos_da_disputa) sao unidos a essas coordenadas.
3. Um join espacial (ponto-em-poligono) com as malhas IBGE CD2022
   (SP_setores_CD2022.gpkg / SP_bairros_CD2022.gpkg) atribui setor
   censitario e bairro oficiais a cada local de votacao.

O codigo de municipio do TSE (CD_MUNICIPIO) e diferente do codigo IBGE
(CD_MUN) usado nas malhas - a compatibilizacao e feita pelo NOME do
municipio (maiusculo, sem acento), unico dentro de uma UF.
"""
from __future__ import annotations

import unicodedata

import duckdb
import geopandas as gpd
import pandas as pd

from .candidate_finder import Candidatura
from .utils import cache_key, data_sources, get_logger, read_cache, resolve_path, settings, write_cache

logger = get_logger(__name__)


def _normalizar_nome(texto: str) -> str:
    """Remove acentos e normaliza caixa - usado para casar nomes de
    municipio entre TSE e IBGE, que usam grafias/acentuacao diferentes."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sem_acento.strip().upper()


def uf_tem_malha_completa(uf: str) -> bool:
    """Verifica se ha malha geografica (setores + bairros) disponivel para
    a UF - secao 19: informar limitacao em vez de simular dados."""
    ufs = settings()["geografia"]["ufs_com_malha_completa"]
    return uf.upper() in [u.upper() for u in ufs]


def _caminho(caminho: str) -> str:
    path = caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))
    return path.replace("\\", "/")


def carregar_coordenadas_locais(candidatura: Candidatura) -> pd.DataFrame:
    """Carrega lat/long + bairro (auto-declarado pelo TSE) de cada local de
    votacao do municipio da candidatura, a partir do arquivo nacional de
    eleitorado por local de votacao."""
    key = cache_key("coordenadas_locais", candidatura.codigo_municipio_tse)
    cached = read_cache("geographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["tse"]["eleitorado_local_votacao"]
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    sql = f"""
        SELECT
            NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO, NM_LOCAL_VOTACAO, NM_BAIRRO,
            TRY_CAST(NR_LATITUDE AS DOUBLE) AS latitude,
            TRY_CAST(NR_LONGITUDE AS DOUBLE) AS longitude
        FROM read_csv('{_caminho(fonte["arquivo_local"])}', delim='{fonte["separador"]}',
            header=true, quote='"', encoding='{fonte["encoding"]}', ignore_errors=true)
        WHERE CD_MUNICIPIO = {candidatura.codigo_municipio_tse}
    """
    df = con.execute(sql).fetchdf()
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-34, 6) & df["longitude"].between(-74, -28)]
    write_cache("geographic_analysis", key, df)
    return df


def juntar_votos_com_coordenadas(
    votos_candidatura: pd.DataFrame, coordenadas: pd.DataFrame
) -> pd.DataFrame:
    """Agrega votos do candidato por local de votacao e junta com as
    coordenadas correspondentes (chave: NR_ZONA + NR_LOCAL_VOTACAO)."""
    votos_local = (
        votos_candidatura.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO"], as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "votos_candidato"})
    )
    out = votos_local.merge(coordenadas, on=["NR_ZONA", "NR_LOCAL_VOTACAO"], how="left")
    sem_coordenada = int(out["latitude"].isna().sum())
    if sem_coordenada:
        logger.warning(
            "%s de %s locais de votacao sem coordenada disponivel", sem_coordenada, len(out)
        )
    return out


def carregar_malha(nome_fonte: str, municipio: str) -> gpd.GeoDataFrame | None:
    fonte = data_sources()["ibge"][nome_fonte]
    path = _caminho(fonte["arquivo_local"])
    from pathlib import Path

    if not Path(path).exists():
        logger.warning("Malha '%s' nao encontrada em %s", nome_fonte, path)
        return None
    municipio_norm = _normalizar_nome(municipio)
    gdf = None
    try:
        # OGR SQL faz comparacao literal (sensivel a acento/caixa); tenta
        # primeiro pelo nome como esta na malha (Title Case, com acento).
        gdf = gpd.read_file(path, where=f"UPPER(NM_MUN) = '{municipio_norm}'")
    except Exception:
        gdf = None
    if gdf is None or gdf.empty:
        # Fallback: carrega tudo e filtra em pandas normalizando acento/caixa
        # dos dois lados (nome do TSE pode vir grafado de forma diferente).
        gdf = gpd.read_file(path)
        gdf = gdf[gdf["NM_MUN"].apply(_normalizar_nome) == municipio_norm]
    if gdf.empty:
        logger.warning(
            "Nenhum poligono encontrado para o municipio '%s' (normalizado: '%s') em %s",
            municipio, municipio_norm, nome_fonte,
        )
        return None
    return gdf


def carregar_fronteira_municipio(candidatura: Candidatura) -> gpd.GeoDataFrame | None:
    """Retorna uma malha poligonal cobrindo o municipio inteiro (bairros,
    ou setores censitarios como alternativa), usada para recortar o
    diagrama de Voronoi nos limites reais do municipio."""
    malha = carregar_malha("bairros_sp", candidatura.municipio)
    if malha is None:
        malha = carregar_malha("setores_censitarios_sp", candidatura.municipio)
    return malha


def atribuir_setor_e_bairro(
    pontos: pd.DataFrame, candidatura: Candidatura
) -> tuple[pd.DataFrame, list[str]]:
    """Faz o join espacial ponto-em-poligono dos locais de votacao com as
    malhas de setor censitario e bairro (CD2022). Retorna o dataframe
    enriquecido e uma lista de avisos/limitacoes encontradas."""
    avisos: list[str] = []
    if not uf_tem_malha_completa(candidatura.uf):
        avisos.append(
            f"Malha geografica (setor censitario/bairro) nao configurada para a UF "
            f"'{candidatura.uf}'. Analises espaciais nao serao geradas."
        )
        return pontos, avisos

    validos = pontos.dropna(subset=["latitude", "longitude"])
    if validos.empty:
        avisos.append("Nenhum local de votacao com coordenadas validas para join espacial.")
        return pontos, avisos

    gdf_pontos = gpd.GeoDataFrame(
        validos,
        geometry=gpd.points_from_xy(validos["longitude"], validos["latitude"]),
        crs="EPSG:4674",
    )

    setores = carregar_malha("setores_censitarios_sp", candidatura.municipio)
    if setores is not None:
        setores = setores.to_crs(gdf_pontos.crs)
        gdf_pontos = gpd.sjoin(
            gdf_pontos, setores[["CD_SETOR", "CD_BAIRRO", "NM_DIST", "geometry"]],
            how="left", predicate="within",
        ).drop(columns=["index_right"], errors="ignore")
    else:
        avisos.append(
            f"Malha de setores censitarios sem poligonos para o municipio "
            f"'{candidatura.municipio}' - setor censitario nao sera atribuido."
        )
        gdf_pontos["CD_SETOR"] = None
        gdf_pontos["NM_DIST"] = None

    bairros = carregar_malha("bairros_sp", candidatura.municipio)
    if bairros is not None:
        bairros = bairros.to_crs(gdf_pontos.crs)
        gdf_pontos = gpd.sjoin(
            gdf_pontos, bairros[["NM_BAIRRO", "geometry"]].rename(columns={"NM_BAIRRO": "NM_BAIRRO_IBGE"}),
            how="left", predicate="within",
        ).drop(columns=["index_right"], errors="ignore")
    else:
        # Alguns municipios (ex.: capital de SP) nao possuem "bairro" na
        # malha oficial CD2022 - usa "distrito" (NM_DIST, ja atribuido via
        # setores) como nivel territorial alternativo, mantendo o dado real
        # do IBGE em vez de reportar apenas uma limitacao.
        avisos.append(
            f"Malha de bairros sem poligonos oficiais para o municipio "
            f"'{candidatura.municipio}' - usando 'distrito' (IBGE) como nivel "
            "territorial alternativo, alem do bairro auto-declarado pelo TSE."
        )
        gdf_pontos["NM_BAIRRO_IBGE"] = None

    resultado = pd.DataFrame(gdf_pontos.drop(columns="geometry"))
    faltantes = int(resultado["CD_SETOR"].isna().sum()) if "CD_SETOR" in resultado else len(resultado)
    if faltantes:
        avisos.append(
            f"{faltantes} de {len(resultado)} locais de votacao nao caíram dentro de "
            "nenhum poligono de setor censitario (possivel erro de coordenada ou "
            "poligono desatualizado)."
        )
    return resultado, avisos


def total_votos_validos_por_territorio(
    votos_disputa: pd.DataFrame, pontos_com_territorio: pd.DataFrame, nivel: str
) -> pd.DataFrame:
    """Soma os votos validos de TODOS os candidatos da disputa por
    territorio geografico (bairro/distrito), reaproveitando o crosswalk
    NR_ZONA+NR_LOCAL_VOTACAO -> territorio ja calculado para o
    candidato-alvo (os mesmos locais de votacao fisicos servem todos os
    candidatos da disputa). Usado para calcular o percentual real de
    votos validos do candidato em cada territorio (nao apenas a
    participacao dentro dos proprios votos do candidato)."""
    from .vote_filtering import votos_validos

    crosswalk = pontos_com_territorio[["NR_ZONA", "NR_LOCAL_VOTACAO", nivel]].drop_duplicates()
    validos = votos_validos(votos_disputa)
    com_territorio = validos.merge(crosswalk, on=["NR_ZONA", "NR_LOCAL_VOTACAO"], how="inner")
    return (
        com_territorio.groupby(nivel, as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "votos_validos_territorio"})
    )


def agregar_votos_por_bairro(pontos_com_bairro: pd.DataFrame, coluna_bairro: str = "NM_BAIRRO_IBGE") -> pd.DataFrame:
    """Agrega votos do candidato por territorio de bairro. Ordem de
    preferencia: bairro oficial IBGE (join espacial) -> distrito IBGE
    (quando o municipio nao tem malha de bairro, ex.: capital de SP) ->
    bairro auto-declarado pelo TSE (menos confiavel, mas melhor que nada)."""
    df = pontos_com_bairro.copy()
    if coluna_bairro not in df.columns:
        coluna_bairro = "NM_BAIRRO"
    candidatos_fallback = [coluna_bairro, "NM_DIST", "NM_BAIRRO"]
    df["_bairro_final"] = None
    for col in candidatos_fallback:
        if col in df.columns:
            df["_bairro_final"] = df["_bairro_final"].fillna(df[col])
    df["_bairro_final"] = df["_bairro_final"].fillna("BAIRRO NAO IDENTIFICADO")

    agregado = df.groupby("_bairro_final", as_index=False).agg(
        votos_candidato=("votos_candidato", "sum"),
        n_locais_votacao=("NR_LOCAL_VOTACAO", "nunique"),
    ).rename(columns={"_bairro_final": "bairro"})
    total = agregado["votos_candidato"].sum()
    agregado["pct_do_total_candidato"] = (
        100 * agregado["votos_candidato"] / total
    ).round(2) if total else 0.0
    return agregado.sort_values("votos_candidato", ascending=False).reset_index(drop=True)
