from pydantic import BaseModel
from typing import Optional


class HebergementType(BaseModel):
    nb: int
    lits: int


class Commune(BaseModel):
    commune: str
    insee: str
    epci: str
    epci_name: str

    # Totaux synthétiques (source Excel)
    total_marchands: int
    total_classes: int

    # Par type (lits)
    lits_hotels: int
    lits_rt: int
    lits_camping: int
    lits_prl: int
    lits_vv: int
    lits_gdf: int
    lits_ch: int          # CH GDF + CH CLE + Autres CH
    lits_cle: int         # Clévacances logements
    lits_meublés: int
    lits_etape_grp: int
    lits_res2aires: int

    # Regroupements analytiques
    lits_plein_air: int   # camping + PRL + VV
    lits_labellisé: int   # GDF + CLE + meublés classés

    # Par type (nb établissements)
    nb_hotels: int
    nb_rt: int
    nb_camping: int
    nb_prl: int
    nb_vv: int
    nb_gdf: int
    nb_ch: int
    nb_cle: int
    nb_meublés: int
    nb_etape_grp: int
    nb_res2aires: int

    # Détail complet par type
    hebergement: dict[str, HebergementType]


class EpciSummary(BaseModel):
    epci: str
    epci_name: str
    nb_communes: int
    total_marchands: int
    total_classes: int
    lits_hotels: int
    lits_rt: int
    lits_camping: int
    lits_prl: int
    lits_vv: int
    lits_gdf: int
    lits_ch: int
    lits_cle: int
    lits_meublés: int
    lits_etape_grp: int
    lits_res2aires: int
    lits_plein_air: int
    lits_labellisé: int
    nb_hotels: int
    nb_rt: int
    nb_camping: int
    nb_prl: int
    nb_vv: int
    nb_gdf: int
    nb_ch: int
    nb_cle: int
    nb_meublés: int
    nb_etape_grp: int
    nb_res2aires: int


class TypesHebergement(BaseModel):
    hotels: HebergementType
    residences_tourisme: HebergementType
    campings: HebergementType
    prl: HebergementType
    villages_vacances: HebergementType
    gites_gdf: HebergementType
    chambres_hotes_gdf: HebergementType
    clevacances: HebergementType
    chambres_cle: HebergementType
    meublés_classés: HebergementType
    meublés_nc: HebergementType
    autres_ch: HebergementType
    gites_etape: HebergementType
    accueil_groupe: HebergementType
    residences_secondaires: HebergementType
