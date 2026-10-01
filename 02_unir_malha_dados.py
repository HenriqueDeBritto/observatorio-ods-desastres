"""
02_unir_malha_dados.py
Une a malha municipal do IBGE (esqueleto) com a planilha DTB (dados)
pelo código IBGE e gera um shapefile pronto para o Tableau.

Rodar depois do 01_baixar_malha_ibge.py.

Dependências:
    pip install geopandas pyarrow pandas openpyxl
(não usa pyogrio, pyproj nem pyshp: o shapefile é gravado pelo salvar_shp.py)
"""

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore", message="Cannot set the CRS")

ANO = 2024
# Pasta do projeto (caminho fixo: no Spyder o __file__ nem sempre existe)
PASTA = Path(r"C:\Users\Aluno\Documents\supermapa")
sys.path.insert(0, str(PASTA))  # pra achar o salvar_shp.py

from salvar_shp import salvar_shp  # noqa: E402

ARQ_MALHA = PASTA / "dados" / "malha_ibge" / f"malha_municipios_{ANO}.parquet"
ARQ_EXCEL = PASTA / "DTB_Brasil_Municipios_biomas_siafi_censo.xlsx"
PASTA_SAIDA = PASTA / "saida"
ARQ_SAIDA = PASTA_SAIDA / "mapa_municipios_dados.shp"
ARQ_DICIONARIO = PASTA_SAIDA / "dicionario_colunas.csv"

# Polígonos a remover do mapa:
# 4300001 / 4300002 = Lagoa Mirim e Lagoa dos Patos (áreas operacionais, não são municípios)
# 5101837 = Boa Esperança do Norte (MT) - sem dados do Censo 2022
EXCLUIR = [4300001, 4300002, 5101837]

# Colunas da planilha que não vão pro mapa
DESCARTAR = ["bioma_3"]  # 100% vazia

# Nome original -> nome do .shp (máx. 10 caracteres)
RENOMEAR = {
    "Cod_Mun": "cod_mun",
    "Cod_SIAFI": "cod_siafi",
    "Municipio": "municipio",
    "UF": "uf",
    "num_uf": "num_uf",
    "municipiouf": "mun_uf",
    "nome_UF": "nome_uf",
    "cod_meso_regiao": "cod_meso",
    "meso_regiao": "meso",
    "cod_regiao_geo_imediata": "cod_rgi",
    "regiao_geo_imediata": "rgi",
    "populacao_residente_2022": "pop_2022",
    "pop_estimada_dou_2026": "pop_2026",
    "area_km2": "area_km2",
    "densidade_hab_km2": "dens_hab",
    "domicilios_ocupados": "dom_ocup",
    "moradores_dom_ocupados": "mor_dom",
    "media_moradores_dom": "med_mor",
    "semi_arido": "semiarido",
    "amazonia_legal": "amaz_legal",
    "municipio_costeiro": "costeiro",
    "bioma1_predominante": "bioma1",
    "bioma_2": "bioma2",
    "sub_regiao_SP": "subreg_sp",
    "Regiao_Turistica": "reg_tur",
    "Categoria_Turistica_SP": "cat_tur_sp",
    "Categoria_SP": "cat_sp",
}

# Colunas 0/1 que o Excel lê como float -> inteiro
INTEIROS = ["cod_siafi", "pop_2022", "dom_ocup", "mor_dom",
            "semiarido", "amaz_legal", "costeiro"]


def main():
    # 1) Esqueleto: só código, região e geometria
    #    (nome, UF etc. vêm da planilha, pra não duplicar colunas)
    malha = gpd.read_parquet(ARQ_MALHA)[["cod_mun", "nome_reg", "geometry"]]
    malha = malha.rename(columns={"nome_reg": "regiao"})
    malha["cod_mun"] = malha["cod_mun"].astype("int64")

    # 2) Dados
    dados = pd.read_excel(ARQ_EXCEL, sheet_name="dtb_municipios")
    dados = dados.drop(columns=DESCARTAR).rename(columns=RENOMEAR)
    dados["cod_mun"] = dados["cod_mun"].astype("int64")

    faltando = set(RENOMEAR.values()) - set(dados.columns) - {c for c in DESCARTAR}
    assert not faltando, f"Colunas esperadas não encontradas: {faltando}"
    assert dados["cod_mun"].is_unique, "Código de município repetido na planilha"
    assert malha["cod_mun"].is_unique, "Código de município repetido na malha"

    # 3) Exclusões
    malha = malha[~malha["cod_mun"].isin(EXCLUIR)]
    dados = dados[~dados["cod_mun"].isin(EXCLUIR)]

    # 4) Conferência antes do join
    so_malha = set(malha["cod_mun"]) - set(dados["cod_mun"])
    so_dados = set(dados["cod_mun"]) - set(malha["cod_mun"])
    print(f"Malha: {len(malha)} | Planilha: {len(dados)}")
    print(f"Só na malha (vão ficar sem dados): {sorted(so_malha) or 'nenhum'}")
    print(f"Só na planilha (vão ficar fora do mapa): {sorted(so_dados) or 'nenhum'}")

    # 5) Left join a partir do mapa (o mapa é o esqueleto)
    mapa = malha.merge(dados, on="cod_mun", how="left", validate="one_to_one")

    for col in INTEIROS:
        mapa[col] = mapa[col].astype("Int64")

    # Ordem: chave e identificação primeiro, geometria por último
    ordem = ["cod_mun", "municipio", "uf", "regiao"]
    ordem += [c for c in mapa.columns if c not in ordem + ["geometry"]]
    mapa = mapa[ordem + ["geometry"]]

    # 6) Exportar
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    salvar_shp(mapa, ARQ_SAIDA)

    dic = pd.DataFrame(
        [{"coluna_shp": v, "coluna_original": k} for k, v in RENOMEAR.items()]
        + [{"coluna_shp": "regiao", "coluna_original": "name_region (malha IBGE)"}]
    )
    dic.to_csv(ARQ_DICIONARIO, index=False, encoding="utf-8-sig")

    print(f"OK: {len(mapa)} municípios | {mapa.shape[1] - 1} colunas de dados")
    print(f"Shapefile: {ARQ_SAIDA}")
    print(f"Dicionário de colunas: {ARQ_DICIONARIO}")


if __name__ == "__main__":
    main()
