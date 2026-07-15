"""Download/verificacao local-first dos arquivos oficiais do TSE.

Antes de baixar qualquer coisa, verifica se o arquivo ja existe localmente
(ver config/data_sources.yaml). So aciona o download quando o arquivo nao
esta presente. URLs seguem o padrao publico do repositorio de dados
abertos do TSE (cdn.tse.jus.br/estatistica/sead/odsele) e foram validadas
manualmente (secao 3 do briefing: usar apenas fontes oficiais).
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import requests

from .utils import data_sources, get_logger, resolve_path

logger = get_logger(__name__)

_TIMEOUT = 120


def _caminho_absoluto(caminho: str) -> Path:
    if len(caminho) > 1 and caminho[1] == ":":
        return Path(caminho)
    return resolve_path(caminho)


def arquivo_disponivel(nome_fonte: str) -> bool:
    fonte = data_sources()["tse"][nome_fonte]
    return _caminho_absoluto(fonte["arquivo_local"]).exists()


def garantir_arquivo(nome_fonte: str, uf: str | None = None, membro_zip: str | None = None) -> Path:
    """Garante que o arquivo de `nome_fonte` esteja disponivel localmente.
    Se ja existir, apenas retorna o caminho (nao baixa de novo). Caso
    contrario, baixa o zip oficial do TSE e extrai o CSV necessario.
    """
    fonte = data_sources()["tse"][nome_fonte]
    destino = _caminho_absoluto(fonte["arquivo_local"])
    if destino.exists():
        logger.info("Arquivo '%s' ja disponivel localmente: %s", nome_fonte, destino)
        return destino

    if "url_padrao" not in fonte:
        raise FileNotFoundError(
            f"Arquivo '{nome_fonte}' nao encontrado em {destino} e nao ha URL de "
            "download configurada em config/data_sources.yaml. Baixe manualmente "
            "no repositorio de dados abertos do TSE (https://dadosabertos.tse.jus.br)."
        )

    url = fonte["url_padrao"].format(uf=uf or "")
    logger.info("Baixando '%s' de %s", nome_fonte, url)
    destino.parent.mkdir(parents=True, exist_ok=True)
    zip_path = destino.parent / (Path(url).name)

    resp = requests.get(url, timeout=_TIMEOUT, stream=True)
    resp.raise_for_status()
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    membro = membro_zip or destino.name
    with zipfile.ZipFile(zip_path) as z:
        nomes = z.namelist()
        if membro not in nomes:
            candidatos = [n for n in nomes if n.lower().endswith(".csv")]
            if not candidatos:
                raise FileNotFoundError(f"Nenhum CSV encontrado dentro de {zip_path}")
            membro = candidatos[0]
        with z.open(membro) as src, open(destino, "wb") as dst:
            dst.write(src.read())

    logger.info("Arquivo '%s' extraido em %s", nome_fonte, destino)
    return destino
