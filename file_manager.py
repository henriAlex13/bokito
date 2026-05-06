"""
Gestion physique des fichiers : indexation des sources et copie
vers les dossiers MATCH / PAS_MATCH avec arborescence MMAA/JJMMAA.
"""
import os
import shutil
import logging
from datetime import datetime, timedelta

from config import (
    MATCHED_DIR, PAS_MATCH_DIR,
    DAYS_THRESHOLD_NO_MATCH,
)
from storage import load_csv, log_copied_file

logger = logging.getLogger(__name__)


# ============================================================
# Indexation des fichiers source (perf : 1 seul os.walk)
# ============================================================

def build_source_index(root_path, min_ctime=None):
    """
    Parcourt root_path une seule fois et construit un index {filename: filepath}.

    OPTIMISATION : si min_ctime est fourni, le filtrage se fait au niveau des
    DOSSIERS (via leur ctime, date de création) et non des fichiers individuels.
    Les sous-dossiers créés avant min_ctime sont entièrement skippés (pas de
    descente). Cela évite des dizaines de milliers d'appels réseau sur
    lecteurs SMB/CIFS comme Y:/ ou Z:/.

    HYPOTHÈSE : les fichiers récents sont toujours dans des dossiers récents.
    Un fichier de janvier 2026 ne sera jamais dans un dossier de décembre 2025.

    En cas de doublons de noms, on garde le premier rencontré.

    Args:
        root_path: dossier racine à parcourir
        min_ctime: datetime optionnel. Si fourni, les sous-dossiers créés
                   avant cette date ne seront PAS explorés.

    Returns:
        dict {filename: filepath}
    """
    index = {}
    duplicates = 0
    pruned_dirs = 0
    ctime_errors = 0

    min_ts = min_ctime.timestamp() if min_ctime else None

    for root, dirs, files in os.walk(root_path):
        # Élagage : retirer les sous-dossiers trop anciens AVANT que os.walk
        # n'y descende. Modification IN-PLACE de dirs[] (important pour os.walk).
        if min_ts is not None:
            kept_dirs = []
            for d in dirs:
                full_dir = os.path.join(root, d)
                try:
                    if os.path.getctime(full_dir) >= min_ts:
                        kept_dirs.append(d)
                    else:
                        pruned_dirs += 1
                except OSError as e:
                    logger.warning(f"Impossible de lire ctime pour {full_dir}: {e}")
                    ctime_errors += 1
                    # En cas d'erreur, on garde le dossier (on préfère trop indexer
                    # que pas assez)
                    kept_dirs.append(d)
            dirs[:] = kept_dirs  # IMPORTANT : modification in-place

        # Indexer les fichiers du dossier courant
        for f in files:
            if f in index:
                duplicates += 1
                continue
            index[f] = os.path.join(root, f)

    msg = f"Index source {root_path} : {len(index)} fichier(s) retenu(s)"
    if min_ctime:
        msg += f" (dossiers depuis {min_ctime.date()})"
    if pruned_dirs:
        msg += f", {pruned_dirs} sous-dossier(s) anciens élagués"
    if duplicates:
        msg += f", {duplicates} doublon(s) ignoré(s)"
    if ctime_errors:
        msg += f", {ctime_errors} erreur(s) ctime"
    logger.info(msg)

    return index


# ============================================================
# Construction de l'arborescence cible
# ============================================================

def build_subdir_path(date_str):
    """
    Convertit une date AAMMJJ en (MMAA, JJMMAA).

    Exemple : '250915' -> ('0925', '150925')
    Retourne (None, None) si la date est invalide.
    """
    date_str = str(date_str).strip()

    if len(date_str) != 6 or not date_str.isdigit():
        return None, None

    yy, mm, dd = date_str[:2], date_str[2:4], date_str[4:6]
    return mm + yy, dd + mm + yy


# ============================================================
# Copie d'un fichier
# ============================================================

def copy_file(filename, date_str, source_index, dest_root,
              sub_type='', prefix='', copied_set=None):
    """
    Copie un fichier vers dest_root/sub_type/MMAA/JJMMAA/<prefix><filename>.

    Args:
        filename:     nom du fichier à chercher dans l'index
        date_str:     date AAMMJJ pour construire l'arborescence
        source_index: dict {filename: filepath} construit par build_source_index
        dest_root:    racine de destination (MATCHED_DIR ou PAS_MATCH_DIR)
        sub_type:     sous-dossier ('MX', 'MT' ou '')
        prefix:       préfixe à ajouter au nom du fichier (ex: 'match_id_')
        copied_set:   set des fichiers déjà copiés (pour éviter doublons)

    Returns:
        True si copie réussie ou déjà présent, False sinon.
    """
    # 1. Construire le chemin cible
    mmaa, jjmmaa = build_subdir_path(date_str)
    if not mmaa:
        logger.warning(f"Date invalide pour {filename}: {date_str!r}")
        return False

    dest_dir = os.path.join(dest_root, sub_type, mmaa, jjmmaa)
    dest_file = os.path.join(dest_dir, f"{prefix}{filename}")

    # 2. Court-circuit : déjà copié ?
    if copied_set is not None and dest_file in copied_set:
        return True

    if os.path.exists(dest_file):
        if copied_set is not None:
            copied_set.add(dest_file)
        return True

    # 3. Localiser la source via l'index
    source_path = source_index.get(filename)
    if not source_path or not os.path.exists(source_path):
        logger.warning(f"Fichier source introuvable : {filename}")
        return False

    # 4. Copie
    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(source_path, dest_file)
        logger.info(f"Copié : {filename} -> {dest_file}")

        if copied_set is not None:
            copied_set.add(dest_file)
            log_copied_file(dest_file)
        return True
    except Exception as e:
        logger.error(f"Erreur copie {filename}: {e}")
        return False


# ============================================================
# Copie des fichiers matchés
# ============================================================

def copy_matched_files(df_matches, mx_index, mt_index, copied_set):
    """Copie toutes les paires matchées vers MATCHED_DIR."""
    if df_matches.empty:
        logger.info("Aucun fichier matché à copier")
        return

    os.makedirs(MATCHED_DIR, exist_ok=True)

    for _, row in df_matches.iterrows():
        prefix = f"{row['match_id']}_"

        copy_file(
            filename=row['filename_mx'],
            date_str=row['date_mx'],
            source_index=mx_index,
            dest_root=MATCHED_DIR,
            prefix=prefix,
            copied_set=copied_set,
        )
        copy_file(
            filename=row['filename_mt'],
            date_str=row['date_mt'],
            source_index=mt_index,
            dest_root=MATCHED_DIR,
            prefix=prefix,
            copied_set=copied_set,
        )


# ============================================================
# Copie des fichiers non matchés (vieux)
# ============================================================

def copy_unmatched_old_files(csv_path, df_matches, source_index,
                              sub_type, copied_set,
                              days_threshold=DAYS_THRESHOLD_NO_MATCH):
    """
    Copie vers PAS_MATCH_DIR les fichiers qui :
    - ne sont pas dans les matches
    - sont plus vieux que `days_threshold` jours

    Args:
        csv_path:     CSV des fichiers extraits (MX103_CSV ou MT910_CSV)
        df_matches:   DataFrame des matches (pour identifier les non-matchés)
        source_index: dict {filename: filepath} de la source correspondante
        sub_type:     'MX' ou 'MT'
    """
    df_all = load_csv(csv_path)
    if df_all.empty:
        logger.info(f"Aucun fichier dans {os.path.basename(csv_path)}")
        return

    # Identifier les fichiers déjà matchés
    matched_col = {'MX': 'filename_mx', 'MT': 'filename_mt'}.get(sub_type)
    if not matched_col:
        logger.error(f"sub_type invalide : {sub_type}")
        return

    matched_files = (
        set(df_matches[matched_col]) if not df_matches.empty else set()
    )

    df_unmatched = df_all[~df_all['filename'].isin(matched_files)]
    if df_unmatched.empty:
        logger.info(f"Aucun fichier non matché pour {sub_type}")
        return

    # Filtrer par ancienneté
    now = datetime.now()
    threshold = timedelta(days=days_threshold)

    for _, row in df_unmatched.iterrows():
        date_str = str(row['date']).strip()
        if len(date_str) != 6:
            continue

        try:
            date_obj = datetime.strptime(date_str, "%y%m%d")
        except ValueError:
            logger.warning(f"Date invalide pour {row['filename']}: {date_str!r}")
            continue

        if (now - date_obj) > threshold:
            copy_file(
                filename=row['filename'],
                date_str=date_str,
                source_index=source_index,
                dest_root=PAS_MATCH_DIR,
                sub_type=sub_type,
                copied_set=copied_set,
            )
