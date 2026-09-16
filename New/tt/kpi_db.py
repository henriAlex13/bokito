import io
import sqlite3

import pandas as pd

DB_PATH = "kpi_historique.db"

MOIS_KW = ['JANV', 'FEV', 'FÉV', 'MARS', 'AVR', 'MAI', 'JUIN', 'JUIL',
           'AOUT', 'AOÛT', 'SEPT', 'OCT', 'NOV', 'DEC', 'DÉC']

MOIS_OPTIONS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

# Indicateurs CRC devant être affichés en pourcentage
PERCENT_KEYWORDS = ["occupation", "interaction", "joignabilité", "reitération",
                     "réitération", "réponse à la 1ère demande", "qualité"]


def mois_sort_key(mois_str):
    """Clé de tri chronologique pour une chaîne 'Mois Année' (ex: 'Janvier 2026')."""
    if not mois_str:
        return (9999, 99)
    parts = str(mois_str).rsplit(' ', 1)
    if len(parts) != 2:
        return (9999, 99)
    mois_nom, annee = parts
    try:
        m_idx = MOIS_OPTIONS.index(mois_nom)
    except ValueError:
        m_idx = 99
    try:
        a = int(annee)
    except ValueError:
        a = 9999
    return (a, m_idx)


def sort_mois_columns(df, id_cols):
    """Réordonne les colonnes d'un pivot : id_cols en premier, puis les colonnes
    mois triées chronologiquement (au lieu de l'ordre alphabétique par défaut)."""
    mois_cols = [c for c in df.columns if c not in id_cols]
    mois_cols_sorted = sorted(mois_cols, key=mois_sort_key)
    return df[list(id_cols) + mois_cols_sorted]


def format_percent(val):
    """Formate une valeur en pourcentage (ex: '0.87' ou '87' → '87%')."""
    if val is None:
        return val
    s = str(val).strip()
    if s in ('', 'nan', 'None', 'N/A'):
        return s
    s_clean = s.replace('%', '').replace(',', '.').strip()
    try:
        f = float(s_clean)
    except ValueError:
        return s
    if abs(f) <= 1:
        f *= 100
    return f"{int(f)}%" if f == int(f) else f"{f:.1f}%"

# ── Mapping UC → Agences (référentiel fixe) ──────────────────
UC_MAPPING = {
    "UC-ABIDJAN EST DEUX PLATEAUX": [
        "AGHIEN", "COCODY VALLONS", "LYCEE TECHNIQUE", "AGENCE COCODY CENTRE",
        "COCODY 2 PLATEAUX", "RUE DES JARDINS", "ANGRE DJIBI CENTRE",
    ],
    "UC-ABIDJAN CENTRE": [
        "PYRAMIDE", "AKWABA", "LONGCHAMPS", "DU PARC", "COMMERCE",
        "PRESTIGE", "PLATEAU SIEGE", "PRIVILEGE", "CITE FINANCIERE",
    ],
    "UC-ABIDJAN EST RIVIERA": [
        "BINGERVILLE", "ABATTA", "RIVIERA PALMERAIE", "RIVIERA GOLF",
        "RIVIERA ANONO", "RIVIERA SAINTE FAMILLE",
    ],
    "UC-ABIDJAN NORD": [
        "INDENIE", "WILLIAMSVILLE", "ADJAME MARCHE", "ADJAME LIBERTE",
        "AGBOVILLE", "ABOBO", "ABOBO SAMAKE", "ANYAMA", "PLATEAU-DOKUI",
    ],
    "UC-ABIDJAN OUEST": [
        "SONGON", "DABOU", "YOPOUGON ZONE INDUSTRIELLE", "YOPOUGON ANANERAIE",
        "YOPOUGON BEL AIR", "YOPOUGON SAINT ANDRE", "YOPOUGON NIANGON SUD",
        "YOPOUGON NIANGON NORD", "YOPOUGON FIGAYO",
    ],
    "UC-ABIDJAN SUD": [
        "ELITE", "MOSQUEE", "MARINE", "BIETRY", "NANAN YAMOUSSO",
        "MARCORY CENTRE", "AGENCE TOTAL", "AUTOROUTE", "ESPACE 1er PAUL LANGEVIN",
    ],
    "UC-ABIDJAN SUD COMOE": [
        "ABOISSO", "BONOUA", "KOUMASSI SAINT ETIENNE", "KOUMASSI REMBLAIS",
        "GRAND-BASSAM", "KOUMASSI-MARCHE", "VRIDI", "PORT BOUET",
    ],
    "UC-PROVINCE CENTRE-EST": [
        "DAOUKRO", "AGNIBILEKROU", "ADZOPE", "BONGOUANOU", "DIMBOKRO",
        "BONDOUKOU", "ABENGOUROU", "TOUMODI", "YAMOUSSOUKRO",
    ],
    "UC-PROVINCE CENTRE-NORD": [
        "SUCAF 2 FERKE", "TIEBISSOU", "BOUNDIALI", "ODIENNE", "KATIOLA",
        "KORHOGO", "FERKESSEDOUGOU", "BOUAKE COMMERCE", "TINGRELA",
    ],
    "UC-PROVINCE OUEST": [
        "GUIGLO", "AGENCE SEGUELA", "DUEKOUE", "DALOA", "ISSIA",
        "DANANE", "MAN", "BOUAFLE",
    ],
    "UC-PROVINCE SUD-OUEST": [
        "AGENCE TABOU", "OUME", "SASSANDRA", "SAN PEDRO", "TIASSALE",
        "GAGNOA", "SOUBRE", "DIVO", "SAN PEDRO BARDOT",
    ],
}
AGENCE_TO_UC = {ag: uc for uc, ags in UC_MAPPING.items() for ag in ags}


def get_uc_list():
    return sorted(UC_MAPPING.keys())


def get_agences_for_uc(uc=None):
    return UC_MAPPING.get(uc, []) if uc else sorted(AGENCE_TO_UC.keys())


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS kpi_crc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mois TEXT, indicateur TEXT, objectif TEXT, valeur TEXT,
        UNIQUE(mois, indicateur)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS kpi_sat_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mois TEXT, feuille TEXT, entite TEXT, valeur TEXT, uc TEXT, is_uc INTEGER,
        UNIQUE(mois, feuille, entite)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS kpi_sat_pro_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mois TEXT, feuille TEXT, entite TEXT, valeur TEXT, uc TEXT, is_uc INTEGER,
        UNIQUE(mois, feuille, entite)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS kpi_feuille1 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT, mois TEXT, segment TEXT, indicateur TEXT, valeur TEXT,
        UNIQUE(source, mois, segment, indicateur)
    )""")
    con.commit()
    con.close()


# ── Parsers ──────────────────────────────────────────────────

def parse_crc(raw_bytes: bytes, filename: str, mois: str):
    """KPI CRC.xlsx : col A=indicateur, col B=objectif, col C+=mois."""
    init_db()
    try:
        xf = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=0, header=None, engine='openpyxl')
        if xf.empty or xf.shape[0] < 2:
            return False, "Fichier vide ou structure invalide."

        header_row, best_score = None, 0
        for i in range(min(10, len(xf))):
            row_str = ' '.join([str(v).upper() for v in xf.iloc[i] if str(v).strip() not in ('nan', '')])
            score = sum(1 for k in MOIS_KW if k in row_str)
            if score > best_score:
                best_score, header_row = score, i
        if header_row is None:
            header_row = 2

        data_start = header_row + 1
        for i in range(header_row + 1, min(header_row + 5, len(xf))):
            indic = str(xf.iloc[i, 1]).strip()
            if indic and indic.upper() not in ('NAN', '', 'INDICATEURS DE PERFORMANCE', 'NOS REALISATIONS'):
                data_start = i
                break

        rows = []
        for i in range(data_start, len(xf)):
            indic = str(xf.iloc[i, 1]).strip()
            obj = str(xf.iloc[i, 2]).strip() if xf.shape[1] > 2 else ''
            if indic in ('nan', '') or indic.upper() == 'NAN':
                continue
            vals_row = xf.iloc[i, 3:].dropna() if xf.shape[1] > 3 else pd.Series(dtype=object)
            valeur = str(vals_row.iloc[-1]).strip() if len(vals_row) > 0 else 'N/A'
            rows.append((mois, indic, obj if obj != 'nan' else '', valeur))

        if not rows:
            return False, "Aucun indicateur trouvé — vérifiez la structure du fichier."
    except Exception as e:
        return False, f"Erreur lecture : {e}"

    try:
        con = sqlite3.connect(DB_PATH)
        con.executemany(
            "INSERT OR REPLACE INTO kpi_crc (mois, indicateur, objectif, valeur) VALUES (?,?,?,?)", rows
        )
        con.commit()
        con.close()
        return True, f"{len(rows)} indicateurs CRC sauvegardés pour {mois}"
    except Exception as e:
        return False, f"Erreur SQLite : {e}"


def _parse_feuille1(df, mois, source, con):
    rows = []
    hrow = 1
    for i in range(min(10, len(df))):
        row_str = ' '.join([str(v).upper() for v in df.iloc[i] if str(v).strip() != 'nan'])
        if any(k in row_str for k in MOIS_KW):
            hrow = i
            break

    mois_labels = []
    for j in range(2, df.shape[1]):
        v = str(df.iloc[hrow, j]).strip()
        if v and v.upper() != 'NAN':
            mois_labels.append((j, v))

    current_segment = None
    for i in range(hrow + 1, len(df)):
        seg_val = str(df.iloc[i, 0]).strip()
        indic_val = str(df.iloc[i, 1]).strip()
        if seg_val and seg_val.upper() not in ('NAN', ''):
            current_segment = seg_val.upper()
        if not indic_val or indic_val.upper() in ('NAN', '') or not current_segment:
            continue
        all_vals = [str(df.iloc[i, j]).strip() for j in range(2, df.shape[1])]
        if all(v in ('nan', '', 'NAN') for v in all_vals):
            continue
        for j, m_label in mois_labels:
            v = str(df.iloc[i, j]).strip()
            valeur = '' if v in ('nan', 'NAN', '') else v
            rows.append((source, mois, current_segment, indic_val, valeur))

    if rows:
        con.executemany(
            "INSERT OR REPLACE INTO kpi_feuille1 (source, mois, segment, indicateur, valeur) VALUES (?,?,?,?,?)",
            rows,
        )
    return len(rows)


def _parse_sat_generic(raw_bytes: bytes, mois: str, source: str, table: str):
    """Logique commune à SAT et SAT PRO : structure UC > Agences + Feuille1."""
    init_db()
    rows = []
    nb_f1 = 0
    try:
        xl = pd.ExcelFile(io.BytesIO(raw_bytes), engine='openpyxl')
        con = sqlite3.connect(DB_PATH)
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name, header=None)
            if df.empty:
                continue
            if sheet_name.strip().lower() in ("feuil1", "feuille1", "sheet1", "feuil 1"):
                nb_f1 = _parse_feuille1(df, mois, source, con)
                continue

            hrow = 1
            for i in range(min(10, len(df))):
                row_str = ' '.join([str(v).upper() for v in df.iloc[i] if str(v).strip() != 'nan'])
                if any(k in row_str for k in MOIS_KW):
                    hrow = i
                    break
            for i in range(hrow + 1, len(df)):
                entite = str(df.iloc[i, 0]).strip().upper()
                if not entite or entite in ('NAN', ''):
                    continue
                vals = df.iloc[i, 1:].dropna()
                valeur = str(vals.iloc[-1]).strip() if len(vals) > 0 else 'N/A'
                is_uc = 1 if entite in UC_MAPPING else 0
                uc_ref = entite if is_uc else AGENCE_TO_UC.get(entite, None)
                rows.append((mois, sheet_name, entite, valeur, uc_ref, is_uc))
        con.commit()
        con.close()
    except Exception as e:
        return False, f"Erreur lecture : {e}"

    if not rows and nb_f1 == 0:
        return False, "Aucune ligne trouvée dans le fichier."

    try:
        con = sqlite3.connect(DB_PATH)
        con.executemany(
            f"INSERT OR REPLACE INTO {table} (mois, feuille, entite, valeur, uc, is_uc) VALUES (?,?,?,?,?,?)",
            rows,
        )
        con.commit()
        con.close()
        nb_uc = sum(1 for r in rows if r[5] == 1)
        nb_ag = sum(1 for r in rows if r[5] == 0)
        label = "SAT" if table == "kpi_sat_v2" else "SAT PRO"
        return True, f"{len(rows)} lignes {label} ({nb_uc} UCs, {nb_ag} agences) + {nb_f1} lignes Feuille1"
    except Exception as e:
        return False, f"Erreur SQLite : {e}"


def parse_sat(raw_bytes: bytes, filename: str, mois: str):
    return _parse_sat_generic(raw_bytes, mois, "sat", "kpi_sat_v2")


def parse_sat_pro(raw_bytes: bytes, filename: str, mois: str):
    return _parse_sat_generic(raw_bytes, mois, "sat_pro", "kpi_sat_pro_v2")


# ── Lecture historique ───────────────────────────────────────

def delete_crc_month(mois: str):
    """Supprime toutes les données CRC d'un mois donné (fichier importé par erreur)."""
    init_db()
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM kpi_crc WHERE mois=?", (mois,))
    con.commit()
    con.close()


def get_crc_history(mois_filter=None):
    init_db()
    con = sqlite3.connect(DB_PATH)
    q = "SELECT * FROM kpi_crc"
    params = []
    if mois_filter:
        q += " WHERE mois=?"
        params.append(mois_filter)
    q += " ORDER BY mois"
    df = pd.read_sql(q, con, params=params)
    con.close()
    return df


def _get_sat_generic(table, feuille=None, uc=None, agences=None):
    init_db()
    con = sqlite3.connect(DB_PATH)
    q = f"SELECT * FROM {table} WHERE 1=1"
    params = []
    if feuille:
        q += " AND feuille=?"
        params.append(feuille)
    if uc:
        q += " AND uc=?"
        params.append(uc)
    if agences:
        placeholders = ','.join(['?'] * len(agences))
        q += f" AND entite IN ({placeholders})"
        params.extend(agences)
    q += " ORDER BY mois"
    df = pd.read_sql(q, con, params=params)
    con.close()
    return df


def get_sat_history(feuille=None, uc=None, agences=None):
    return _get_sat_generic("kpi_sat_v2", feuille, uc, agences)


def get_sat_pro_history(feuille=None, uc=None, agences=None):
    return _get_sat_generic("kpi_sat_pro_v2", feuille, uc, agences)


def get_feuille1_history(source, mois_filter=None):
    init_db()
    con = sqlite3.connect(DB_PATH)
    q = "SELECT * FROM kpi_feuille1 WHERE source=?"
    params = [source]
    if mois_filter:
        q += " AND mois=?"
        params.append(mois_filter)
    q += " ORDER BY mois, segment, indicateur"
    df = pd.read_sql(q, con, params=params)
    con.close()
    return df


def get_crc_mois_list():
    init_db()
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT DISTINCT mois FROM kpi_crc ORDER BY mois", con)
    con.close()
    return sorted(df["mois"].tolist(), key=mois_sort_key)


def get_mois_list():
    init_db()
    con = sqlite3.connect(DB_PATH)
    mois = []
    for table in ['kpi_crc', 'kpi_sat_v2', 'kpi_sat_pro_v2']:
        try:
            df = pd.read_sql(f"SELECT DISTINCT mois FROM {table}", con)
            mois.extend(df['mois'].tolist())
        except Exception:
            pass
    con.close()
    return sorted(set(mois))
