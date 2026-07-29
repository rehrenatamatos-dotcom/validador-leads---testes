"""Histórico — lista as últimas auditorias rodadas (volume, validador ou
combinada), num lugar só e fácil de achar, com download e exclusão."""
import streamlit as st

from nucleo.historico import carregar_historico, excluir_do_historico, ler_resultado_salvo
from nucleo.tema import hero, tema_ativo, titulo_painel

tema, T = tema_ativo()

hero(
    "HISTÓRICO",
    "Histórico de auditorias",
    "As últimas auditorias rodadas — de volume, de validação de foco ou combinadas — com os "
    "arquivos prontos pra baixar de novo.",
)

RESUMO_POR_TIPO = {
    "volume": lambda h: f"{h.get('Perdidos', 0)} perdido(s)",
    "validador": lambda h: (
        f"{h.get('Leads', 0)} leads "
        f"(<span style='color:{T['sucesso']};'>{h.get('Dentro do foco', 0)}</span>/"
        f"<span style='color:{T['perigo']};'>{h.get('Fora de foco', 0)}</span>/"
        f"<span style='color:{T['aviso']};'>{h.get('Aberto', 0)}</span>)"
    ),
    "combinado": lambda h: (
        f"<span style='color:{T['perigo']};'>{h.get('Perdidos', 0)} perdidos</span> · "
        f"<span style='color:{T['aviso']};'>{h.get('Fora de foco', 0)} fora</span> · "
        f"<span style='color:{T['sucesso']};'>{h.get('Dentro do foco', 0)} dentro</span>"
    ),
}
NOME_TIPO = {"volume": "Leads perdidos", "validador": "Leads recebidos", "combinado": "Ambos"}


@st.dialog("Excluir do histórico")
def dialogo_excluir(rid, rotulo):
    st.write(f"Tem certeza que deseja excluir **{rotulo}**?")
    st.caption("O registro e os arquivos dele serão apagados. Essa ação não tem volta.")
    cd1, cd2 = st.columns(2)
    if cd1.button("Sim, excluir", type="primary", use_container_width=True, key=f"hi_conf_{rid}"):
        excluir_do_historico(rid)
        st.rerun()
    if cd2.button("Cancelar", use_container_width=True, key=f"hi_canc_{rid}"):
        st.rerun()


with st.container(border=True, key="hi_painel"):
    titulo_painel("route", "Buscar no histórico")
    col_f, col_t = st.columns([3, 1])
    with col_f:
        filtro = st.text_input(
            "Empresa ou chave única", placeholder="Ex.: Metalúrgica ou 12-34567-1", key="hi_filtro",
            label_visibility="collapsed",
        )
    with col_t:
        tipo_filtro = st.selectbox(
            "Tipo", ["Todos", "Leads perdidos", "Leads recebidos", "Ambos"], key="hi_tipo",
            label_visibility="collapsed",
        )

historico = carregar_historico()
if tipo_filtro != "Todos":
    tipo_chave = {v: k for k, v in NOME_TIPO.items()}[tipo_filtro]
    historico = [h for h in historico if h.get("tipo") == tipo_chave]
if filtro.strip():
    alvo = filtro.strip().lower()
    historico = [
        h for h in historico
        if alvo in str(h.get("Chave única", "")).lower() or alvo in str(h.get("Empresa", "")).lower()
    ]

if not historico:
    st.caption("Nenhuma auditoria encontrada. As próximas que você rodar aparecem aqui.")
else:
    colunas_hist = [1.1, 1.15, 1.3, 1.05, 1.5, 1.4, 0.6, 0.6, 0.35]
    cab = st.columns(colunas_hist)
    for col, titulo in zip(cab, ("Data", "Tipo", "Empresa/Chave", "Chave", "Período", "Resultado", "Excel", "Painel", "")):
        col.markdown(f"<span style='font-size:0.72rem; color:{T['texto']}; font-weight:600;'>{titulo}</span>", unsafe_allow_html=True)

    for h in historico:
        rid = h.get("id", "")
        tipo = h.get("tipo", "")
        with st.container(border=True):
            c = st.columns(colunas_hist)
            c[0].markdown(f"<span style='font-size:0.78rem;'>{h.get('Data da solicitação', '')}</span>", unsafe_allow_html=True)
            c[1].markdown(f"<span style='font-size:0.78rem;'>{NOME_TIPO.get(tipo, tipo)}</span>", unsafe_allow_html=True)
            c[2].markdown(f"<span style='font-size:0.78rem;'>{h.get('Empresa', '') or '—'}</span>", unsafe_allow_html=True)
            c[3].markdown(f"<span style='font-size:0.78rem;'>{h.get('Chave única', '')}</span>", unsafe_allow_html=True)
            c[4].markdown(f"<span style='font-size:0.78rem;'>{h.get('Período', '')}</span>", unsafe_allow_html=True)
            resumo_fn = RESUMO_POR_TIPO.get(tipo)
            c[5].markdown(f"<span style='font-size:0.78rem;'>{resumo_fn(h) if resumo_fn else '—'}</span>", unsafe_allow_html=True)

            xlsx_salvo = ler_resultado_salvo(rid, "xlsx") if rid else None
            dash_salvo = ler_resultado_salvo(rid, "html") if rid else None
            if xlsx_salvo:
                c[6].download_button("Excel", data=xlsx_salvo, file_name=h.get("xlsx_nome") or h.get("excel_nome") or f"{rid}.xlsx",
                                      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                      use_container_width=True, key=f"hi_xlsx_{rid}", help="Baixar Excel")
            else:
                c[6].caption("—")
            if dash_salvo:
                c[7].download_button("Painel", data=dash_salvo, file_name=h.get("dash_nome", f"{rid}.html"),
                                      mime="text/html", use_container_width=True, key=f"hi_dash_{rid}",
                                      help="Baixar dashboard")
            else:
                c[7].caption("—")
            if rid and c[8].button("✕", key=f"hi_x_{rid}", help="Excluir esta auditoria"):
                dialogo_excluir(rid, f"{h.get('Empresa', '') or h.get('Chave única', '')} · {h.get('Data da solicitação', '')}")
