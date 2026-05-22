"""
API REST — Offre en hébergement IPN
Intense Périgord Noir · Dordogne (24)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional
import json

from .parser import load_all_data, get_summary
from .models import Commune, EpciSummary
from .config import DATA_DIR, EPCI_CODES, INSEE_CORRECTIONS
from .geo import load_geojson_from_shapefile, find_shapefile

GEO_DIR    = DATA_DIR / "geo"
STATIC_DIR = Path(__file__).parent.parent / "static"
STATIC_GEO = STATIC_DIR / "communes_ipn.geojson"   # GeoJSON embarqué

_cache: dict = {}


def _load_geojson():
    """Charge le GeoJSON : shapefile local > fichier statique embarqué > API externe."""
    data   = _cache["communes"]
    insees = [c["insee"] for c in data]

    # 1. Shapefile local dans data/geo/
    shp = find_shapefile(GEO_DIR)
    if shp:
        try:
            geo = load_geojson_from_shapefile(shp, insees)
            print(f"✓ GeoJSON depuis shapefile : {shp.name}")
            return geo
        except Exception as e:
            print(f"⚠ Shapefile erreur : {e}")

    # 2. Fichier statique embarqué dans static/communes_ipn.geojson
    if STATIC_GEO.exists():
        geo = json.loads(STATIC_GEO.read_text(encoding="utf-8"))
        print(f"✓ GeoJSON depuis fichier statique ({len(geo.get('features',[]))} features)")
        return geo

    # 3. API nationale (tentative)
    try:
        import httpx
        codes  = ",".join(insees)
        url    = f"https://geo.api.gouv.fr/communes?code={codes}&geometry=contour&format=geojson&fields=code,nom"
        resp   = httpx.get(url, timeout=20)
        resp.raise_for_status()
        geo    = resp.json()
        print(f"✓ GeoJSON depuis geo.api.gouv.fr ({len(geo.get('features',[]))} features)")
        return geo
    except Exception as e:
        print(f"⚠ API externe indisponible : {e}")
        return None


def _build_epci_boundaries(communes_geo: dict, communes_data: list[dict]) -> dict | None:
    """
    Calcule les contours fusionnés des 3 EPCI via shapely unary_union.
    Topologiquement correct : pas de bords internes parasites entre communes
    d'un même EPCI. Bien plus fiable que turf.union côté navigateur.
    """
    try:
        from shapely.geometry import shape, mapping
        from shapely.ops import unary_union
    except ImportError:
        print("⚠ shapely non installé : limites EPCI non précalculées")
        return None

    by_ins = {c["insee"]: c["epci"] for c in communes_data}
    groups: dict[str, list] = {}
    for f in communes_geo.get("features", []):
        code = f["properties"].get("code", "")
        code = INSEE_CORRECTIONS.get(code, code)
        epci = by_ins.get(code)
        if not epci:
            continue
        try:
            groups.setdefault(epci, []).append(shape(f["geometry"]))
        except Exception as e:
            print(f"⚠ géométrie illisible pour {code} : {e}")

    # Fermeture morphologique : buffer(+ε) puis buffer(-ε) soude les slivers
    # de quelques mètres entre polygones voisins (artefacts de la simplification
    # du shapefile faite indépendamment par commune). ε en degrés WGS84.
    # 0.00015° ≈ 17 m au 45e parallèle — supérieur à la tolérance de simplify(0.0001)
    # de fix_communes.py, suffisant pour gommer les décalages entre communes voisines,
    # sans déformer visiblement le contour externe.
    CLOSING_TOL = 0.00015

    features = []
    for epci, geoms in groups.items():
        try:
            cleaned = [g.buffer(0) for g in geoms]               # invalidités → propre
            inflated = unary_union([g.buffer(CLOSING_TOL) for g in cleaned])
            merged = inflated.buffer(-CLOSING_TOL)               # contour externe préservé
            features.append({
                "type": "Feature",
                "properties": {"epci": epci},
                "geometry": mapping(merged),
            })
        except Exception as e:
            print(f"⚠ union impossible pour {epci} : {e}")

    print(f"✓ Contours EPCI précalculés : {[f['properties']['epci'] for f in features]}")
    return {"type": "FeatureCollection", "features": features}


@asynccontextmanager
async def lifespan(app: FastAPI):
    _cache["communes"] = load_all_data(DATA_DIR)
    print(f"✓ {len(_cache['communes'])} communes chargées")
    _cache["geojson_raw"] = _load_geojson()
    if _cache["geojson_raw"]:
        _cache["epci_boundaries"] = _build_epci_boundaries(
            _cache["geojson_raw"], _cache["communes"]
        )
    yield


app = FastAPI(
    title="IPN — Hébergement touristique",
    description="Intense Périgord Noir · API offre hébergement",
    version="1.3.1",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET","POST"], allow_headers=["*"])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_data():
    if "communes" not in _cache:
        _cache["communes"] = load_all_data(DATA_DIR)
    return _cache["communes"]


@app.get("/", include_in_schema=False)
def root():
    index = STATIC_DIR / "index.html"
    return FileResponse(index) if index.exists() else {"message": "IPN API — voir /docs"}


@app.get("/api/debug", include_in_schema=False)
def debug():
    geo = _cache.get("geojson_raw")
    epci_b = _cache.get("epci_boundaries")
    shp = find_shapefile(GEO_DIR)
    return {
        "communes": len(_cache.get("communes", [])),
        "geojson_ok": bool(geo),
        "geojson_features": len(geo.get("features", [])) if geo else 0,
        "epci_boundaries_ok": bool(epci_b),
        "epci_boundaries_count": len(epci_b.get("features", [])) if epci_b else 0,
        "source": "shapefile" if shp else ("statique" if STATIC_GEO.exists() else "api"),
        "shapefile": str(shp) if shp else None,
    }


@app.get("/api/communes", response_model=list[Commune])
def communes(epci: Optional[str] = Query(None)):
    data = get_data()
    if epci:
        eu = epci.upper()
        if eu not in EPCI_CODES:
            raise HTTPException(400, f"EPCI inconnu : {', '.join(EPCI_CODES)}")
        data = [c for c in data if c["epci"] == eu]
    return data


@app.get("/api/communes/{insee}", response_model=Commune)
def commune_by_insee(insee: str):
    for c in get_data():
        if c["insee"] == insee:
            return c
    raise HTTPException(404, f"Commune {insee} introuvable")


@app.get("/api/summary", response_model=list[EpciSummary])
def summary():
    return get_summary(get_data())


@app.get("/api/types")
def types_hebergement(epci: Optional[str] = None):
    data = get_data()
    if epci:
        data = [c for c in data if c["epci"] == epci.upper()]
    mapping = {
        "hotels":["Hôtels","Hôtels non classés"], "residences_tourisme":["RT classés","RT non classés"],
        "campings":["Campings","Cpgs non classés"], "prl":["PRL classés","PRL non classés"],
        "villages_vacances":["VV classés","VV non classés"], "gites_gdf":["GDF"],
        "chambres_hotes_gdf":["CH GDF"], "clevacances":["CLE"], "chambres_cle":["CH CLE"],
        "meublés_classés":["Meub. classés"], "meublés_nc":["Meub. non cl."],
        "autres_ch":["Autres CH"], "gites_etape":["Gîte d'étape GF"],
        "accueil_groupe":["Accu. grp","Auberge collective"], "residences_secondaires":["Res. 2aires"],
    }
    result = {k: {"nb":0,"lits":0} for k in mapping}
    for c in data:
        for key, types in mapping.items():
            for t in types:
                if t in c.get("hebergement", {}):
                    result[key]["nb"]   += c["hebergement"][t]["nb"]
                    result[key]["lits"] += c["hebergement"][t]["lits"]
    return result


@app.get("/api/top/{metric}")
def top_communes(metric: str, n: int = Query(10, ge=1), epci: Optional[str] = None):
    VALID = {
        "total_marchands", "total_classes",
        "lits_hotels", "lits_rt", "lits_camping", "lits_prl", "lits_vv",
        "lits_gdf", "lits_ch", "lits_cle",
        "lits_meublés", "lits_etape_grp", "lits_res2aires",
        "lits_plein_air", "lits_labellisé",
    }
    if metric not in VALID:
        raise HTTPException(400, f"Indicateur invalide : {', '.join(sorted(VALID))}")
    data = get_data()
    if epci:
        eu = epci.upper()
        if eu not in EPCI_CODES:
            raise HTTPException(400, f"EPCI inconnu : {', '.join(EPCI_CODES)}")
        data = [c for c in data if c["epci"] == eu]
    n = min(n, len(data))
    return sorted(data, key=lambda c: c.get(metric, 0), reverse=True)[:n]


@app.get("/api/geojson")
def geojson():
    geo = _cache.get("geojson_raw")
    if not geo:
        raise HTTPException(503, "GeoJSON non disponible — placez un shapefile dans data/geo/")

    by_ins = {c["insee"]: c for c in get_data()}
    features_out = []
    for f in geo.get("features", []):
        code = f["properties"].get("code", "")
        # Normalisation défensive : si la geojson contient encore d'anciens codes,
        # on les fait correspondre aux nouveaux codes utilisés par le parser.
        code = INSEE_CORRECTIONS.get(code, code)
        f["properties"]["code"] = code
        c = by_ins.get(code, {})
        f["properties"].update({
            "epci": c.get("epci",""), "epci_name": c.get("epci_name",""),
            "commune": c.get("commune",""),
            "total_marchands": c.get("total_marchands",0), "total_classes": c.get("total_classes",0),
            "lits_camping": c.get("lits_camping",0), "lits_hotels": c.get("lits_hotels",0),
            "lits_meublés": c.get("lits_meublés",0), "lits_gdf": c.get("lits_gdf",0),
            "lits_ch": c.get("lits_ch",0), "lits_prl": c.get("lits_prl",0),
            "lits_vv": c.get("lits_vv",0), "lits_rt": c.get("lits_rt",0),
            "lits_cle": c.get("lits_cle",0),
            "lits_etape_grp": c.get("lits_etape_grp",0),
            "lits_plein_air": c.get("lits_plein_air",0),
            "lits_labellisé": c.get("lits_labellisé",0),
            "lits_res2aires": c.get("lits_res2aires",0),
        })
        features_out.append(f)

    return JSONResponse({"type":"FeatureCollection","features":features_out})


@app.get("/api/epci-geojson")
def epci_geojson():
    """
    Contours fusionnés des 3 EPCI (limites externes uniquement, sans frontières
    communales internes). Précalculés au démarrage via shapely unary_union.
    """
    boundaries = _cache.get("epci_boundaries")
    if not boundaries:
        raise HTTPException(503, "Contours EPCI non disponibles — vérifiez l'installation de shapely")
    return JSONResponse(boundaries)


@app.post("/api/reload")
def reload_data():
    # Charge dans des variables temporaires : si l'une des étapes échoue,
    # le cache existant reste intact (pas d'API en panne pendant un mauvais rechargement).
    try:
        new_communes = load_all_data(DATA_DIR)
    except Exception as e:
        raise HTTPException(500, f"Échec du chargement Excel : {e}")
    _cache["communes"] = new_communes
    try:
        _cache["geojson_raw"] = _load_geojson()
        if _cache["geojson_raw"]:
            _cache["epci_boundaries"] = _build_epci_boundaries(
                _cache["geojson_raw"], new_communes
            )
    except Exception as e:
        # Les données restent rechargées même si la geojson échoue.
        return {"status": "partial", "communes": len(new_communes), "geojson_error": str(e)}
    return {"status": "ok", "communes": len(new_communes)}
