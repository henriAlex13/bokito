import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "reclamations_historique.db"

# Colonnes métier conservées telles que produites par processing.load_data()
# Note : SQLite ignore la casse pour l'unicité des noms de colonnes, donc on ne
# garde que les versions dérivées (AGENCE, GROUPE RESOLUTION) et pas les brutes.
COLUMNS = [
    "Réf. Réclamation", "Client", "Typologie", "Segment", "SEGMENTATION",
    "AGENCE", "GROUPE RESOLUTION",
    "Canal de réception", "Créateur", "Caractère de la réclamation", "NATURE",
    "Date de création", "Date de résolution", "Annee", "Mois",
    "DATE_RECLAMATION", "DELAI_RECLAMATION", "Treatment duration",
]


def init_db():
    con = sqlite3.connect(DB_PATH)
    cols_sql = ",\n".join([f'"{c}" TEXT' for c in COLUMNS if c != "Réf. Réclamation"])
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS reclamations (
            "Réf. Réclamation" TEXT PRIMARY KEY,
            {cols_sql},
            date_import TEXT,
            date_maj TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS reclamations_sla (
            "Réf. Réclamation" TEXT,
            "SLA_ETAPE" TEXT,
            "SLA_JOURS" REAL,
            "AGENCE" TEXT,
            "GROUPE RESOLUTION" TEXT,
            date_maj TEXT,
            PRIMARY KEY ("Réf. Réclamation", "SLA_ETAPE")
        )
    """)
    con.commit()
    con.close()


def upsert_reclamations(df: pd.DataFrame) -> int:
    """Insère ou met à jour chaque ticket (upsert par Réf. Réclamation).
    Retourne le nombre de lignes traitées."""
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    present_cols = [c for c in COLUMNS if c in df.columns]
    placeholders = ",".join(["?"] * (len(present_cols) + 2))  # + date_import, date_maj
    col_names = ",".join([f'"{c}"' for c in present_cols] + ["date_import", "date_maj"])
    update_clause = ",".join([f'"{c}"=excluded."{c}"' for c in present_cols if c != "Réf. Réclamation"])
    update_clause += ', date_maj=excluded.date_maj'

    sql = f"""
        INSERT INTO reclamations ({col_names})
        VALUES ({placeholders})
        ON CONFLICT("Réf. Réclamation") DO UPDATE SET {update_clause}
    """

    rows = []
    for _, row in df.iterrows():
        vals = []
        for c in present_cols:
            v = row.get(c)
            if pd.isna(v):
                vals.append(None)
            elif hasattr(v, "isoformat"):
                vals.append(v.isoformat())
            else:
                vals.append(str(v))
        vals.append(now)  # date_import (ignoré par UPDATE grâce à excluded)
        vals.append(now)  # date_maj
        rows.append(tuple(vals))

    cur.executemany(sql, rows)
    con.commit()
    con.close()
    return len(rows)


def get_all_reclamations() -> pd.DataFrame:
    init_db()
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM reclamations", con)
    con.close()
    for c in ["Date de création", "Date de résolution"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["Annee", "Mois", "DATE_RECLAMATION", "Treatment duration"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def upsert_sla(df: pd.DataFrame) -> int:
    """Enregistre chaque ligne SLA (une ligne = un ticket + une étape SLA).
    df doit contenir : Réf. Réclamation, SLA_ETAPE, SLA_JOURS, AGENCE, GROUPE RESOLUTION."""
    init_db()
    needed = ["Réf. Réclamation", "SLA_ETAPE", "SLA_JOURS", "AGENCE", "GROUPE RESOLUTION"]
    dff = df[[c for c in needed if c in df.columns]].dropna(subset=["SLA_ETAPE"])
    dff = dff[dff["SLA_ETAPE"].astype(str).str.strip() != ""]
    if dff.empty:
        return 0

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    sql = """
        INSERT INTO reclamations_sla ("Réf. Réclamation","SLA_ETAPE","SLA_JOURS","AGENCE","GROUPE RESOLUTION",date_maj)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT("Réf. Réclamation","SLA_ETAPE") DO UPDATE SET
            "SLA_JOURS"=excluded."SLA_JOURS",
            "AGENCE"=excluded."AGENCE",
            "GROUPE RESOLUTION"=excluded."GROUPE RESOLUTION",
            date_maj=excluded.date_maj
    """
    rows = [
        (r.get("Réf. Réclamation"), r.get("SLA_ETAPE"), r.get("SLA_JOURS"),
         r.get("AGENCE"), r.get("GROUPE RESOLUTION"), now)
        for _, r in dff.iterrows()
    ]
    cur.executemany(sql, rows)
    con.commit()
    con.close()
    return len(rows)


def get_sla_history() -> pd.DataFrame:
    init_db()
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM reclamations_sla', con)
    con.close()
    if "SLA_JOURS" in df.columns:
        df["SLA_JOURS"] = pd.to_numeric(df["SLA_JOURS"], errors="coerce")
    return df
