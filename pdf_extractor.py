"""
Extraction des informations métier depuis les PDF SWIFT.
- MX103 / PACS.008 : ordre de paiement
- MT910 : avis de crédit
"""
import os
import re
import logging
import fitz  # PyMuPDF

from config import MX103_MAX_PAGES, MT910_MAX_PAGES

logger = logging.getLogger(__name__)


# ============================================================
# Helpers
# ============================================================

def _open_pdf_text(filepath, max_pages):
    """
    Ouvre un PDF et retourne le texte concaténé des N premières pages.
    Retourne None si le fichier est illisible ou vide.
    """
    try:
        with fitz.open(filepath) as doc:
            num_pages = min(doc.page_count, max_pages)
            text = "".join(doc.load_page(i).get_text() or "" for i in range(num_pages))
    except Exception as e:
        logger.error(f"Erreur ouverture PDF {filepath}: {e}")
        return None

    if not text.strip():
        logger.warning(f"PDF vide ou non textuel : {filepath}")
        return None

    return text


def _extract_reference_from_filename(filename, position):
    """
    Extrait la référence depuis le nom de fichier (split par '_').

    Args:
        filename: nom du fichier (avec ou sans extension)
        position: index Python de l'élément à extraire

    Returns:
        La référence trimmée et en minuscules, ou "" si position invalide.
    """
    # On retire l'extension pour ne pas polluer la dernière position
    base = os.path.splitext(filename)[0]
    parts = base.split("_")

    if position >= len(parts):
        return ""

    return parts[position].strip().lower()


# ============================================================
# Extraction MX103 / PACS.008
# ============================================================

def extract_mx103_info(filepath):
    """
    Extrait les champs métier d'un MX103/PACS.008.
    Retourne un dict ou None en cas d'échec.

    Champs extraits :
        - montant          : montant de la transaction
        - date             : date de règlement (format AAMMJJ)
        - adresse_debtor   : nom du débiteur (sans espaces)
        - adresse_creditor : nom du créditeur (sans espaces)
        - cle_32A          : concaténation date + montant (sans séparateurs)
        - reference_mx     : référence extraite du nom de fichier (index 4)
    """
    text = _open_pdf_text(filepath, MX103_MAX_PAGES)
    if not text:
        return None

    filename = os.path.basename(filepath)

    # --- Référence depuis le nom de fichier (4e position en index Python)
    reference_mx = _extract_reference_from_filename(filename, position=4)
    if not reference_mx:
        logger.warning(f"[MX103] Référence introuvable dans le nom de fichier {filename}")

    # --- Montant : entre le 1er et le 2e '#'
    montant = ""
    parts = text.split("#")
    if len(parts) >= 2:
        montant = parts[1].strip()
    else:
        logger.warning(f"[MX103] Montant introuvable dans {filename}")

    # --- Date : après "InterbankSettlementDate:"
    date_formatted = ""
    match_date = re.search(r"InterbankSettlementDate:\s*([\d\-]+)", text)
    if match_date:
        date_raw = match_date.group(1)
        date_formatted = date_raw.replace("-", "")[2:]
    else:
        logger.warning(f"[MX103] Date introuvable dans {filename}")

    # --- Adresse Debtor : ligne "Name:" du bloc Debtor
    adresse_debtor = ""
    match_debtor = re.search(
        r"Debtor.*?Name:\s*([^\n]+)",
        text,
        re.DOTALL,
    )
    if match_debtor:
        adresse_debtor = match_debtor.group(1).strip().replace(" ", "")
    else:
        logger.warning(f"[MX103] Debtor.Name introuvable dans {filename}")

    # --- Adresse Creditor : ligne "Name:" du bloc Creditor
    adresse_creditor = ""
    match_creditor = re.search(
        r"Creditor.*?Name:\s*([^\n]+)",
        text,
        re.DOTALL,
    )
    if match_creditor:
        adresse_creditor = match_creditor.group(1).strip().replace(" ", "")
    else:
        logger.warning(f"[MX103] Creditor.Name introuvable dans {filename}")

    # --- Clé 32A : date + montant nettoyé
    cle_32A = ""
    if date_formatted and montant:
        montant_clean = montant.replace(".", "").replace(",", "")
        cle_32A = date_formatted + montant_clean

    return {
        "filename": filename,
        "filepath": filepath,
        "cle_32A": cle_32A,
        "adresse_debtor": adresse_debtor,
        "adresse_creditor": adresse_creditor,
        "date": date_formatted,
        "montant": montant,
        "reference_mx": reference_mx,
    }


# ============================================================
# Extraction MT910
# ============================================================

def extract_mt910_info(filepath):
    """
    Extrait les champs métier d'un MT910.
    Retourne un dict ou None en cas d'échec.

    Champs extraits :
        - date          : date de valeur (AAMMJJ)
        - montant       : montant
        - cle_32A       : concaténation des chiffres du bloc 32A
        - texte_72      : contenu du bloc 72 (sans espaces)
        - reference_mt  : référence extraite du nom de fichier (index 5)
    """
    text = _open_pdf_text(filepath, MT910_MAX_PAGES)
    if not text:
        return None

    filename = os.path.basename(filepath)

    # --- Référence depuis le nom de fichier (5e position en index Python)
    reference_mt = _extract_reference_from_filename(filename, position=5)
    if not reference_mt:
        logger.warning(f"[MT910] Référence introuvable dans le nom de fichier {filename}")

    date, montant, cle_32A, texte_72 = "", "", "", ""

    # --- Bloc 32A : date + montant
    if "32A:" in text:
        try:
            bloc_32A = text.split("32A:")[1].split("\n")[1:4]
            bloc_32A_clean = [e.replace(" ", "") for e in bloc_32A]

            date = next(
                (s.replace("#", "").replace("Date:", "")
                 for s in bloc_32A_clean if "Date:" in s),
                ""
            ).strip()

            montant = next(
                (s.replace("#", "").replace("Amount:", "").replace(",", "")
                 for s in bloc_32A_clean if "Amount:" in s),
                ""
            )

            cle_32A = "".join(re.findall(r"\d+", "".join(bloc_32A)))
        except Exception as e:
            logger.error(f"[MT910] Erreur extraction bloc 32A dans {filename}: {e}")
    else:
        logger.warning(f"[MT910] Bloc 32A absent dans {filename}")

    # --- Bloc 72 : informations expéditeur
    if "72:" in text:
        try:
            partie_72 = text.split("72:")[1]
            if "Receiver Information" in partie_72:
                partie_72 = partie_72.split("Receiver Information")[1]
            if "----------------" in partie_72:
                partie_72 = partie_72.split("----------------")[0]
            texte_72 = re.sub(r"\s+", "", partie_72)
        except Exception as e:
            logger.error(f"[MT910] Erreur extraction bloc 72 dans {filename}: {e}")
    else:
        logger.warning(f"[MT910] Bloc 72 absent dans {filename}")

    return {
        "filename": filename,
        "filepath": filepath,
        "cle_32A": cle_32A,
        "texte_72": texte_72,
        "date": date,
        "montant": montant,
        "reference_mt": reference_mt,
    }
