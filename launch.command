#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
#  IPN Hébergement — Lanceur macOS
#  Double-cliquez sur ce fichier pour démarrer l'application.
# ─────────────────────────────────────────────────────────────────────

# Se placer dans le dossier du script (indépendant de l'emplacement)
cd "$(dirname "$0")"

PORT=8000
URL="http://localhost:$PORT"

# ── Couleurs terminal ────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  IPN — Offre en hébergement touristique  ║"
echo "  ║  Itinéraire du Périgord Noir · 2025      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── Vérifier Python 3 ───────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 introuvable. Installez-le depuis python.org${NC}"
    read -p "  Appuyez sur Entrée pour fermer..."
    exit 1
fi

PY=$(python3 --version 2>&1)
echo -e "  ${GREEN}✓${NC} $PY"

# ── Environnement virtuel ────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo -e "  ${YELLOW}→${NC} Création de l'environnement virtuel..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── Dépendances ──────────────────────────────────────────────────────
# Installer uniquement si fastapi manque (évite l'attente à chaque lancement)
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "  ${YELLOW}→${NC} Installation des dépendances (première fois)..."
    pip install -q "fastapi>=0.111.0" "uvicorn[standard]>=0.29.0" "httpx>=0.27.0" "pandas>=2.2.0" "openpyxl>=3.1.0" "pydantic>=2.7.0" "python-multipart>=0.0.9"
    echo -e "  ${GREEN}✓${NC} Dépendances installées"
else
    echo -e "  ${GREEN}✓${NC} Dépendances OK"
fi

# ── Vérifier les fichiers Excel ──────────────────────────────────────
MISSING=0
for f in \
    "CCSPN_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx" \
    "CCVV_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx" \
    "CCPF_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx"; do
    if [ ! -f "data/$f" ]; then
        echo -e "  ${RED}✗ Fichier manquant : data/$f${NC}"
        MISSING=1
    fi
done

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "  ${RED}Placez les 3 fichiers Excel dans le dossier data/ et relancez.${NC}"
    read -p "  Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Fichiers Excel présents"

# ── Vérifier si le port est déjà utilisé ────────────────────────────
if lsof -ti tcp:$PORT &>/dev/null; then
    echo -e "  ${YELLOW}→${NC} Port $PORT occupé — arrêt du processus précédent..."
    lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null
    sleep 1
fi

# ── Ouvrir le navigateur après 1,5 s ────────────────────────────────
(sleep 1.5 && open "$URL") &

# ── Lancement ────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}▶ Serveur démarré sur $URL${NC}"
echo "  ─────────────────────────────────────────"
echo "  Ctrl+C pour arrêter"
echo ""

python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --reload \
    --log-level warning

# ── À l'arrêt ────────────────────────────────────────────────────────
echo ""
echo -e "  ${YELLOW}Serveur arrêté.${NC}"
read -p "  Appuyez sur Entrée pour fermer..."
