"""
Logique de matching entre MX103 (ordres de paiement) et MT910 (avis de crédit).

Une paire matche si AU MOINS UN des deux critères est vrai :
1. Référence : reference_mx == reference_mt (extraites des noms de fichiers)
2. Montant : même cle_32A ET adresse_debtor ⊂ texte_72

La colonne 'match_type' du CSV trace lequel a déclenché : "reference", "32A" ou "both".
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
# Matching principal
# ============================================================

def match_data():
    """
    Effectue le matching entre les MX103 et MT910 stockés en CSV.
    Sauvegarde les nouvelles paires dans matches.csv.

    Returns:
        DataFrame des paires matchées (peut être vide).
    """
    df_mx = load_csv(MX103_CSV)
    df_mt = load_csv(MT910_CSV)

    if df_mx.empty or df_mt.empty:
        logger.info("Matching impossible : MX ou MT vide")
        return _empty_matches_df()

    # --- Match A : par cle_32A + debtor
    df_match_32A = _match_by_cle_32A(df_mx, df_mt)
    logger.info(f"Match par cle_32A/debtor : {len(df_match_32A)} paire(s)")

    # --- Match B : par référence
    df_match_ref = _match_by_reference(df_mx, df_mt)
    logger.info(f"Match par référence : {len(df_match_ref)} paire(s)")

    # --- Union des deux
    df_match = _union_matches(df_match_32A, df_match_ref)

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
# Match A : par cle_32A + debtor⊂texte_72
# ============================================================

def _match_by_cle_32A(df_mx, df_mt):
    """Jointure sur cle_32A puis filtre debtor ⊂ texte_72."""
    # Jointure (avec préfixes pour éviter collisions de colonnes)
    df = pd.merge(df_mx, df_mt, on='cle_32A', suffixes=('_mx', '_mt'))

    if df.empty:
        return _empty_matches_df()

    # Filtre debtor
    mask = df.apply(_debtor_in_texte_72, axis=1)
    df = df[mask].copy()

    if df.empty:
        return _empty_matches_df()

    df['match_type'] = '32A'
    return df[['cle_32A', 'filename_mx', 'filename_mt', 'date_mx', 'date_mt', 'match_type']]


def _debtor_in_texte_72(row):
    """Vérifie si l'adresse du débiteur (MX) apparaît dans le texte 72 (MT)."""
    debtor = str(row.get('adresse_debtor', '')).lower().strip()
    texte = str(row.get('texte_72', '')).lower().strip()

    if not debtor or not texte:
        return False
    return debtor in texte


# ============================================================
# Match B : par référence (nom de fichier)
# ============================================================

def _match_by_reference(df_mx, df_mt):
    """Jointure entre reference_mx (MX) et reference_mt (MT)."""
    # On exclut les références vides pour ne pas matcher du vide avec du vide
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

    # Côté MX, cle_32A devient cle_32A_mx après le merge (à cause des suffixes).
    # On harmonise : on prend la valeur du MX (les deux devraient être égales si elles existent).
    df['cle_32A'] = df.get('cle_32A_mx', df.get('cle_32A', ''))

    df['match_type'] = 'reference'
    return df[['cle_32A', 'filename_mx', 'filename_mt', 'date_mx', 'date_mt', 'match_type']]


# ============================================================
# Union des deux types de matchs
# ============================================================

def _union_matches(df_a, df_b):
    """
    Concatène les deux DataFrames de matchs et déduplique sur (filename_mx, filename_mt).
    Si une paire est trouvée par les deux critères, match_type devient 'both'.
    """
    if df_a.empty and df_b.empty:
        return _empty_matches_df()

    df = pd.concat([df_a, df_b], ignore_index=True)

    # Détecter les doublons (même paire fichier-fichier trouvée par les 2 critères)
    paires_groupees = df.groupby(['filename_mx', 'filename_mt'])['match_type'].apply(
        lambda s: 'both' if s.nunique() > 1 else s.iloc[0]
    ).reset_index()

    # Garder une seule ligne par paire (la première rencontrée) puis remplacer match_type
    df = df.drop_duplicates(subset=['filename_mx', 'filename_mt'], keep='first').copy()
    df = df.drop(columns=['match_type']).merge(
        paires_groupees, on=['filename_mx', 'filename_mt']
    )

    return df


# ============================================================
# Helper : DataFrame vide avec bonnes colonnes
# ============================================================

def _empty_matches_df():
    """DataFrame vide avec les colonnes attendues côté appelant."""
    return pd.DataFrame(columns=[
        'cle_32A', 'filename_mx', 'filename_mt',
        'date_mx', 'date_mt', 'match_type'
    ])
