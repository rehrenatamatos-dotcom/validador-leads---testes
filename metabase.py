"""Acesso ao Metabase — autenticação e consulta de questions.

Compartilhado pelas três páginas (saúde do cliente, auditoria de volume e
validador de foco). Suporta autenticação por API key (preferida) ou por
login/senha (sessão renovada automaticamente se expirar).
"""
import json
import os

import requests
import streamlit as st


def secret(nome: str, padrao: str = "") -> str:
    try:
        return str(st.secrets.get(nome, padrao)).strip()
    except Exception:
        return os.environ.get(nome, padrao).strip()


def cabecalhos_metabase():
    """Autentica no Metabase por API key ou por login/senha (sessão)."""
    api_key = secret("METABASE_API_KEY")
    if api_key:
        return {"X-API-KEY": api_key}
    if "mb_sessao" in st.session_state:
        return {"X-Metabase-Session": st.session_state["mb_sessao"]}
    usuario, senha = secret("METABASE_USER"), secret("METABASE_PASSWORD")
    if not (usuario and senha):
        return None
    r = requests.post(
        secret("METABASE_URL").rstrip("/") + "/api/session",
        json={"username": usuario, "password": senha},
        timeout=30,
    )
    r.raise_for_status()
    st.session_state["mb_sessao"] = r.json()["id"]
    return {"X-Metabase-Session": st.session_state["mb_sessao"]}


def metabase_configurado() -> bool:
    if not secret("METABASE_URL"):
        return False
    return bool(secret("METABASE_API_KEY") or (secret("METABASE_USER") and secret("METABASE_PASSWORD")))


def consultar_question(card_id: int, parametros: list) -> str:
    """Baixa o resultado CSV de uma question do Metabase com parâmetros.

    parametros: lista de tuplas (nome_do_template_tag, valor, tipo_do_metabase).
    """
    url = secret("METABASE_URL").rstrip("/") + f"/api/card/{card_id}/query/csv"
    headers = cabecalhos_metabase()
    if headers is None:
        raise RuntimeError(
            "Credenciais do Metabase não configuradas. Adicione nos Secrets: "
            "METABASE_URL e (METABASE_API_KEY ou METABASE_USER + METABASE_PASSWORD)."
        )
    params_mb = [
        {"type": tipo, "target": ["variable", ["template-tag", nome]], "value": valor}
        for nome, valor, tipo in parametros
    ]
    r = requests.post(url, headers=headers, data={"parameters": json.dumps(params_mb)}, timeout=120)
    if r.status_code == 401 and "mb_sessao" in st.session_state:
        del st.session_state["mb_sessao"]           # sessão expirada → renova e tenta de novo
        headers = cabecalhos_metabase()
        r = requests.post(url, headers=headers, data={"parameters": json.dumps(params_mb)}, timeout=120)
    r.raise_for_status()
    return r.content.decode("utf-8-sig", errors="replace")


def run_card(card_id: int, parametros_json: list):
    """Roda uma question e devolve um pandas.DataFrame (usado pela auditoria de
    volume, que precisa filtrar/agrupar em memória em vez de só ler linha a
    linha de um CSV). parametros_json é a lista de parâmetros já no formato
    de payload do Metabase (type/target/value)."""
    import pandas as pd

    url = secret("METABASE_URL").rstrip("/") + f"/api/card/{card_id}/query"
    headers = cabecalhos_metabase()
    if headers is None:
        raise RuntimeError(
            "Credenciais do Metabase não configuradas. Adicione nos Secrets: "
            "METABASE_URL e (METABASE_API_KEY ou METABASE_USER + METABASE_PASSWORD)."
        )
    resp = requests.post(url, headers=headers, json={"parameters": parametros_json}, timeout=60)
    if resp.status_code == 401 and "mb_sessao" in st.session_state:
        del st.session_state["mb_sessao"]
        headers = cabecalhos_metabase()
        resp = requests.post(url, headers=headers, json={"parameters": parametros_json}, timeout=60)
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"Erro ao consultar a question {card_id} no Metabase: "
            f"{resp.status_code} - {resp.text}"
        )
    data = resp.json()
    rows = data.get("data", {}).get("rows", [])
    cols = [c["display_name"] for c in data.get("data", {}).get("cols", [])]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)
