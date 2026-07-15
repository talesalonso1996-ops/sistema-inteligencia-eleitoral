# Sistema de Inteligencia Eleitoral

Sistema que, a partir apenas do **numero de um candidato**, localiza a
candidatura nas Eleicoes Municipais 2024 (SP), cruza dados oficiais do TSE
e do IBGE (Censo Demografico 2022) e gera analises de resultado, concorrencia,
territorio, demografia, estatistica e um relatorio executivo (HTML/PDF/Excel).

Todos os dados usados sao oficiais e locais - nenhum numero e inventado ou
estimado sem origem documentada (ver `config/data_sources.yaml`).

## Como rodar

```powershell
cd sistema_inteligencia_eleitoral
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Abra `http://localhost:8501`, digite o numero do candidato e escolha a
candidatura correta na lista (o mesmo numero pode pertencer a candidatos
de cargos/municipios diferentes).

## Fontes de dados

Todas documentadas em `config/data_sources.yaml` (fonte, ano, arquivo,
metodologia). Resumo:

| Fonte | Conteudo | Uso |
|---|---|---|
| TSE - `consulta_cand_2024_SP.csv` | Identidade, partido, coligacao, situacao, resultado final | Identificacao do candidato |
| TSE - `votacao_secao_2024_SP.csv` (~2,7 GB) | Votos por candidato/secao | Metricas, ranking, territorio |
| TSE - `eleitorado_local_votacao_2024.csv` | Coordenadas de cada local de votacao (Brasil) | Mapas, join espacial |
| TSE - `detalhe_votacao_secao_2024_SP.csv` | Comparecimento/abstencao/brancos/nulos por secao | Indice de performance |
| IBGE - `SP_setores_CD2022.gpkg` / `SP_bairros_CD2022.gpkg` | Malhas de setor censitario e bairro | Geografia, Voronoi |
| IBGE - Agregados por Setores Censitarios 2022 (demografia, cor/raca, alfabetizacao, renda do responsavel) | Perfil demografico por setor | Demografia, correlacao, regressao, clustering |

O arquivo de 2,7 GB nunca e carregado inteiro em memoria: todas as consultas
usam DuckDB com projecao de colunas e filtros aplicados durante a leitura.
Resultados de consultas repetidas sao cacheados em `data/cache/` (parquet).

### Limitacoes conhecidas

- **Malha geografica**: setor censitario e bairro (IBGE CD2022) so estao
  configurados para SP (`config/settings.yaml -> geografia.ufs_com_malha_completa`).
  Para outras UFs o sistema informa a limitacao em vez de simular dados.
- **Bairro na capital de SP**: a malha oficial de "bairro" do IBGE nao cobre
  o municipio de Sao Paulo (usa "distrito" oficial como nivel alternativo).
- **Perfil demografico por local de votacao**: aproximado pelo setor
  censitario onde o local fica fisicamente localizado - nao captura
  eleitores que se deslocam de outros setores.
- **Regressao/correlacao por territorio**: dados agregados (ecological
  regression) - nao permitem inferencia sobre o comportamento de eleitores
  individuais.
- **Indice de performance (0-100)**: mede forca *relativa* entre os
  territorios do proprio candidato (normalizacao min-max), nao dominio
  eleitoral absoluto. Pesos ajustaveis em `config/indicators.yaml`.
- Variaveis genericas de caracteristicas do domicilio ("dom1/dom2/dom3")
  foram deliberadamente excluidas por falta de identificacao clara
  (ver `variaveis_excluidas_automaticamente` em `config/data_sources.yaml`).

## Arquitetura

```
config/            YAML: fontes de dados, configuracoes gerais, pesos do indice
src/
  candidate_finder.py     Busca/desambiguacao de candidaturas (DuckDB)
  tse_downloader.py       Download local-first dos arquivos do TSE
  ibge_downloader.py      Download local-first dos arquivos do IBGE
  data_cleaning.py        Correcao de coordenadas/numeros corrompidos
  data_validation.py      Validacoes de qualidade (nao interrompem o pipeline)
  electoral_metrics.py    Resultado geral e desempenho territorial
  competitor_analysis.py  Ranking de concorrentes, zonas de disputa
  geographic_analysis.py  Join espacial local de votacao -> setor/bairro
  voronoi_analysis.py     Diagrama de Voronoi (area de influencia)
  demographic_analysis.py Cruzamento com o Censo 2022 (IBGE)
  correlation_analysis.py Correlacao votos x demografia
  regression_models.py    Regressao linear (OLS)
  clustering.py           Segmentacao de territorios (K-Means)
  potential_index.py      Indice de Performance Eleitoral (0-100)
  charts.py               Graficos Plotly (paleta fixa e acessivel)
  maps.py                 Mapas Folium (pontos, coropletico, Voronoi)
  report_generator.py     Relatorio executivo HTML + PDF
  excel_exporter.py       Exportacao Excel multi-abas
app.py              Interface Streamlit (abas: Resumo, Concorrentes,
                    Territorio, Geografia, Demografia, Estatistica, Relatorio)
tests/              Testes automatizados (pytest)
```

## Testes

```powershell
.venv\Scripts\python -m pytest tests -v
```
