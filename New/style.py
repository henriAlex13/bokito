import streamlit as st

CUSTOM_CSS = """
<style>
:root {
    --bg: #0d1117;
    --sidebar: #161b22;
    --card: #1c2128;
    --card2: #21262d;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f78166;
    --orange: #ffa657;
    --muted: #8b949e;
    --text: #e6edf3;
    --border: #30363d;
}

.stApp {
    background-color: var(--bg);
}

section[data-testid="stSidebar"] {
    background-color: var(--sidebar);
    border-right: 1px solid var(--border);
}

/* Header */
.dashboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 22px;
    background-color: var(--sidebar);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 22px;
}
.dashboard-header h1 {
    color: var(--text);
    font-size: 20px;
    font-weight: 800;
    margin: 0;
}
.dashboard-header .subtitle {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
}
.role-badge {
    background-color: rgba(88,166,255,0.12);
    color: var(--accent);
    border: 1px solid rgba(88,166,255,0.35);
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

/* KPI cards */
.kpi-row { display: flex; gap: 14px; margin-bottom: 22px; flex-wrap: wrap; }
.kpi-card {
    flex: 1;
    min-width: 180px;
    background-color: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
}
.kpi-card .kpi-label {
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.kpi-card .kpi-value {
    font-size: 28px;
    font-weight: 800;
    line-height: 1;
}

/* Section titles */
.section-title {
    color: var(--text);
    font-weight: 700;
    font-size: 15px;
    margin: 6px 0 12px 0;
    padding-left: 10px;
    border-left: 3px solid var(--accent);
}

/* Tabs */
button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 14px;
}
button[data-baseweb="tab"] p {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: var(--muted) !important;
}
button[data-baseweb="tab"][aria-selected="true"] p {
    color: var(--accent) !important;
}

/* Radio buttons (ex: choix de regroupement SLA) */
div[data-testid="stRadio"] label p {
    color: var(--text) !important;
    font-size: 13px !important;
}

/* Expander */
details summary p, details summary span {
    color: var(--text) !important;
    font-weight: 600 !important;
}

/* Chart containers */
div[data-testid="stPlotlyChart"] {
    background-color: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 6px;
}

/* Sidebar widget labels */
section[data-testid="stSidebar"] label {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* Reduce default top padding */
.block-container { padding-top: 1.4rem; }

/* ── Page d'accueil : cartes de modules ── */
.home-wrap {
    max-width: 980px;
    margin: 40px auto 0 auto;
    text-align: center;
}
.home-wrap .home-logo { font-size: 40px; margin-bottom: 16px; }
.home-wrap h1 {
    color: var(--text);
    font-weight: 800;
    font-size: 30px;
    margin-bottom: 6px;
}
.home-wrap .home-subtitle {
    color: var(--muted);
    font-size: 15px;
    margin-bottom: 40px;
}
.home-grid {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    justify-content: center;
}
.home-card {
    flex: 1;
    min-width: 240px;
    max-width: 300px;
    background-color: var(--card);
    border: 1px solid var(--border);
    border-top: 3px solid var(--card-accent, var(--accent));
    border-radius: 12px;
    padding: 28px 22px;
    text-align: center;
    text-decoration: none;
    display: block;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.home-card:hover {
    transform: translateY(-3px);
    border-color: var(--card-accent, var(--accent));
}
.home-card .home-icon { font-size: 34px; margin-bottom: 12px; }
.home-card .home-title {
    color: var(--text);
    font-weight: 700;
    font-size: 18px;
    margin-bottom: 8px;
}
.home-card .home-desc {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 20px;
    min-height: 40px;
}
.home-card .home-btn {
    display: block;
    width: 100%;
    padding: 10px 0;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    color: #ffffff !important;
    background-color: var(--card-accent, var(--accent));
}

/* Bouton retour accueil */
.back-home-btn {
    display: inline-block;
    color: var(--muted) !important;
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 12px;
}
.back-home-btn:hover { color: var(--accent) !important; border-color: var(--accent); }
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def header(title, subtitle, role_label):
    html = (
        f'<div class="dashboard-header">'
        f'<div><h1>{title}</h1><div class="subtitle">{subtitle}</div></div>'
        f'<div class="role-badge">{role_label}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def kpi_row(cards):
    """cards: liste de (label, value, icon, color_hex)"""
    items = "".join(
        f'<div class="kpi-card" style="border-left:3px solid {color};">'
        f'<div class="kpi-label">{icon} {label}</div>'
        f'<div class="kpi-value" style="color:{color};">{value}</div>'
        f'</div>'
        for label, value, icon, color in cards
    )
    st.markdown(f'<div class="kpi-row">{items}</div>', unsafe_allow_html=True)


def section_title(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def home_page(title, subtitle, cards):
    """cards: liste de dicts {icon, title, desc, color, href, btn_label, external(bool)}"""
    cards_html = "".join(
        f'<a class="home-card" style="--card-accent:{c["color"]};" href="{c["href"]}"'
        f'{" target=\'_blank\'" if c.get("external") else ""}>'
        f'<div class="home-icon">{c["icon"]}</div>'
        f'<div class="home-title">{c["title"]}</div>'
        f'<div class="home-desc">{c["desc"]}</div>'
        f'<span class="home-btn">{c["btn_label"]}</span>'
        f'</a>'
        for c in cards
    )
    html = (
        f'<div class="home-wrap">'
        f'<div class="home-logo">📋</div>'
        f'<h1>{title}</h1>'
        f'<div class="home-subtitle">{subtitle}</div>'
        f'<div class="home-grid">{cards_html}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def back_home_link():
    st.markdown('<a class="back-home-btn" href="?">← Accueil</a>', unsafe_allow_html=True)
