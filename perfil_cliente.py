"""Monta o "perfil do cliente" usado pela IA para julgar foco — a mesma
peça de contexto é usada tanto pelo validador de foco (leads recebidos)
quanto pela auditoria de volume (leads não recebidos), pra garantir que os
dois lados apliquem exatamente o mesmo crítério."""
import csv
import io
import re

import requests

from nucleo.metabase import consultar_question

LIMITE_FONTE = 4000
LIMITE_PERFIL = 9000

CARD_BRIEFING = 286    # question do Metabase: briefing do cliente por chave única
CARD_ANUNCIOS = 185    # question do Metabase: anúncios por chave única


def csv_anuncios_para_texto(conteudo_csv, limite=LIMITE_FONTE):
    """Transforma o CSV de anúncios em uma lista compacta de nomes."""
    linhas = list(csv.reader(io.StringIO(conteudo_csv)))
    if len(linhas) < 2:
        return ""
    itens = []
    for r in linhas[1:]:
        valores = [c.strip() for c in r if c.strip()]
        if valores:
            itens.append(" | ".join(valores))
    return "\n".join(itens)[:limite]


def extrair_nome_empresa(conteudo_csv):
    """Procura o nome do cliente em qualquer CSV do Metabase que tenha essa coluna."""
    try:
        linhas = list(csv.reader(io.StringIO(conteudo_csv)))
        if len(linhas) < 2:
            return None
        h = [c.strip().lower() for c in linhas[0]]
        for cand in ("nome fantasia", "nome da empresa", "empresa"):
            if cand in h:
                v = linhas[1][h.index(cand)].strip()
                if v:
                    return v
    except Exception:
        pass
    return None


def buscar_site(url, limite=LIMITE_FONTE):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        html = r.text
    except Exception:
        return ""
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    texto = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", texto).strip()[:limite]


def csv_briefing_para_texto(conteudo_csv, limite=LIMITE_FONTE):
    """Converte o CSV do briefing (colunas longas) em texto legível para a IA."""
    linhas = list(csv.reader(io.StringIO(conteudo_csv)))
    if len(linhas) < 2:
        return ""
    h = linhas[0]
    blocos = []
    for r in linhas[1:]:
        campos = [f"{h[j]}: {r[j].strip()}" for j in range(min(len(h), len(r))) if r[j].strip()]
        blocos.append("\n".join(campos))
    return ("\n\n--- produto/linha seguinte ---\n\n".join(blocos))[:limite]


def montar_perfil_cliente(chave_unica: str, site: str = "", obs: str = "", incluir_anuncios: bool = True):
    """Busca briefing (286) e, opcionalmente, anúncios ativos (185) no
    Metabase para a chave única informada, e monta o texto de perfil usado
    pela IA (mesmo formato nos dois fluxos).

    Devolve (perfil_texto, nome_empresa_ou_None, avisos: list[str], csv_briefing: str).
    Lança RuntimeError apenas se a consulta ao Metabase falhar de verdade —
    briefing/anúncios ausentes geram aviso, não erro (nem todo cliente tem
    briefing cadastrado)."""
    avisos = []

    try:
        csv_briefing = consultar_question(CARD_BRIEFING, [("chave_unica", chave_unica, "category")])
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar o briefing (question {CARD_BRIEFING}): {e}")
    texto_briefing = csv_briefing_para_texto(csv_briefing)
    if not texto_briefing:
        avisos.append(
            f'Nenhum briefing cadastrado para a chave "{chave_unica}". '
            "A IA vai se basear no site informado e nas observações do projeto."
        )
    nome_empresa = extrair_nome_empresa(csv_briefing)

    texto_anuncios = ""
    if incluir_anuncios:
        try:
            csv_anuncios = consultar_question(CARD_ANUNCIOS, [("chave_unica", chave_unica, "category")])
            texto_anuncios = csv_anuncios_para_texto(csv_anuncios)
        except Exception:
            avisos.append("Não consegui buscar os anúncios ativos (question 185) — prosseguindo sem eles.")

    texto_site = ""
    if site.strip():
        texto_site = buscar_site(site.strip())
        if not texto_site:
            avisos.append("Não consegui ler o site informado — prosseguindo sem ele.")

    partes_perfil = []
    if obs.strip():
        partes_perfil.append(f"===== OBSERVAÇÕES DO PROJETO (prioridade máxima) =====\n{obs.strip()}")
    if texto_briefing:
        partes_perfil.append(f"===== BRIEFING DO CLIENTE (Metabase) =====\n{texto_briefing}")
    if texto_site:
        partes_perfil.append(f"===== SITE DO CLIENTE ({site.strip()}) =====\n{texto_site}")
    if texto_anuncios:
        partes_perfil.append(f"===== ANÚNCIOS ATIVOS DO CLIENTE (termos anunciados) =====\n{texto_anuncios}")
    perfil = "\n\n".join(partes_perfil)

    if len(perfil) > LIMITE_PERFIL:
        perfil = perfil[:LIMITE_PERFIL] + "\n[... perfil truncado para caber no limite da IA gratuita ...]"

    return perfil, nome_empresa, avisos, csv_briefing
