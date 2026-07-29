"""Saúde do cliente — tela de síntese que junta as duas auditorias (volume
perdido + validação de foco) para o mesmo cliente, mostrando o funil
completo: quantos orçamentos existiam, quantos foram perdidos de verdade,
e dos que chegaram, quantos são bons ou ruins."""
import streamlit as st

from nucleo.dashboard_html import gerar_dashboard_combinado
from nucleo.excel import combinar_workbooks
from nucleo.historico import salvar_no_historico
from nucleo.tema import hero, tema_ativo, titulo_painel
from datetime import datetime

tema, T = tema_ativo()

hero(
    "Saúde do cliente",
    "Auditoria de cliente",
    "Rode as duas auditorias — volume perdido e validação de foco — para o mesmo cliente e "
    "período, e veja aqui o funil combinado: quanto foi perdido de verdade e quanto do que "
    "chegou é bom ou ruim.",
)

rv = st.session_state.get("resultado_volume")
rf = st.session_state.get("resultado_validador")


def _cartao(label, valor, cor_var, sub=""):
    st.markdown(
        f"<div style='background:{T['painel_bg']}; border:1px solid {T['painel_borda']}; "
        f"border-radius:14px; padding:16px 18px;'>"
        f"<div style='font-size:11px; color:{T['texto']}; font-weight:600; text-transform:uppercase; "
        f"letter-spacing:.4px; margin-bottom:6px;'>{label}</div>"
        f"<div style='font-size:24px; font-weight:700; color:{cor_var};'>{valor}</div>"
        f"<div style='font-size:11px; color:{T['texto']}; margin-top:4px;'>{sub}</div>"
        f"</div>", unsafe_allow_html=True,
    )


with st.container(border=True, key="sc_painel_status"):
    titulo_painel("route", "Status das auditorias para o cliente atual")
    col_v, col_f = st.columns(2)
    with col_v:
        if rv:
            st.success(f"Volume perdido rodado — chave {rv['chave']} · {rv['periodo']}")
        else:
            st.info("Volume perdido ainda não rodado para nenhum cliente.")
        st.page_link("paginas/auditoria_volume.py", label="Ir para Volume perdido", icon=":material/trending_down:")
    with col_f:
        if rf:
            st.success(f"Validação de foco rodada — chave {rf['chave']} · {rf['periodo']}")
        else:
            st.info("Validação de foco ainda não rodada para nenhum cliente.")
        st.page_link("paginas/validador_foco.py", label="Ir para Validação de foco", icon=":material/fact_check:")

if not rv and not rf:
    st.caption("Assim que uma das duas auditorias rodar, o resumo aparece aqui.")
    st.stop()

if rv and rf and rv["chave"].strip() != rf["chave"].strip():
    st.warning(
        f"As duas auditorias mais recentes são de clientes diferentes "
        f"(volume: {rv['chave']} · validação: {rf['chave']}). Rode as duas para o mesmo cliente "
        "e período para ver o funil combinado abaixo."
    )

if rv and rf and rv["chave"].strip() == rf["chave"].strip():
    empresa = rf.get("empresa", rv["chave"])
    contagem = rf["contagem"]
    n_dentro = contagem.get("Dentro do foco", 0)
    n_fora = contagem.get("Fora do foco", 0)
    n_perdidos = rv["n_perdidos"]
    total_periodo = n_dentro + n_fora + n_perdidos

    st.markdown(f"<p style='font-weight:600; margin: 1.5rem 0 0.75rem; color:{T['label']};'>Funil combinado — {empresa}</p>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _cartao("Orçamentos no período", total_periodo, T["label"], "recebidos + perdidos")
    with c2:
        _cartao("Perdidos (dentro do foco)", n_perdidos, "#D85A30", "falta de vínculo")
    with c3:
        _cartao("Recebidos fora de foco", n_fora, "#BA7517", f"{round(100*n_fora/(n_dentro+n_fora)) if (n_dentro+n_fora) else 0}% dos recebidos")
    with c4:
        _cartao("Recebidos dentro do foco", n_dentro, "#1D9E75", f"{round(100*n_dentro/(n_dentro+n_fora)) if (n_dentro+n_fora) else 0}% dos recebidos")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        with st.container(border=True):
            titulo_painel("trending_down", "Volume perdido · por produto")
            produtos_perdidos = rv.get("produtos_perdidos") or []
            if produtos_perdidos:
                for nome, qtd in produtos_perdidos:
                    st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:13px; padding:4px 0; color:{T['texto']};'><span>{nome}</span><b style='color:{T['label']};'>{qtd}</b></div>", unsafe_allow_html=True)
            else:
                st.caption("Nenhum orçamento perdido encontrado.")
    with col_p2:
        with st.container(border=True):
            titulo_painel("filter_alt", "Fora de foco · anúncios mais frequentes")
            anuncios_ruins = rf.get("anuncios_ruins") or []
            if anuncios_ruins:
                for nome, qtd in anuncios_ruins:
                    st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:13px; padding:4px 0; color:{T['texto']};'><span>{nome}</span><b style='color:{T['label']};'>{qtd}</b></div>", unsafe_allow_html=True)
            else:
                st.caption("Nenhum lead fora de foco encontrado.")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    excel_combinado = combinar_workbooks([
        ("Volume", rv.get("excel_bytes")),
        ("Validador", rf.get("xlsx_bytes")),
    ])
    dash_combinado = gerar_dashboard_combinado(
        empresa, rv["chave"], rv["periodo"], total_periodo, n_perdidos, n_fora, n_dentro,
        produtos_perdidos=produtos_perdidos, motivos_fora=anuncios_ruins,
        tema=tema, xlsx_bytes=excel_combinado, xlsx_nome=f"{empresa} - Saude do cliente.xlsx",
    )

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Baixar Excel combinado", data=excel_combinado,
                           file_name=f"{empresa} - Saude do cliente.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True, key="sc_dl_excel")
    with col_dl2:
        st.download_button("Baixar dashboard combinado (HTML)", data=dash_combinado.encode("utf-8"),
                           file_name=f"{empresa} - Saude do cliente.html", mime="text/html",
                           use_container_width=True, key="sc_dl_dash")

    if st.session_state.get("sc_ultima_chave_salva") != rv["chave"].strip():
        salvar_no_historico({
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "tipo": "combinado",
            "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Empresa": empresa,
            "Chave única": rv["chave"].strip(),
            "Período": rv["periodo"],
            "Perdidos": n_perdidos, "Fora de foco": n_fora, "Dentro do foco": n_dentro,
        }, arquivos={"xlsx": excel_combinado, "html": dash_combinado.encode("utf-8")})
        st.session_state["sc_ultima_chave_salva"] = rv["chave"].strip()
elif rv or rf:
    st.caption("Rode a outra auditoria para o mesmo cliente e período para liberar o funil combinado.")
