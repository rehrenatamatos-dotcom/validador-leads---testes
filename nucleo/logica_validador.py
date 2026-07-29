"""Lógica de negócio da validação de foco (leads recebidos) — extraída da
antiga página `validador_foco.py` para poder ser chamada tanto isolada
quanto junto com a auditoria de volume, na página única de auditoria.

Todas as chamadas st.* daqui (progress, warning) aparecem dentro do
`st.status(...)` que a página abre ao redor de `rodar_validacao()` — é
assim que o Streamlit roteia saídas de uma função pra um container, sem
precisar passar callback explícito."""
import csv
import io
import time
from datetime import datetime

import streamlit as st

from nucleo.excel import gerar_xlsx_validado
from nucleo.dashboard_html import gerar_dashboard_html
from nucleo.ia import MODELOS_ESCOLHA, STATUS_VALIDOS, TAMANHO_LOTE, chamar_ia, provedores_ativos
from nucleo.metabase import consultar_question
from nucleo.perfil_cliente import (
    CARD_BRIEFING, CARD_ANUNCIOS, extrair_nome_empresa,
    csv_briefing_para_texto, csv_anuncios_para_texto, buscar_site,
)

CARD_ORCAMENTOS = 47   # question do Metabase: base de orçamentos por chave única
LIMITE_PERFIL = 9000

MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def normalizar_data_orcamento(texto):
    """Converte 'maio 4, 2026, 4:47 PM' (formato do Metabase) numa chave por
    MINUTO, pra comparar horários sem depender de locale do servidor.
    Retorna "" se não conseguir interpretar (nunca conta como duplicado)."""
    try:
        mes_dia, ano_str, hora_str = [p.strip() for p in texto.strip().split(",")]
        mes_nome, dia_str = mes_dia.split()
        mes = MESES_PT.get(mes_nome.lower())
        if not mes:
            return ""
        hora_dt = datetime.strptime(hora_str, "%I:%M %p")
        return f"{int(ano_str):04d}-{mes:02d}-{int(dia_str):02d} {hora_dt.hour:02d}:{hora_dt.minute:02d}"
    except Exception:
        return ""


def rodar_validacao(chave_unica: str, data_inicio, data_fim, site: str, obs: str,
                     modelo_escolha: str, tema: str) -> dict:
    """Roda o pipeline completo da validação de foco. Lança RuntimeError nos
    casos que impedem continuar (sem chave de IA, sem orçamento, etc.) —
    quem chama decide como mostrar o erro. Avisos que não impedem continuar
    (sem briefing, sem anúncios) viram st.warning direto, que aparece
    dentro do st.status aberto por quem chamou."""
    chave_unica = chave_unica.strip()
    ordem_ia = provedores_ativos()
    if not ordem_ia:
        raise RuntimeError(
            "Nenhuma chave de IA configurada. Adicione CEREBRAS_API_KEY, GROQ_API_KEY, "
            "SAMBANOVA_API_KEY ou GEMINI_API_KEY nos Secrets."
        )
    if not chave_unica:
        raise RuntimeError("Preencha a chave única do cliente.")
    if data_inicio > data_fim:
        raise RuntimeError("A data de início não pode ser depois da data de fim.")

    modelo_forcado = None
    escolha = MODELOS_ESCOLHA.get(modelo_escolha)
    if escolha:
        prov, modelo_forcado = escolha
        if prov not in ordem_ia:
            raise RuntimeError(
                f"O modelo escolhido usa {prov.title()}, mas não há chave desse provedor nos "
                "Secrets. Escolha outro modelo ou adicione a chave."
            )
        ordem_ia = [prov] + [p for p in ordem_ia if p != prov]

    st.write("Buscando briefing no Metabase...")
    try:
        csv_briefing = consultar_question(CARD_BRIEFING, [("chave_unica", chave_unica, "category")])
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar o briefing (question {CARD_BRIEFING}): {e}")
    texto_briefing = csv_briefing_para_texto(csv_briefing)
    if not texto_briefing:
        st.warning(
            f'Nenhum briefing cadastrado para a chave "{chave_unica}". A IA vai se basear no '
            "site informado e nas observações do projeto."
        )
    nome_empresa = extrair_nome_empresa(csv_briefing) or chave_unica

    st.write("Buscando orçamentos no Metabase...")
    try:
        csv_orcamentos = consultar_question(CARD_ORCAMENTOS, [
            ("chave_unica", chave_unica, "category"),
            ("data_inicio", data_inicio.isoformat(), "date/single"),
            ("data_fim", data_fim.isoformat(), "date/single"),
        ])
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar os orçamentos (question {CARD_ORCAMENTOS}): {e}")
    linhas = list(csv.reader(io.StringIO(csv_orcamentos)))
    if len(linhas) < 2:
        raise RuntimeError("Nenhum orçamento encontrado para essa chave única nesse período.")

    if nome_empresa == chave_unica:
        nome_empresa = extrair_nome_empresa(csv_orcamentos) or nome_empresa
    st.write(f"Cliente identificado: {nome_empresa}")

    texto_anuncios = ""
    st.write("Buscando anúncios do cliente...")
    try:
        csv_anuncios = consultar_question(CARD_ANUNCIOS, [("chave_unica", chave_unica, "category")])
        texto_anuncios = csv_anuncios_para_texto(csv_anuncios)
    except Exception:
        st.warning("Não consegui buscar os anúncios (question 185) — prosseguindo sem eles.")

    texto_site = ""
    if site.strip():
        texto_site = buscar_site(site.strip())
        if not texto_site:
            st.warning("Não consegui ler o site informado — prosseguindo sem ele.")

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

    if not perfil.strip():
        raise RuntimeError(
            "Não há briefing, site nem observações suficientes para avaliar esse cliente. "
            "Preencha o site ou as observações do projeto e envie de novo."
        )
    if len(perfil) > LIMITE_PERFIL:
        perfil = perfil[:LIMITE_PERFIL] + "\n[... perfil truncado para caber no limite da IA gratuita ...]"

    cabecalho = [c.strip() for c in linhas[0]]
    col_msg = "Mensagem do Cliente"
    if col_msg not in cabecalho:
        raise RuntimeError(f'Coluna "{col_msg}" não encontrada no retorno do Metabase. Colunas: {", ".join(cabecalho)}')
    idx_msg = cabecalho.index(col_msg)

    def idx_de(*nomes):
        for n in nomes:
            if n in cabecalho:
                return cabecalho.index(n)
        return -1

    idx_id = idx_de("ID do Orçamento", "ID do Orcamento")
    idx_nome = idx_de("Nome do Comprador", "Nome do comprador")
    idx_email = idx_de("E-mail do Comprador", "Email do Comprador", "E-mail do comprador")
    idx_anuncio = idx_de("anúncio de origem do Orçamento", "Anúncio do cliente", "anuncio de origem do Orçamento")
    idx_data = idx_de("Data da Solicitação do Orçamento", "Data da Solicitação")

    registros = [r for r in linhas[1:] if any(c.strip() for c in r)]
    st.write(f"{len(registros)} leads encontrados de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}.")

    def celula(r, idx):
        return r[idx].strip() if 0 <= idx < len(r) else ""

    leads = []
    for i, r in enumerate(registros):
        extra = "; ".join(
            f"{cabecalho[j]}: {r[j]}" for j in range(len(cabecalho))
            if j != idx_msg and j < len(r) and r[j].strip()
        )[:500]
        nome_raw = celula(r, idx_nome)
        email_raw = celula(r, idx_email)
        msg_raw = celula(r, idx_msg)
        leads.append({
            "id": f"L{i+2}",
            "mensagem": r[idx_msg] if idx_msg < len(r) else "",
            "extra": extra,
            "id_orc": celula(r, idx_id) or f"linha {i+2}",
            "nome": nome_raw or "(sem nome)",
            "email": email_raw or "(sem e-mail)",
            "anuncio": celula(r, idx_anuncio) or "(sem anúncio)",
            "tam_msg": len(msg_raw),
            "_dedup_chave": (nome_raw.lower(), email_raw.lower(), msg_raw.lower(),
                             normalizar_data_orcamento(celula(r, idx_data))),
        })

    vistos_dedup = set()
    duplicados_count = 0
    for l in leads:
        chave = l["_dedup_chave"]
        completa = all(chave)
        if completa and chave in vistos_dedup:
            l["duplicado"] = True
            duplicados_count += 1
        else:
            l["duplicado"] = False
            if completa:
                vistos_dedup.add(chave)
    if duplicados_count:
        st.warning(
            f"{duplicados_count} lead(s) identificado(s) como duplicado de plataforma — "
            "marcados como \"Duplicado\" no Excel, sem entrar na contagem nem na análise da IA."
        )
    leads_para_ia = [l for l in leads if not l["duplicado"]]

    classificacoes = {}
    erros_ia = []
    for l in leads:
        if l["duplicado"]:
            classificacoes[l["id"]] = {
                "status": "Duplicado",
                "motivo": "Mesmo nome, e-mail, mensagem e horário (minuto) de outro orçamento — "
                          "provável duplicação da plataforma. Não entrou na análise da IA.",
            }

    def processar(lista, tamanho_lote, rotulo):
        total_lotes = (len(lista) + tamanho_lote - 1) // tamanho_lote
        progresso = st.progress(0, text=f"{rotulo}: {len(lista)} leads...")
        for n in range(total_lotes):
            lote = lista[n * tamanho_lote:(n + 1) * tamanho_lote]
            try:
                resultado = chamar_ia(perfil, lote, ordem_ia, modelo_forcado)
            except RuntimeError:
                progresso.empty()
                raise
            except Exception as e:
                erros_ia.append(f"{type(e).__name__}: {e}")
                resultado = []
            for item in resultado:
                status = str(item.get("status", "")).strip()
                if status not in STATUS_VALIDOS:
                    status = "Aberto"
                classificacoes[str(item.get("id", "")).strip()] = {
                    "status": status, "motivo": str(item.get("motivo", "")).strip(),
                }
            progresso.progress((n + 1) / total_lotes, text=f"{rotulo}: lote {n+1} de {total_lotes}")
            if n + 1 < total_lotes:
                time.sleep(1)
        progresso.empty()

    st.write("Classificando leads com IA...")
    processar(leads_para_ia, TAMANHO_LOTE, "Classificando")
    pendentes = [l for l in leads_para_ia if l["id"] not in classificacoes]
    if pendentes:
        st.write(f"{len(pendentes)} lead(s) sem resposta — reprocessando em lotes menores...")
        time.sleep(5)
        processar(pendentes, 5, "Reprocessando")
    pendentes = [l for l in leads_para_ia if l["id"] not in classificacoes]
    if pendentes:
        time.sleep(5)
        processar(pendentes, 1, "Última passada")
    falhas = sum(1 for l in leads_para_ia if l["id"] not in classificacoes)

    contagem = {"Dentro do foco": 0, "Fora do foco": 0, "Aberto": 0}
    for i in range(len(registros)):
        c = classificacoes.get(leads[i]["id"])
        status = c["status"] if c else "Aberto"
        leads[i]["status"] = status
        if status != "Duplicado":
            contagem[status] += 1

    dentro = [l for l in leads if l.get("status") == "Dentro do foco"]
    fora = [l for l in leads if l.get("status") == "Fora do foco"]
    melhores = sorted(dentro, key=lambda l: l["tam_msg"], reverse=True)[:10]
    melhores = [{"id": l["id_orc"], "nome": l["nome"], "email": l["email"]} for l in melhores]
    piores = fora[:10]
    piores = [{"id": l["id_orc"], "nome": l["nome"], "email": l["email"]} for l in piores]
    cont_anuncios = {}
    for l in fora:
        cont_anuncios[l["anuncio"]] = cont_anuncios.get(l["anuncio"], 0) + 1
    anuncios_ruins = sorted(cont_anuncios.items(), key=lambda x: x[1], reverse=True)[:8]

    xlsx_bytes = gerar_xlsx_validado(cabecalho, registros, leads, classificacoes)

    total = len(registros) - duplicados_count
    periodo_txt = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    base_nome = f"{nome_empresa} - {data_inicio.isoformat()} a {data_fim.isoformat()}"
    dash_html = gerar_dashboard_html(nome_empresa, chave_unica, periodo_txt, total, contagem,
                                     melhores=melhores, piores=piores, anuncios_ruins=anuncios_ruins,
                                     tema=tema, xlsx_bytes=xlsx_bytes,
                                     xlsx_nome=f"{base_nome} - Validado.xlsx")

    return {
        "chave": chave_unica, "empresa": nome_empresa, "periodo": periodo_txt,
        "total": total, "contagem": contagem, "falhas": falhas,
        "erro_ia": erros_ia[-1] if erros_ia else "",
        "anuncios_ruins": anuncios_ruins,
        "xlsx_bytes": xlsx_bytes, "xlsx_nome": f"{base_nome} - Validado.xlsx",
        "dash_bytes": dash_html.encode("utf-8"), "dash_nome": f"{base_nome} - Dashboard.html",
    }
