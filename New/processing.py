import base64
import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
import unidecode

DURATION_PATTERNS = {
    'days': re.compile(r'(\d+)\s*[dDjJ]'),
    'hours': re.compile(r'(\d+)\s*[hH]'),
    'minutes': re.compile(r'(\d+)\s*[mM]'),
    'seconds': re.compile(r'(\d+)\s*[sS]'),
}


def convert_to_days(duration):
    if pd.isna(duration) or duration == '':
        return 0
    total_seconds = 0
    for unit, pattern in DURATION_PATTERNS.items():
        match = pattern.search(duration)
        if match:
            value = int(match.group(1))
            if unit == 'days':
                total_seconds += value * 86400
            elif unit == 'hours':
                total_seconds += value * 3600
            elif unit == 'minutes':
                total_seconds += value * 60
            elif unit == 'seconds':
                total_seconds += value
    return round(total_seconds / 86400, 2)


def categorize_segment(segment):
    if str(segment).startswith('101'):
        return 'PARTICULIER'
    elif str(segment).startswith('102'):
        return 'PROFESSIONNEL'
    elif segment == 'INCONNU':
        return 'INCONNU'
    else:
        return 'CORPORATE'


def load_data(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.replace("\n", " ").str.strip()

    cols_text = ["SLA Réclamation", "Typologie", "Segment", "Agence",
                 "Groupe de résolution", "Canal de réception", "Client"]
    for col in cols_text:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    df["SLA Réclamation"] = (
        df["SLA Réclamation"]
        .str.replace('[', '', regex=False)
        .str.replace('REC-', '', regex=False)
        .str.replace(']', '', regex=False)
    )
    # Une cellule peut contenir plusieurs étapes séparées par des virgules
    # (ex: "INITIALISATION: 3J,TRAITEMENT: 0J,VALIDATION: -1J"). On éclate
    # véritablement le dataframe (une ligne par étape, les autres colonnes
    # du ticket sont dupliquées), pas seulement la colonne.
    df["SLA Réclamation"] = df["SLA Réclamation"].str.split(',')
    df = df.explode("SLA Réclamation", ignore_index=True)
    df['SLA Réclamation'] = df['SLA Réclamation'].str.strip()
    df['SLA_ETAPE'] = df['SLA Réclamation'].apply(lambda x: x.split(':')[0].strip() if ':' in x else None)
    df['Value'] = df['SLA Réclamation'].apply(lambda x: x.split(':')[1].strip() if ':' in x else None)
    df['SEGMENTATION'] = df['Segment'].apply(categorize_segment)

    df["Caractère de la réclamation"] = df["Caractère de la réclamation"].fillna("INCONNU")
    df.loc[df["Caractère de la réclamation"] == 'Fondé avec faute SG', "NATURE"] = 'FONDEE'
    df.loc[df["Caractère de la réclamation"] == 'Fondé sans faute SG', "NATURE"] = 'FONDEE'
    df.loc[df["Caractère de la réclamation"] == 'Non fondée', "NATURE"] = 'NON FONDEE'
    df['NATURE'] = df['NATURE'].fillna('INCONNU')

    df['Date de création'] = pd.to_datetime(df['Date de création'].str.split(' ').str[0], format='%d-%m-%Y', errors='coerce')
    df['Date de résolution'] = pd.to_datetime(df['Date de résolution'].str.split(' ').str[0], format='%d-%m-%Y', errors='coerce')
    df['Annee'] = df['Date de création'].dt.year
    df['Mois'] = df['Date de création'].dt.month

    df["GROUPE RESOLUTION"] = df["Groupe de résolution"].str.replace('SGCI', '', regex=False)
    df["AGENCE"] = df["Agence"].str[6:]
    df["Typologie"] = df.Typologie.str.upper().apply(unidecode.unidecode).str.replace("'", " ", regex=False)
    df["DATE_AUJOURDUI"] = datetime.today()

    time_columns = ["Time Technical Study", "Temps Infos complémentaires", "Temps Traitemen",
                     "Temps SUPPORT", "Temps Traitée", "Temps A Terminer", "Temps Initialisation",
                     "Temps Valider Regularisation", "Time In the process of Régularisation",
                     "Temps Attente retour tiers"]
    for col in time_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') / 86400
        else:
            df[col] = 0

    df["Treatment duration"] = df['Durée de traitement (En J)'] if 'Durée de traitement (En J)' in df.columns else 0
    df["Duree Traitee"] = df['Value'].apply(convert_to_days)
    df["Value"] = df["Value"].fillna("").astype(str)
    df["signe"] = np.where(df["Value"].str.startswith("-"), -1, 1)

    df["Duree Traitee"] = pd.to_numeric(df["Duree Traitee"], errors='coerce').fillna(0).astype(int)
    df["signe"] = df["signe"].astype(int)
    df["SLA_JOURS"] = df["Duree Traitee"] * df["signe"]

    df['DATE_RECLAMATION'] = (
        df['Date de résolution'].where(df['Date de résolution'].notna(), df['DATE_AUJOURDUI'])
        .sub(df['Date de création']).dt.days
    )
    df['DELAI_RECLAMATION'] = np.where(df['DATE_RECLAMATION'] <= 30, 'PAS HORS DELAI', 'HORS DELAI')
    return df


def parse_contents(contents_bytes: bytes, filename: str):
    """contents_bytes : bytes bruts du fichier uploadé (st.file_uploader -> .getvalue())."""
    try:
        if filename.endswith('.csv'):
            df = None
            for h in range(6):
                candidate = pd.read_csv(io.BytesIO(contents_bytes), header=h)
                if "Réf. Réclamation" in candidate.columns:
                    df = candidate
                    break
            if df is None:
                return None, "Impossible de trouver l'entête contenant 'Réf. Réclamation'."
        elif filename.endswith(('.xlsx', '.xls')):
            df = None
            for h in range(6):
                temp_df = pd.read_excel(io.BytesIO(contents_bytes), engine='openpyxl', header=h)
                if "Réf. Réclamation" in temp_df.columns.astype(str):
                    df = temp_df
                    break
            if df is None:
                return None, "Impossible de trouver l'entête contenant 'Réf. Réclamation'."
        else:
            return None, "Type de fichier non pris en charge."
    except Exception as e:
        return None, f"Erreur : {e}"

    return df, ""
