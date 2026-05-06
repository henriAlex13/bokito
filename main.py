"""
Point d'entrée du traitement SWIFT.

Flux :
1. Initialisation (logs, CSV)
2. Indexation des fichiers source (MX103 et MT910)
3. Extraction des nouveaux PDF -> CSV (avec filtre mtime >= START_DATE)
4. Matching MX103 <-> MT910
5. Copie des fichiers matchés (MATCH/) et non matchés vieux (PAS_MATCH/)
"""
import os
import logging
from datetime import datetime

from config import (
    OUTPUT_PATH, LOG_FILE, LOG_FORMAT,
    MX103_PATH, MT910_PATH,
    MX103_CSV, MT910_CSV,
    MX103_SUBDIR_FILTERS, MT910_SUBDIR_FILTERS,
    START_DATE,
)
from storage import (
    init_csv_files,
    append_extracted_files,
    get_already_processed_filenames,
    load_copied_files_set,
    load_no_read_set,
    log_no_read_file,
)
from pdf_extractor import extract_mx103_info, extract_mt910_info
from matcher import match_data
from file_manager import (
    build_source_index,
    copy_matched_files,
    copy_unmatched_old_files,
)


# ============================================================
# Configuration du logger
# ============================================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )

logger = logging.getLogger(__name__)


# ============================================================
# Extraction des nouveaux PDF
# ============================================================

def extract_new_pdfs(source_index, csv_path, extract_func,
                     subdir_filters, already_processed, no_read_set):
    """
    Parcourt l'index des fichiers source, extrait ceux qui :
    - sont des PDF
    - n'ont pas déjà été traités
    - ne sont pas dans le log NO_read
    - sont dans un sous-dossier matchant un des filtres
    - ont une date de modification (mtime) >= START_DATE

    Returns:
        Liste de dicts (records) à insérer dans le CSV.
    """
    new_records = []
    start_ts = START_DATE.timestamp()  # conversion en timestamp pour comparaison rapide

    # Compteurs pour le log de fin
    skipped_too_old = 0
    skipped_already = 0
    skipped_no_read = 0
    skipped_subdir = 0
    skipped_extension = 0
    skipped_mtime_error = 0

    for filename, filepath in source_index.items():
        # Filtre extension
        if not filename.lower().endswith('.pdf'):
            skipped_extension += 1
            continue

        # Filtre déjà traité
        if filename in already_processed:
            skipped_already += 1
            continue

        # Filtre déjà identifié comme illisible
        if filepath in no_read_set:
            skipped_no_read += 1
            continue

        # Filtre sous-dossier
        path_low = filepath.lower()
        if not any(all(f.lower() in path_low for f in flt)
                   for flt in subdir_filters):
            skipped_subdir += 1
            continue

        # Filtre date de modification >= START_DATE
        try:
            mtime = os.path.getmtime(filepath)
        except OSError as e:
            logger.warning(f"Impossible de lire mtime pour {filepath}: {e}")
            skipped_mtime_error += 1
            continue

        if mtime < start_ts:
            skipped_too_old += 1
            continue

        # Extraction
        info = extract_func(filepath)
        if info is None:
            log_no_read_file(filepath, reason="extraction échouée")
            continue

        new_records.append(info)

    logger.info(
        f"Filtrage : {len(new_records)} retenu(s), "
        f"{skipped_already} déjà traité(s), "
        f"{skipped_too_old} trop ancien(s), "
        f"{skipped_no_read} déjà NO_read, "
        f"{skipped_subdir} hors sous-dossier, "
        f"{skipped_extension} non-PDF, "
        f"{skipped_mtime_error} erreur mtime"
    )

    return new_records


# ============================================================
# Pipeline complet pour un type de message
# ============================================================

def process_message_type(label, source_path, csv_path, extract_func,
                          subdir_filters, no_read_set):
    """
    Traite un type de message (MX103 ou MT910) :
    1. Indexe la source
    2. Extrait les nouveaux PDF
    3. Met à jour le CSV

    Returns:
        L'index source (utile pour la phase de copie ultérieure).
    """
    logger.info(f"=== Traitement {label} ===")

    source_index = build_source_index(source_path)
    already_processed = get_already_processed_filenames(csv_path)

    new_records = extract_new_pdfs(
        source_index=source_index,
        csv_path=csv_path,
        extract_func=extract_func,
        subdir_filters=subdir_filters,
        already_processed=already_processed,
        no_read_set=no_read_set,
    )

    append_extracted_files(new_records, csv_path)
    return source_index


# ============================================================
# Main
# ============================================================

def main():
    setup_logging()
    logger.info(f"========== Démarrage : {datetime.now()} ==========")
    logger.info(f"Filtre date : fichiers modifiés depuis {START_DATE}")

    # 1. Préparation
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    init_csv_files()

    no_read_set = load_no_read_set()
    copied_set = load_copied_files_set()

    # 2. Extraction MX103
    mx_index = process_message_type(
        label="MX103 / PACS.008",
        source_path=MX103_PATH,
        csv_path=MX103_CSV,
        extract_func=extract_mx103_info,
        subdir_filters=MX103_SUBDIR_FILTERS,
        no_read_set=no_read_set,
    )

    # 3. Extraction MT910
    mt_index = process_message_type(
        label="MT910",
        source_path=MT910_PATH,
        csv_path=MT910_CSV,
        extract_func=extract_mt910_info,
        subdir_filters=MT910_SUBDIR_FILTERS,
        no_read_set=no_read_set,
    )

    # 4. Matching
    logger.info("=== Matching ===")
    df_matches = match_data()
    logger.info(f"{len(df_matches)} paire(s) trouvée(s)")

    # 5. Copies
    logger.info("=== Copie des fichiers ===")
    copy_matched_files(df_matches, mx_index, mt_index, copied_set)

    copy_unmatched_old_files(
        csv_path=MX103_CSV,
        df_matches=df_matches,
        source_index=mx_index,
        sub_type='MX',
        copied_set=copied_set,
    )
    copy_unmatched_old_files(
        csv_path=MT910_CSV,
        df_matches=df_matches,
        source_index=mt_index,
        sub_type='MT',
        copied_set=copied_set,
    )

    logger.info(f"========== Fin : {datetime.now()} ==========")


if __name__ == "__main__":
    main()
