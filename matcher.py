"""
Logique de matching entre MX103 (ordres de paiement) et MT910 (avis de crédit).

Logique séquentielle en 2 étapes :
1. Match par référence : reference_mx == reference_mt
   Les paires trouvées sont retirées des pools MX et MT.
2. Sur le reste, match par cle_32A identique ET adresse_debtor ⊂ texte_72.

La colonne 'match_type' du CSV trace le critère :
- "reference"   : matché à l'étape 1
- "32A_debtor"  : matché à l'étape 2

Les match_id sont des entiers incrémentaux (1, 2, 3...) MAIS STABLES :
une paire conserve son match_id entre les runs grâce à la réutilisation
des IDs présents dans matches.csv (lookup sur cle_32A + filenames).
Cela garantit l'idempotence en cas de relance après interruption.
"""
import logging
import pandas as pd

from storage import load_csv, append_matches
from config import MX103_CSV, MT910_CSV, MATCHES_CSV

logger = logging.getLogger(__name__)


MATCH_COLUMNS = [
    'match_id', 'cle_32A',
    'filename_mx', 'filename_mt',
    'date_mx', 'date_mt',
    'match_type',
]

# Clé naturelle d'une paire (utilisée pour réutiliser les match_id existants)
PAIR_KEY = ['cle_32A', 'filename_mx', 'filename_mt']


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

    # --- Attribution stable des match_id incrémentaux
    df_match = _assign_stable_match_ids(df_match)
    df_match = df_match[MATCH_COLUMNS]

    append_matches(df_match)
    logger.info(f"Total : {len(df_match)} paire(s) matchée(s)")

    return df_match


# ============================================================
# Attribution stable des match_id
# ============================================================

def _assign_stable_match_ids(df_new):
    """
    Attribue des match_id incrémentaux (1, 2, 3...) en réutilisant ceux
    déjà présents dans matches.csv pour les paires existantes.

    Logique :
    - Pour chaque paire (cle_32A, filename_mx, filename_mt) déjà connue
      dans matches.csv, on reprend son match_id existant.
    - Pour les nouvelles paires, on attribue les ID suivants
      (max_existant + 1, +2, ...).

    Returns:
        DataFrame avec une colonne 'match_id' (int) renseignée.
    """
    df_existing = load_csv(MATCHES_CSV)

    # Dictionnaire {(cle_32A, filename_mx, filename_mt): match_id}
    existing_ids = {}
    max_existing = 0

    if not df_existing.empty and 'match_id' in df_existing.columns:
        for _, row in df_existing.iterrows():
            key = (str(row['cle_32A']), str(row['filename_mx']), str(row['filename_mt']))
            try:
                mid = int(row['match_id'])
                existing_ids[key] = mid
                max_existing = max(max_existing, mid)
            except (ValueError, TypeError):
                # match_id non numérique (ancien format hash par ex.) → on ignore
                continue

    # Attribuer les ID
    next_id = max_existing + 1
    new_count = 0
    reused_count = 0
    new_ids = []

    for _, row in df_new.iterrows():
        key = (str(row['cle_32A']), str(row['filename_mx']), str(row['filename_mt']))
        if key in existing_ids:
            new_ids.append(existing_ids[key])
            reused_count += 1
        else:
            new_ids.append(next_id)
            existing_ids[key] = next_id  # au cas où la même paire apparaît 2x dans df_new
            next_id += 1
            new_count += 1

    df_new = df_new.copy()
    df_new['match_id'] = new_ids

    logger.info(
        f"Match IDs : {reused_count} réutilisé(s), {new_count} nouveau(x) "
        f"(prochain ID disponible : {next_id})"
    )

    return df_new


# ============================================================
# Étape 1 : match par référence
# ============================================================

def _match_by_reference(df_mx, df_mt):
    """Jointure entre reference_mx (MX) et reference_mt (MT)."""
    df_mx_ref = df_mx[df_mx['reference_mx'].astype(str).str.strip() != ''].copy()
    df_mt_ref = df_mt[df_mt['reference_mt'].astype(str).str.strip() != ''].copy()

    if df_mx_ref.empty or df_mt_ref.empty:
        return _empty_matches_df()

    df = pd.merge(
        df_mx_ref, df_mt_ref,
        left_on='reference_mx', right_on='reference_mt',
        suffixes=('_mx', '_mt'),
    )

    if df.empty:
        return _empty_matches_df()

    df['cle_32A'] = df['cle_32A_mx']
    df['match_type'] = 'reference'

    return df[['cle_32A', 'filename_mx', 'filename_mt',
               'date_mx', 'date_mt', 'match_type']]


# ============================================================
# Étape 2 : match par cle_32A + debtor⊂texte_72
# ============================================================

def _match_by_cle_32A_debtor(df_mx, df_mt):
    """
    Jointure sur cle_32A puis filtre :
    - adresse_debtor ⊂ texte_72 ET
    - adresse_creditor ⊂ texte_72

    (Les deux acteurs doivent apparaître dans le bloc 72 du MT910.)
    """
    if df_mx.empty or df_mt.empty:
        return _empty_matches_df()

    df_mx_ok = df_mx[df_mx['cle_32A'].astype(str).str.strip() != ''].copy()
    df_mt_ok = df_mt[df_mt['cle_32A'].astype(str).str.strip() != ''].copy()

    if df_mx_ok.empty or df_mt_ok.empty:
        return _empty_matches_df()

    df = pd.merge(df_mx_ok, df_mt_ok, on='cle_32A', suffixes=('_mx', '_mt'))

    if df.empty:
        return _empty_matches_df()

    mask = df.apply(_debtor_and_creditor_in_texte_72, axis=1)
    df = df[mask].copy()

    if df.empty:
        return _empty_matches_df()

    df['match_type'] = '32A_debtor'

    return df[['cle_32A', 'filename_mx', 'filename_mt',
               'date_mx', 'date_mt', 'match_type']]


def _debtor_and_creditor_in_texte_72(row):
    """
    Vérifie que l'adresse_debtor ET l'adresse_creditor (MX) apparaissent
    tous deux dans le texte 72 (MT). Les deux conditions sont obligatoires.
    """
    debtor = str(row.get('adresse_debtor', '')).lower().strip()
    creditor = str(row.get('adresse_creditor', '')).lower().strip()
    texte = str(row.get('texte_72', '')).lower().strip()

    # Les 3 valeurs doivent être non vides
    if not debtor or not creditor or not texte:
        return False

    return (debtor in texte) and (creditor in texte)


# ============================================================
# Helper
# ============================================================

def _empty_matches_df():
    """DataFrame vide avec les colonnes attendues côté appelant."""
    return pd.DataFrame(columns=[
        'cle_32A', 'filename_mx', 'filename_mt',
        'date_mx', 'date_mt', 'match_type'
    ])
