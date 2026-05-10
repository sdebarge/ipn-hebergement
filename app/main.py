"""
API REST — Offre en hébergement IPN
Itinéraire du Périgord Noir · Dordogne (24)
"""
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional

from .parser import load_all_data, get_summary
from .models import Commune, EpciSummary
from .config import DATA_DIR, EPCI_CODES
from .geo import load_geojson_from_shapefile, find_shapefile

GEO_DIR  = DATA_DIR / "geo"
STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(
    title="IPN — Hébergement touristique",
    description="API de l'offre en hébergement de l'Itinéraire du Périgord Noir",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Cache ─────────────────────────────────────────────────────────────
_cache: dict = {}

def get_data() -> list[dict]:
    if "communes" not in _cache:
        _cache["communes"] = load_all_data(DATA_DIR)
    return _cache["communes"]


# ── Frontend ──────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "IPN Hébergement API — voir /docs"}


# ── Debug ─────────────────────────────────────────────────────────────
@app.get("/api/debug", include_in_schema=False)
def debug():
    shp = find_shapefile(GEO_DIR)
    try:
        data = get_data()
        data_ok = len(data)
    except Exception as e:
        data_ok = f"ERREUR : {e}"
    return {
        "communes_chargées": data_ok,
        "shapefile_détecté": str(shp) if shp else None,
        "geo_dir": str(GEO_DIR),
        "geo_dir_existe": GEO_DIR.exists(),
    }


# ── Communes ──────────────────────────────────────────────────────────
@app.get("/api/communes", response_model=list[Commune])
def communes(epci: Optional[str] = Query(None)):
    data = get_data()
    if epci:
        epci_upper = epci.upper()
        if epci_upper not in EPCI_CODES:
            raise HTTPException(400, f"EPCI inconnu. Valeurs : {', '.join(EPCI_CODES)}")
        data = [c for c in data if c["epci"] == epci_upper]
    return data


@app.get("/api/communes/{insee}", response_model=Commune)
def commune_by_insee(insee: str):
    for c in get_data():
        if c["insee"] == insee:
            return c
    raise HTTPException(404, f"Commune {insee} introuvable")


# ── Summary ───────────────────────────────────────────────────────────
@app.get("/api/summary", response_model=list[EpciSummary])
def summary():
    return get_summary(get_data())


# ── Types d'hébergement ───────────────────────────────────────────────
@app.get("/api/types")
def types_hebergement(epci: Optional[str] = None):
    data = get_data()
    if epci:
        data = [c for c in data if c["epci"] == epci.upper()]

    mapping = {
        "hotels":                ["Hôtels", "Hôtels non classés"],
        "residences_tourisme":   ["RT classés", "RT non classés"],
        "campings":              ["Campings", "Cpgs non classés"],
        "prl":                   ["PRL classés", "PRL non classés"],
        "villages_vacances":     ["VV classés", "VV non classés"],
        "gites_gdf":             ["GDF"],
        "chambres_hotes_gdf":    ["CH GDF"],
        "clevacances":           ["CLE"],
        "chambres_cle":          ["CH CLE"],
        "meublés_classés":       ["Meub. classés"],
        "meublés_nc":            ["Meub. non cl."],
        "autres_ch":             ["Autres CH"],
        "gites_etape":           ["Gîte d'étape GF"],
        "accueil_groupe":        ["Accu. grp", "Auberge collective"],
        "residences_secondaires":["Res. 2aires"],
    }

    result = {k: {"nb": 0, "lits": 0} for k in mapping}
    for c in data:
        heb = c.get("hebergement", {})
        for key, types in mapping.items():
            for t in types:
                if t in heb:
                    result[key]["nb"]   += heb[t]["nb"]
                    result[key]["lits"] += heb[t]["lits"]
    return result


# ── Top communes ──────────────────────────────────────────────────────
@app.get("/api/top/{metric}")
def top_communes(metric: str, n: int = Query(10, ge=1, le=56), epci: Optional[str] = None):
    VALID = {
        "total_marchands", "total_classes", "lits_camping", "lits_hotels",
        "lits_meublés", "lits_gdf", "lits_ch", "lits_prl",
        "lits_vv", "lits_rt", "lits_res2aires",
    }
    if metric not in VALID:
        raise HTTPException(400, f"Indicateur invalide. Valeurs : {', '.join(sorted(VALID))}")
    data = get_data()
    if epci:
        data = [c for c in data if c["epci"] == epci.upper()]
    return sorted(data, key=lambda c: c.get(metric, 0), reverse=True)[:n]


# ── GeoJSON ───────────────────────────────────────────────────────────
@app.get("/api/geojson")
def geojson():
    """
    GeoJSON des communes IPN avec données hébergement embarquées.
    Source : shapefile local dans data/geo/ (priorité) ou geo.api.gouv.fr.
    """
    data    = get_data()
    by_ins  = {c["insee"]: c for c in data}
    insees  = list(by_ins.keys())

    # ── 1. Shapefile local ────────────────────────────────────────────
    shp = find_shapefile(GEO_DIR)
    geo = None
    if shp:
        try:
            geo = load_geojson_from_shapefile(shp, insees)
        except Exception:
            geo = None  # geopandas/fiona absents → repli sur l'API nationale

    if geo is None:
        # ── 2. API nationale par département (fallback) ───────────────
        # L'API ne supporte pas les codes multiples en query string ;
        # on récupère toutes les communes du département 24 et on filtre.
        import httpx
        insee_set = set(insees)
        url = (
            "https://geo.api.gouv.fr/departements/24/communes"
            "?geometry=contour&format=geojson&fields=code,nom"
        )
        try:
            resp = httpx.get(url, timeout=20)
            resp.raise_for_status()
            raw = resp.json()
            raw["features"] = [
                f for f in raw.get("features", [])
                if f["properties"].get("code") in insee_set
            ]
            geo = raw
        except Exception as e:
            raise HTTPException(
                503,
                f"Shapefile illisible et API nationale inaccessible : {e}"
            )

    # ── Injection des données hébergement ─────────────────────────────
    for feature in geo.get("features", []):
        insee = feature["properties"].get("code")
        c = by_ins.get(insee, {})
        feature["properties"].update({
            "epci":            c.get("epci", ""),
            "epci_name":       c.get("epci_name", ""),
            "commune":         c.get("commune", feature["properties"].get("nom", "")),
            "total_marchands": c.get("total_marchands", 0),
            "total_classes":   c.get("total_classes", 0),
            "lits_camping":    c.get("lits_camping", 0),
            "lits_hotels":     c.get("lits_hotels", 0),
            "lits_meublés":    c.get("lits_meublés", 0),
            "lits_gdf":        c.get("lits_gdf", 0),
            "lits_ch":         c.get("lits_ch", 0),
            "lits_prl":        c.get("lits_prl", 0),
            "lits_vv":         c.get("lits_vv", 0),
            "lits_rt":         c.get("lits_rt", 0),
            "lits_res2aires":  c.get("lits_res2aires", 0),
            "lits_plein_air":  c.get("lits_plein_air", 0),
            "lits_labellisé":  c.get("lits_labellisé", 0),
        })

    return JSONResponse(geo)


# ── Reload (local uniquement) ─────────────────────────────────────────
@app.post("/api/reload")
def reload_data(request: Request):
    if request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Accès réservé à localhost")
    _cache.clear()
    data = get_data()
    return {"status": "ok", "communes_chargées": len(data)}
