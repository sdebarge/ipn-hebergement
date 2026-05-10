"""
Lecture et conversion du shapefile des communes vers GeoJSON.
Fonctionne avec geopandas (Anaconda) ou fiona en fallback.

Placez dans data/geo/ les fichiers :
  communes.shp  communes.dbf  communes.shx  communes.prj
  (tous les fichiers du shapefile, même nom de base)
"""
import json
from pathlib import Path

# Noms de champ INSEE possibles selon la source du shapefile
CANDIDATE_FIELDS = [
    "CODE_INSEE", "INSEE_COM", "code_insee", "insee_com",
    "INSEE", "CODE", "code", "COMMUNE", "id",
]


def find_insee_field(gdf) -> str:
    """Détecte automatiquement le champ contenant le code INSEE."""
    for f in CANDIDATE_FIELDS:
        if f in gdf.columns:
            return f
    # Chercher un champ dont les valeurs ressemblent à des codes INSEE à 5 chiffres
    for col in gdf.columns:
        sample = gdf[col].dropna().astype(str).head(20)
        if sample.str.match(r'^\d{5}$').mean() > 0.8:
            return col
    raise ValueError(
        f"Champ INSEE introuvable. Colonnes disponibles : {list(gdf.columns)}"
    )


def load_geojson_from_shapefile(shp_path: Path, insee_codes: list[str]) -> dict:
    """
    Lit le shapefile, filtre sur les communes IPN, injecte les données,
    retourne un dict GeoJSON.
    """
    try:
        import geopandas as gpd
        return _with_geopandas(shp_path, insee_codes)
    except ImportError:
        try:
            import fiona
            return _with_fiona(shp_path, insee_codes)
        except ImportError:
            raise RuntimeError(
                "geopandas ou fiona requis pour lire le shapefile.\n"
                "Installez avec : pip install geopandas  ou  pip install fiona"
            )


def _with_geopandas(shp_path: Path, insee_codes: list[str]) -> dict:
    import geopandas as gpd

    gdf = gpd.read_file(shp_path)

    # Reprojection en WGS84 si nécessaire
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    insee_field = find_insee_field(gdf)

    # Normaliser : ajouter "24" si les codes sont à 3 chiffres
    gdf[insee_field] = gdf[insee_field].astype(str).str.strip()
    if gdf[insee_field].str.len().median() == 3:
        gdf[insee_field] = "24" + gdf[insee_field].str.zfill(3)

    # Filtrer sur les communes IPN
    gdf_ipn = gdf[gdf[insee_field].isin(insee_codes)].copy()
    gdf_ipn = gdf_ipn.rename(columns={insee_field: "code"})

    # Simplifier légèrement les géométries (réduit le poids)
    gdf_ipn["geometry"] = gdf_ipn["geometry"].simplify(0.0001)

    return json.loads(gdf_ipn[["code", "geometry"]].to_json())


def _with_fiona(shp_path: Path, insee_codes: list[str]) -> dict:
    import fiona
    from shapely.geometry import shape, mapping
    from shapely.ops import transform
    import pyproj

    features = []
    insee_set = set(insee_codes)

    with fiona.open(shp_path) as src:
        # Transformation de projection si nécessaire
        if src.crs and "4326" not in str(src.crs.get("init", "")):
            try:
                project = pyproj.Transformer.from_crs(
                    src.crs_wkt, "EPSG:4326", always_xy=True
                ).transform
            except Exception:
                project = None
        else:
            project = None

        # Détecter le champ INSEE
        sample_props = next(iter(src))["properties"]
        insee_field = next(
            (f for f in CANDIDATE_FIELDS if f in sample_props), None
        )
        if not insee_field:
            raise ValueError(f"Champ INSEE introuvable. Champs : {list(sample_props.keys())}")

        src.seek(0)
        for feat in src:
            code = str(feat["properties"].get(insee_field, "")).strip()
            if len(code) == 3:
                code = "24" + code.zfill(3)
            if code not in insee_set:
                continue
            geom = shape(feat["geometry"])
            if project:
                geom = transform(project, geom)
            features.append({
                "type": "Feature",
                "properties": {"code": code},
                "geometry": mapping(geom),
            })

    return {"type": "FeatureCollection", "features": features}


def find_shapefile(geo_dir: Path) -> Path | None:
    """Cherche un .shp dans data/geo/"""
    if not geo_dir.exists():
        return None
    shp_files = list(geo_dir.glob("*.shp"))
    if not shp_files:
        return None
    # Préférer un fichier dont le nom contient "commune"
    for shp in shp_files:
        if "commune" in shp.stem.lower():
            return shp
    return shp_files[0]
