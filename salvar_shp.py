"""
salvar_shp.py
Grava um GeoDataFrame como shapefile escrevendo os arquivos binários
(.shp, .shx, .dbf, .prj, .cpg) na mão, seguindo a especificação ESRI.

Não depende de pyogrio, fiona, pyproj nem pyshp: só pandas e shapely,
que já funcionam no PC da faculdade.
"""

import datetime
import struct
from pathlib import Path

import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient

# SIRGAS 2000 (EPSG:4674) - sistema de coordenadas da malha do IBGE
PRJ_SIRGAS2000 = (
    'GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
    'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)

TIPO_POLIGONO = 5
TIPO_NULO = 0


# ---------------------------------------------------------------- geometria
def _aneis(geom):
    """(Multi)Polygon -> lista de anéis. Padrão shapefile:
    anel externo no sentido horário, buracos no anti-horário."""
    if geom is None or geom.is_empty:
        return []
    poligonos = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    aneis = []
    for p in poligonos:
        if not isinstance(p, Polygon):
            continue
        p = orient(p, sign=-1.0)
        aneis.append(list(p.exterior.coords))
        aneis.extend(list(anel.coords) for anel in p.interiors)
    return aneis


def _conteudo_registro(geom):
    """Bytes do conteúdo de um registro do .shp (sem o cabeçalho do registro)."""
    aneis = _aneis(geom)
    if not aneis:
        return struct.pack("<i", TIPO_NULO), None

    pontos = [pt[:2] for anel in aneis for pt in anel]
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    inicios, total = [], 0
    for anel in aneis:
        inicios.append(total)
        total += len(anel)

    dados = struct.pack("<i4d2i", TIPO_POLIGONO, *bbox, len(aneis), len(pontos))
    dados += struct.pack(f"<{len(inicios)}i", *inicios)
    dados += struct.pack(f"<{2 * len(pontos)}d", *[c for p in pontos for c in p])
    return dados, bbox


def _cabecalho(tamanho_bytes, bbox):
    return (
        struct.pack(">i5ii", 9994, 0, 0, 0, 0, 0, tamanho_bytes // 2)
        + struct.pack("<ii", 1000, TIPO_POLIGONO)
        + struct.pack("<4d", *bbox)
        + struct.pack("<4d", 0, 0, 0, 0)
    )


# --------------------------------------------------------------- atributos
def _definir_campo(serie):
    nome = str(serie.name)
    if len(nome) > 10:
        raise ValueError(f"Nome de coluna com mais de 10 caracteres: {nome}")
    if pd.api.types.is_bool_dtype(serie):
        return (nome, "N", 1, 0)
    if pd.api.types.is_integer_dtype(serie):
        return (nome, "N", 18, 0)
    if pd.api.types.is_float_dtype(serie):
        return (nome, "N", 19, 6)
    tam = serie.dropna().astype(str).map(lambda s: len(s.encode("utf-8"))).max()
    tam = int(tam) if pd.notna(tam) else 1
    return (nome, "C", max(1, min(tam, 254)), 0)


def _vazio(v):
    return v is None or (not isinstance(v, str) and pd.isna(v))


def _formatar(valor, tipo, tamanho, decimais):
    if _vazio(valor):
        return b" " * tamanho
    if tipo == "C":
        b = str(valor).encode("utf-8")[:tamanho]
        b = b.decode("utf-8", errors="ignore").encode("utf-8")  # não corta acento ao meio
        return b.ljust(tamanho, b" ")
    if decimais:
        texto = f"{float(valor):.{decimais}f}"
    else:
        texto = str(int(valor))
    return texto.encode("ascii")[:tamanho].rjust(tamanho, b" ")


def _gravar_dbf(caminho, atributos):
    campos = [_definir_campo(atributos[c]) for c in atributos.columns]
    tam_registro = 1 + sum(c[2] for c in campos)
    tam_cabecalho = 32 + 32 * len(campos) + 1
    hoje = datetime.date.today()

    with open(caminho, "wb") as f:
        f.write(struct.pack("<B3BIHH20x", 0x03, hoje.year - 1900, hoje.month,
                            hoje.day, len(atributos), tam_cabecalho, tam_registro))
        for nome, tipo, tamanho, decimais in campos:
            f.write(struct.pack("<11sc4xBB14x", nome.encode("ascii"),
                                tipo.encode("ascii"), tamanho, decimais))
        f.write(b"\r")
        for linha in atributos.itertuples(index=False):
            f.write(b" ")  # registro não deletado
            for valor, (_, tipo, tamanho, decimais) in zip(linha, campos):
                f.write(_formatar(valor, tipo, tamanho, decimais))
        f.write(b"\x1a")


# -------------------------------------------------------------- principal
def salvar_shp(gdf, caminho):
    """Salva o GeoDataFrame em `caminho` (.shp) + .shx, .dbf, .prj e .cpg."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    base = caminho.with_suffix("")

    registros, caixas = [], []
    for geom in gdf.geometry:
        conteudo, bbox = _conteudo_registro(geom)
        registros.append(conteudo)
        if bbox:
            caixas.append(bbox)

    bbox_total = (
        min(c[0] for c in caixas), min(c[1] for c in caixas),
        max(c[2] for c in caixas), max(c[3] for c in caixas),
    ) if caixas else (0, 0, 0, 0)

    tam_shp = 100 + sum(8 + len(r) for r in registros)
    tam_shx = 100 + 8 * len(registros)

    with open(base.with_suffix(".shp"), "wb") as shp, \
         open(base.with_suffix(".shx"), "wb") as shx:
        shp.write(_cabecalho(tam_shp, bbox_total))
        shx.write(_cabecalho(tam_shx, bbox_total))
        posicao = 100
        for i, conteudo in enumerate(registros, start=1):
            shx.write(struct.pack(">ii", posicao // 2, len(conteudo) // 2))
            shp.write(struct.pack(">ii", i, len(conteudo) // 2))
            shp.write(conteudo)
            posicao += 8 + len(conteudo)

    atributos = gdf.drop(columns=gdf.geometry.name)
    _gravar_dbf(base.with_suffix(".dbf"), atributos)

    base.with_suffix(".prj").write_text(PRJ_SIRGAS2000, encoding="ascii")
    base.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
