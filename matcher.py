"""
Logique de matching entre MX103 (ordres de paiement) et MT910 (avis de crédit).

Une paire matche si :
1. Même cle_32A (date + montant identiques)
2. adresse_debtor (MX) est contenue dans texte_72 (MT)
"""
import logging
import pandas as pd

from storage import load_csv, append_matches
from config import MX103_CSV, MT910_CSV

logger = logging.getLogger(__name__)


# ============================================================
# Matching principal
# ============================================================

def match_data():
    """
    Effectue le matching entre les MX103 et MT910 stockés en CSV.
    Sauvegarde les nouvelles paires dans matches.csv.

    Returns:
        DataFrame des paires matchées (peut être vide).
        Colonnes : match_id, cle_32A, filename_mx, filename_mt, date_mx, date_mt
    """
    df_mx = load_csv(MX103_CSV)
    df_mt = load_csv(MT910_CSV)

    if df_mx.empty or df_mt.empty:
        logger.info("Matching impossible : MX ou MT vide")
        return _empty_matches_df()

    # Étape 1 : jointure sur cle_32A
    df_merged = pd.merge(
        df_mx, df_mt,
        on='cle_32A',
        suffixes=('_mx', '_mt'),
    )

    if df_merged.empty:
        logger.info("Aucune correspondance sur cle_32A")
        return _empty_matches_df()

    # Étape 2 : filtre adresse_debtor ⊂ texte_72
    mask = df_merged.apply(_debtor_in_texte_72, axis=1)
    df_match = df_merged[mask].copy()

    if df_match.empty:
        logger.info("Aucune correspondance après filtre debtor/texte_72")
        return _empty_matches_df()

    # Étape 3 : structurer le résultat
    df_match = df_match.reset_index(drop=True)
    df_match.insert(0, 'match_id', df_match.index + 1)
    df_match = df_match[
        ['match_id', 'cle_32A', 'filename_mx', 'filename_mt', 'date_mx', 'date_mt']
    ]

    # Étape 4 : persister
    append_matches(df_match)
    logger.info(f"{len(df_match)} paire(s) matchée(s)")

    return df_match


# ============================================================
# Helpers internes
# ============================================================

def _debtor_in_texte_72(row):
    """Vérifie si l'adresse du débiteur (MX) apparaît dans le texte 72 (MT)."""
    debtor = str(row.get('adresse_debtor', '')).lower().strip()
    texte = str(row.get('texte_72', '')).lower().strip()

    if not debtor or not texte:
        return False
    return debtor in texte


def _empty_matches_df():
    """DataFrame vide avec les bonnes colonnes (évite les KeyError côté appelant)."""
    return pd.DataFrame(columns=[
        'match_id', 'cle_32A', 'filename_mx', 'filename_mt', 'date_mx', 'date_mt'
    ])
