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
from .config import DATA_DIR, EPCI_CODES
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _cache["communes"] = load_all_data(DATA_DIR)
    print(f"✓ {len(_cache['communes'])} communes chargées")
    _cache["geojson_raw"] = _load_geojson()
    yield


app = FastAPI(
    title="IPN — Hébergement touristique",
    description="Intense Périgord Noir · API offre hébergement",
    version="1.3.0",
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
    shp = find_shapefile(GEO_DIR)
    return {
        "communes": len(_cache.get("communes", [])),
        "geojson_ok": bool(geo),
        "geojson_features": len(geo.get("features", [])) if geo else 0,
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
def top_communes(metric: str, n: int = Query(10, ge=1, le=56), epci: Optional[str] = None):
    VALID = {"total_marchands","total_classes","lits_camping","lits_hotels","lits_meublés",
             "lits_gdf","lits_ch","lits_prl","lits_vv","lits_rt","lits_res2aires"}
    if metric not in VALID:
        raise HTTPException(400, f"Indicateur invalide : {', '.join(sorted(VALID))}")
    data = get_data()
    if epci:
        data = [c for c in data if c["epci"] == epci.upper()]
    return sorted(data, key=lambda c: c.get(metric, 0), reverse=True)[:n]


@app.get("/api/geojson")
def geojson():
    geo = _cache.get("geojson_raw")
    if not geo:
        raise HTTPException(503, "GeoJSON non disponible — placez un shapefile dans data/geo/")

    by_ins = {c["insee"]: c for c in get_data()}
    REMAP = {"24364": "24127", "24325": "24314"}
    features_out = []
    for f in geo.get("features", []):
        code = f["properties"].get("code", "")
        if code in REMAP:
            code = REMAP[code]
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
            "lits_res2aires": c.get("lits_res2aires",0),
        })
        features_out.append(f)

    return JSONResponse({"type":"FeatureCollection","features":features_out})


@app.post("/api/reload")
def reload_data():
    _cache.pop("communes", None)
    _cache.pop("geojson_raw", None)
    _cache["communes"] = load_all_data(DATA_DIR)
    _cache["geojson_raw"] = _load_geojson()
    return {"status": "ok", "communes": len(_cache["communes"])}
