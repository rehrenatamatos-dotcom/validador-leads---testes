"""Auditoria — página única. Um seletor de modo decide o que roda:
- Leads recebidos: valida foco dos leads já recebidos (IA).
- Leads perdidos: audita volume não recebido por falta de vínculo.
- Ambos: roda os dois e mostra o funil combinado.

Os campos obrigatórios mudam conforme o modo escolhido — só pede o que
aquele modo realmente precisa."""
from datetime import date, datetime, timedelta

import streamlit as st

from nucleo.dashboard_html import gerar_dashboard_combinado
from nucleo.excel import combinar_workbooks
from nucleo.historico import salvar_no_historico
from nucleo.ia import MODELOS_ESCOLHA
from nucleo.logica_validador import rodar_validacao
from nucleo.logica_volume import get_anuncios_candidatos_bloqueio, get_client_products, normalizar_texto, rodar_volume
from nucleo.regioes import NACIONAL, OPCOES_REGIAO
from nucleo.tema import hero, tema_ativo, titulo_painel

tema, T = tema_ativo()

hero(
    "AUDITORIA",
    "Analisar cliente",
    "Escolha o que quer analisar — leads recebidos, leads perdidos, ou os dois — e preencha só "
    "os campos que essa análise precisa.",
)

if "au_produtos" not in st.session_state:
    st.session_state.au_produtos = None
if "au_anuncios_candidatos" not in st.session_state:
    st.session_state.au_anuncios_candidatos = None

with st.container(border=True, key="au_painel_form"):
    titulo_painel("fact_check", "Cliente e período")
    grid_a, grid_b = st.columns(2)
    with grid_a:
        chave = st.text_input("Chave única do cliente *", placeholder="Ex.: 12-34567-1", key="au_chave")
    with grid_b:
        st.markdown(
            f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin-bottom:0.4rem;'>Período *</div>",
            unsafe_allow_html=True,
        )
        p_a, p_b = st.columns(2)
        with p_a:
            data_inicio = st.date_input(
                "Início", value=date.today() - timedelta(days=90), format="DD/MM/YYYY",
                label_visibility="collapsed", key="au_data_inicio",
            )
        with p_b:
            data_fim = st.date_input(
                "Fim", value=date.today(), format="DD/MM/YYYY",
                label_visibility="collapsed", key="au_data_fim",
            )

    st.markdown(
        f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin:1.1rem 0 0.5rem;'>O que você quer fazer *</div>",
        unsafe_allow_html=True,
    )
    modo = st.segmented_control(
        "Modo", options=["Leads recebidos", "Leads perdidos", "Ambos"],
        default="Ambos", key="au_modo", label_visibility="collapsed",
    )
    quer_recebidos = modo in ("Leads recebidos", "Ambos")
    quer_perdidos = modo in ("Leads perdidos", "Ambos")

    if quer_recebidos:
        st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
        titulo_painel("fact_check", "Leads recebidos — perfil para a IA julgar foco")
        col_c, col_d = st.columns(2)
        with col_c:
            site = st.text_input(
                "Site do cliente (opcional)", placeholder="https://www.sitedocliente.com.br", key="au_site",
                help="Importante quando não houver briefing cadastrado para o cliente.",
            )
        with col_d:
            obs = st.text_area(
                "Observações (opcional)", height=68, key="au_obs",
                help="Ex.: cliente só vende máquinas (serviço, assistência, aluguel e peças = fora do foco).",
            )
        modelo_escolha = st.selectbox("Processamento da IA", list(MODELOS_ESCOLHA.keys()), key="au_modelo")
    else:
        site = st.session_state.get("au_site", "")
        obs = st.session_state.get("au_obs", "")
        modelo_escolha = st.session_state.get("au_modelo") or list(MODELOS_ESCOLHA.keys())[0]

    if quer_perdidos:
        st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
        titulo_painel("trending_down", "Leads perdidos — cobertura e anúncios")
        regioes_selecionadas = st.multiselect(
            "Onde o cliente atua", options=OPCOES_REGIAO, default=[NACIONAL], key="au_regioes",
            help="Leads fora dessa cobertura não entram na lista de perdidos.",
        )
        termos_txt = st.text_input(
            "Bloquear anúncios por palavra-chave (opcional, separe por vírgula)",
            key="au_termos_bloqueados",
            help="Ex.: locação, aluguel, assistência — remove da lista de perdidos qualquer anúncio "
                 "cujo nome contenha esses termos, mesmo sem buscar as sugestões abaixo.",
        )
        termos_bloqueados = [t.strip() for t in termos_txt.split(",") if t.strip()]
        st.caption(
            "Opcional: busque os produtos do cliente pra ver sugestões de anúncios de outras empresas "
            "dentro das mesmas categorias — marque os que não fazem sentido pra esse cliente. "
            "Se pular esta etapa, a auditoria roda direto com os produtos do cliente."
        )
        if st.button("Buscar produtos e sugestões de anúncios", disabled=not chave, key="au_btn_buscar"):
            try:
                with st.spinner("Buscando produtos ativos cadastrados do cliente..."):
                    st.session_state.au_produtos = get_client_products(chave)
                if not st.session_state.au_produtos:
                    st.warning("Não encontrei nenhum produto com anúncio ativo para essa chave de cliente.")
                    st.session_state.au_anuncios_candidatos = []
                else:
                    with st.spinner("Buscando anúncios candidatos por produto..."):
                        st.session_state.au_anuncios_candidatos = get_anuncios_candidatos_bloqueio(
                            st.session_state.au_produtos, chave
                        )
            except RuntimeError as e:
                st.error(str(e))

        anuncios_bloqueados_selecionados = []
        produtos = st.session_state.au_produtos
        if produtos:
            st.write(f"**{len(produtos)} produto(s) com anúncio ativo:** {', '.join(produtos)}")
            candidatos = st.session_state.au_anuncios_candidatos or []
            if candidatos:
                busca_anuncio = st.text_input(
                    "Buscar por palavra (ex: TNT) pra marcar vários de uma vez", key="au_busca_anuncio",
                )
                busca_normalizada = normalizar_texto(busca_anuncio.strip())
                filtrados = (
                    [c for c in candidatos if busca_normalizada in normalizar_texto(c)]
                    if busca_anuncio.strip() else candidatos
                )
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    if st.button(f"Marcar os {len(filtrados)} encontrados", disabled=not filtrados, key="au_btn_marcar_filtrados"):
                        atual = set(st.session_state.get("au_anuncios_bloqueados_ms", []))
                        atual.update(filtrados)
                        st.session_state["au_anuncios_bloqueados_ms"] = sorted(atual)
                with col_b2:
                    if st.button("Marcar todos", key="au_btn_marcar_todos"):
                        st.session_state["au_anuncios_bloqueados_ms"] = sorted(candidatos)
                with col_b3:
                    if st.button("Limpar seleção", key="au_btn_limpar_selecao"):
                        st.session_state["au_anuncios_bloqueados_ms"] = []
                anuncios_bloqueados_selecionados = st.multiselect(
                    "Anúncios de outras empresas que não fazem sentido pra esse cliente",
                    options=candidatos, key="au_anuncios_bloqueados_ms",
                )
            else:
                st.caption("Nenhum anúncio de outra empresa encontrado nessas categorias.")
    else:
        regioes_selecionadas = [NACIONAL]
        anuncios_bloqueados_selecionados = []
        termos_bloqueados = []

    st.divider()
    pronto = bool(chave and data_inicio and data_fim and modo)
    rodar = st.button("Rodar auditoria", type="primary", disabled=not pronto, key="au_btn_rodar")
    if quer_perdidos and not st.session_state.au_produtos:
        st.caption("Você pode rodar direto — os produtos do cliente serão buscados automaticamente. "
                   "A busca de anúncios acima é opcional, só pra bloquear anúncios específicos antes.")

if rodar:
    if data_inicio > data_fim:
        st.error("A data de início não pode ser depois da data de fim.")
        st.stop()

    resultado_volume = None
    resultado_validador = None

    if quer_perdidos:
        st.session_state.pop("au_resultado_volume", None)
        with st.status("Rodando auditoria de leads perdidos...", expanded=True) as status:
            try:
                produtos_volume = st.session_state.au_produtos
                if not produtos_volume:
                    st.write("Buscando produtos ativos do cliente...")
                    produtos_volume = get_client_products(chave)
                    st.session_state.au_produtos = produtos_volume
                if not produtos_volume:
                    status.update(label="Nenhum produto ativo encontrado", state="error")
                    st.warning("Não encontrei nenhum produto com anúncio ativo para essa chave — "
                               "não há como auditar leads perdidos.")
                else:
                    resultado_volume = rodar_volume(
                        chave, produtos_volume, data_inicio, data_fim,
                        regioes_selecionadas, set(anuncios_bloqueados_selecionados), site, obs,
                        termos_bloqueados=termos_bloqueados,
                    )
                    status.update(label="Auditoria de leads perdidos concluída", state="complete")
            except RuntimeError as e:
                status.update(label="Erro na auditoria de leads perdidos", state="error")
                st.error(str(e))

    if quer_recebidos:
        st.session_state.pop("au_resultado_validador", None)
        with st.status("Rodando validação de leads recebidos...", expanded=True) as status:
            try:
                resultado_validador = rodar_validacao(chave, data_inicio, data_fim, site, obs, modelo_escolha, tema)
                status.update(label="Validação de leads recebidos concluída", state="complete")
            except RuntimeError as e:
                status.update(label="Erro na validação de leads recebidos", state="error")
                st.error(str(e))

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    if resultado_volume is not None:
        st.session_state["au_resultado_volume"] = resultado_volume
        if not resultado_volume.get("vazio") and modo != "Ambos":
            salvar_no_historico({
                "id": agora, "tipo": "volume",
                "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Chave única": resultado_volume["chave"], "Período": resultado_volume["periodo"],
                "Perdidos": resultado_volume["n_perdidos"], "Fora de foco": resultado_volume["n_fora"],
                "Aberto": resultado_volume["n_aberto"], "excel_nome": resultado_volume["excel_nome"],
            }, arquivos={"xlsx": resultado_volume["excel_bytes"]})

    if resultado_validador is not None:
        st.session_state["au_resultado_validador"] = resultado_validador
        if modo != "Ambos":
            salvar_no_historico({
                "id": agora, "tipo": "validador",
                "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Empresa": resultado_validador["empresa"], "Chave única": resultado_validador["chave"],
                "Período": resultado_validador["periodo"], "Leads": resultado_validador["total"],
                "Dentro do foco": resultado_validador["contagem"]["Dentro do foco"],
                "Fora do foco": resultado_validador["contagem"]["Fora do foco"],
                "Aberto": resultado_validador["contagem"]["Aberto"],
                "xlsx_nome": resultado_validador["xlsx_nome"], "dash_nome": resultado_validador["dash_nome"],
            }, arquivos={"xlsx": resultado_validador["xlsx_bytes"], "html": resultado_validador["dash_bytes"]})

    if modo == "Ambos" and resultado_volume is not None and resultado_validador is not None \
            and not resultado_volume.get("vazio"):
        empresa = resultado_validador.get("empresa", resultado_volume["chave"])
        contagem = resultado_validador["contagem"]
        n_dentro, n_fora = contagem.get("Dentro do foco", 0), contagem.get("Fora do foco", 0)
        n_perdidos = resultado_volume["n_perdidos"]
        excel_combinado = combinar_workbooks([
            ("Volume", resultado_volume.get("excel_bytes")),
            ("Validador", resultado_validador.get("xlsx_bytes")),
        ])
        dash_combinado = gerar_dashboard_combinado(
            empresa, resultado_volume["chave"], resultado_volume["periodo"],
            n_dentro + n_fora + n_perdidos, n_perdidos, n_fora, n_dentro,
            produtos_perdidos=resultado_volume.get("produtos_perdidos"),
            anuncios_fora=resultado_validador.get("anuncios_ruins"),
            melhores=resultado_validador.get("melhores"),
            tema=tema, xlsx_bytes=excel_combinado, xlsx_nome=f"{empresa} - Saude do cliente.xlsx",
        )
        st.session_state["au_resultado_combinado"] = {
            "empresa": empresa, "excel_bytes": excel_combinado, "dash_bytes": dash_combinado.encode("utf-8"),
        }
        salvar_no_historico({
            "id": agora, "tipo": "combinado",
            "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Empresa": empresa, "Chave única": resultado_volume["chave"], "Período": resultado_volume["periodo"],
            "Perdidos": n_perdidos, "Fora de foco": n_fora, "Dentro do foco": n_dentro,
        }, arquivos={"xlsx": excel_combinado, "html": dash_combinado.encode("utf-8")})
    else:
        st.session_state.pop("au_resultado_combinado", None)


def _cartao(label, valor, cor, sub=""):
    st.markdown(
        f"<div style='background:{T['painel_bg']}; border:1px solid {T['painel_borda']}; "
        f"border-radius:10px; padding:14px 16px;'>"
        f"<div style='font-size:11px; color:{T['texto']}; font-weight:500; text-transform:uppercase; "
        f"letter-spacing:.4px; margin-bottom:6px;'>{label}</div>"
        f"<div style='font-size:24px; font-weight:600; color:{cor};'>{valor}</div>"
        f"<div style='font-size:11px; color:{T['texto']}; margin-top:4px;'>{sub}</div>"
        f"</div>", unsafe_allow_html=True,
    )


res_volume = st.session_state.get("au_resultado_volume")
res_validador = st.session_state.get("au_resultado_validador")
res_combinado = st.session_state.get("au_resultado_combinado")

if res_combinado:
    empresa = res_combinado["empresa"]
    contagem = res_validador["contagem"]
    n_dentro, n_fora = contagem.get("Dentro do foco", 0), contagem.get("Fora do foco", 0)
    n_perdidos = res_volume["n_perdidos"]
    total_periodo = n_dentro + n_fora + n_perdidos

    st.markdown(f"<p style='font-weight:600; margin:1.5rem 0 0.75rem; color:{T['label']};'>Funil combinado — {empresa}</p>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _cartao("Orçamentos no período", total_periodo, T["label"], "recebidos + perdidos")
    with c2:
        _cartao("Perdidos (dentro do foco)", n_perdidos, T["perigo"], "falta de vínculo")
    with c3:
        pct_fora = round(100 * n_fora / (n_dentro + n_fora)) if (n_dentro + n_fora) else 0
        _cartao("Recebidos fora de foco", n_fora, T["aviso"], f"{pct_fora}% dos recebidos")
    with c4:
        pct_dentro = round(100 * n_dentro / (n_dentro + n_fora)) if (n_dentro + n_fora) else 0
        _cartao("Recebidos dentro do foco", n_dentro, T["sucesso"], f"{pct_dentro}% dos recebidos")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        with st.container(border=True):
            titulo_painel("trending_down", "Volume perdido · por produto")
            produtos_perdidos = res_volume.get("produtos_perdidos") or []
            if produtos_perdidos:
                for nome, qtd in produtos_perdidos:
                    st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:13px; padding:4px 0; color:{T['texto']};'><span>{nome}</span><b style='color:{T['label']};'>{qtd}</b></div>", unsafe_allow_html=True)
            else:
                st.caption("Nenhum orçamento perdido encontrado.")
    with col_p2:
        with st.container(border=True):
            titulo_painel("filter_alt", "Fora de foco · anúncios mais frequentes")
            anuncios_ruins = res_validador.get("anuncios_ruins") or []
            if anuncios_ruins:
                for nome, qtd in anuncios_ruins:
                    st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:13px; padding:4px 0; color:{T['texto']};'><span>{nome}</span><b style='color:{T['label']};'>{qtd}</b></div>", unsafe_allow_html=True)
            else:
                st.caption("Nenhum lead fora de foco encontrado.")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Baixar Excel combinado", data=res_combinado["excel_bytes"],
                           file_name=f"{empresa} - Saude do cliente.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True, key="au_dl_excel_combinado")
    with col_dl2:
        st.download_button("Baixar dashboard combinado (HTML)", data=res_combinado["dash_bytes"],
                           file_name=f"{empresa} - Saude do cliente.html", mime="text/html",
                           use_container_width=True, key="au_dl_dash_combinado")

else:
    if res_volume:
        if res_volume.get("vazio"):
            st.success("Nenhum orçamento perdido encontrado para os produtos deste cliente.")
        else:
            rotulo = (
                f"{res_volume['n_perdidos']} orçamento(s) perdido(s) de verdade (dentro do foco) — "
                f"{res_volume['n_fora']} descartado(s) (fora de foco) e {res_volume['n_aberto']} incerto(s)."
                if res_volume.get("filtro_foco_aplicado")
                else f"{res_volume['n_perdidos']} orçamento(s) não recebido(s) encontrado(s)."
            )
            st.success(rotulo)
            st.download_button("Baixar Excel", data=res_volume["excel_bytes"], file_name=res_volume["excel_nome"],
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="au_dl_excel_volume")

    if res_validador:
        total, contagem = res_validador["total"], res_validador["contagem"]
        st.success(f"Validação concluída — {total} leads processados! ({res_validador['empresa']})")
        c1, c2, c3 = st.columns(3)
        c1.metric("Dentro do foco", f"{contagem['Dentro do foco']/total:.0%}" if total else "0%", f"{contagem['Dentro do foco']} leads", delta_color="off")
        c2.metric("Fora do foco", f"{contagem['Fora do foco']/total:.0%}" if total else "0%", f"{contagem['Fora do foco']} leads", delta_color="off")
        c3.metric("Aberto", f"{contagem['Aberto']/total:.0%}" if total else "0%", f"{contagem['Aberto']} leads", delta_color="off")
        if res_validador["falhas"]:
            st.warning(f"{res_validador['falhas']} lead(s) sem resposta da IA (marcados como Aberto) — rode de novo para reprocessar.")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("Baixar Excel validado", data=res_validador["xlsx_bytes"], file_name=res_validador["xlsx_nome"],
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True, key="au_dl_xlsx_validador")
        with col_dl2:
            st.download_button("Baixar dashboard (HTML)", data=res_validador["dash_bytes"], file_name=res_validador["dash_nome"],
                               mime="text/html", use_container_width=True, key="au_dl_dash_validador")
