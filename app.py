"""Auditoria de Cliente — ponto de entrada único.

Uma página só de auditoria, com um seletor de modo:
- Leads recebidos: dos leads que o cliente já recebeu, quais são
  realmente do interesse dele, via IA.
- Leads perdidos: quantos orçamentos o cliente deveria ter recebido e não
  recebeu, por falta de vínculo produto/anúncio/região.
- Ambos: roda as duas e mostra o funil combinado.

Mais a página de histórico, com as auditorias já rodadas.

Configuração de uma vez só, em Settings > Secrets (Streamlit Cloud) ou
`.streamlit/secrets.toml` local — ver secrets.exemplo.toml.
"""
import streamlit as st

from nucleo.metabase import metabase_configurado
from nucleo.tema import aplicar_estilo_global, seletor_tema

st.set_page_config(page_title="Auditoria de Cliente", page_icon="📋", layout="wide")

if "tema" not in st.session_state:
    st.session_state["tema"] = "escuro"

aplicar_estilo_global()
seletor_tema()

if not metabase_configurado():
    st.error(
        "Metabase não configurado. Quem administra o app precisa cadastrar em "
        "Settings > Secrets: METABASE_URL e (METABASE_API_KEY ou METABASE_USER + METABASE_PASSWORD)."
    )
    st.stop()

paginas = [
    st.Page("paginas/auditoria.py", title="Auditoria", icon=":material/fact_check:", default=True),
    st.Page("paginas/historico.py", title="Histórico", icon=":material/history:"),
]
pg = st.navigation(paginas)
pg.run()
