import streamlit as st
import pandas as pd

import db
import graphs
import processing
import style
import kpi_db
import kpi_views

st.set_page_config(page_title="Plateforme SGCI", layout="wide", page_icon="📋")
style.inject_css()

# ── Configuration des accès (à adapter / déplacer en variables d'environnement) ──
PASSWORDS = {
    "admin": "admin123",
    "consultation": "lecture123",
}

RESSOURCE_EXTERNE_URL = "https://did-spymarketbank-sgci.onrender.com/"

MOIS_NOMS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

FILTER_KEYS = ["f_ticket", "f_agence", "f_annee", "f_mois", "f_seg", "f_delai", "f_client"]


def login():
    st.markdown("<br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(
            '<div style="text-align:center; margin-bottom:24px;">'
            '<div style="font-size:40px;">📋</div>'
            '<h1 style="color:#e6edf3; margin-bottom:4px;">Plateforme Réclamations SGCI</h1>'
            '<div style="color:#8b949e; font-size:13px;">Connexion</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        role = st.selectbox(
            "Profil", ["consultation", "admin"],
            format_func=lambda r: "Admin (import)" if r == "admin" else "Consultation (lecture seule)",
        )
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", type="primary", use_container_width=True):
            if pwd == PASSWORDS.get(role):
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")


def sidebar_account():
    with st.sidebar:
        role_txt = "Admin" if st.session_state["role"] == "admin" else "Consultation"
        st.markdown(f"**👤 Profil :** {role_txt}")
        if st.button("Se déconnecter", use_container_width=True):
            del st.session_state["role"]
            st.rerun()
        st.divider()


def page_admin():
    style.section_title("🛠 Import d'un fichier réclamations")
    uploaded = st.file_uploader("Fichier réclamations (CSV ou Excel)", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        df_raw, error = processing.parse_contents(uploaded.getvalue(), uploaded.name)
        if error:
            st.error(error)
        else:
            with st.spinner("Traitement et enregistrement en base..."):
                df_clean = processing.load_data(df_raw)
                n = db.upsert_reclamations(df_clean)
                n_sla = db.upsert_sla(df_clean)
            st.success(
                f"✅ {n:,} tickets et {n_sla:,} lignes SLA enregistrés (upsert).".replace(",", " ")
            )

    st.markdown("<div style='margin:18px 0;'></div>", unsafe_allow_html=True)
    style.section_title("📚 Aperçu de l'historique en base")
    df_hist = db.get_all_reclamations()
    if df_hist.empty:
        st.info("Aucune donnée en base pour le moment.")
    else:
        st.caption(f"{len(df_hist):,} tickets en base".replace(",", " "))
        st.dataframe(df_hist.sort_values("date_maj", ascending=False), use_container_width=True, height=400)


def page_kpi_module(is_admin):
    with st.sidebar:
        style.section_title("📅 Période de référence")
        mois_sel = st.selectbox("Mois", kpi_views.MOIS_OPTIONS, key="kpi_mois", index=None, placeholder="Mois...")
        annee_sel = st.selectbox("Année", kpi_views.ANNEE_OPTIONS, key="kpi_annee", index=len(kpi_views.ANNEE_OPTIONS) - 3)

    if is_admin:
        with st.sidebar:
            st.divider()
            style.section_title("📥 Import mensuel")
            up_crc = st.file_uploader("📞 KPI CRC", type=["xlsx", "xls"], key="up_crc")
            up_sat = st.file_uploader("😊 KPIS SAT", type=["xlsx", "xls"], key="up_sat")
            up_sat_pro = st.file_uploader("⭐ KPIS SAT PRO", type=["xlsx", "xls"], key="up_sat_pro")

        mois_str = f"{mois_sel} {annee_sel}" if mois_sel and annee_sel else None

        for uploaded, parser, label in [
            (up_crc, kpi_db.parse_crc, "CRC"),
            (up_sat, kpi_db.parse_sat, "SAT"),
            (up_sat_pro, kpi_db.parse_sat_pro, "SAT PRO"),
        ]:
            if uploaded is not None:
                if not mois_str:
                    st.warning(f"⚠ Sélectionnez le mois et l'année avant d'importer le fichier {label}.")
                else:
                    ok, msg = parser(uploaded.getvalue(), uploaded.name, mois_str)
                    (st.success if ok else st.error)(f"{'✅' if ok else '❌'} {msg}")

        with st.sidebar:
            st.divider()
            style.section_title("🗑 Supprimer un import CRC erroné")
            crc_mois_opts = kpi_db.get_crc_mois_list()
            crc_mois_del = st.selectbox("Mois à supprimer", [None] + crc_mois_opts,
                                         format_func=lambda m: "Choisir..." if m is None else m, key="crc_del_mois")
            if crc_mois_del:
                if st.button(f"🗑 Supprimer {crc_mois_del}", key="btn_del_crc"):
                    kpi_db.delete_crc_month(crc_mois_del)
                    st.success(f"Données CRC de {crc_mois_del} supprimées.")
                    st.rerun()

    with st.sidebar:
        style.section_title("🗂 Filtrer l'affichage")
        mois_hist_opts = kpi_db.get_mois_list()
        mois_filter = st.selectbox("Mois (historique)", [None] + mois_hist_opts,
                                    format_func=lambda m: "Tous" if m is None else m, key="kpi_hist_filter")
        uc_filter = st.selectbox("UC", [None] + kpi_db.get_uc_list(),
                                  format_func=lambda u: "Toutes" if u is None else u, key="kpi_uc_filter")
        agence_opts = kpi_db.get_agences_for_uc(uc_filter)
        agence_filter = st.multiselect("Agence", agence_opts, key="kpi_agence_filter")

    tab_crc, tab_sat, tab_sat_pro = st.tabs(["📞 KPI CRC", "😊 SAT RETAIL", "⭐ SAT PRO"])
    with tab_crc:
        kpi_views.render_crc(mois_filter)
    with tab_sat:
        kpi_views.render_sat(mois_filter, uc_filter, agence_filter)
    with tab_sat_pro:
        kpi_views.render_sat_pro(mois_filter, uc_filter, agence_filter)


def _reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def apply_filters(df):
    """Filtres liés entre eux : les options de chaque filtre sont recalculées
    en fonction des valeurs déjà sélectionnées dans les AUTRES filtres,
    y compris la recherche client."""

    # La recherche client est appliquée en amont : elle réduit aussi les
    # options des autres filtres (dont Ticket).
    client_val = st.session_state.get("f_client", "")
    base_df = df
    if client_val and "Client" in base_df.columns:
        base_df = base_df[base_df["Client"].astype(str).str.contains(client_val, case=False, na=False)]

    current = {
        "Réf. Réclamation": st.session_state.get("f_ticket"),
        "AGENCE": st.session_state.get("f_agence", []),
        "Annee": st.session_state.get("f_annee", []),
        "Mois": st.session_state.get("f_mois", []),
        "SEGMENTATION": st.session_state.get("f_seg", []),
        "DELAI_RECLAMATION": st.session_state.get("f_delai", []),
    }

    def filtered(dframe, exclude_key=None):
        out = dframe
        for key, val in current.items():
            if key == exclude_key or val in (None, [], ""):
                continue
            out = out[out[key].isin(val)] if isinstance(val, list) else out[out[key] == val]
        return out

    with st.sidebar:
        style.section_title("⚙ Filtres")

        ticket_opts = sorted(filtered(base_df, "Réf. Réclamation")["Réf. Réclamation"].dropna().unique())
        if st.session_state.get("f_ticket") not in ([None] + ticket_opts):
            st.session_state["f_ticket"] = None
        st.selectbox("🎫 Ticket", [None] + ticket_opts,
                     format_func=lambda x: "Tous" if x is None else x, key="f_ticket")

        agence_opts = sorted(filtered(base_df, "AGENCE")["AGENCE"].dropna().unique())
        st.session_state["f_agence"] = [v for v in st.session_state.get("f_agence", []) if v in agence_opts]
        st.multiselect("🏢 Agence", agence_opts, key="f_agence")

        annee_opts = sorted(filtered(base_df, "Annee")["Annee"].dropna().unique().astype(int).tolist())
        st.session_state["f_annee"] = [v for v in st.session_state.get("f_annee", []) if v in annee_opts]
        st.multiselect("📅 Année", annee_opts, key="f_annee")

        mois_opts = sorted(filtered(base_df, "Mois")["Mois"].dropna().unique().astype(int).tolist())
        st.session_state["f_mois"] = [v for v in st.session_state.get("f_mois", []) if v in mois_opts]
        st.multiselect("🗓 Mois", mois_opts, format_func=lambda m: MOIS_NOMS.get(m, m), key="f_mois")

        seg_opts = sorted(filtered(base_df, "SEGMENTATION")["SEGMENTATION"].dropna().unique())
        st.session_state["f_seg"] = [v for v in st.session_state.get("f_seg", []) if v in seg_opts]
        st.multiselect("👤 Segmentation", seg_opts, key="f_seg")

        delai_opts = sorted(filtered(base_df, "DELAI_RECLAMATION")["DELAI_RECLAMATION"].dropna().unique())
        st.session_state["f_delai"] = [v for v in st.session_state.get("f_delai", []) if v in delai_opts]
        st.multiselect("⏱ Délai", delai_opts, key="f_delai")

        st.text_input("🔍 Rechercher un client", key="f_client")

        st.button("↺ Réinitialiser les filtres", use_container_width=True, on_click=_reset_filters)

    # Recalcule avec les valeurs définitives de ce cycle (incluant le ticket)
    current["Réf. Réclamation"] = st.session_state.get("f_ticket")
    df_final = filtered(base_df, exclude_key=None)
    return df_final


def page_consultation():
    df = db.get_all_reclamations()
    if df.empty:
        st.info("Aucune donnée disponible pour le moment.")
        return

    df_f = apply_filters(df)
    if df_f.empty:
        st.warning("Aucune réclamation ne correspond à ces filtres.")
        return

    k = graphs.kpis(df_f)
    style.kpi_row([
        ("Total réclamations", f"{k['total']:,}".replace(",", " "), "📋", "#58a6ff"),
        ("Hors délai", f"{k['hors_delai']:,}".replace(",", " "), "⚠️", "#f78166"),
        ("Taux hors délai", f"{k['taux_hors_delai']}%", "📊", "#ffa657"),
        ("Fondées", f"{k['fondees']:,}".replace(",", " "), "✅", "#3fb950"),
    ])

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Vue générale", "👥 Par groupe", "🎫 Par créateur", "📡 Canaux / Délais", "📋 SLA PAR"]
    )

    with tab1:
        cA, cB, cC = st.columns(3)
        with cA:
            st.plotly_chart(graphs.fig_nature(df_f), use_container_width=True, key="chart_nature")
        with cB:
            st.plotly_chart(graphs.fig_evolution_mensuelle(df_f), use_container_width=True, key="chart_evolution")
        with cC:
            st.plotly_chart(graphs.fig_top_agences(df_f), use_container_width=True, key="chart_top_agences_1")

    with tab2:
        cA, cB = st.columns(2)
        with cA:
            st.plotly_chart(graphs.fig_top_groupe(df_f), use_container_width=True, key="chart_top_groupe")
        with cB:
            st.plotly_chart(graphs.fig_top_agences(df_f), use_container_width=True, key="chart_top_agences_2")

    with tab3:
        cA, cB = st.columns(2)
        with cA:
            if "Créateur" in df_f.columns:
                st.plotly_chart(graphs.fig_par_createur(df_f), use_container_width=True, key="chart_par_createur")
        with cB:
            st.plotly_chart(graphs.fig_typologie(df_f), use_container_width=True, key="chart_typologie_1")

    with tab4:
        cA, cB, cC = st.columns(3)
        with cA:
            st.plotly_chart(graphs.fig_delai(df_f), use_container_width=True, key="chart_delai")
        with cB:
            st.plotly_chart(graphs.fig_canaux(df_f), use_container_width=True, key="chart_canaux")
        with cC:
            st.plotly_chart(graphs.fig_typologie(df_f), use_container_width=True, key="chart_typologie_2")

    with tab5:
        df_sla = db.get_sla_history()
        tickets_filtres = set(df_f["Réf. Réclamation"].unique())
        df_sla_f = df_sla[df_sla["Réf. Réclamation"].isin(tickets_filtres)]

        if df_sla_f.empty:
            st.info("Aucune donnée SLA disponible pour cette sélection.")
        else:
            group_choice = st.radio(
                "Regrouper par :", ["GROUPE RESOLUTION", "AGENCE", "Réf. Réclamation"],
                format_func=lambda g: {"GROUPE RESOLUTION": "Groupe de résolution",
                                        "AGENCE": "Agence", "Réf. Réclamation": "Ticket"}[g],
                horizontal=True,
            )
            mean_sla, count_sla = graphs.sla_pivot_tables(df_sla_f, group_choice)

            style.section_title(f"Moyenne des SLA (jours) par {group_choice}")
            st.dataframe(graphs.style_sla_table(mean_sla, group_choice), use_container_width=True, height=350)

            style.section_title(f"Nombre d'entrées par {group_choice}")
            st.dataframe(count_sla, use_container_width=True, height=350)

    st.markdown("<div style='margin:14px 0;'></div>", unsafe_allow_html=True)
    with st.expander("📄 Détail des tickets"):
        st.dataframe(df_f, use_container_width=True, height=400)


def page_accueil():
    style.home_intro("Plateforme Réclamations SGCI", "Choisissez un module pour continuer.")

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(key="home_card_reclamations"):
            style.home_card_static("📊", "Dashboard Réclamations",
                                    "Analysez les réclamations, SLA, agences et segments.", "#58a6ff")
            if st.button("Ouvrir le dashboard", key="btn_go_reclamations", use_container_width=True):
                st.session_state["espace"] = "reclamations"
                st.rerun()
    with c2:
        with st.container(key="home_card_externe"):
            style.home_card_static("🌐", "Ressource Externe",
                                    "Accédez à une ressource de référence externe.", "#3fb950")
            st.link_button("Ouvrir le lien", RESSOURCE_EXTERNE_URL, use_container_width=True)
    with c3:
        with st.container(key="home_card_kpi"):
            style.home_card_static("📈", "Tableau de Bord KPI",
                                    "Suivez les KPI : CRC, Satisfaction, SAT PRO.", "#ffa657")
            if st.button("Ouvrir le module KPI", key="btn_go_kpi", use_container_width=True):
                st.session_state["espace"] = "kpi"
                st.rerun()


def main():
    if "role" not in st.session_state:
        login()
        return

    is_admin = st.session_state["role"] == "admin"
    sidebar_account()

    espace = st.session_state.get("espace")

    if espace not in ("reclamations", "kpi"):
        page_accueil()
        return

    role_label = "🛠 Admin" if is_admin else "🔎 Consultation"
    if st.button("← Accueil", key="btn_back_home"):
        st.session_state["espace"] = None
        st.rerun()

    if espace == "reclamations":
        style.header("Plateforme Réclamations SGCI", "Suivi et historique des réclamations clients", role_label)
        if is_admin:
            tab_import, tab_consult = st.tabs(["🛠 Admin", "🔎 Consultation"])
            with tab_import:
                page_admin()
            with tab_consult:
                page_consultation()
        else:
            page_consultation()

    else:
        style.header("Tableau de Bord KPI", "CRC, Satisfaction et SAT PRO", role_label)
        page_kpi_module(is_admin)


if __name__ == "__main__":
    main()
