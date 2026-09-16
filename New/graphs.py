from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLOTLY_BASE = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3", family="'Segoe UI', sans-serif"),
    margin=dict(l=10, r=10, t=52, b=10),
    height=300,
    hoverlabel=dict(bgcolor="#21262d", font_color="#e6edf3", bordercolor="#30363d"),
    xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=10)),
    yaxis=dict(showgrid=True, gridcolor="#30363d", zeroline=False, color="#8b949e", tickfont=dict(size=10)),
    title=dict(font=dict(size=15, color="#e6edf3", weight="bold"), x=0.02, xanchor="left"),
    legend=dict(font=dict(size=11, color="#e6edf3")),
)


def apply_layout(fig, **kw):
    cfg = dict(PLOTLY_BASE)
    cfg.update(kw)
    fig.update_layout(**cfg)
    return fig


def add_line_breaks(text, max_chars=10):
    words = text.split()
    line = ""
    new_text = ""
    for word in words:
        if len(line) + len(word) + 1 <= max_chars:
            line += (word + " ")
        else:
            new_text += line.rstrip() + "<br>"
            line = word + " "
    new_text += line.rstrip()
    return new_text


def kpis(df):
    total = df["Réf. Réclamation"].nunique() if "Réf. Réclamation" in df.columns else 0
    hd = (df["DELAI_RECLAMATION"] == "HORS DELAI").sum() if "DELAI_RECLAMATION" in df.columns else 0
    taux = round(hd / total * 100, 1) if total else 0
    fond = (df["NATURE"] == "FONDEE").sum() if "NATURE" in df.columns else 0
    return {"total": total, "hors_delai": hd, "taux_hors_delai": taux, "fondees": fond}


def fig_nature(data):
    nat = data.groupby("NATURE")["Réf. Réclamation"].count().reset_index(name='nombre')
    fig = px.pie(nat, values='nombre', names='NATURE', title="Répartition par nature", hole=0.55,
                 color_discrete_sequence=["#58a6ff", "#3fb950", "#f78166", "#ffa657"], template='plotly_dark')
    fig.update_traces(textinfo='percent+label', hovertemplate="<b>%{label}</b><br>%{value}<extra></extra>")
    apply_layout(fig)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5))
    return fig


def fig_evolution_mensuelle(data):
    ev = data.groupby("Mois")["Réf. Réclamation"].nunique().reset_index(name='nombre')
    ev['Mois'] = ev['Mois'].apply(lambda m: datetime(2000, int(m), 1).strftime('%b'))
    fig = go.Figure(go.Scatter(
        x=ev['Mois'], y=ev['nombre'], mode='lines+markers+text', text=ev['nombre'],
        textposition='top center', line=dict(color="#58a6ff", width=2.5),
        marker=dict(size=8, color="#58a6ff"), fill='tozeroy', fillcolor="rgba(88,166,255,0.08)",
        hovertemplate="<b>%{x}</b><br>%{y} réclamations<extra></extra>"))
    fig.update_layout(title="Évolution mensuelle des réclamations")
    apply_layout(fig)
    return fig


def fig_top_agences(data, top_n=10):
    ag = data.groupby("AGENCE")["Réf. Réclamation"].count().reset_index(name='nombre').sort_values('nombre').tail(top_n)
    fig = px.bar(ag, y="AGENCE", x='nombre', text='nombre', orientation='h', title=f'Top {top_n} agences',
                 color='nombre', color_continuous_scale=px.colors.sequential.Blues, template='plotly_dark')
    fig.update_traces(textfont_size=12, marker_line_width=0, hovertemplate="<b>%{y}</b><br>%{x} réclamations<extra></extra>")
    fig.update_layout(coloraxis_showscale=False)
    apply_layout(fig, xaxis=dict(visible=False))
    return fig


def fig_top_groupe(data, top_n=5):
    gr = data.groupby("GROUPE RESOLUTION")["Réf. Réclamation"].count().reset_index(name='nombre').sort_values('nombre', ascending=False).head(top_n)
    gr['lbl'] = gr['GROUPE RESOLUTION'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig = px.bar(gr, x='lbl', y='nombre', text='nombre', title=f"Top {top_n} — Groupe de résolution",
                 color='nombre', color_continuous_scale=px.colors.sequential.Purples, template='plotly_dark')
    fig.update_traces(textfont_size=12, marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    return fig


def fig_par_createur(data, top_n=10):
    cr = data.groupby("Créateur")["Réf. Réclamation"].count().reset_index(name='nombre').sort_values('nombre', ascending=False).head(top_n)
    cr['lbl'] = cr['Créateur'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig = px.bar(cr, x='lbl', y='nombre', text='nombre', title=f"Top {top_n} — Par créateur",
                 color='nombre', color_continuous_scale=px.colors.sequential.Reds, template='plotly_dark')
    fig.update_traces(textfont_size=12, marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    return fig


def fig_typologie(data):
    ty = data.groupby("Typologie")["Réf. Réclamation"].count().reset_index(name='nombre').sort_values('nombre', ascending=False)
    ty['lbl'] = ty['Typologie'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig = px.bar(ty, x='lbl', y='nombre', text='nombre', title="Répartition par typologie",
                 color='nombre', color_continuous_scale=px.colors.sequential.Sunset, template='plotly_dark')
    fig.update_traces(textfont_size=12, marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    return fig


def fig_delai(data):
    dl = data["DELAI_RECLAMATION"].value_counts().reset_index()
    dl.columns = ["d", "c"]
    fig = px.pie(dl, values='c', names='d', title="Respect des délais", hole=0.55,
                 color_discrete_map={"PAS HORS DELAI": "#3fb950", "HORS DELAI": "#f78166"}, template='plotly_dark')
    fig.update_traces(textinfo='percent+label')
    apply_layout(fig)
    return fig


def fig_canaux(data):
    cn = data.groupby("Canal de réception")["Réf. Réclamation"].count().reset_index(name='nombre').sort_values('nombre', ascending=False)
    cn['lbl'] = cn['Canal de réception'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig = px.bar(cn, x='lbl', y='nombre', text='nombre', title="Canaux de notification",
                 color='nombre', color_continuous_scale=px.colors.sequential.Teal, template='plotly_dark')
    fig.update_traces(textfont_size=12, marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    return fig


def sla_pivot_tables(df_sla, group_by_field):
    """Retourne (moyenne_par_etape, nombre_par_etape) pivotés sur SLA_ETAPE,
    indexés par group_by_field ('AGENCE', 'GROUPE RESOLUTION' ou 'Réf. Réclamation')."""
    if df_sla.empty or group_by_field not in df_sla.columns:
        return pd.DataFrame(), pd.DataFrame()
    mean_sla = df_sla.pivot_table(index=group_by_field, values='SLA_JOURS', columns='SLA_ETAPE', aggfunc='mean').reset_index()
    count_sla = df_sla.pivot_table(index=group_by_field, values='SLA_JOURS', columns='SLA_ETAPE', aggfunc='count').reset_index()
    return mean_sla.round(2), count_sla


def _sla_cell_color(val):
    """Vert si SLA respecté (valeur positive = marge restante), rouge si dépassé
    (valeur négative), neutre si nul ou non renseigné."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "color:#3fb950; font-weight:700;"
    elif v < 0:
        return "color:#f78166; font-weight:700;"
    return "color:#8b949e;"


def style_sla_table(df, id_col):
    """Applique la coloration vert/rouge/neutre sur toutes les colonnes sauf id_col."""
    if df.empty:
        return df
    value_cols = [c for c in df.columns if c != id_col]
    styler = df.style
    if hasattr(styler, "map"):
        return styler.map(_sla_cell_color, subset=value_cols)
    return styler.applymap(_sla_cell_color, subset=value_cols)
