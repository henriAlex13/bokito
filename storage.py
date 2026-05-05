"""
Persistance CSV pour le traitement SWIFT.

Cinq CSV sont gérés :
- mx103_files.csv      : fichiers MX103 déjà extraits
- mt910_files.csv      : fichiers MT910 déjà extraits
- matches.csv          : paires (MX, MT) matchées
- copied_files_log.csv : log des fichiers déjà copiés en sortie
- no_read_files.csv    : fichiers illisibles (PDF corrompu, vide, etc.)
"""
import os
import logging
from datetime import datetime
import pandas as pd

from config import (
    CSV_DIR,
    MX103_CSV, MT910_CSV, MATCHES_CSV, COPIED_LOG_CSV, NO_READ_CSV,
)

logger = logging.getLogger(__name__)


# ============================================================
# Schémas des CSV
# ============================================================

CSV_SCHEMAS = {
    MX103_CSV:       ['filename', 'filepath', 'cle_32A', 'adresse_debtor',
                      'date', 'montant', 'reference_mx'],
    MT910_CSV:       ['filename', 'filepath', 'cle_32A', 'texte_72',
                      'date', 'montant', 'reference_mt'],
    MATCHES_CSV:     ['match_id', 'cle_32A', 'filename_mx', 'filename_mt',
                      'date_mx', 'date_mt', 'match_type'],
    COPIED_LOG_CSV:  ['filepath', 'copied_at'],
    NO_READ_CSV:     ['filepath', 'reason', 'detected_at'],
}


# ============================================================
# Initialisation
# ============================================================

def init_csv_files():
    """Crée le dossier CSV et les fichiers vides s'ils n'existent pas."""
    os.makedirs(CSV_DIR, exist_ok=True)

    for csv_path, columns in CSV_SCHEMAS.items():
        if not os.path.exists(csv_path):
            pd.DataFrame(columns=columns).to_csv(csv_path, index=False)
            logger.info(f"CSV initialisé : {csv_path}")


# ============================================================
# Lecture / écriture génériques
# ============================================================

def load_csv(csv_path):
    """
    Charge un CSV. Retourne un DataFrame vide (avec les bonnes colonnes
    si le schéma est connu) si le fichier n'existe pas ou est vide.
    """
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        return pd.read_csv(csv_path, dtype=str).fillna("")

    columns = CSV_SCHEMAS.get(csv_path, [])
    return pd.DataFrame(columns=columns)


def save_csv(df, csv_path):
    """Sauvegarde un DataFrame en CSV."""
    df.to_csv(csv_path, index=False)


# ============================================================
# Mise à jour incrémentale (MX103 / MT910)
# ============================================================

def append_extracted_files(new_records, csv_path):
    """
    Ajoute de nouveaux enregistrements extraits au CSV, en évitant
    les doublons sur 'filename'.

    Returns:
        Nombre de nouvelles lignes effectivement ajoutées.
    """
    if not new_records:
        logger.info(f"Aucun nouveau fichier à ajouter dans {os.path.basename(csv_path)}")
        return 0

    df_existing = load_csv(csv_path)
    df_new = pd.DataFrame(new_records)

    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.drop_duplicates(subset=['filename'], keep='last', inplace=True)

    save_csv(df_combined, csv_path)
    logger.info(f"{len(new_records)} nouveau(x) fichier(s) ajouté(s) dans {os.path.basename(csv_path)}")
    return len(new_records)


def get_already_processed_filenames(csv_path):
    """Retourne l'ensemble des filenames déjà présents dans le CSV."""
    df = load_csv(csv_path)
    if df.empty or 'filename' not in df.columns:
        return set()
    return set(df['filename'].tolist())


# ============================================================
# Matches
# ============================================================

def append_matches(df_new_matches):
    """
    Ajoute des nouvelles paires matchées au CSV des matches,
    en évitant les doublons sur (cle_32A, filename_mx, filename_mt).
    """
    if df_new_matches.empty:
        return

    df_existing = load_csv(MATCHES_CSV)
    df_combined = pd.concat([df_existing, df_new_matches], ignore_index=True)
    df_combined.drop_duplicates(
        subset=['cle_32A', 'filename_mx', 'filename_mt'],
        keep='last',
        inplace=True,
    )
    save_csv(df_combined, MATCHES_CSV)


# ============================================================
# Log des fichiers copiés
# ============================================================

def load_copied_files_set():
    """Retourne l'ensemble des chemins de fichiers déjà copiés."""
    df = load_csv(COPIED_LOG_CSV)
    if df.empty or 'filepath' not in df.columns:
        return set()
    return set(df['filepath'].tolist())


def log_copied_file(filepath):
    """Ajoute un fichier au log des copies (avec horodatage)."""
    df = load_csv(COPIED_LOG_CSV)
    new_row = pd.DataFrame([{
        'filepath': filepath,
        'copied_at': datetime.now().isoformat(),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.drop_duplicates(subset=['filepath'], keep='last', inplace=True)
    save_csv(df, COPIED_LOG_CSV)


# ============================================================
# Log des fichiers illisibles
# ============================================================

def load_no_read_set():
    """Retourne l'ensemble des chemins de fichiers déjà identifiés comme illisibles."""
    df = load_csv(NO_READ_CSV)
    if df.empty or 'filepath' not in df.columns:
        return set()
    return set(df['filepath'].tolist())


def log_no_read_file(filepath, reason=""):
    """
    Ajoute un fichier au log des fichiers illisibles.

    Args:
        filepath: chemin du fichier qui n'a pas pu être lu/extrait
        reason:   raison textuelle (ex: "PDF corrompu", "extraction échouée")
    """
    df = load_csv(NO_READ_CSV)
    new_row = pd.DataFrame([{
        'filepath': filepath,
        'reason': reason,
        'detected_at': datetime.now().isoformat(),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.drop_duplicates(subset=['filepath'], keep='last', inplace=True)
    save_csv(df, NO_READ_CSV)
