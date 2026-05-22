# IPN Hébergement — API REST

API de l'offre en hébergement touristique de l'**Intense Périgord Noir** (Dordogne, 24).  
Couvre 56 communes sur 3 EPCI : Sarlat-Périgord Noir · Vallée de l'Homme · Pays de Fénelon.

---

## Installation

```bash
cd ipn_hebergement
pip install -r requirements.txt
```

## Données

Placer les 3 fichiers Excel dans `data/` :

```
data/
  CCSPN_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx
  CCVV_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx
  CCPF_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx
```

Pour une mise à jour annuelle, remplacer simplement les fichiers puis appeler `POST /api/reload`.

## Lancement

```bash
# Développement
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Carte interactive : http://localhost:8000  
Documentation API : http://localhost:8000/docs

---

## Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/` | Carte interactive Leaflet |
| `GET` | `/api/communes` | Toutes les communes (filtre `?epci=CCSPN`) |
| `GET` | `/api/communes/{insee}` | Une commune par code INSEE |
| `GET` | `/api/summary` | Totaux par EPCI + total IPN |
| `GET` | `/api/types` | Agrégat par grand type d'hébergement |
| `GET` | `/api/top/{metric}` | Top N communes (`?n=10&epci=CCVV`) |
| `GET` | `/api/geojson` | GeoJSON + données (contours depuis geo.api.gouv.fr) |
| `POST` | `/api/reload` | Recharge les données depuis les Excel |

### Indicateurs disponibles pour `/api/top/{metric}`

`total_marchands` · `total_classes` · `lits_camping` · `lits_hotels` · `lits_meublés` ·  
`lits_gdf` · `lits_ch` · `lits_prl` · `lits_vv` · `lits_rt` · `lits_res2aires`

---

## Types d'hébergement couverts

| Clé API | Contenu |
|---------|---------|
| `lits_hotels` | Hôtels classés + non classés |
| `lits_rt` | Résidences de tourisme classées + non classées |
| `lits_camping` | Campings classés + non classés |
| `lits_prl` | Parcs Résidentiels de Loisirs classés + non classés |
| `lits_vv` | Villages Vacances classés + non classés |
| `lits_gdf` | Gîtes de France (gîtes, hors chambres) |
| `lits_ch` | Chambres d'hôtes : GDF + CLE + Autres |
| `lits_cle` | Clévacances (logements, hors chambres) |
| `lits_meublés` | Meublés de tourisme classés + non classés |
| `lits_etape_grp` | Gîtes d'étape GF + Accueil groupe + Auberges collectives |
| `lits_plein_air` | Camping + PRL + VV (regroupement analytique) |
| `lits_labellisé` | GDF + CLE + Meublés classés (regroupement analytique) |
| `lits_res2aires` | Résidences secondaires (hors marchands) |

---

## Couleurs IPN

Issues du projet Python d'analyse de fréquentation :

```python
# EPCI
CCSPN (Sarlat-Périgord Noir) : #4f81bd
CCVV  (Vallée de l'Homme)    : #9bbb59
CCPF  (Pays de Fénelon)      : #c0504d

# Palette IPN
Gris   : #95a6b1
Bleu   : #8bcad9
Vert   : #a0ca9a
Rose   : #e4a9cd
Corail : #f3946f
```

---

## Mise en ligne (exemples)

```bash
# Fly.io
fly launch --name ipn-hebergement
fly deploy

# Railway / Render
# Ajouter une variable d'env PORT=8000 et la commande de démarrage :
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Pour persister les données, monter le dossier `data/` en volume ou utiliser un bucket S3/R2.

---

## Mise à jour annuelle

1. Remplacer les fichiers Excel dans `data/`
2. Appeler : `curl -X POST http://localhost:8000/api/reload`
3. Les nouvelles données sont immédiatement disponibles (pas de redémarrage nécessaire)
