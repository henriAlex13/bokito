import dash
from dash import dash_table, dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import io
import unidecode
from datetime import datetime
import re
import numpy as np

image_path = 'assets/logo.png'

items = [
    dbc.DropdownMenuItem("GROUPE DE RESOLUTION", id="item-1"),
    dbc.DropdownMenuItem("AGENCE", id="item-2"),
    dbc.DropdownMenuItem("TICKET", id="item-3"),
]

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)

# ── Palette centralisée
C = {
    "bg":      "#0d1117", "sidebar": "#161b22", "card":   "#1c2128",
    "card2":   "#21262d", "accent":  "#58a6ff", "green":  "#3fb950",
    "red":     "#f78166", "orange":  "#ffa657", "muted":  "#8b949e",
    "text":    "#e6edf3", "border":  "#30363d", "violet": "#6e40c9",
}
PLOTLY_BASE = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e6edf3", family="'Segoe UI', sans-serif"),
    margin=dict(l=12, r=12, t=48, b=12),
    hoverlabel=dict(bgcolor="#21262d", font_color="#e6edf3", bordercolor="#30363d"),
    xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor="#30363d", zeroline=False, color="#8b949e", tickfont=dict(size=11)),
)
def apply_layout(fig, **kw):
    cfg = dict(PLOTLY_BASE); cfg.update(kw); fig.update_layout(**cfg); return fig

card_style  = {"borderRadius": "12px", "border": f"1px solid #30363d",
               "backgroundColor": "#1c2128", "padding": "16px", "marginBottom": "16px"}
btn_style   = {"borderRadius": "8px", "fontWeight": "600", "fontSize": "13px",
               "border": "none", "cursor": "pointer", "letterSpacing": "0.3px"}
label_style = {"color": "#8b949e", "fontWeight": "500", "fontSize": "11px", "marginBottom": "5px",
               "display": "block", "textTransform": "uppercase", "letterSpacing": "0.8px"}
title_style = {"color": "#e6edf3", "fontWeight": "700", "marginBottom": "15px"}

def kpi_card(label, value, icon, color, suffix=""):
    return dbc.Col(html.Div([
        html.Div([
            html.Span(icon, style={"fontSize":"20px","marginRight":"8px"}),
            html.Span(label, style={"fontSize":"11px","color":"#8b949e","textTransform":"uppercase",
                                    "letterSpacing":"0.8px","fontWeight":"600"}),
        ], style={"display":"flex","alignItems":"center","marginBottom":"8px"}),
        html.Div(f"{value}{suffix}", style={"fontSize":"26px","fontWeight":"800","color":color,"lineHeight":"1"}),
    ], style={
        "backgroundColor":"#1c2128","border":"1px solid #30363d",
        "borderLeft":f"3px solid {color}","borderRadius":"10px",
        "padding":"14px 18px","marginBottom":"16px",
    }), width=3)

def kpi_row(df):
    total = df["Complaint reference"].nunique() if "Complaint reference" in df.columns else 0
    hd    = (df["DELAI_RECLAMATION"]=="HORS DELAI").sum() if "DELAI_RECLAMATION" in df.columns else 0
    taux  = round(hd/total*100,1) if total else 0
    fond  = (df["NATURE"]=="FONDEE").sum() if "NATURE" in df.columns else 0
    return dbc.Row([
        kpi_card("Total réclamations", f"{total:,}".replace(","," "), "📋", "#58a6ff"),
        kpi_card("Hors délai",         f"{hd:,}".replace(","," "),   "⚠️", "#f78166"),
        kpi_card("Taux hors délai",    taux,                          "📊", "#ffa657", "%"),
        kpi_card("Fondées",            f"{fond:,}".replace(","," "), "✅", "#3fb950"),
    ], className="mb-2")

DURATION_PATTERNS = {
    'days': re.compile(r'(\d+)\s*[dDjJ]'), 'hours': re.compile(r'(\d+)\s*[hH]'),
    'minutes': re.compile(r'(\d+)\s*[mM]'), 'seconds': re.compile(r'(\d+)\s*[sS]')
}

def convert_to_days(duration):
    if pd.isna(duration) or duration == '': return 0
    total_seconds = 0
    for unit, pattern in DURATION_PATTERNS.items():
        match = pattern.search(duration)
        if match:
            value = int(match.group(1))
            if unit == 'days': total_seconds += value * 86400
            elif unit == 'hours': total_seconds += value * 3600
            elif unit == 'minutes': total_seconds += value * 60
            elif unit == 'seconds': total_seconds += value
    return round(total_seconds / 86400, 2)

def categorize_segment(segment):
    if str(segment).startswith('101'): return 'PARTICULIER'
    elif str(segment).startswith('102'): return 'PROFESSIONNEL'
    elif segment == 'INCONNU': return 'INCONNU'
    else: return 'CORPORATE'

def load_data(df):
    df.columns = df.columns.str.replace("\n", " ")
    df["Claim SLA"] = df["Claim SLA"].str.replace('[', "", regex=False).str.replace('REC', "", regex=False).str.replace('-', "", regex=False).str.replace(']', "", regex=False)
    df['Claim SLA'] = df['Claim SLA'].str.split(',').explode().reset_index(drop=True)
    df['Claim SLA'] = df['Claim SLA'].str.strip()
    df['SLA_ETAPE'] = df['Claim SLA'].apply(lambda x: x.split(':')[0].strip() if ':' in x else None)
    df['Value'] = df['Claim SLA'].apply(lambda x: x.split(':')[1].strip() if ':' in x else None)
    df['SEGMENTATION'] = df['Segment'].apply(categorize_segment)
    df["Nature of the claim"] = df["Nature of the claim"].fillna("INCONNU")
    df.loc[df["Nature of the claim"] == 'Fondé avec faute SG', "NATURE"] = 'FONDEE'
    df.loc[df["Nature of the claim"] == 'Fondé sans faute SG', "NATURE"] = 'FONDEE'
    df.loc[df["Nature of the claim"] == 'Non fondée', "NATURE"] = 'NON FONDEE'
    df['NATURE'] = df['NATURE'].fillna('INCONNU')
    df['Date of creation'] = pd.to_datetime(df['Date of creation'].str.split(' ').str[0], format='%d-%m-%Y', errors='coerce')
    df['Resolved date'] = pd.to_datetime(df['Resolved date'].str.split(' ').str[0], format='%d-%m-%Y', errors='coerce')
    df['Annee'] = df['Date of creation'].dt.year
    df['Mois'] = df['Date of creation'].dt.month
    df["GROUPE RESOLUTION"] = df["Resolution group"].str.replace('SGCI', "", regex=False)
    df["AGENCE"] = df["Branch"].str[6:]
    df["Typology"] = df.Typology.str.upper().apply(unidecode.unidecode).str.replace("'", " ", regex=False)
    df["DATE_AUJOURDUI"] = datetime.today()
    time_columns = ["Time Technical Study", "Time Additional information", "Time Treatment",
                    "Time SUPPORT", "Time Treated", "Time To Complete", "Time Initialization",
                    "Time Validate Regularisation", "Time In the process of regularization", "Time Third party return waiting"]
    for col in time_columns:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce') / 86400
        else: df[col] = 0
    df["Treatment duration"] = df['Treatment duration (In Days)'].apply(convert_to_days) if 'Treatment duration (In Days)' in df.columns else 0
    df["Duree Traitee"] = df['Value'].apply(convert_to_days)
    df['signe'] = np.where(df["Value"].str[0] == "-", -1, 1)
    df["Duree Traitee"] = pd.to_numeric(df["Duree Traitee"], errors='coerce').fillna(0).astype(int)
    df["signe"] = df["signe"].astype(int)
    df["SLA_JOURS"] = df["Duree Traitee"] * df["signe"]
    df['DATE_RECLAMATION'] = df['Resolved date'].where(df['Resolved date'].notna(), df['DATE_AUJOURDUI']).sub(df['Date of creation']).dt.days
    df['DELAI_RECLAMATION'] = np.where(df['DATE_RECLAMATION'] <= 30, 'PAS HORS DELAI', 'HORS DELAI')
    return df

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if filename.endswith('.csv'): df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=7)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'): df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl', header=7)
        else: return None, "Type de fichier non pris en charge."
    except Exception as e: return None, f"Erreur : {e}"
    return df, ""

def create_datatable_from_df(df, page_size=10):
    def style_sla_cells(dataframe):
        styles = []
        for i, row in dataframe.iterrows():
            for col in dataframe.columns:
                if col == dataframe.columns[0]: continue
                value = row[col]
                if pd.isnull(value): continue
                try: val_float = float(value)
                except: continue
                if val_float > 0: styles.append({'if': {'row_index': i, 'column_id': col}, 'color': '#2ecc71', 'fontWeight': 'bold'})
                elif val_float < 0: styles.append({'if': {'row_index': i, 'column_id': col}, 'color': '#e74c3c', 'fontWeight': 'bold'})
        return styles
    return dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df.columns], data=df.to_dict('records'), page_size=page_size,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'minWidth': '120px', 'whiteSpace': 'normal',
                    'color': 'white', 'backgroundColor': '#22272e', 'border': 'none'},
        style_header={'backgroundColor': '#2b303a', 'fontWeight': 'bold', 'color': 'white', 'border': 'none'},
        style_data_conditional=style_sla_cells(df), fill_width=True)

def add_line_breaks(text, max_chars=10):
    words = text.split(); line = ""; new_text = ""
    for word in words:
        if len(line) + len(word) + 1 <= max_chars: line += (word + " ")
        else: new_text += line.rstrip() + "<br>"; line = word + " "
    new_text += line.rstrip()
    return new_text

def generate_view_1(data):
    graphs = [dbc.Col(kpi_row(data), width=12)]
    # Donut nature
    nat = data.groupby("NATURE")["Complaint reference"].count().reset_index(name='nombre')
    fig1 = px.pie(nat, values='nombre', names='NATURE', title="Répartition par nature",
                  hole=0.55, color_discrete_sequence=["#58a6ff","#3fb950","#f78166","#ffa657"], template='plotly_dark')
    fig1.update_traces(textinfo='percent+label', hovertemplate="<b>%{label}</b><br>%{value}<extra></extra>")
    apply_layout(fig1)
    fig1.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig1, config={"displayModeBar":False}), style=card_style), width=6))
    # Line évolution avec aire
    ev = data.groupby("Mois")["Complaint reference"].nunique().reset_index(name='nombre')
    ev['Mois'] = ev['Mois'].apply(lambda m: datetime(2000, m, 1).strftime('%b'))
    fig2 = go.Figure(go.Scatter(
        x=ev['Mois'], y=ev['nombre'], mode='lines+markers+text',
        text=ev['nombre'], textposition='top center',
        line=dict(color="#58a6ff", width=2.5), marker=dict(size=8, color="#58a6ff"),
        fill='tozeroy', fillcolor="rgba(88,166,255,0.08)",
        hovertemplate="<b>%{x}</b><br>%{y} réclamations<extra></extra>",
    ))
    fig2.update_layout(title="Évolution mensuelle des réclamations")
    apply_layout(fig2)
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig2, config={"displayModeBar":False}), style=card_style), width=6))
    # Bar agences
    ag = data.groupby("AGENCE")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre').tail(10)
    fig3 = px.bar(ag, y="AGENCE", x='nombre', text='nombre', orientation='h',
                  title='Top 10 agences', color='nombre',
                  color_continuous_scale=px.colors.sequential.Blues, template='plotly_dark')
    fig3.update_traces(textfont_size=12, marker_line_width=0,
                       hovertemplate="<b>%{y}</b><br>%{x} réclamations<extra></extra>")
    fig3.update_layout(coloraxis_showscale=False)
    apply_layout(fig3, xaxis=dict(visible=False))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig3, config={"displayModeBar":False}), style=card_style), width=12))
    return graphs

def generate_view_2(data):
    graphs = [dbc.Col(kpi_row(data), width=12)]
    gr = data.groupby("GROUPE RESOLUTION")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre', ascending=False).head(5)
    gr['lbl'] = gr['GROUPE RESOLUTION'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig1 = px.bar(gr, x='lbl', y='nombre', text='nombre', title="Top 5 — Groupe de résolution",
                  color='nombre', color_continuous_scale=px.colors.sequential.Purples, template='plotly_dark')
    fig1.update_traces(textfont_size=12, marker_line_width=0)
    fig1.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig1, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig1, config={"displayModeBar":False}), style=card_style), width=6))
    ag = data.groupby("AGENCE")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre').tail(10)
    fig2 = px.bar(ag, y='AGENCE', x='nombre', text='nombre', orientation='h', title='Top 10 agences',
                  color='nombre', color_continuous_scale=px.colors.sequential.Teal, template='plotly_dark')
    fig2.update_traces(textfont_size=12, marker_line_width=0)
    fig2.update_layout(coloraxis_showscale=False)
    apply_layout(fig2, xaxis=dict(visible=False))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig2, config={"displayModeBar":False}), style=card_style), width=6))
    return graphs

def generate_view_3(data):
    graphs = [dbc.Col(kpi_row(data), width=12)]
    if 'Creator' in data.columns:
        cr = data.groupby("Creator")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre', ascending=False).head(10)
        cr['lbl'] = cr['Creator'].apply(lambda x: add_line_breaks(x, max_chars=15))
        fig1 = px.bar(cr, x='lbl', y='nombre', text='nombre', title="Top 10 — Par créateur",
                      color='nombre', color_continuous_scale=px.colors.sequential.Reds, template='plotly_dark')
        fig1.update_traces(textfont_size=12, marker_line_width=0)
        fig1.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
        apply_layout(fig1, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
        graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig1, config={"displayModeBar":False}), style=card_style), width=12))
    ty = data.groupby("Typology")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre', ascending=False)
    ty['lbl'] = ty['Typology'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig2 = px.bar(ty, x='lbl', y='nombre', text='nombre', title="Répartition par typologie",
                  color='nombre', color_continuous_scale=px.colors.sequential.Sunset, template='plotly_dark')
    fig2.update_traces(textfont_size=12, marker_line_width=0)
    fig2.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig2, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig2, config={"displayModeBar":False}), style=card_style), width=12))
    return graphs

def generate_view_4(data):
    graphs = [dbc.Col(kpi_row(data), width=12)]
    # Donut délai
    dl = data["DELAI_RECLAMATION"].value_counts().reset_index(); dl.columns=["d","c"]
    fig0 = px.pie(dl, values='c', names='d', title="Respect des délais", hole=0.55,
                  color_discrete_map={"PAS HORS DELAI":"#3fb950","HORS DELAI":"#f78166"}, template='plotly_dark')
    fig0.update_traces(textinfo='percent+label')
    apply_layout(fig0)
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig0, config={"displayModeBar":False}), style=card_style), width=6))
    cn = data.groupby("Client notification channel")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre', ascending=False)
    cn['lbl'] = cn['Client notification channel'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig1 = px.bar(cn, x='lbl', y='nombre', text='nombre', title="Canaux de notification",
                  color='nombre', color_continuous_scale=px.colors.sequential.Teal, template='plotly_dark')
    fig1.update_traces(textfont_size=12, marker_line_width=0)
    fig1.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig1, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig1, config={"displayModeBar":False}), style=card_style), width=6))
    ty = data.groupby("Typology")["Complaint reference"].count().reset_index(name='nombre').sort_values('nombre', ascending=False)
    ty['lbl'] = ty['Typology'].apply(lambda x: add_line_breaks(x, max_chars=15))
    fig2 = px.bar(ty, x='lbl', y='nombre', text='nombre', title="Répartition par typologie",
                  color='nombre', color_continuous_scale=px.colors.sequential.Sunset, template='plotly_dark')
    fig2.update_traces(textfont_size=12, marker_line_width=0)
    fig2.update_layout(coloraxis_showscale=False, xaxis_tickangle=0)
    apply_layout(fig2, yaxis=dict(visible=False), xaxis=dict(showgrid=False, zeroline=False, color="#8b949e", tickfont=dict(size=11)))
    graphs.append(dbc.Col(html.Div(dcc.Graph(figure=fig2, config={"displayModeBar":False}), style=card_style), width=12))
    return graphs

def generate_sla_table(data, group_by_field):
    mean_sla = data.pivot_table(index=group_by_field, values='SLA_JOURS', columns=['SLA_ETAPE'], aggfunc='mean').reset_index()
    count_sla = data.pivot_table(index=group_by_field, values='SLA_JOURS', columns=['SLA_ETAPE'], aggfunc='count').reset_index()
    mean_sla_rounded = mean_sla.round(2)
    tables = [
        html.Div(html.H5(f"Moyenne des SLA par {group_by_field}", style={"color":"white","backgroundColor":"#6a0dad","padding":"8px 12px","borderRadius":"8px","fontWeight":"bold","marginTop":"10px","marginBottom":"10px","textAlign":"center"})),
        create_datatable_from_df(mean_sla_rounded, page_size=10),
        html.Div(html.H5(f"Nombre d'entrées SLA par {group_by_field}", style={"color":"white","backgroundColor":"#6a0dad","padding":"8px 12px","borderRadius":"8px","fontWeight":"bold","marginTop":"20px","marginBottom":"10px","textAlign":"center"})),
        create_datatable_from_df(count_sla, page_size=10)
    ]
    return [dbc.Card(tables, style=card_style)]

def generate_sla_ticket_table(data):
    mean_sla = data.pivot_table(index='Complaint reference', values='SLA_JOURS', columns=['SLA_ETAPE'], aggfunc='mean').reset_index()
    mean_sla_rounded = mean_sla.round(2)
    table = [
        html.Div(html.H5("Moyenne des SLA par Ticket", style={"color":"white","backgroundColor":"#6a0dad","padding":"8px 12px","borderRadius":"8px","fontWeight":"bold","marginTop":"10px","marginBottom":"10px","textAlign":"center"})),
        create_datatable_from_df(mean_sla_rounded, page_size=10)
    ]
    return [dbc.Card(table, style=card_style)]

graph_mapping = {
    "btn-1": generate_view_1, "btn-2": generate_view_2,
    "btn-3": generate_view_3, "btn-4": generate_view_4,
    "item-1": lambda data: generate_sla_table(data, 'GROUPE RESOLUTION'),
    "item-2": lambda data: generate_sla_table(data, 'AGENCE'),
    "item-3": generate_sla_ticket_table
}

# ── PAGE ACCUEIL ─────────────────────────────────────────────────────────────
accueil = html.Div([
    html.Div([
        html.Img(src=image_path, style={'height': '80px', 'marginBottom': '24px'}),
        html.H1("Plateforme Réclamations SGCI", style={"color":"white","fontWeight":"800","fontSize":"32px","marginBottom":"12px"}),
        html.P("Choisissez un module pour continuer.", style={"color":"#8b949e","fontSize":"16px","marginBottom":"48px"}),
        html.Div([
            # Bouton 1 — Dashboard
            html.Div([
                html.Div("📊", style={"fontSize":"36px","marginBottom":"12px"}),
                html.H4("Dashboard Réclamations", style={"color":"white","fontWeight":"700","marginBottom":"8px"}),
                html.P("Analysez les réclamations, SLA, agences et segments.", style={"color":"#8b949e","fontSize":"13px","marginBottom":"20px"}),
                dbc.Button("Ouvrir le dashboard", id="btn-open-dashboard", color="primary",
                           style={"borderRadius":"8px","fontWeight":"600","width":"100%"}),
            ], style={"backgroundColor":"#1c2128","border":"1px solid #30363d","borderTop":"3px solid #58a6ff",
                      "borderRadius":"12px","padding":"28px","flex":"1","minWidth":"220px","textAlign":"center"}),
            # Bouton 2 — Lien externe
            html.Div([
                html.Div("🌐", style={"fontSize":"36px","marginBottom":"12px"}),
                html.H4("Ressource Externe", style={"color":"white","fontWeight":"700","marginBottom":"8px"}),
                html.P("Accédez à une ressource de référence externe.", style={"color":"#8b949e","fontSize":"13px","marginBottom":"20px"}),
                html.A(dbc.Button("Ouvrir le lien", color="success",
                           style={"borderRadius":"8px","fontWeight":"600","width":"100%"}),
                       href="https://fr.wikipedia.org/wiki/Lionel_Messi", target="_blank"),
            ], style={"backgroundColor":"#1c2128","border":"1px solid #30363d","borderTop":"3px solid #3fb950",
                      "borderRadius":"12px","padding":"28px","flex":"1","minWidth":"220px","textAlign":"center"}),
            # Bouton 3 — Page future
            html.Div([
                html.Div("🚧", style={"fontSize":"36px","marginBottom":"12px"}),
                html.H4("Module en cours", style={"color":"white","fontWeight":"700","marginBottom":"8px"}),
                html.P("Ce module est en cours de développement.", style={"color":"#8b949e","fontSize":"13px","marginBottom":"20px"}),
                dbc.Button("Bientôt disponible", id="btn-open-module", color="warning",
                           style={"borderRadius":"8px","fontWeight":"600","width":"100%"}),
            ], style={"backgroundColor":"#1c2128","border":"1px solid #30363d","borderTop":"3px solid #ffa657",
                      "borderRadius":"12px","padding":"28px","flex":"1","minWidth":"220px","textAlign":"center"}),
        ], style={"display":"flex","gap":"20px","flexWrap":"wrap","justifyContent":"center"}),
    ], style={"maxWidth":"900px","margin":"0 auto","textAlign":"center"}),
], style={"backgroundColor":"#0d1117","minHeight":"100vh","display":"flex",
          "alignItems":"center","justifyContent":"center","padding":"40px 20px"})

# ── DASHBOARD (original inchangé) ────────────────────────────────────────────
DD_STYLE = {"color": "#000", "fontSize": "13px"}

def filter_block(label, comp):
    return html.Div([html.Label(label, style=label_style), comp,
                     html.Div(style={"marginBottom": "14px"})])

dashboard = dbc.Container(fluid=True,
    style={"backgroundColor": "#0d1117", "minHeight": "100vh", "padding": "0"},
    children=[
        # ── Topbar ──
        html.Div([
            dbc.Row([
                dbc.Col(html.Img(src=image_path, style={"height": "38px"}), width="auto"),
                dbc.Col(html.Span("Dashboard Réclamations", style={
                    "color": "#e6edf3", "fontWeight": "700", "fontSize": "17px", "lineHeight": "38px",
                }), width="auto"),
                dbc.Col(
                    dbc.Button("← Accueil", id="btn-retour-accueil", color="secondary", size="sm",
                               style={**btn_style, "fontSize": "12px"}),
                    width="auto", style={"marginLeft": "auto"}
                ),
            ], align="center"),
        ], style={
            "backgroundColor": "#161b22", "borderBottom": "1px solid #30363d",
            "padding": "12px 24px", "position": "sticky", "top": "0", "zIndex": "100",
        }),
        dbc.Row([
            # ── Sidebar filtres ──
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Span("⚙ ", style={"opacity": "0.7"}),
                        html.Span("Filtres", style={"color": "#e6edf3", "fontWeight": "700",
                                                     "fontSize": "13px", "textTransform": "uppercase", "letterSpacing": "1px"}),
                    ], style={"marginBottom": "18px", "paddingBottom": "12px", "borderBottom": "1px solid #30363d"}),
                    filter_block("🎫 Ticket",     dcc.Dropdown(id="ticket-filter",      clearable=True, style=DD_STYLE)),
                    filter_block("🏢 Agence",     dcc.Dropdown(id="agence-filter",      multi=True,     style=DD_STYLE)),
                    filter_block("📅 Année",      dcc.Dropdown(id="annee-dropdown",     clearable=True, style=DD_STYLE)),
                    filter_block("🗓 Mois",       dcc.Dropdown(id="mois-dropdown",      clearable=True, style=DD_STYLE)),
                    filter_block("👤 Segmentation",dcc.Dropdown(id="segmentation-filter",clearable=True,style=DD_STYLE)),
                    filter_block("⏱ Délai",      dcc.Dropdown(id="delai-filter",       multi=True,     style=DD_STYLE)),
                    dbc.Button([html.I(className="bi bi-arrow-counterclockwise me-2"), "Réinitialiser"],
                               id="reset-filters", color="danger", outline=True, size="sm",
                               className="w-100 mt-1", style={**btn_style, "fontSize": "12px"}),
                    dcc.Upload(id="upload-data",
                        children=html.Div([
                            html.Span("☁", style={"fontSize": "26px", "display": "block", "marginBottom": "4px"}),
                            html.Span("Glisser / cliquer", style={"fontSize": "12px", "color": "#e6edf3", "fontWeight": "600"}),
                            html.Br(),
                            html.Span("CSV ou Excel", style={"fontSize": "11px", "color": "#8b949e"}),
                        ], style={"textAlign": "center"}),
                        style={"marginTop": "20px", "borderWidth": "1.5px", "borderStyle": "dashed",
                               "borderColor": "#58a6ff", "borderRadius": "10px", "padding": "18px 8px", "cursor": "pointer",
                               "backgroundColor": "rgba(88,166,255,0.04)"},
                        multiple=False),
                ], style={
                    "backgroundColor": "#161b22", "borderRight": "1px solid #30363d",
                    "padding": "20px 16px", "minHeight": "calc(100vh - 64px)",
                }),
            ], width=2, style={"padding": "0"}),
            # ── Zone principale ──
            dbc.Col([
                html.Div([
                    dbc.Row([
                        dbc.Col(dbc.Button("📊 Vue Générale", id="btn-1", color="primary",   className="w-100", style={**btn_style, "fontSize": "12px", "padding": "8px"}), width=2),
                        dbc.Col(dbc.Button("👥 Par Groupe",   id="btn-2", color="secondary", className="w-100", style={**btn_style, "fontSize": "12px", "padding": "8px"}), width=2),
                        dbc.Col(dbc.Button("🎫 Par Ticket",  id="btn-3", color="secondary", className="w-100", style={**btn_style, "fontSize": "12px", "padding": "8px"}), width=2),
                        dbc.Col(dbc.Button("📡 Canaux",      id="btn-4", color="secondary", className="w-100", style={**btn_style, "fontSize": "12px", "padding": "8px"}), width=2),
                        dbc.Col(dbc.DropdownMenu(label="📋 SLA PAR", children=items, id="sla-dropdown",
                                                  color="info", className="w-100"), width=2),
                    ], className="mb-4 g-2"),
                    html.Div(id="content", style={"minHeight": "400px"}),
                    dcc.Store(id="stored-data"),
                    dcc.Store(id="stored-active-view"),
                ], style={"padding": "24px"}),
            ], width=10, style={"padding": "0"}),
        ], style={"margin": "0"}),
    ]
)

# ── MODULE FUTUR ─────────────────────────────────────────────────────────────
module = html.Div([
    html.Div([
        html.Div("🚧", style={"fontSize":"64px","marginBottom":"16px"}),
        html.H2("Page en construction", style={"color":"white","fontWeight":"800","marginBottom":"12px"}),
        html.P("Ce module sera bientôt disponible.", style={"color":"#8b949e","marginBottom":"32px"}),
        dbc.Button("← Retour à l'accueil", id="btn-retour-accueil-module", color="secondary", style=btn_style),
    ], style={"textAlign":"center"}),
], style={"backgroundColor":"#0d1117","minHeight":"100vh","display":"flex",
          "alignItems":"center","justifyContent":"center"})

# ── LAYOUT RACINE ─────────────────────────────────────────────────────────────
# On utilise display:none / display:block — PAS de routing, PAS de dcc.Location
# Les 3 pages sont toujours dans le DOM, on les affiche/masque simplement
app.layout = html.Div([
    html.Div(accueil,  id="page-accueil",  style={"display":"block"}),
    html.Div(dashboard, id="page-dashboard", style={"display":"none"}),
    html.Div(module,   id="page-module",   style={"display":"none"}),
])

# ── CALLBACK NAVIGATION ───────────────────────────────────────────────────────
@app.callback(
    Output("page-accueil",  "style"),
    Output("page-dashboard", "style"),
    Output("page-module",   "style"),
    Input("btn-open-dashboard",      "n_clicks"),
    Input("btn-open-module",         "n_clicks"),
    Input("btn-retour-accueil",      "n_clicks"),
    Input("btn-retour-accueil-module","n_clicks"),
    prevent_initial_call=True,
)
def navigate(n1, n2, n3, n4):
    show   = {"display": "block"}
    hide   = {"display": "none"}
    tid = ctx.triggered_id
    if tid == "btn-open-dashboard":
        return hide, show, hide
    if tid == "btn-open-module":
        return hide, hide, show
    # retour accueil (depuis dashboard ou module)
    return show, hide, hide

# ── LECTURE ROBUSTE DU STORE ──────────────────────────────────────────────────
def read_stored_df(stored_json):
    """Reconstruit un DataFrame quel que soit le format présent dans le dcc.Store.

    Le Store peut contenir, selon la version du code qui l'a rempli :
      - une chaîne JSON orient='split'  (format actuel, produit par store_uploaded_data)
      - un dict {'columns','data','index'}  (orient='split' déjà désérialisé)
      - une liste de dicts  (ancien to_dict('records'))
    Retourne un DataFrame vide si le contenu est inexploitable.
    """
    if stored_json is None:
        return pd.DataFrame()
    try:
        if isinstance(stored_json, str):
            return pd.read_json(io.StringIO(stored_json), orient='split')
        if isinstance(stored_json, dict):
            if 'columns' in stored_json and 'data' in stored_json:
                return pd.DataFrame(stored_json['data'], columns=stored_json['columns'])
            return pd.DataFrame([stored_json])
        if isinstance(stored_json, list):
            return pd.DataFrame(stored_json)
    except Exception as e:
        print(f"[read_stored_df] Impossible de lire le Store : {e}")
    return pd.DataFrame()

# ── CALLBACKS DASHBOARD ───────────────────────────────────────────────────────
@app.callback(
    Output('stored-data', 'data'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    prevent_initial_call=True
)
def store_uploaded_data(contents, filename):
    if not contents or not filename: return dash.no_update
    df_raw, error = parse_contents(contents, filename)
    if error: return dash.no_update
    df = load_data(df_raw)
    return df.to_json(date_format='iso', orient='split')

@app.callback(
    [Output('ticket-filter', 'options'), Output('ticket-filter', 'value'),
     Output('agence-filter', 'options'), Output('agence-filter', 'value'),
     Output('annee-dropdown', 'options'), Output('annee-dropdown', 'value'),
     Output('mois-dropdown', 'options'), Output('mois-dropdown', 'value'),
     Output('segmentation-filter', 'options'), Output('segmentation-filter', 'value'),
     Output('delai-filter', 'options'), Output('delai-filter', 'value'),
     Output('content', 'children'),
     Output('btn-1', 'color'), Output('btn-2', 'color'), Output('btn-3', 'color'), Output('btn-4', 'color'),
     Output('stored-active-view', 'data')],
    [Input('ticket-filter', 'value'), Input('agence-filter', 'value'),
     Input('annee-dropdown', 'value'), Input('mois-dropdown', 'value'),
     Input('segmentation-filter', 'value'), Input('delai-filter', 'value'),
     Input('stored-data', 'data'),
     Input("btn-1", "n_clicks"), Input("btn-2", "n_clicks"),
     Input("btn-3", "n_clicks"), Input("btn-4", "n_clicks"),
     Input("item-1", "n_clicks"), Input("item-2", "n_clicks"), Input("item-3", "n_clicks"),
     Input("reset-filters", "n_clicks"), Input('stored-active-view', 'data')],
    prevent_initial_call=True
)
def update_all_filters(ticket_val, agence_val, annee_val, mois_val, segmentation_val, delai_val,
                       stored_json, btn1, btn2, btn3, btn4, item1, item2, item3, reset_click, stored_active_view):
    trigger_id = ctx.triggered_id
    view_buttons = ["btn-1", "btn-2", "btn-3", "btn-4", "item-1", "item-2", "item-3"]
    active_view = trigger_id if trigger_id in view_buttons else (stored_active_view or "btn-1")
    if trigger_id == "reset-filters":
        ticket_val = agence_val = annee_val = mois_val = segmentation_val = delai_val = None
    if not isinstance(agence_val, (list, type(None))): agence_val = [agence_val]
    if not isinstance(delai_val,  (list, type(None))): delai_val  = [delai_val]
    filters = {"Complaint reference": ticket_val, "AGENCE": agence_val, "Annee": annee_val,
               "Mois": mois_val, "SEGMENTATION": segmentation_val, "DELAI_RECLAMATION": delai_val}

    def filter_df(dframe, filter_dict, exclude_key=None):
        df_f = dframe
        for key, val in filter_dict.items():
            if val is not None and key != exclude_key and key in df_f.columns:
                df_f = df_f[df_f[key].isin(val) if isinstance(val, list) else df_f[key] == val]
        return df_f

    def validate_opt(val, opts, multi=False):
        valid_vals = {opt['value'] for opt in opts}
        if multi:
            if val is None: return None
            filtered = [v for v in val if v in valid_vals]
            return filtered if filtered else None
        else:
            if isinstance(val, list): val = val[0] if val else None
            return val if val in valid_vals else None

    # ── Lecture robuste du Store ──────────────────────────────────────────────
    df = read_stored_df(stored_json)

    # Aucune donnée encore chargée
    if stored_json is None:
        return [[]]*12 + ["Veuillez uploader un fichier pour commencer.",
                          "primary", "secondary", "secondary", "secondary", active_view]

    # Donnée présente mais inexploitable (Store corrompu / format inconnu / colonnes manquantes)
    required_cols = {"Complaint reference", "AGENCE", "Annee", "Mois",
                     "SEGMENTATION", "DELAI_RECLAMATION"}
    if df.empty or not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        print(f"[update_all_filters] Store invalide. Colonnes lues : {df.columns.tolist()} "
              f"| Manquantes : {missing}")
        return [[]]*12 + ["⚠️ Les données stockées sont invalides ou incomplètes. "
                          "Veuillez ré-uploader le fichier source.",
                          "primary", "secondary", "secondary", "secondary", active_view]

    options_ticket = [{'label': str(x), 'value': x} for x in sorted(filter_df(df, filters, "Complaint reference")['Complaint reference'].dropna().unique())]
    options_agence = [{'label': str(x), 'value': x} for x in sorted(filter_df(df, filters, "AGENCE")['AGENCE'].dropna().unique())]
    options_annee  = [{'label': str(x), 'value': x} for x in sorted(filter_df(df, filters, "Annee")['Annee'].dropna().unique())]
    mois_unique    = sorted(filter_df(df, filters, "Mois")['Mois'].dropna().unique())
    options_mois   = [{'label': datetime(2000, int(m), 1).strftime('%B'), 'value': m} for m in mois_unique]
    options_segmentation = [{'label': str(x), 'value': x} for x in sorted(filter_df(df, filters, "SEGMENTATION")['SEGMENTATION'].dropna().unique())]
    options_delai  = [{'label': str(x), 'value': x} for x in sorted(filter_df(df, filters, "DELAI_RECLAMATION")['DELAI_RECLAMATION'].dropna().unique())]

    ticket_val       = validate_opt(ticket_val, options_ticket)
    agence_val       = validate_opt(agence_val, options_agence, multi=True)
    annee_val        = validate_opt(annee_val, options_annee)
    mois_val         = validate_opt(mois_val, options_mois)
    segmentation_val = validate_opt(segmentation_val, options_segmentation)
    delai_val        = validate_opt(delai_val, options_delai, multi=True)

    df_filtered = filter_df(df, filters)
    graphs = graph_mapping.get(active_view, lambda d: [])(df_filtered)
    btn_colors = {"btn-1": "secondary", "btn-2": "secondary", "btn-3": "secondary", "btn-4": "secondary"}
    if active_view in btn_colors: btn_colors[active_view] = "primary"

    return (options_ticket, ticket_val, options_agence, agence_val, options_annee, annee_val,
            options_mois, mois_val, options_segmentation, segmentation_val, options_delai, delai_val,
            dbc.Row(graphs), btn_colors["btn-1"], btn_colors["btn-2"], btn_colors["btn-3"], btn_colors["btn-4"], active_view)

if __name__ == '__main__':
    app.run(debug=True)
