import io
from datetime import datetime

import pandas as pd
import streamlit as st

import kpi_db
import style

MOIS_OPTIONS = kpi_db.MOIS_OPTIONS
ANNEE_OPTIONS = [str(a) for a in range(2024, 2028)]


def _empty_state(msg):
    st.info(msg)


def _style_uc_rows(df):
    """Colore les lignes UC (is_uc=1) en orange pour les distinguer des agences."""
    def _row_style(row):
        if row.get("is_uc") == 1:
            return ['background-color:#C0714F; color:white; font-weight:700;'] * len(row)
        return [''] * len(row)
    return df.style.apply(_row_style, axis=1)


def render_crc(mois_filter):
    df = kpi_db.get_crc_history(mois_filter)
    if df.empty:
        _empty_state("Importez le fichier KPI CRC.xlsx pour afficher les indicateurs.")
        return
    pivot = df.pivot_table(index=["indicateur", "objectif"], columns="mois", values="valeur", aggfunc="first").reset_index()
    pivot.columns.name = None
    style.section_title("Historique des indicateurs CRC")
    st.dataframe(pivot, use_container_width=True, height=420)
    _export_button("crc", mois_filter)


def _render_sat_like(history_getter, source_key, mois_filter, uc_filter, agence_filter, title_prefix, export_key):
    f1 = kpi_db.get_feuille1_history(source_key, mois_filter)
    if not f1.empty:
        style.section_title(f"{title_prefix} — Enquête à froid par segment")
        pivot_f1 = f1.pivot_table(index=["segment", "indicateur"], columns="mois", values="valeur", aggfunc="first").reset_index()
        pivot_f1.columns.name = None
        st.dataframe(pivot_f1, use_container_width=True, height=280)
        st.markdown("<div style='margin:10px 0;'></div>", unsafe_allow_html=True)

    agences_filtre = None
    if agence_filter:
        agences_filtre = agence_filter if isinstance(agence_filter, list) else [agence_filter]
    elif uc_filter:
        agences_filtre = kpi_db.get_agences_for_uc(uc_filter)

    df = history_getter(uc=uc_filter, agences=agences_filtre)
    if df.empty:
        _empty_state(f"Importez le fichier {title_prefix}.xlsx pour afficher les indicateurs.")
        return
    if mois_filter:
        df = df[df["mois"] == mois_filter]
    if df.empty:
        _empty_state("Aucune donnée pour cette combinaison de filtres.")
        return

    for feuille in df["feuille"].unique():
        dff = df[df["feuille"] == feuille]
        titre = feuille + (f" — {uc_filter}" if uc_filter else "")
        style.section_title(titre)
        pivot = dff.pivot_table(index="entite", columns="mois", values="valeur", aggfunc="first").reset_index()
        pivot.columns.name = None
        uc_info = dff.drop_duplicates("entite")[["entite", "is_uc"]]
        pivot = pivot.merge(uc_info, on="entite", how="left")
        display_cols = [c for c in pivot.columns if c != "is_uc"]
        try:
            styled = _style_uc_rows(pivot)
            st.dataframe(styled, column_order=display_cols, use_container_width=True, height=320)
        except Exception:
            st.dataframe(pivot[display_cols], use_container_width=True, height=320)
        st.markdown("<div style='margin:10px 0;'></div>", unsafe_allow_html=True)

    _export_button(export_key, mois_filter)


def render_sat(mois_filter, uc_filter, agence_filter):
    _render_sat_like(kpi_db.get_sat_history, "sat", mois_filter, uc_filter, agence_filter, "KPIS SAT", "sat")


def render_sat_pro(mois_filter, uc_filter, agence_filter):
    _render_sat_like(kpi_db.get_sat_pro_history, "sat_pro", mois_filter, uc_filter, agence_filter, "KPIS SAT PRO", "sat_pro")


def _export_button(tab, mois_filter):
    if st.button("⬇ Exporter en Excel", key=f"export_{tab}"):
        buf = io.BytesIO()
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            if tab == "crc":
                df = kpi_db.get_crc_history(mois_filter)
                pivot = pd.DataFrame({"Message": ["Aucune donnée"]}) if df.empty else (
                    df.pivot_table(index=["indicateur", "objectif"], columns="mois", values="valeur", aggfunc="first")
                    .reset_index().rename_axis(None, axis=1)
                )
                pivot.to_excel(writer, sheet_name="KPI CRC", index=False)
                fname = f"KPI_CRC_export_{ts}.xlsx"
            else:
                getter = kpi_db.get_sat_history if tab == "sat" else kpi_db.get_sat_pro_history
                df = getter()
                if mois_filter:
                    df = df[df["mois"] == mois_filter]
                if df.empty:
                    pd.DataFrame({"Message": ["Aucune donnée"]}).to_excel(writer, sheet_name=tab.upper(), index=False)
                else:
                    for feuille in df["feuille"].unique():
                        dff = df[df["feuille"] == feuille]
                        pivot = dff.pivot_table(index="entite", columns="mois", values="valeur", aggfunc="first").reset_index()
                        pivot.columns.name = None
                        pivot.to_excel(writer, sheet_name=feuille[:31], index=False)
                fname = f"KPIS_{tab.upper()}_export_{ts}.xlsx"
        st.download_button("📄 Télécharger le fichier", data=buf.getvalue(), file_name=fname,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{tab}")
