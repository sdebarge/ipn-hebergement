"""
Configuration IPN — couleurs et noms issus du projet Python de référence.
"""
from pathlib import Path

# ── Répertoire des données ────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"

# ── Fichiers Excel (à adapter si les noms changent) ───────────────────
EPCI_FILE_MAP = {
    "CCSPN": "CCSPN_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx",
    "CCVV":  "CCVV_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx",
    "CCPF":  "CCPF_Re_partion_des_lits_par_type_d_heberg__et_communes_2025.xlsx",
}

EPCI_CODES = set(EPCI_FILE_MAP.keys())

EPCI_NAMES = {
    "CCSPN": "Sarlat-Périgord Noir",
    "CCVV":  "Vallée de l'Homme",
    "CCPF":  "Pays de Fénelon",
}

# ── Couleurs issues du projet Python IPN (analyse fréquentation) ──────
# EPCI
EPCI_COLORS = {
    "CCSPN": "#4f81bd",   # Bleu acier — Sarlat
    "CCVV":  "#9bbb59",   # Vert — Vallée de l'Homme
    "CCPF":  "#c0504d",   # Rouge brique — Pays de Fénelon
}

# Palette IPN (thématique)
IPN_COLORS = {
    "Gris":   "#95a6b1",
    "Bleu":   "#8bcad9",
    "Vert":   "#a0ca9a",
    "Rose":   "#e4a9cd",
    "Corail": "#f3946f",
}

# ── Corrections codes INSEE (communes nouvelles) ──────────────────────
# Clé = code généré depuis l'Excel (ancien), valeur = code INSEE actuel
INSEE_CORRECTIONS = {
    "24127": "24364",   # Coly-Saint-Amand (fusion 2019 : Coly + Saint-Amand-de-Coly)
    "24314": "24325",   # Pechs-de-l'Espérance (commune nouvelle)
}

# ── Motifs pour ignorer les lignes de total ───────────────────────────
TOTAL_ROW_PATTERNS = [
    "PAYS DE FENELON",
    "SARLAT PERIGORD NOIR",
    "SARLAT - PÉRIGORD NOIR",
    "VALLEE DE L'HOMME",
    "VALLÉE DE L'HOMME",
]
