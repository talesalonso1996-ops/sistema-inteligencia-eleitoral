"""Diagrama de Voronoi por local de votacao (secao 8.3 do briefing).

Cada local de votacao "controla" uma area de influencia (poligono de
Voronoi), permitindo visualizar cobertura territorial e calcular
densidade eleitoral (votos por km2) mesmo quando o local nao cai
claramente dentro de um bairro delimitado.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import shapely

from .utils import get_logger, settings

logger = get_logger(__name__)


def _fronteira_municipio(malha: gpd.GeoDataFrame) -> shapely.Geometry:
    """Uniao de todos os poligonos da malha (setores ou bairros) do
    municipio - usado para recortar o diagrama de Voronoi nos limites reais."""
    return malha.union_all()


def gerar_voronoi(
    pontos: pd.DataFrame, malha_municipio: gpd.GeoDataFrame
) -> gpd.GeoDataFrame | None:
    """Gera poligonos de Voronoi para os locais de votacao (pontos com
    lat/long validas), recortados pela fronteira do municipio. Retorna
    None se houver menos de 4 pontos (Voronoi nao e informativo)."""
    validos = pontos.dropna(subset=["latitude", "longitude"]).drop_duplicates(
        subset=["latitude", "longitude"]
    )
    if len(validos) < 4:
        logger.warning("Apenas %s locais com coordenada unica - Voronoi nao gerado.", len(validos))
        return None

    crs_metros = settings()["geografia"]["crs_metros"]
    gdf_pontos = gpd.GeoDataFrame(
        validos,
        geometry=gpd.points_from_xy(validos["longitude"], validos["latitude"]),
        crs="EPSG:4674",
    ).to_crs(crs_metros)

    fronteira = malha_municipio.to_crs(crs_metros).union_all()
    multiponto = shapely.MultiPoint(list(gdf_pontos.geometry))
    colecao = shapely.voronoi_polygons(multiponto, extend_to=fronteira)
    poligonos = gpd.GeoDataFrame(geometry=list(colecao.geoms), crs=crs_metros)
    poligonos["geometry"] = poligonos.geometry.intersection(fronteira)
    poligonos = poligonos[~poligonos.geometry.is_empty]

    # Reassocia cada poligono ao ponto (local de votacao) que ele contem.
    junto = gpd.sjoin(poligonos, gdf_pontos, how="left", predicate="contains")
    junto = junto.drop(columns=["index_right"], errors="ignore")
    junto["area_km2"] = junto.to_crs(crs_metros).geometry.area / 1_000_000
    junto["densidade_votos_km2"] = (junto["votos_candidato"] / junto["area_km2"]).round(2)
    return junto.to_crs("EPSG:4674")
