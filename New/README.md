# Plateforme SGCI (Réclamations + KPI)

## Installation
pip install -r requirements.txt

## Lancement
streamlit run app.py

## Comptes de test (à changer avant mise en prod, dans app.py > PASSWORDS)
- admin / admin123
- consultation / lecture123

## Structure
- app.py         : point d'entrée, navigation, authentification
- db.py          : stockage réclamations (upsert par ticket) + historique SLA
- processing.py  : parsing et transformation des fichiers réclamations
- graphs.py      : graphiques Plotly (réclamations)
- style.py       : CSS et composants d'interface
- kpi_db.py      : stockage et parsing du module KPI (CRC/SAT/SAT PRO)
- kpi_views.py   : affichage du module KPI
- .streamlit/config.toml : thème sombre (à conserver au même endroit relatif à app.py)
