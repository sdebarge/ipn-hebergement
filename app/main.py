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
import httpx
import json

from .parser import load_all_data, get_summary
from .models import Commune, EpciSummary
from .config import DATA_DIR, EPCI_CODES
from .geo import load_geojson_from_shapefile, find_shapefile

GEO_DIR   = DATA_DIR / "geo"
STATIC_DIR = Path(__file__).parent.parent / "static"

# ── Cache partagé ─────────────────────────────────────────────────────
_cache: dict = {}


async def _prefetch_geojson():
    """Pré-charge les contours communaux depuis geo.api.gouv.fr au démarrage."""
    try:
        data   = _cache.get("communes") or load_all_data(DATA_DIR)
        insees = ",".join(c["insee"] for c in data)
        url    = (
            f"https://geo.api.gouv.fr/communes"
            f"?code={insees}&geometry=contour&format=geojson&fields=code,nom"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            geo = resp.json()
            _cache["geojson_raw"] = geo
            print(f"✓ GeoJSON pré-chargé : {len(geo.get('features', []))} communes")
    except Exception as e:
        print(f"⚠ GeoJSON non disponible au démarrage : {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chargement des données + GeoJSON au démarrage
    _cache["communes"] = load_all_data(DATA_DIR)
    print(f"✓ {len(_cache['communes'])} communes chargées")

    # Essayer le shapefile local d'abord
    shp = find_shapefile(GEO_DIR)
    if shp:
        try:
            insees = [c["insee"] for c in _cache["communes"]]
            _cache["geojson_raw"] = load_geojson_from_shapefile(shp, insees)
            print(f"✓ GeoJSON depuis shapefile local : {shp.name}")
        except Exception as e:
            print(f"⚠ Shapefile erreur : {e} — tentative API nationale")
            await _prefetch_geojson()
    else:
        await _prefetch_geojson()

    yield  # L'app tourne ici


app = FastAPI(
    title="IPN — Hébergement touristique",
    description="Intense Périgord Noir · API offre hébergement",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
    geo = _cache.get("geojson_raw")
    return {
        "communes_chargées": len(_cache.get("communes", [])),
        "geojson_en_cache":  bool(geo),
        "geojson_features":  len(geo.get("features", [])) if geo else 0,
        "shapefile_détecté": str(shp) if shp else None,
    }


# ── Communes ──────────────────────────────────────────────────────────
@app.get("/api/communes", response_model=list[Commune])
def communes(epci: Optional[str] = Query(None)):
    data = get_data()
    if epci:
        eu = epci.upper()
        if eu not in EPCI_CODES:
            raise HTTPException(400, f"EPCI inconnu. Valeurs : {', '.join(EPCI_CODES)}")
        data = [c for c in data if c["epci"] == eu]
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


# ── Types ─────────────────────────────────────────────────────────────
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
        for key, types in mapping.items():
            for t in types:
                if t in c.get("hebergement", {}):
                    result[key]["nb"]   += c["hebergement"][t]["nb"]
                    result[key]["lits"] += c["hebergement"][t]["lits"]
    return result


# ── Top ───────────────────────────────────────────────────────────────
@app.get("/api/top/{metric}")
def top_communes(metric: str, n: int = Query(10, ge=1, le=56), epci: Optional[str] = None):
    VALID = {
        "total_marchands","total_classes","lits_camping","lits_hotels",
        "lits_meublés","lits_gdf","lits_ch","lits_prl",
        "lits_vv","lits_rt","lits_res2aires",
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
    GeoJSON des 56 communes IPN avec données hébergement embarquées.
    Servi depuis le cache pré-chargé au démarrage.
    """
    geo = _cache.get("geojson_raw")

    if not geo:
        raise HTTPException(
            503,
            "Contours non disponibles. "
            "Placez un shapefile dans data/geo/ ou vérifiez la connexion réseau du serveur."
        )

    by_ins = {c["insee"]: c for c in get_data()}

    # Injection des données hébergement dans chaque feature
    features_ipn = []
    for feature in geo.get("features", []):
        insee = feature["properties"].get("code")
        c = by_ins.get(insee)
        if not c:
            continue
        feature["properties"].update({
            "epci":           c.get("epci", ""),
            "epci_name":      c.get("epci_name", ""),
            "commune":        c.get("commune", ""),
            "total_marchands":c.get("total_marchands", 0),
            "total_classes":  c.get("total_classes", 0),
            "lits_camping":   c.get("lits_camping", 0),
            "lits_hotels":    c.get("lits_hotels", 0),
            "lits_meublés":   c.get("lits_meublés", 0),
            "lits_gdf":       c.get("lits_gdf", 0),
            "lits_ch":        c.get("lits_ch", 0),
            "lits_prl":       c.get("lits_prl", 0),
            "lits_vv":        c.get("lits_vv", 0),
            "lits_rt":        c.get("lits_rt", 0),
            "lits_res2aires": c.get("lits_res2aires", 0),
            "lits_plein_air": c.get("lits_plein_air", 0),
            "lits_labellisé": c.get("lits_labellisé", 0),
        })
        features_ipn.append(feature)

    return JSONResponse({
        "type": "FeatureCollection",
        "features": features_ipn
    })


# ── Reload ────────────────────────────────────────────────────────────
@app.post("/api/reload")
async def reload_data():
    """Recharge données Excel + GeoJSON sans redémarrage."""
    _cache.pop("communes", None)
    _cache.pop("geojson_raw", None)
    _cache["communes"] = load_all_data(DATA_DIR)
    await _prefetch_geojson()
    return {"status": "ok", "communes_chargées": len(_cache["communes"])}
