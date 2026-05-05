"""
Configuration centrale du traitement SWIFT.
Tous les chemins et constantes se trouvent ici.
"""
import os

# ============================================================
# CHEMINS SOURCES (à ajuster selon environnement)
# ============================================================

# Production
# MX103_PATH = 'Y:/'
# MT910_PATH = 'Z:/SWIFT_SGCI'
# OUTPUT_PATH = 'Y:/TRAITEMENT_MX_MT910'

# Développement / test
MX103_PATH = 'C:/Users/5368/Documents/DONNEES_D/ALEX_l/SWIFT/new/mx'
MT910_PATH = 'C:/Users/5368/Documents/DONNEES_D/ALEX_l/SWIFT/new/mt'
OUTPUT_PATH = 'C:/Users/5368/Documents/DONNEES_D/ALEX_l/SWIFT/SWIFT'

# ============================================================
# DOSSIERS DE SORTIE
# ============================================================

CSV_DIR = os.path.join(OUTPUT_PATH, "csv_data")
MATCHED_DIR = os.path.join(OUTPUT_PATH, "MATCH")
PAS_MATCH_DIR = os.path.join(OUTPUT_PATH, "PAS_MATCH")

# ============================================================
# FICHIERS CSV
# ============================================================

MX103_CSV = os.path.join(CSV_DIR, "mx103_files.csv")
MT910_CSV = os.path.join(CSV_DIR, "mt910_files.csv")
MATCHES_CSV = os.path.join(CSV_DIR, "matches.csv")
COPIED_LOG_CSV = os.path.join(CSV_DIR, "copied_files_log.csv")
NO_READ_CSV = os.path.join(CSV_DIR, "no_read_files.csv")

# ============================================================
# FILTRES DE SOUS-DOSSIERS (chemins à scanner)
# ============================================================

# Pour les MX103 : on scanne 2 sous-arborescences
MX103_SUBDIR_FILTERS = [
    ["entrant", "pacs.008", "manu", "sgci"],
    ["entrant", "pacs.008", "auto"],
]

# Pour les MT910 : un seul filtre
MT910_SUBDIR_FILTERS = [
    ["entrant", "mt910"],
]

# ============================================================
# PARAMÈTRES MÉTIER
# ============================================================

# Nombre de jours après lesquels un fichier non matché part en "PAS_MATCH"
DAYS_THRESHOLD_NO_MATCH = 10

# Nombre max de pages PDF à lire pour l'extraction
MX103_MAX_PAGES = 2
MT910_MAX_PAGES = 1

# ============================================================
# LOGGING
# ============================================================

LOG_FILE = "process_swift.log"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
