"""
Régénère static/communes_ipn.geojson à partir du shapefile Admin Express (COG)
et met à jour les centroïdes dans static/index.html pour les 56 communes IPN.

Convention INSEE : on utilise les codes ACTUELS (post-fusions).
- Coly-Saint-Amand   : 24364 (anciennement 24127 + 24388)
- Pechs-de-l'Espérance : 24325 (anciennement 24314 + 24368)

Prérequis :
- data/geo/COMMUNE.shp + .dbf + .shx + .prj (Admin Express COG, Lambert 93)
- geopandas installé : pip install geopandas
"""
import geopandas as gpd, json, re

# ── Set INSEE des 56 communes IPN (codes actuels) ─────────────────────
IPN = {
    # CCSPN — Sarlat-Périgord Noir (13)
    '24040','24252','24255','24341','24355','24366','24510','24512',
    '24471','24520','24544','24577','24587',
    # CCVV — Vallée de l'Homme (26) — 24364 = Coly-Saint-Amand
    '24014','24015','24067','24076','24106','24172','24174','24175',
    '24183','24217','24240','24261','24291','24326','24330','24356',
    '24364','24377','24388','24404','24443','24524','24531','24552',
    '24559','24563',
    # CCPF — Pays de Fénelon (17) — 24325 = Pechs-de-l'Espérance
    '24012','24050','24074','24081','24082','24215','24301','24317',
    '24325','24336','24392','24412','24432','24470','24516','24535',
    '24574',
}

print(f"Lecture du shapefile (cible : {len(IPN)} communes)...")
gdf = gpd.read_file('data/geo/COMMUNE.shp')
gdf = gdf.set_crs(epsg=2154, allow_override=True)

# Le shapefile Admin Express COG contient déjà les codes actuels.
gdf_ipn = gdf[gdf['INSEE_COM'].isin(IPN)].copy()
gdf_ipn = gdf_ipn.to_crs(epsg=4326)
gdf_ipn = gdf_ipn.rename(columns={'INSEE_COM': 'code'})
gdf_ipn['geometry'] = gdf_ipn['geometry'].simplify(0.0001)

print(f"✓ {len(gdf_ipn)} communes trouvées (attendu : {len(IPN)})")
missing = IPN - set(gdf_ipn['code'])
if missing:
    print(f"⚠ Communes absentes du shapefile : {sorted(missing)}")

# ── Centroïdes officiels depuis les géométries reprojetées ────────────
centroids = {}
for _, row in gdf_ipn.iterrows():
    c = row.geometry.centroid
    centroids[row['code']] = (round(c.y, 5), round(c.x, 5))

# Afficher les 2 communes fusionnées (sanity check)
for code in ('24364', '24325'):
    if code in centroids:
        print(f"  {code} centroïde : {centroids[code]}")

# ── Sauvegarder le GeoJSON ────────────────────────────────────────────
geo = json.loads(gdf_ipn[['code', 'geometry']].to_json())
with open('static/communes_ipn.geojson', 'w', encoding='utf-8') as f:
    json.dump(geo, f, ensure_ascii=False, separators=(',', ':'))
print("✓ static/communes_ipn.geojson mis à jour")

# ── Mettre à jour les centroïdes dans index.html ──────────────────────
# Pour les 2 communes fusionnées : remplace lat/lng dans le DATA.
content = open('static/index.html', encoding='utf-8').read()

def update_coord(html, insee, lat, lng):
    pattern = r'(\{[^}]*"insee":"' + insee + r'"[^}]*?"lat":)[0-9.]+([^}]*?"lng":)[0-9.]+'
    def replacer(m):
        return m.group(1) + str(lat) + m.group(2) + str(lng)
    return re.sub(pattern, replacer, html)

for code in ('24364', '24325'):
    if code in centroids:
        lat, lng = centroids[code]
        content = update_coord(content, code, lat, lng)
        print(f"  Mis à jour dans index.html : {code} → {lat},{lng}")

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("✓ static/index.html mis à jour")
print("\nPrêt à pousser !")
