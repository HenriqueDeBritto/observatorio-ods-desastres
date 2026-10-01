"""
01_baixar_malha_ibge.py
Baixa a malha municipal do IBGE (via geobr/IPEA) e salva como shapefile.

Fonte: IBGE - Malha Municipal, distribuída pelo pacote geobr (IPEA).
Ano: 2024 (bate 100% com os códigos da planilha DTB).

Dependências:
    pip install geobr geopandas pyarrow requests
(não usa pyogrio, pyproj nem pyshp: o shapefile é gravado pelo salvar_shp.py)
"""

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import requests

# Sem o pyproj o geopandas avisa que não conseguiu registrar o CRS.
# Não faz diferença aqui: o .prj é gravado à mão em salvar_shp.py
warnings.filterwarnings("ignore", message="Cannot set the CRS")

ANO = 2024
SIMPLIFICADA = True  # malha simplificada: bem mais leve pro Tableau

# Pasta do projeto (caminho fixo: no Spyder o __file__ nem sempre existe)
PASTA = Path(r"C:\Users\Aluno\Documents\supermapa")
sys.path.insert(0, str(PASTA))  # pra achar o salvar_shp.py

from salvar_shp import salvar_shp  # noqa: E402

PASTA_SAIDA = PASTA / "dados" / "malha_ibge"
ARQ_SAIDA = PASTA_SAIDA / f"malha_municipios_{ANO}.shp"
ARQ_PARQUET = PASTA_SAIDA / f"malha_municipios_{ANO}.parquet"  # usado pelo script 02

# Link direto do arquivo que o geobr usa (plano B caso a API do GitHub falhe)
URL_DIRETA = (
    "https://github.com/ipea/geobr_prep_data/releases/latest/download/"
    f"municipalities_{ANO}{'_simplified' if SIMPLIFICADA else ''}.parquet"
)

# Nomes do geobr -> nomes com até 10 caracteres (limite do .shp)
RENOMEAR = {
    "code_muni": "cod_mun",
    "name_muni": "nome_mun",
    "code_state": "cod_uf",
    "abbrev_state": "sigla_uf",
    "name_state": "nome_uf",
    "code_region": "cod_reg",
    "name_region": "nome_reg",
}


def baixar_via_geobr() -> gpd.GeoDataFrame:
    import geobr
    print(f"Baixando malha {ANO} pelo geobr...")
    return geobr.read_municipality(code_muni="all", year=ANO, simplified=SIMPLIFICADA)


def baixar_direto() -> gpd.GeoDataFrame:
    print("Baixando direto do repositório do IPEA...")
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    tmp = PASTA_SAIDA / "_malha_tmp.parquet"
    r = requests.get(URL_DIRETA, timeout=300)
    r.raise_for_status()
    tmp.write_bytes(r.content)
    gdf = gpd.read_parquet(tmp)
    tmp.unlink()
    return gdf


def main():
    try:
        malha = baixar_via_geobr()
    except Exception as erro:
        print(f"geobr falhou ({type(erro).__name__}): {erro}")
        malha = baixar_direto()

    malha = malha.rename(columns=RENOMEAR)[list(RENOMEAR.values()) + ["geometry"]]

    # geobr entrega códigos como float (1100015.0) -> inteiro
    for col in ["cod_mun", "cod_uf", "cod_reg"]:
        malha[col] = malha[col].astype("int64")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    malha.to_parquet(ARQ_PARQUET)
    salvar_shp(malha, ARQ_SAIDA)

    print(f"OK: {len(malha)} polígonos")
    print(f"Salvo em: {ARQ_SAIDA}")
    print(f"Cópia para o script 02: {ARQ_PARQUET}")


if __name__ == "__main__":
    main()
