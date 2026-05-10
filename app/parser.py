"""
Extraction des données hébergement depuis les fichiers Excel IPN.

Structure attendue (3 EPCI, format identique) :
  Ligne 0 : en-têtes (type d'hébergement, cellules fusionnées)
  Ligne 1 : Nb / Lits alternés
  Lignes 2+ : données par commune (dernière ligne = total EPCI → ignorée)

Types d'hébergement (21 × 2 colonnes) :
  Hôtels | Hôtels non classés | RT classés | RT non classés |
  Campings | Cpgs non classés | PRL classés | PRL non classés |
  GDF | CH GDF | CLE | CH CLE | Meub. classés | Meub. non cl. |
  Autres CH | Gîte d'étape GF | Accu. grp | Auberge collective |
  VV classés | VV non classés | Res. 2aires
"""
import pandas as pd
from pathlib import Path
from .config import EPCI_FILE_MAP, TOTAL_ROW_PATTERNS, INSEE_CORRECTIONS


# ─── Types d'hébergement (dans l'ordre des colonnes) ─────────────────
HEBERGEMENT_TYPES = [
    "Hôtels", "Hôtels non classés",
    "RT classés", "RT non classés",
    "Campings", "Cpgs non classés",
    "PRL classés", "PRL non classés",
    "GDF", "CH GDF",
    "CLE", "CH CLE",
    "Meub. classés", "Meub. non cl.",
    "Autres CH",
    "Gîte d'étape GF",
    "Accu. grp", "Auberge collective",
    "VV classés", "VV non classés",
    "Res. 2aires",
]


def _safe_int(val) -> int:
    try:
        if pd.isna(val):
            return 0
        return int(float(val))
    except Exception:
        return 0


def _is_total_row(name: str) -> bool:
    u = str(name).upper().strip()
    return any(p in u for p in TOTAL_ROW_PATTERNS)


def parse_file(path: Path, epci_code: str) -> list[dict]:
    df = pd.read_excel(path, header=None)
    communes = []

    for i in range(2, df.shape[0]):
        commune_name = df.iloc[i, 0]
        code_raw = df.iloc[i, 1]

        if pd.isna(commune_name) or str(commune_name).strip() == "":
            continue
        if _is_total_row(str(commune_name)):
            continue

        try:
            code_num = int(float(code_raw))
            insee = f"24{code_num:03d}"
            insee = INSEE_CORRECTIONS.get(insee, insee)
        except Exception:
            continue

        epci_name = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ""

        # ── Extraction hébergement ────────────────────────────────────
        hebergement = {}
        for t_idx, t_name in enumerate(HEBERGEMENT_TYPES):
            col_nb   = 3 + t_idx * 2
            col_lits = 4 + t_idx * 2
            nb   = _safe_int(df.iloc[i, col_nb])   if col_nb   < df.shape[1] else 0
            lits = _safe_int(df.iloc[i, col_lits])  if col_lits < df.shape[1] else 0
            hebergement[t_name] = {"nb": nb, "lits": lits}

        # ── Totaux depuis les colonnes de synthèse ────────────────────
        total_classes   = 0
        total_marchands = 0
        for col in range(df.shape[1]):
            h0 = str(df.iloc[0, col]) if pd.notna(df.iloc[0, col]) else ""
            h1 = str(df.iloc[1, col]) if pd.notna(df.iloc[1, col]) else ""
            if "Total lits" in h0 and "classés" in h1:
                total_classes = _safe_int(df.iloc[i, col])
            elif "Total lits" in h0 and "marchands" in h1:
                total_marchands = _safe_int(df.iloc[i, col])

        # ── Métriques dérivées complètes ──────────────────────────────
        def lits(*types):
            return sum(hebergement.get(t, {}).get("lits", 0) for t in types)

        def nb(*types):
            return sum(hebergement.get(t, {}).get("nb", 0) for t in types)

        communes.append({
            "commune":          str(commune_name).strip(),
            "insee":            insee,
            "epci":             epci_code,
            "epci_name":        epci_name,
            "hebergement":      hebergement,

            # ── Totaux synthétiques (depuis colonnes Excel) ────────────
            "total_classes":    total_classes,
            "total_marchands":  total_marchands,

            # ── Métriques par grand type ───────────────────────────────
            "lits_hotels":      lits("Hôtels", "Hôtels non classés"),
            "nb_hotels":        nb("Hôtels", "Hôtels non classés"),

            "lits_rt":          lits("RT classés", "RT non classés"),
            "nb_rt":            nb("RT classés", "RT non classés"),

            "lits_camping":     lits("Campings", "Cpgs non classés"),
            "nb_camping":       nb("Campings", "Cpgs non classés"),

            "lits_prl":         lits("PRL classés", "PRL non classés"),
            "nb_prl":           nb("PRL classés", "PRL non classés"),

            "lits_vv":          lits("VV classés", "VV non classés"),
            "nb_vv":            nb("VV classés", "VV non classés"),

            # Gîtes de France (gîtes uniquement, hors CH)
            "lits_gdf":         lits("GDF"),
            "nb_gdf":           nb("GDF"),

            # Chambres d'hôtes toutes labels confondues
            "lits_ch":          lits("CH GDF", "CH CLE", "Autres CH"),
            "nb_ch":            nb("CH GDF", "CH CLE", "Autres CH"),

            # Clévacances (logements, hors CH CLE)
            "lits_cle":         lits("CLE"),
            "nb_cle":           nb("CLE"),

            # Meublés (tous labels)
            "lits_meublés":     lits("Meub. classés", "Meub. non cl."),
            "nb_meublés":       nb("Meub. classés", "Meub. non cl."),

            # Gîtes d'étape & accueil collectif
            "lits_etape_grp":   lits("Gîte d'étape GF", "Accu. grp", "Auberge collective"),
            "nb_etape_grp":     nb("Gîte d'étape GF", "Accu. grp", "Auberge collective"),

            # Résidences secondaires (hors marchands)
            "lits_res2aires":   lits("Res. 2aires"),
            "nb_res2aires":     nb("Res. 2aires"),

            # ── Regroupements analytiques ──────────────────────────────
            # Hébergement plein air (camping + PRL + VV)
            "lits_plein_air":   lits("Campings", "Cpgs non classés",
                                     "PRL classés", "PRL non classés",
                                     "VV classés", "VV non classés"),

            # Hébergement labellisé (GDF + CLE + meublés classés)
            "lits_labellisé":   lits("GDF", "CH GDF", "CLE", "CH CLE", "Meub. classés"),
        })

    return communes


def load_all_data(data_dir: Path) -> list[dict]:
    """Charge les 3 fichiers Excel et retourne la liste consolidée des communes."""
    all_communes = []
    for epci_code, filename in EPCI_FILE_MAP.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Fichier manquant : {path}\n"
                f"Placez les fichiers Excel dans le dossier data/"
            )
        all_communes.extend(parse_file(path, epci_code))
    return all_communes


def get_summary(communes: list[dict]) -> list[dict]:
    """Calcule les totaux agrégés par EPCI."""
    from .config import EPCI_NAMES
    metrics = [
        "total_marchands", "total_classes",
        "lits_hotels", "lits_rt", "lits_camping", "lits_prl",
        "lits_vv", "lits_gdf", "lits_ch", "lits_cle",
        "lits_meublés", "lits_etape_grp", "lits_res2aires",
        "lits_plein_air", "lits_labellisé",
        "nb_hotels", "nb_rt", "nb_camping", "nb_prl", "nb_vv",
        "nb_gdf", "nb_ch", "nb_cle", "nb_meublés",
        "nb_etape_grp", "nb_res2aires",
    ]

    summaries = {}
    for c in communes:
        epci = c["epci"]
        if epci not in summaries:
            summaries[epci] = {
                "epci": epci,
                "epci_name": EPCI_NAMES[epci],
                "nb_communes": 0,
                **{m: 0 for m in metrics},
            }
        summaries[epci]["nb_communes"] += 1
        for m in metrics:
            summaries[epci][m] += c.get(m, 0)

    # Ajouter total IPN
    ipn = {
        "epci": "IPN",
        "epci_name": "Itinéraire du Périgord Noir (total)",
        "nb_communes": sum(s["nb_communes"] for s in summaries.values()),
        **{m: sum(s[m] for s in summaries.values()) for m in metrics},
    }

    return list(summaries.values()) + [ipn]
