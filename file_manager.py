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
# Helpers de matching de chemins
# ============================================================

WILDCARD = "*"


def _path_segments(path):
    """
    Décompose un chemin en segments (séparés par / ou \\), en lowercase.
    Le filename final n'est PAS inclus si path est un chemin vers un fichier.

    Exemple :
        'Y:/entrant/pacs.008/X/auto/file.pdf'
        -> ['y:', 'entrant', 'pacs.008', 'x', 'auto']
    """
    # Si path se termine par une extension, on retire le filename
    if os.path.splitext(path)[1]:
        path = os.path.dirname(path)
    normalized = path.replace('\\', '/').lower()
    return [seg for seg in normalized.split('/') if seg]


def _filter_matches_segments(segments, flt):
    """
    Vérifie si la fin de `segments` (liste de segments du dirname)
    matche exactement `flt` (filtre avec éventuels wildcards).

    Le filtre matche si les N derniers segments correspondent un à un
    aux N éléments du filtre, où :
    - '*' matche n'importe quel segment
    - tout autre élément doit être strictement égal au segment

    Exemple :
        segments = ['y:', 'entrant', 'pacs.008', '2026_01', 'auto']
        flt      = ['entrant', 'pacs.008', '*', 'auto']
        -> True (les 4 derniers segments matchent)
    """
    n = len(flt)
    if len(segments) < n:
        return False

    # Comparer les N derniers segments avec le filtre
    tail = segments[-n:]
    flt_lower = [t.lower() for t in flt]

    for seg, expected in zip(tail, flt_lower):
        if expected == WILDCARD:
            continue
        if seg != expected:
            return False
    return True


def path_matches_filter(path, subdir_filters):
    """
    Vérifie qu'un chemin satisfait au moins un des filtres.

    Le matching exige que les derniers segments du dirname correspondent
    exactement (avec wildcards) à un filtre. Les fichiers doivent donc
    être dans le dossier final exact, pas dans un sous-dossier.

    Exemple :
        path = 'Y:/entrant/pacs.008/2026_01/auto/file.pdf'
        filtre = ['entrant', 'pacs.008', '*', 'auto']
        -> True
    """
    segments = _path_segments(path)
    return any(_filter_matches_segments(segments, flt) for flt in subdir_filters)


def _can_descend_to_filter(full_dir, root_path, subdir_filters):
    """
    Détermine si descendre dans `full_dir` peut potentiellement mener à
    un chemin satisfaisant un filtre.

    Logique : à chaque niveau de profondeur dans le walk, on vérifie qu'au
    moins un filtre reste "compatible" avec le chemin construit jusque-là.

    Un filtre est compatible si, en alignant la fin de `segments` avec
    le DÉBUT du filtre, tous les segments alignés matchent (avec wildcards).
    Si on a déjà parcouru K segments du filtre, il en reste (N-K) à
    rencontrer en descendant.

    Args:
        full_dir:        chemin du sous-dossier candidat (sans filename)
        root_path:       racine du parcours
        subdir_filters:  liste de filtres
    """
    dir_segments = _path_segments(full_dir)
    root_segments = _path_segments(root_path)

    # Combien de segments avons-nous descendus sous root_path ?
    depth_under_root = len(dir_segments) - len(root_segments)
    if depth_under_root < 0:
        return True  # on n'a pas encore atteint root, on garde

    for flt in subdir_filters:
        # Si on est plus profond que le filtre, on a dépassé : pas un match
        # potentiel pour ce filtre (mais peut-être pour un autre).
        if depth_under_root > len(flt):
            continue

        # Aligner les `depth_under_root` derniers segments avec le DÉBUT du filtre.
        # Sauf qu'on ne sait pas où le filtre commence à matcher dans dir_segments.
        # Heuristique pratique : on essaie d'aligner la fin de dir_segments avec
        # un préfixe du filtre.
        #
        # Pour chaque longueur de préfixe k allant de 1 à depth_under_root, on
        # vérifie si les k derniers segments matchent les k premiers du filtre.
        # Si OUI pour au moins une longueur, le filtre reste possible.

        flt_lower = [t.lower() for t in flt]

        # Cas 1 : on n'a encore rien parcouru sous root → tout filtre est possible
        if depth_under_root == 0:
            return True

        # Cas 2 : on a parcouru K segments sous root.
        # On essaie d'aligner les K derniers segments (sous root) avec le préfixe
        # du filtre.
        relative = dir_segments[len(root_segments):]
        k = len(relative)

        # Vérifier si relative[-min(k, len(flt)):] matche le préfixe correspondant
        # du filtre.
        match_len = min(k, len(flt))
        prefix_flt = flt_lower[:match_len]
        suffix_relative = relative[-match_len:] if match_len > 0 else []

        ok = True
        for seg, expected in zip(suffix_relative, prefix_flt):
            if expected == WILDCARD:
                continue
            if seg != expected:
                ok = False
                break

        if ok:
            return True

    return False


# ============================================================
# Indexation des fichiers source (perf : 1 seul os.walk)
# ============================================================

def build_source_index(root_path, min_ctime=None, subdir_filters=None):
    """
    Parcourt root_path une seule fois et construit un index {filename: filepath}.

    Deux niveaux d'élagage pour minimiser les appels réseau :
    1. Par ctime : sous-dossiers créés avant min_ctime → skip
    2. Par filtres : sous-dossiers ne pouvant mener à aucun filtre → skip

    Le matching utilise des SEGMENTS de chemin (pas des sous-chaînes), avec
    support du wildcard '*' pour autoriser un niveau intermédiaire variable.
    Cela garantit qu'un terme comme 'auto' ne matche pas '2026_01_auto' ni
    un fichier nommé 'sgci_xxx.pdf' dans un mauvais dossier.

    Args:
        root_path:       dossier racine à parcourir
        min_ctime:       datetime optionnel pour le filtre ctime
        subdir_filters:  liste de listes de termes (avec '*' pour wildcard)

    Returns:
        dict {filename: filepath}
    """
    index = {}
    duplicates = 0
    pruned_dirs_old = 0
    pruned_dirs_filter = 0
    ctime_errors = 0

    min_ts = min_ctime.timestamp() if min_ctime else None

    for root, dirs, files in os.walk(root_path):
        # === Élagage des sous-dossiers (modification IN-PLACE) ===
        kept_dirs = []
        for d in dirs:
            full_dir = os.path.join(root, d)

            # Filtre 1 : ctime
            if min_ts is not None:
                try:
                    if os.path.getctime(full_dir) < min_ts:
                        pruned_dirs_old += 1
                        continue
                except OSError as e:
                    logger.warning(f"Impossible de lire ctime pour {full_dir}: {e}")
                    ctime_errors += 1
                    kept_dirs.append(d)
                    continue

            # Filtre 2 : sous-dossiers menant aux filtres pertinents
            if subdir_filters:
                if not _can_descend_to_filter(full_dir, root_path, subdir_filters):
                    pruned_dirs_filter += 1
                    continue

            kept_dirs.append(d)

        dirs[:] = kept_dirs

        # === Indexer les fichiers du dossier courant ===
        # On n'indexe les fichiers que si le dossier courant satisfait
        # exactement un filtre (matching par suffixe ordonné).
        if subdir_filters and not path_matches_filter(root, subdir_filters):
            continue

        for f in files:
            if f in index:
                duplicates += 1
                continue
            index[f] = os.path.join(root, f)

    msg = f"Index source {root_path} : {len(index)} fichier(s) retenu(s)"
    if min_ctime:
        msg += f" (dossiers depuis {min_ctime.date()})"
    if pruned_dirs_old:
        msg += f", {pruned_dirs_old} sous-dossier(s) anciens élagués"
    if pruned_dirs_filter:
        msg += f", {pruned_dirs_filter} sous-dossier(s) hors filtre élagués"
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
    """
    mmaa, jjmmaa = build_subdir_path(date_str)
    if not mmaa:
        logger.warning(f"Date invalide pour {filename}: {date_str!r}")
        return False

    dest_dir = os.path.join(dest_root, sub_type, mmaa, jjmmaa)
    dest_file = os.path.join(dest_dir, f"{prefix}{filename}")

    if copied_set is not None and dest_file in copied_set:
        return True

    if os.path.exists(dest_file):
        if copied_set is not None:
            copied_set.add(dest_file)
        return True

    source_path = source_index.get(filename)
    if not source_path or not os.path.exists(source_path):
        logger.warning(f"Fichier source introuvable : {filename}")
        return False

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
    """Copie vers PAS_MATCH_DIR les fichiers non matchés depuis plus de N jours."""
    df_all = load_csv(csv_path)
    if df_all.empty:
        logger.info(f"Aucun fichier dans {os.path.basename(csv_path)}")
        return

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
