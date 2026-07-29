"""Auditoria de Cliente — ponto de entrada único.

Reúne, numa ferramenta só, o que antes eram dois apps separados:
- Volume perdido (quantos orçamentos o cliente deveria ter recebido e não
  recebeu, por falta de vínculo produto/anúncio/região).
- Validação de foco (dos leads que o cliente já recebeu, quais são
  realmente do interesse dele, via IA).
- Saúde do cliente: tela de síntese que junta as duas auditorias.

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
    st.Page("paginas/saude_cliente.py", title="Saúde do cliente", icon="📋", default=True),
    st.Page("paginas/auditoria_volume.py", title="Volume perdido", icon="📉"),
    st.Page("paginas/validador_foco.py", title="Validação de foco", icon="✅"),
]
pg = st.navigation(paginas)
pg.run()
