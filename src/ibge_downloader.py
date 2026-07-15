"""Download/verificacao local-first dos arquivos oficiais do IBGE
(Censo Demografico 2022 - Agregados por Setores Censitarios) e das malhas
territoriais (setores/bairros CD2022).

Mesma logica local-first do tse_downloader: nunca baixa de novo um arquivo
ja presente. URLs sao do FTP publico do IBGE (ftp.ibge.gov.br), validadas
manualmente (secao 3 do briefing).
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import requests

from .utils import data_sources, get_logger, resolve_path

logger = get_logger(__name__)

_TIMEOUT = 180


def _caminho_absoluto(caminho: str) -> Path:
    if len(caminho) > 1 and caminho[1] == ":":
        return Path(caminho)
    return resolve_path(caminho)


def arquivo_disponivel(nome_fonte: str) -> bool:
    fonte = data_sources()["ibge"][nome_fonte]
    return _caminho_absoluto(fonte["arquivo_local"]).exists()


def _baixar(url: str, destino: Path) -> None:
    logger.info("Baixando %s -> %s", url, destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=_TIMEOUT, stream=True)
    resp.raise_for_status()
    with open(destino, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)


def garantir_arquivo(nome_fonte: str) -> Path:
    """Garante que o arquivo IBGE de `nome_fonte` esteja disponivel
    localmente (zip original OU csv/gpkg ja extraido). Baixa apenas se
    nenhuma das duas formas estiver presente."""
    fonte = data_sources()["ibge"][nome_fonte]
    destino = _caminho_absoluto(fonte["arquivo_local"])
    if destino.exists():
        return destino

    if "url_padrao" not in fonte:
        raise FileNotFoundError(
            f"Arquivo IBGE '{nome_fonte}' nao encontrado em {destino} e nao ha "
            "URL de download configurada. Baixe manualmente em "
            "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
        )

    zip_path = destino.parent / Path(fonte["url_padrao"]).name
    _baixar(fonte["url_padrao"], zip_path)

    if destino.suffix.lower() == ".zip":
        return zip_path

    with zipfile.ZipFile(zip_path) as z:
        candidatos = [n for n in z.namelist() if n.lower().endswith(destino.suffix.lower())]
        if not candidatos:
            raise FileNotFoundError(f"Nenhum arquivo {destino.suffix} encontrado em {zip_path}")
        with z.open(candidatos[0]) as src, open(destino, "wb") as dst:
            dst.write(src.read())
    return destino


def garantir_dicionario(nome_fonte: str) -> Path | None:
    """Baixa o dicionario de variaveis associado a uma fonte IBGE, se
    configurado e ainda nao presente. Retorna None se nao houver dicionario
    documentado (nesse caso a fonte NAO deve ser usada automaticamente,
    conforme secao 4 do briefing)."""
    fonte = data_sources()["ibge"][nome_fonte]
    if "dicionario" not in fonte:
        return None
    destino = _caminho_absoluto(fonte["dicionario"])
    if destino.exists():
        return destino
    if "url_dicionario" not in fonte:
        return None
    _baixar(fonte["url_dicionario"], destino)
    return destino
