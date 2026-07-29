"""Lógica de negócio da auditoria de volume (leads perdidos) — extraída da
antiga página `auditoria_volume.py` para poder ser chamada tanto isolada
quanto junto com a validação de foco, na página única de auditoria."""
import unicodedata

import pandas as pd
import streamlit as st

from nucleo.excel import gerar_xlsx_volume
from nucleo.ia import classificar_lote, provedores_ativos
from nucleo.metabase import run_card
from nucleo.perfil_cliente import montar_perfil_cliente
from nucleo.regioes import resolver_ufs

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


def rodar_volume(chave_cliente: str, produtos: list, data_inicio, data_final,
                  regioes_selecionadas: list, anuncios_bloqueados: set,
                  site: str, obs: str) -> dict:
    """Roda a auditoria de volume completa (todos os produtos do cliente) e,
    se possível, aplica o filtro de foco por IA nos não recebidos. Todas as
    chamadas st.* aqui aparecem dentro do `st.status(...)` aberto por quem
    chamou. Devolve um dict com o resultado — nunca lança por 'nada
    encontrado' (isso é resultado válido, só sem orçamentos perdidos)."""
    chave_cliente = chave_cliente.strip()
    ufs_permitidas = resolver_ufs(regioes_selecionadas)

    progress = st.progress(0.0)
    resultados = []
    for i, produto in enumerate(produtos):
        st.write(f"Consultando leads do produto: {produto}")
        faltantes = get_leads_not_received(
            produto, chave_cliente, data_inicio.isoformat(), data_final.isoformat(),
            ufs_permitidas, anuncios_bloqueados,
        )
        if not faltantes.empty:
            resultados.append(faltantes)
        progress.progress((i + 1) / len(produtos))
    progress.empty()

    periodo_txt = f"{data_inicio.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"

    if not resultados:
        return {
            "chave": chave_cliente, "periodo": periodo_txt, "vazio": True,
            "n_perdidos": 0, "n_fora": 0, "n_aberto": 0,
            "produtos_perdidos": [], "excel_bytes": None, "filtro_foco_aplicado": False,
        }

    resultado_bruto = pd.concat(resultados, ignore_index=True)
    col_msg = _coluna_mensagem(resultado_bruto)
    ordem_ia = provedores_ativos()
    filtro_foco_aplicado = False

    if col_msg is None:
        st.warning(
            "A question de leads não trouxe uma coluna de mensagem reconhecida — o filtro de "
            "foco por IA não pôde rodar. Mostrando todos os não recebidos como 'perdido'."
        )
    elif not ordem_ia:
        st.warning(
            "Nenhuma chave de IA configurada nos Secrets — o filtro de foco não pôde rodar. "
            "Mostrando todos os não recebidos como 'perdido'."
        )
    else:
        st.write("Montando perfil do cliente (briefing, anúncios, site)...")
        try:
            perfil, _nome, avisos_perfil, _csv_briefing = montar_perfil_cliente(chave_cliente, site=site, obs=obs)
        except RuntimeError as e:
            perfil = ""
            avisos_perfil = [str(e)]
        for aviso in avisos_perfil:
            st.warning(aviso)

        if not perfil.strip():
            st.warning(
                "Não há briefing, site nem observações suficientes para julgar foco — "
                "mostrando todos os não recebidos como 'perdido'."
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

    if filtro_foco_aplicado:
        perdido_dentro = resultado_bruto[resultado_bruto["STATUS_IA"] == "Dentro do foco"]
        n_fora = int((resultado_bruto["STATUS_IA"] == "Fora do foco").sum())
        n_aberto = int((resultado_bruto["STATUS_IA"] == "Aberto").sum())
    else:
        perdido_dentro = resultado_bruto
        n_fora = 0
        n_aberto = 0

    if not perdido_dentro.empty and "Produto Consultado" in perdido_dentro.columns:
        produtos_perdidos = list(
            perdido_dentro.groupby("Produto Consultado").size().sort_values(ascending=False).items()
        )[:8]
    else:
        produtos_perdidos = []

    excel_bytes = gerar_xlsx_volume(resultado_bruto)

    return {
        "chave": chave_cliente, "periodo": periodo_txt, "vazio": False,
        "filtro_foco_aplicado": filtro_foco_aplicado,
        "n_perdidos": len(perdido_dentro), "n_fora": n_fora, "n_aberto": n_aberto,
        "produtos_perdidos": produtos_perdidos,
        "excel_bytes": excel_bytes, "excel_nome": f"orcamentos_perdidos_{chave_cliente}.xlsx",
    }
