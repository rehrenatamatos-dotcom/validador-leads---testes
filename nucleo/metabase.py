"""Acesso ao Metabase — autenticação e consulta de questions.

Compartilhado pelas três páginas (saúde do cliente, auditoria de volume e
validador de foco). Suporta autenticação por API key (preferida) ou por
login/senha (sessão renovada automaticamente se expirar).
"""
import json
import os
import unicodedata

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


def _norm_nome(s) -> str:
    """Normaliza o nome de um parâmetro pra casar sem depender de acento,
    maiúscula, underscore ou espaço (ex.: 'Chave Única' == 'chave_unica')."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("_", "").replace(" ", "")


def _params_do_card(card_id: int, headers: dict, url_base: str):
    """Busca (e cacheia) os parâmetros de um card: um mapa {nome_template_tag: id}
    e a lista de TODOS os ids de parâmetro do card.

    As versões novas do Metabase EXIGEM um campo `id` (não-vazio) em cada
    parâmetro do payload — o mesmo que a interface envia. Aqui lemos esse id
    direto da definição do card.
    """
    chave_cache = f"mb_params_{card_id}"
    if chave_cache in st.session_state:
        return st.session_state[chave_cache]
    r = requests.get(f"{url_base}/api/card/{card_id}", headers=headers, timeout=30)
    r.raise_for_status()
    card = r.json()
    mapa, todos = {}, []
    # 1) parâmetros declarados no card (o que a UI usa)
    for p in card.get("parameters") or []:
        pid = p.get("id")
        if not pid:
            continue
        if pid not in todos:
            todos.append(pid)
        alvo = p.get("target")
        if isinstance(alvo, list) and len(alvo) >= 2 and isinstance(alvo[1], list):
            mapa.setdefault(alvo[1][-1], pid)
    # 2) template-tags da query nativa (fonte mais confiável do id)
    tags = ((card.get("dataset_query") or {}).get("native") or {}).get("template-tags") or {}
    for nome, tag in tags.items():
        pid = tag.get("id")
        if pid:
            mapa.setdefault(nome, pid)
            if pid not in todos:
                todos.append(pid)
    resultado = (mapa, todos)
    st.session_state[chave_cache] = resultado
    return resultado


def _injetar_ids(card_id: int, headers: dict, url_base: str, params_mb: list) -> list:
    """Adiciona o campo `id` em cada parâmetro. Casa pelo nome do template-tag
    (tolerante a acento/maiúscula/underscore) e, se o card tem um único
    parâmetro, usa esse id mesmo que o nome não bata exatamente."""
    mapa, todos = _params_do_card(card_id, headers, url_base)
    mapa_norm = {_norm_nome(k): v for k, v in mapa.items()}
    resultado = []
    for p in params_mb:
        novo = dict(p)
        alvo = p.get("target")
        nome = alvo[1][-1] if (isinstance(alvo, list) and len(alvo) >= 2 and isinstance(alvo[1], list)) else None
        pid = None
        if nome is not None:
            pid = mapa.get(nome) or mapa_norm.get(_norm_nome(nome))
        if pid is None and len(todos) == 1:
            pid = todos[0]
        if pid is not None:
            novo["id"] = pid
        resultado.append(novo)
    return resultado


def consultar_question(card_id: int, parametros: list) -> str:
    """Baixa o resultado CSV de uma question do Metabase com parâmetros.

    parametros: lista de tuplas (nome_do_template_tag, valor, tipo_do_metabase).
    """
    url_base = secret("METABASE_URL").rstrip("/")
    url = f"{url_base}/api/card/{card_id}/query/csv"
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
    params_mb = _injetar_ids(card_id, headers, url_base, params_mb)
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

    url_base = secret("METABASE_URL").rstrip("/")
    url = f"{url_base}/api/card/{card_id}/query"
    headers = cabecalhos_metabase()
    if headers is None:
        raise RuntimeError(
            "Credenciais do Metabase não configuradas. Adicione nos Secrets: "
            "METABASE_URL e (METABASE_API_KEY ou METABASE_USER + METABASE_PASSWORD)."
        )
    parametros_json = _injetar_ids(card_id, headers, url_base, parametros_json)
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
