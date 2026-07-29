"""Volume perdido — quantos orçamentos o cliente deveria ter recebido
(produto com anúncio ativo) e não recebeu, cruzando produto e anúncio,
filtrando por região e por anúncios de terceiros bloqueados manualmente.

Desde esta versão, os "não recebidos" passam também pelo mesmo crítério de
foco usado na Validação de foco (IA): só conta como orçamento realmente
perdido quem seria "Dentro do foco" se tivesse chegado — quem seria
rejeitado de qualquer forma é mostrado à parte, não somado no número
principal. Esse filtro exige uma coluna de mensagem na question de leads
(39); se ela não existir, a ferramenta avisa e volta ao comportamento
antigo (perdidos sem filtro de foco), em vez de quebrar.

Adaptado de "Ferramenta volume"/app_volume.py.
"""
import copy
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from nucleo.excel import gerar_xlsx_volume
from nucleo.historico import salvar_no_historico
from nucleo.ia import classificar_lote, provedores_ativos
from nucleo.metabase import run_card
from nucleo.perfil_cliente import montar_perfil_cliente
from nucleo.regioes import NACIONAL, OPCOES_REGIAO, resolver_ufs
from nucleo.tema import hero, tema_ativo, titulo_painel

# Question 287 - "Produto por Cliente" (filtro: chave_unica)
PRODUTOS_CARD_ID = 287
COLUNA_PRODUTO = "Produto"
COLUNA_STATUS_ANUNCIO = "Status do Anuncio"
STATUS_ATIVO = "ativo"

# Question 39 - "Growth - Relatório de Orçamentos Únicos"
LEADS_CARD_ID = 39
TAG_PRODUTO = "produto"
TAG_ANUNCIO = "announcements"
TAG_MENSAGEM = "mensagem"
TAG_SATELITE = "satellite"
TAG_DATA_INICIO = "data_inicio"
TAG_DATA_FINAL = "data_final"

COLUNA_ORCAMENTO_ID = "Orçamento ID"
COLUNA_ANUNCIO = "Anúncio"
COLUNA_EMPRESAS_QUE_RECEBERAM = "Empresas Recebedoras"
SEPARADOR_EMPRESAS = ","
COLUNA_UF = "region"
COLUNAS_MENSAGEM_CANDIDATAS = ("Mensagem do Cliente", "Mensagem", "mensagem")

# Question 220 - "Anúncios por Produto (busca por ID ou nome)" (filtro: produto)
ANUNCIOS_CARD_ID = 220
COLUNA_NOME_ANUNCIO_220 = "Nome do Anuncio"
COLUNA_CHAVE_UNICA_220 = "Chave Unica"


def normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _parametro_categoria(tag: str, valor: str) -> dict:
    return {"type": "category", "target": ["variable", ["template-tag", tag]], "value": valor}


def get_client_products(chave_cliente: str) -> list:
    param = _parametro_categoria("chave_unica", chave_cliente)
    df = run_card(PRODUTOS_CARD_ID, [param])
    faltando = [c for c in (COLUNA_PRODUTO, COLUNA_STATUS_ANUNCIO) if c not in df.columns]
    if faltando:
        raise RuntimeError(
            f"Coluna(s) {faltando} não encontrada(s) na question de produtos. "
            f"Colunas encontradas: {list(df.columns)}"
        )
    df["_status_norm"] = df[COLUNA_STATUS_ANUNCIO].astype(str).str.strip().str.lower()
    produtos_com_ativo = df.loc[df["_status_norm"] == STATUS_ATIVO, COLUNA_PRODUTO]
    return sorted(set(produtos_com_ativo.dropna().astype(str).str.strip()))


def get_anuncios_candidatos_bloqueio(produtos: list, chave_cliente: str) -> list:
    nomes = set()
    for produto in produtos:
        param = _parametro_categoria("produto", produto)
        df = run_card(ANUNCIOS_CARD_ID, [param])
        if df.empty:
            continue
        faltando = [c for c in (COLUNA_NOME_ANUNCIO_220, COLUNA_CHAVE_UNICA_220) if c not in df.columns]
        if faltando:
            raise RuntimeError(
                f"Coluna(s) {faltando} não encontrada(s) na question de anúncios por produto. "
                f"Colunas encontradas: {list(df.columns)}"
            )
        de_outras_empresas = df[df[COLUNA_CHAVE_UNICA_220].astype(str).str.strip() != chave_cliente]
        nomes.update(de_outras_empresas[COLUNA_NOME_ANUNCIO_220].dropna().astype(str).str.strip())
    return sorted(nomes)


def _buscar_leads_por_campo(tag_filtro: str, valor: str, data_inicio: str, data_final: str) -> pd.DataFrame:
    params = [
        _parametro_categoria(TAG_PRODUTO, valor if tag_filtro == TAG_PRODUTO else ""),
        _parametro_categoria(TAG_ANUNCIO, valor if tag_filtro == TAG_ANUNCIO else ""),
        _parametro_categoria(TAG_MENSAGEM, ""),
        _parametro_categoria(TAG_SATELITE, ""),
        {"type": "date/single", "target": ["variable", ["template-tag", TAG_DATA_INICIO]], "value": data_inicio},
        {"type": "date/single", "target": ["variable", ["template-tag", TAG_DATA_FINAL]], "value": data_final},
    ]
    return run_card(LEADS_CARD_ID, params)


def get_leads_not_received(produto, chave_cliente, data_inicio, data_final, ufs_permitidas, anuncios_bloqueados):
    df_por_produto = _buscar_leads_por_campo(TAG_PRODUTO, produto, data_inicio, data_final)
    df_por_anuncio = _buscar_leads_por_campo(TAG_ANUNCIO, produto, data_inicio, data_final)
    df = pd.concat([df_por_produto, df_por_anuncio], ignore_index=True)
    if df.empty:
        return df

    if COLUNA_ORCAMENTO_ID in df.columns:
        df = df.drop_duplicates(subset=COLUNA_ORCAMENTO_ID)

    faltando = [c for c in (COLUNA_EMPRESAS_QUE_RECEBERAM, COLUNA_ANUNCIO, COLUNA_UF) if c not in df.columns]
    if faltando:
        raise RuntimeError(
            f"Coluna(s) {faltando} não encontrada(s) na question de leads. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    def recebeu(valor) -> bool:
        if pd.isna(valor):
            return False
        chaves = [v.strip() for v in str(valor).split(SEPARADOR_EMPRESAS)]
        return chave_cliente in chaves

    faltantes = df[~df[COLUNA_EMPRESAS_QUE_RECEBERAM].apply(recebeu)].copy()

    if ufs_permitidas is not None and not faltantes.empty:
        faltantes = faltantes[faltantes[COLUNA_UF].isin(ufs_permitidas)]

    if anuncios_bloqueados and not faltantes.empty:
        faltantes = faltantes[~faltantes[COLUNA_ANUNCIO].astype(str).str.strip().isin(anuncios_bloqueados)]

    if not faltantes.empty:
        faltantes.insert(0, "Produto Consultado", produto)
    return faltantes


def _coluna_mensagem(df: pd.DataFrame):
    for cand in COLUNAS_MENSAGEM_CANDIDATAS:
        if cand in df.columns:
            return cand
    return None


tema, T = tema_ativo()

hero(
    "Volume perdido",
    "Volume perdido por falta de vínculo",
    "Descubra quantos orçamentos um cliente deixou de receber, produto por produto — agora já "
    "filtrando pela IA quem realmente seria aproveitado, e não só quem nunca chegou.",
)

if "av_produtos" not in st.session_state:
    st.session_state.av_produtos = None
if "av_anuncios_candidatos" not in st.session_state:
    st.session_state.av_anuncios_candidatos = None

with st.container(border=True, key="av_painel_form"):
    titulo_painel("fact_check", "Cliente a auditar")
    chave_cliente = st.text_input("Chave única (ID) do cliente no Metabase", key="av_chave")

    st.markdown(f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin:1rem 0 0.4rem;'>Período a analisar</div>", unsafe_allow_html=True)
    col_data1, col_data2 = st.columns(2)
    with col_data1:
        data_inicio = st.date_input("Data início", value=date.today() - timedelta(days=90), format="DD/MM/YYYY", key="av_data_inicio")
    with col_data2:
        data_final = st.date_input("Data fim", value=date.today(), format="DD/MM/YYYY", key="av_data_final")

    st.markdown(f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin:1rem 0 0.4rem;'>Onde o cliente atua</div>", unsafe_allow_html=True)
    regioes_selecionadas = st.multiselect(
        "Nacional, região(ões) e/ou estado(s) específico(s)",
        options=OPCOES_REGIAO, default=[NACIONAL], key="av_regioes",
        help="Leads fora dessa cobertura não entram na lista de perdidos.",
    )

    st.markdown(f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin:1rem 0 0.4rem;'>Perfil do cliente (para o filtro de foco por IA)</div>", unsafe_allow_html=True)
    col_site, col_obs = st.columns(2)
    with col_site:
        site = st.text_input("Site do cliente (opcional)", placeholder="https://www.sitedocliente.com.br", key="av_site")
    with col_obs:
        obs = st.text_area("Observações (opcional)", height=68, key="av_obs",
                            help="Mesmas observações usadas na Validação de foco — ajudam a IA a decidir o que é 'perdido de verdade'.")

    st.markdown(f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin:1rem 0 0.4rem;'>Anúncios a bloquear</div>", unsafe_allow_html=True)
    st.caption(
        "Busque os produtos do cliente pra ver sugestões de anúncios de outras empresas "
        "dentro das mesmas categorias — marque os que não fazem sentido pra esse cliente."
    )

    if st.button("Buscar produtos e sugestões de anúncios", disabled=not chave_cliente, key="av_btn_buscar"):
        try:
            with st.spinner("Buscando produtos ativos cadastrados do cliente..."):
                st.session_state.av_produtos = get_client_products(chave_cliente)
            if not st.session_state.av_produtos:
                st.warning("Não encontrei nenhum produto com anúncio ativo para essa chave de cliente.")
                st.session_state.av_anuncios_candidatos = []
            else:
                with st.spinner("Buscando anúncios candidatos por produto..."):
                    st.session_state.av_anuncios_candidatos = get_anuncios_candidatos_bloqueio(
                        st.session_state.av_produtos, chave_cliente
                    )
        except RuntimeError as e:
            st.error(str(e))

    anuncios_bloqueados_selecionados = []
    if st.session_state.av_produtos:
        st.write(
            f"**{len(st.session_state.av_produtos)} produto(s) com anúncio ativo:** "
            f"{', '.join(st.session_state.av_produtos)}"
        )
        if st.session_state.av_anuncios_candidatos:
            if "av_anuncios_bloqueados_ms" not in st.session_state:
                st.session_state["av_anuncios_bloqueados_ms"] = []

            busca_anuncio = st.text_input("Buscar por palavra (ex: TNT) pra marcar vários de uma vez", key="av_busca_anuncio")
            candidatos = st.session_state.av_anuncios_candidatos
            busca_normalizada = normalizar_texto(busca_anuncio.strip())
            filtrados = (
                [c for c in candidatos if busca_normalizada in normalizar_texto(c)]
                if busca_anuncio.strip() else candidatos
            )

            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button(f"Marcar os {len(filtrados)} encontrados", disabled=not filtrados, key="av_btn_marcar_filtrados"):
                    atual = set(st.session_state["av_anuncios_bloqueados_ms"])
                    atual.update(filtrados)
                    st.session_state["av_anuncios_bloqueados_ms"] = sorted(atual)
            with col_b2:
                if st.button("Marcar todos", key="av_btn_marcar_todos"):
                    st.session_state["av_anuncios_bloqueados_ms"] = sorted(candidatos)
            with col_b3:
                if st.button("Limpar seleção", key="av_btn_limpar_selecao"):
                    st.session_state["av_anuncios_bloqueados_ms"] = []

            anuncios_bloqueados_selecionados = st.multiselect(
                "Anúncios de outras empresas que não fazem sentido pra esse cliente",
                options=candidatos, key="av_anuncios_bloqueados_ms",
            )
        else:
            st.caption("Nenhum anúncio de outra empresa encontrado nessas categorias.")

    st.divider()
    periodo_ok = data_inicio and data_final
    pronto_para_gerar = bool(chave_cliente and periodo_ok and st.session_state.av_produtos)
    gerar = st.button("Gerar relatório", type="primary", disabled=not pronto_para_gerar, key="av_btn_gerar")

if gerar:
    try:
        ufs_permitidas = resolver_ufs(regioes_selecionadas)
        anuncios_bloqueados = set(anuncios_bloqueados_selecionados)

        produtos = st.session_state.av_produtos
        progress = st.progress(0.0)
        status_area = st.empty()
        resultados = []
        for i, produto in enumerate(produtos):
            status_area.text(f"Consultando leads do produto: {produto}")
            faltantes = get_leads_not_received(
                produto, chave_cliente, data_inicio.isoformat(), data_final.isoformat(),
                ufs_permitidas, anuncios_bloqueados,
            )
            if not faltantes.empty:
                resultados.append(faltantes)
            progress.progress((i + 1) / len(produtos))
        status_area.empty()
        progress.empty()

        if not resultados:
            st.success("Nenhum orçamento perdido encontrado para os produtos deste cliente.")
            st.session_state.pop("av_resultado", None)
        else:
            resultado_bruto = pd.concat(resultados, ignore_index=True)
            col_msg = _coluna_mensagem(resultado_bruto)
            ordem_ia = provedores_ativos()

            perdido_dentro = resultado_bruto
            descartado_fora = pd.DataFrame()
            aberto_incerto = pd.DataFrame()
            filtro_foco_aplicado = False
            avisos_perfil = []

            if col_msg is None:
                st.warning(
                    "A question de leads não trouxe uma coluna de mensagem reconhecida — "
                    "o filtro de foco por IA não pôde rodar. Mostrando todos os não recebidos "
                    "como 'perdido', sem o crítério de foco."
                )
            elif not ordem_ia:
                st.warning(
                    "Nenhuma chave de IA configurada nos Secrets — o filtro de foco não pôde rodar. "
                    "Mostrando todos os não recebidos como 'perdido', sem o crítério de foco."
                )
            else:
                with st.spinner("Montando perfil do cliente (briefing, anúncios, site)..."):
                    try:
                        perfil, _nome, avisos_perfil, _csv_briefing = montar_perfil_cliente(
                            chave_cliente, site=site, obs=obs,
                        )
                    except RuntimeError as e:
                        perfil = ""
                        avisos_perfil = [str(e)]
                for aviso in avisos_perfil:
                    st.warning(aviso)

                if not perfil.strip():
                    st.warning(
                        "Não há briefing, site nem observações suficientes para julgar foco — "
                        "mostrando todos os não recebidos como 'perdido', sem o crítério de foco."
                    )
                else:
                    leads_ia = [
                        {"id": f"V{idx}", "mensagem": str(row[col_msg]) if pd.notna(row[col_msg]) else "",
                         "extra": "; ".join(
                             f"{col}: {row[col]}" for col in resultado_bruto.columns
                             if col != col_msg and pd.notna(row[col])
                         )[:500]}
                        for idx, row in resultado_bruto.reset_index(drop=True).iterrows()
                    ]
                    barra_ia = st.progress(0.0, text="Classificando não recebidos por foco...")
                    classificacoes = classificar_lote(
                        perfil, leads_ia, ordem_ia,
                        progresso_callback=lambda feito, total: barra_ia.progress(feito / total if total else 1.0),
                    )
                    barra_ia.empty()
                    filtro_foco_aplicado = True

                    resultado_bruto = resultado_bruto.reset_index(drop=True)
                    resultado_bruto["STATUS_IA"] = [
                        classificacoes.get(f"V{i}", {}).get("status", "Aberto")
                        for i in range(len(resultado_bruto))
                    ]
                    resultado_bruto["MOTIVO_IA"] = [
                        classificacoes.get(f"V{i}", {}).get("motivo", "Não classificado pela IA.")
                        for i in range(len(resultado_bruto))
                    ]
                    perdido_dentro = resultado_bruto[resultado_bruto["STATUS_IA"] == "Dentro do foco"].copy()
                    descartado_fora = resultado_bruto[resultado_bruto["STATUS_IA"] == "Fora do foco"].copy()
                    aberto_incerto = resultado_bruto[resultado_bruto["STATUS_IA"] == "Aberto"].copy()

            n_perdidos = len(perdido_dentro)
            n_fora = len(descartado_fora)
            n_aberto = len(aberto_incerto)
            if filtro_foco_aplicado:
                st.success(
                    f"{n_perdidos} orçamento(s) perdido(s) de verdade (dentro do foco) — "
                    f"{n_fora} descartado(s) (fora de foco) e {n_aberto} incerto(s), mostrados à parte."
                )
            else:
                st.success(f"{n_perdidos} orçamento(s) não recebido(s) encontrado(s).")

            st.dataframe(perdido_dentro, use_container_width=True)
            if filtro_foco_aplicado and n_fora:
                with st.expander(f"Descartados — fora de foco ({n_fora})"):
                    st.dataframe(descartado_fora, use_container_width=True)
            if filtro_foco_aplicado and n_aberto:
                with st.expander(f"Incertos — aberto ({n_aberto})"):
                    st.dataframe(aberto_incerto, use_container_width=True)

            excel_bytes = gerar_xlsx_volume(perdido_dentro, descartado_fora, aberto_incerto)
            periodo_txt = f"{data_inicio.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"

            st.session_state["av_resultado"] = {
                "excel_bytes": excel_bytes,
                "excel_nome": f"orcamentos_perdidos_{chave_cliente}.xlsx",
                "n_perdidos": n_perdidos, "n_fora": n_fora, "n_aberto": n_aberto,
            }
            if not perdido_dentro.empty and "Produto Consultado" in perdido_dentro.columns:
                contagem_produtos = perdido_dentro.groupby("Produto Consultado").size().sort_values(ascending=False)
                produtos_perdidos = list(contagem_produtos.items())[:8]
            else:
                produtos_perdidos = []

            st.session_state["resultado_volume"] = {
                "chave": chave_cliente, "periodo": periodo_txt,
                "n_perdidos": n_perdidos, "n_fora": n_fora, "n_aberto": n_aberto,
                "produtos_perdidos": produtos_perdidos,
                "excel_bytes": excel_bytes,
                "excel_nome": f"orcamentos_perdidos_{chave_cliente}.xlsx",
            }

            salvar_no_historico({
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "tipo": "volume",
                "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Chave única": chave_cliente,
                "Período": periodo_txt,
                "Perdidos": n_perdidos, "Fora de foco": n_fora, "Aberto": n_aberto,
                "excel_nome": f"orcamentos_perdidos_{chave_cliente}.xlsx",
            }, arquivos={"xlsx": excel_bytes})
    except RuntimeError as e:
        st.error(str(e))

res_av = st.session_state.get("av_resultado")
if res_av:
    st.download_button(
        "Baixar Excel",
        data=res_av["excel_bytes"], file_name=res_av["excel_nome"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="av_dl_excel",
    )

if not st.session_state.av_produtos:
    st.caption('Clique em "Buscar produtos e sugestões de anúncios" antes de gerar o relatório.')
