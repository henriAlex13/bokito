"""
Logique de matching entre MX103 (ordres de paiement) et MT910 (avis de crédit).

Logique séquentielle en 2 étapes :
1. Match par référence : reference_mx == reference_mt
   Les paires trouvées sont retirées des pools MX et MT.
2. Sur le reste, match par cle_32A identique ET adresse_debtor ⊂ texte_72.

La colonne 'match_type' du CSV trace le critère :
- "reference"   : matché à l'étape 1
- "32A_debtor"  : matché à l'étape 2
"""
import logging
import pandas as pd

from storage import load_csv, append_matches
from config import MX103_CSV, MT910_CSV

logger = logging.getLogger(__name__)


MATCH_COLUMNS = [
    'match_id', 'cle_32A',
    'filename_mx', 'filename_mt',
    'date_mx', 'date_mt',
    'match_type',
]


# ============================================================
# Matching principal (séquentiel)
# ============================================================

def match_data():
    """
    Effectue le matching séquentiel entre les MX103 et MT910.
    Sauvegarde les nouvelles paires dans matches.csv.

    Returns:
        DataFrame des paires matchées (peut être vide).
    """
    df_mx = load_csv(MX103_CSV)
    df_mt = load_csv(MT910_CSV)

    if df_mx.empty or df_mt.empty:
        logger.info("Matching impossible : MX ou MT vide")
        return _empty_matches_df()

    logger.info(f"Pool initial : {len(df_mx)} MX, {len(df_mt)} MT")

    # --- Étape 1 : match par référence
    df_match_ref = _match_by_reference(df_mx, df_mt)
    logger.info(f"Étape 1 (référence) : {len(df_match_ref)} paire(s)")

    # --- Retirer les fichiers déjà appariés des pools
    matched_mx_files = set(df_match_ref['filename_mx']) if not df_match_ref.empty else set()
    matched_mt_files = set(df_match_ref['filename_mt']) if not df_match_ref.empty else set()

    df_mx_remaining = df_mx[~df_mx['filename'].isin(matched_mx_files)].copy()
    df_mt_remaining = df_mt[~df_mt['filename'].isin(matched_mt_files)].copy()

    logger.info(
        f"Pool restant après étape 1 : "
        f"{len(df_mx_remaining)} MX, {len(df_mt_remaining)} MT"
    )

    # --- Étape 2 : match par cle_32A + debtor sur le reste
    df_match_32A = _match_by_cle_32A_debtor(df_mx_remaining, df_mt_remaining)
    logger.info(f"Étape 2 (cle_32A + debtor) : {len(df_match_32A)} paire(s)")

    # --- Concaténation (pools disjoints, pas de dédoublonnage nécessaire)
    df_match = pd.concat([df_match_ref, df_match_32A], ignore_index=True)

    if df_match.empty:
        logger.info("Aucune correspondance trouvée")
        return _empty_matches_df()

    # --- Numérotation et persistance
    df_match = df_match.reset_index(drop=True)
    df_match.insert(0, 'match_id', df_match.index + 1)
    df_match = df_match[MATCH_COLUMNS]

    append_matches(df_match)
    logger.info(f"Total : {len(df_match)} paire(s) matchée(s)")

    return df_match


# ============================================================
# Étape 1 : match par référence
# ============================================================

def _match_by_reference(df_mx, df_mt):
    """Jointure entre reference_mx (MX) et reference_mt (MT)."""
    # Exclure les références vides
    df_mx_ref = df_mx[df_mx['reference_mx'].astype(str).str.strip() != ''].copy()
    df_mt_ref = df_mt[df_mt['reference_mt'].astype(str).str.strip() != ''].copy()

    if df_mx_ref.empty or df_mt_ref.empty:
        return _empty_matches_df()

    # Jointure (left_on/right_on car les colonnes ont des noms différents)
    df = pd.merge(
        df_mx_ref, df_mt_ref,
        left_on='reference_mx', right_on='reference_mt',
        suffixes=('_mx', '_mt'),
    )

    if df.empty:
        return _empty_matches_df()

    # Côté MX, cle_32A est devenue cle_32A_mx après le merge (suffixes)
    df['cle_32A'] = df['cle_32A_mx']
    df['match_type'] = 'reference'

    return df[['cle_32A', 'filename_mx', 'filename_mt',
               'date_mx', 'date_mt', 'match_type']]


# ============================================================
# Étape 2 : match par cle_32A + debtor⊂texte_72
# ============================================================

def _match_by_cle_32A_debtor(df_mx, df_mt):
    """Jointure sur cle_32A puis filtre adresse_debtor ⊂ texte_72."""
    if df_mx.empty or df_mt.empty:
        return _empty_matches_df()

    # Exclure les cle_32A vides (sinon merge sur "" qui peut tout faire matcher)
    df_mx_ok = df_mx[df_mx['cle_32A'].astype(str).str.strip() != ''].copy()
    df_mt_ok = df_mt[df_mt['cle_32A'].astype(str).str.strip() != ''].copy()

    if df_mx_ok.empty or df_mt_ok.empty:
        return _empty_matches_df()

    df = pd.merge(df_mx_ok, df_mt_ok, on='cle_32A', suffixes=('_mx', '_mt'))

    if df.empty:
        return _empty_matches_df()

    # Filtre debtor ⊂ texte_72
    mask = df.apply(_debtor_in_texte_72, axis=1)
    df = df[mask].copy()

    if df.empty:
        return _empty_matches_df()

    df['match_type'] = '32A_debtor'

    return df[['cle_32A', 'filename_mx', 'filename_mt',
               'date_mx', 'date_mt', 'match_type']]


def _debtor_in_texte_72(row):
    """Vérifie si l'adresse du débiteur (MX) apparaît dans le texte 72 (MT)."""
    debtor = str(row.get('adresse_debtor', '')).lower().strip()
    texte = str(row.get('texte_72', '')).lower().strip()

    if not debtor or not texte:
        return False
    return debtor in texte


# ============================================================
# Helper
# ============================================================

def _empty_matches_df():
    """DataFrame vide avec les colonnes attendues côté appelant."""
    return pd.DataFrame(columns=[
        'cle_32A', 'filename_mx', 'filename_mt',
        'date_mx', 'date_mt', 'match_type'
    ])
