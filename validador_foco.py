"""Validação de foco — dos leads que o cliente já recebeu (question 47),
classifica cada um via IA como Dentro do foco / Fora do foco / Aberto,
comparando a mensagem com o briefing, o site e os anúncios ativos do
cliente. Adaptado de validador-leads/webapp/app_v3.py."""
import csv
import io
import time
from datetime import date, datetime, timedelta

import streamlit as st

from nucleo.excel import gerar_xlsx_validado
from nucleo.dashboard_html import gerar_dashboard_html
from nucleo.historico import (
    carregar_historico, salvar_no_historico, excluir_do_historico, ler_resultado_salvo,
)
from nucleo.ia import (
    MODELOS_ESCOLHA, STATUS_VALIDOS, TAMANHO_LOTE,
    chamar_ia, provedores_ativos,
)
from nucleo.metabase import consultar_question
from nucleo.perfil_cliente import (
    CARD_BRIEFING, CARD_ANUNCIOS, extrair_nome_empresa,
    csv_briefing_para_texto, csv_anuncios_para_texto, buscar_site,
)
from nucleo.tema import hero, tema_ativo, titulo_painel

CARD_ORCAMENTOS = 47   # question do Metabase: base de orçamentos por chave única

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


tema, T = tema_ativo()

hero(
    "Validação de foco",
    "Validação de foco",
    "Informe a chave única do cliente e o período — a ferramenta busca sozinha o briefing, "
    "os orçamentos e os anúncios no Metabase e classifica cada lead recebido com IA.",
)

CAMPOS_FORM = ("vf_chave", "vf_site", "vf_obs", "vf_modelo")
if st.session_state.pop("vf_limpar_form", False):
    for k in CAMPOS_FORM:
        st.session_state.pop(k, None)
    st.session_state.pop("vf_resultado", None)

with st.container(border=True, key="vf_painel_form"):
    titulo_painel("fact_check", "Configurações de validação")
    st.caption("Preencha os campos obrigatórios (*) para iniciar a validação.")
    grid_a, grid_b = st.columns(2)
    with grid_a:
        chave_unica = st.text_input(
            "Chave única do cliente *", placeholder="Ex.: 12-34567-1", key="vf_chave",
            help="Identificador usado para localizar o briefing, os orçamentos e os anúncios do cliente.",
        )
    with grid_b:
        st.markdown(
            f"<div style='font-weight:600; font-size:0.82rem; color:{T['label']}; margin-bottom:0.4rem;'>Período</div>",
            unsafe_allow_html=True,
        )
        p_a, p_b = st.columns(2)
        with p_a:
            data_inicio = st.date_input(
                "Início", value=date.today() - timedelta(days=90), format="DD/MM/YYYY",
                label_visibility="collapsed", key="vf_data_inicio",
            )
        with p_b:
            data_fim = st.date_input(
                "Fim", value=date.today(), format="DD/MM/YYYY",
                label_visibility="collapsed", key="vf_data_fim",
            )

    grid_c, grid_d = st.columns(2)
    with grid_c:
        site = st.text_input(
            "Site do cliente (opcional)",
            placeholder="https://www.sitedocliente.com.br", key="vf_site",
            help="Importante quando não houver briefing cadastrado para o cliente.",
        )
    with grid_d:
        obs = st.text_area(
            "Observações (opcional)",
            placeholder="Ex.: cliente só vende máquinas (serviço, assistência, aluguel e peças = fora do foco).",
            height=90, key="vf_obs",
            help="Use para informar restrições de escopo, principalmente se não existir briefing.",
        )

    linha_final_a, linha_final_b, linha_final_c = st.columns([2, 1, 1])
    with linha_final_a:
        modelo_escolha = st.selectbox(
            "Processamento",
            list(MODELOS_ESCOLHA.keys()),
            key="vf_modelo",
            help="Rápido = resposta mais veloz, boa para o dia a dia. Preciso = mais lento, "
                 "melhor em casos sutis. Automático usa o provedor com maior cota disponível.",
        )
    with linha_final_b:
        st.markdown("<div style='height:1.85rem;'></div>", unsafe_allow_html=True)
        confirmando_limpeza = st.session_state.get("vf_confirmar_limpar", False)
        rotulo_limpar = "Confirmar limpeza" if confirmando_limpeza else "Limpar campos"
        if st.button(rotulo_limpar, use_container_width=True, key="vf_btn_limpar", type="secondary"):
            if confirmando_limpeza:
                st.session_state["vf_confirmar_limpar"] = False
                st.session_state["vf_limpar_form"] = True
                st.rerun()
            else:
                st.session_state["vf_confirmar_limpar"] = True
                st.rerun()
    with linha_final_c:
        st.markdown("<div style='height:1.85rem;'></div>", unsafe_allow_html=True)
        botao_validar_ph = st.empty()
        with botao_validar_ph.container():
            validar = st.button("Validar leads", type="primary", use_container_width=True, key="vf_btn_validar")
        st.caption("A análise pode levar alguns minutos. Não feche esta página durante o processamento.")

TOTAL_ETAPAS = 5


def marcar_etapa(n, texto):
    with botao_validar_ph.container():
        st.markdown(
            f"<div style='background: rgba(46,123,255,0.16); border: 1px solid rgba(46,123,255,0.45); "
            f"color: {T['label']}; text-align: center; padding: 11px 10px; border-radius: 999px; "
            f"font-size: 0.82rem; font-weight: 700;'>Etapa {n} de {TOTAL_ETAPAS} · {texto}</div>",
            unsafe_allow_html=True,
        )


def marcar_etapa_erro(n, texto):
    with botao_validar_ph.container():
        st.markdown(
            f"<div style='background: rgba(216,90,48,0.16); border: 1px solid rgba(216,90,48,0.55); "
            f"color: #D85A30; text-align: center; padding: 11px 10px; border-radius: 999px; "
            f"font-size: 0.82rem; font-weight: 700;'>Erro na Etapa {n} · {texto}</div>",
            unsafe_allow_html=True,
        )


def montar_regras():
    if obs.strip():
        return f"- Observações do projeto (prioridade máxima): {obs.strip()}"
    return ""


if validar:
    st.session_state.pop("vf_resultado", None)
    st.session_state["vf_confirmar_limpar"] = False
    ordem_ia = provedores_ativos()
    if not ordem_ia:
        st.error("Nenhuma chave de IA configurada. Adicione CEREBRAS_API_KEY, GROQ_API_KEY, "
                 "SAMBANOVA_API_KEY ou GEMINI_API_KEY nos Secrets.")
        st.stop()
    if not chave_unica.strip():
        st.error("Preencha a chave única do cliente.")
        st.stop()
    if data_inicio > data_fim:
        st.error("A data de início não pode ser depois da data de fim.")
        st.stop()

    modelo_forcado = None
    escolha = MODELOS_ESCOLHA.get(modelo_escolha)
    if escolha:
        prov, modelo_forcado = escolha
        if prov not in ordem_ia:
            st.error(f"O modelo escolhido usa {prov.title()}, mas não há chave desse provedor nos Secrets. "
                     "Escolha outro modelo ou adicione a chave.")
            st.stop()
        ordem_ia = [prov] + [p for p in ordem_ia if p != prov]

    nomes_ia = {"cerebras": "Cerebras", "groq": "Groq", "sambanova": "SambaNova", "gemini": "Gemini"}
    if modelo_forcado:
        st.caption(f"IA: {modelo_escolha}"
                   + (f" · reserva: {nomes_ia[ordem_ia[1]]}" if len(ordem_ia) > 1 else ""))
    else:
        st.caption("IA: " + " → ".join(nomes_ia[n] for n in ordem_ia)
                   + (" (reserva automática)" if len(ordem_ia) > 1 else ""))

    marcar_etapa(1, "Buscando briefing no Metabase...")
    try:
        csv_briefing = consultar_question(CARD_BRIEFING, [("chave_unica", chave_unica.strip(), "category")])
    except Exception as e:
        marcar_etapa_erro(1, "falha ao buscar briefing")
        st.error(f"Erro ao buscar o briefing (question {CARD_BRIEFING}): {e}")
        st.stop()
    texto_briefing = csv_briefing_para_texto(csv_briefing)
    if not texto_briefing:
        st.warning(
            f'Nenhum briefing cadastrado para a chave "{chave_unica}". '
            "A IA vai se basear no site informado e nas observações do projeto — "
            "preencha ao menos um desses dois campos para esse cliente."
        )
    nome_empresa = extrair_nome_empresa(csv_briefing) or chave_unica.strip()

    marcar_etapa(2, "Buscando orçamentos no Metabase...")
    try:
        csv_orcamentos = consultar_question(CARD_ORCAMENTOS, [
            ("chave_unica", chave_unica.strip(), "category"),
            ("data_inicio", data_inicio.isoformat(), "date/single"),
            ("data_fim", data_fim.isoformat(), "date/single"),
        ])
    except Exception as e:
        marcar_etapa_erro(2, "falha ao buscar orçamentos")
        st.error(f"Erro ao buscar os orçamentos (question {CARD_ORCAMENTOS}): {e}")
        st.stop()
    linhas = list(csv.reader(io.StringIO(csv_orcamentos)))
    if len(linhas) < 2:
        marcar_etapa_erro(2, "nenhum orçamento encontrado")
        st.error("Nenhum orçamento encontrado para essa chave única nesse período.")
        st.stop()

    if nome_empresa == chave_unica.strip():
        nome_empresa = extrair_nome_empresa(csv_orcamentos) or nome_empresa
    st.caption(f"Cliente identificado: {nome_empresa}")

    texto_anuncios = ""
    marcar_etapa(3, "Buscando anúncios do cliente...")
    try:
        csv_anuncios = consultar_question(CARD_ANUNCIOS, [("chave_unica", chave_unica.strip(), "category")])
        texto_anuncios = csv_anuncios_para_texto(csv_anuncios)
    except Exception:
        st.warning("Não consegui buscar os anúncios (question 185) — prosseguindo sem eles.")

    texto_site = ""
    marcar_etapa(4, "Preparando perfil do cliente...")
    if site.strip():
        texto_site = buscar_site(site.strip())
        if not texto_site:
            st.warning("Não consegui ler o site informado — prosseguindo sem ele.")

    partes_perfil = []
    regras_projeto = montar_regras()
    if regras_projeto:
        partes_perfil.append(f"===== OBSERVAÇÕES DO PROJETO (prioridade máxima) =====\n{regras_projeto}")
    if texto_briefing:
        partes_perfil.append(f"===== BRIEFING DO CLIENTE (Metabase) =====\n{texto_briefing}")
    if texto_site:
        partes_perfil.append(f"===== SITE DO CLIENTE ({site.strip()}) =====\n{texto_site}")
    if texto_anuncios:
        partes_perfil.append(f"===== ANÚNCIOS ATIVOS DO CLIENTE (termos anunciados) =====\n{texto_anuncios}")
    perfil = "\n\n".join(partes_perfil)

    LIMITE_PERFIL = 9000
    if not perfil.strip():
        marcar_etapa_erro(4, "perfil do cliente insuficiente")
        st.error(
            "Não há briefing, site nem observações suficientes para avaliar esse cliente. "
            "Preencha o site ou as observações do projeto e envie de novo."
        )
        st.stop()
    if len(perfil) > LIMITE_PERFIL:
        perfil = perfil[:LIMITE_PERFIL] + "\n[... perfil truncado para caber no limite da IA gratuita ...]"

    cabecalho = [c.strip() for c in linhas[0]]
    col_msg = "Mensagem do Cliente"
    if col_msg not in cabecalho:
        marcar_etapa_erro(4, "coluna de mensagem não encontrada")
        st.error(f'Coluna "{col_msg}" não encontrada no retorno do Metabase. Colunas: {", ".join(cabecalho)}')
        st.stop()
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
    st.info(f"{len(registros)} leads encontrados de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}.")

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
            f"{duplicados_count} lead(s) identificado(s) como duplicado de plataforma "
            "(mesmo nome, e-mail, mensagem e horário) — marcados como \"Duplicado\" no Excel, "
            "sem entrar na contagem, no dashboard nem na análise da IA."
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
            except RuntimeError as e:
                progresso.empty()
                marcar_etapa_erro(5, "cota de IA esgotada")
                st.error(str(e))
                st.stop()
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

    marcar_etapa(5, "Classificando leads com IA...")
    processar(leads_para_ia, TAMANHO_LOTE, "Classificando")
    pendentes = [l for l in leads_para_ia if l["id"] not in classificacoes]
    if pendentes:
        st.info(f"{len(pendentes)} lead(s) sem resposta — reprocessando em lotes menores...")
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
    dash_html = gerar_dashboard_html(nome_empresa, chave_unica.strip(), periodo_txt, total, contagem,
                                     melhores=melhores, piores=piores, anuncios_ruins=anuncios_ruins,
                                     tema=tema, xlsx_bytes=xlsx_bytes,
                                     xlsx_nome=f"{base_nome} - Validado.xlsx")

    st.session_state["vf_resultado"] = {
        "empresa": nome_empresa,
        "total": total,
        "contagem": contagem,
        "falhas": falhas,
        "erro_ia": erros_ia[-1] if erros_ia else "",
        "xlsx_bytes": xlsx_bytes,
        "xlsx_nome": f"{base_nome} - Validado.xlsx",
        "dash_bytes": dash_html.encode("utf-8"),
        "dash_nome": f"{base_nome} - Dashboard.html",
    }

    # Guarda também no estado global compartilhado, para a tela "Saúde do
    # cliente" combinar com a auditoria de volume quando for a mesma chave.
    st.session_state["resultado_validador"] = {
        "chave": chave_unica.strip(), "periodo": periodo_txt,
        "empresa": nome_empresa, "total": total, "contagem": dict(contagem),
        "anuncios_ruins": anuncios_ruins,
        "xlsx_bytes": xlsx_bytes, "xlsx_nome": f"{base_nome} - Validado.xlsx",
        "dash_bytes": dash_html.encode("utf-8"),
    }

    salvar_no_historico({
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "tipo": "validador",
        "Data da solicitação": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "Empresa": nome_empresa,
        "Chave única": chave_unica.strip(),
        "Período": periodo_txt,
        "Leads": total,
        "Dentro do foco": contagem["Dentro do foco"],
        "Fora do foco": contagem["Fora do foco"],
        "Aberto": contagem["Aberto"],
        "xlsx_nome": f"{base_nome} - Validado.xlsx",
        "dash_nome": f"{base_nome} - Dashboard.html",
    }, arquivos={"xlsx": xlsx_bytes, "html": st.session_state["vf_resultado"]["dash_bytes"]})

    botao_validar_ph.empty()

res = st.session_state.get("vf_resultado")
if res:
    total, contagem = res["total"], res["contagem"]
    st.success(f"Validação concluída — {total} leads processados! ({res['empresa']})")
    st.caption("Revise o resumo abaixo e baixe o Excel para consultar a classificação individual de cada lead.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Dentro do foco", f"{contagem['Dentro do foco']/total:.0%}" if total else "0%", f"{contagem['Dentro do foco']} leads", delta_color="off")
    c2.metric("Fora do foco", f"{contagem['Fora do foco']/total:.0%}" if total else "0%", f"{contagem['Fora do foco']} leads", delta_color="off")
    c3.metric("Aberto", f"{contagem['Aberto']/total:.0%}" if total else "0%", f"{contagem['Aberto']} leads", delta_color="off")
    if res["falhas"]:
        st.warning(f"{res['falhas']} lead(s) sem resposta da IA (marcados como Aberto) — rode de novo para reprocessar.")
        if res["erro_ia"]:
            st.error(f"Motivo técnico da falha na IA: {res['erro_ia'][:400]}")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Baixar Excel validado", data=res["xlsx_bytes"],
                           file_name=res["xlsx_nome"],
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True, key="vf_dl_xlsx")
    with col_dl2:
        st.download_button("Baixar dashboard (HTML)", data=res["dash_bytes"],
                           file_name=res["dash_nome"], mime="text/html",
                           use_container_width=True, key="vf_dl_dash")


@st.dialog("Excluir pesquisa")
def dialogo_excluir_vf(rid, rotulo):
    st.write(f"Tem certeza que deseja excluir a pesquisa **{rotulo}**?")
    st.caption("O registro e os arquivos (Excel e dashboard) dela serão apagados. Essa ação não tem volta.")
    cd1, cd2 = st.columns(2)
    if cd1.button("Sim, excluir", type="primary", use_container_width=True, key=f"vf_conf_{rid}"):
        excluir_do_historico(rid)
        st.rerun()
    if cd2.button("Cancelar", use_container_width=True, key=f"vf_canc_{rid}"):
        st.rerun()


st.markdown("<p style='font-weight:600; margin-top:32px;'>Histórico de validações</p>", unsafe_allow_html=True)
historico = [h for h in carregar_historico() if h.get("tipo") == "validador"]
if historico:
    filtro_historico = st.text_input(
        "Buscar no histórico",
        placeholder="Digite uma empresa ou chave única (ex.: Metalúrgica ou 12-34567-1)",
        key="vf_filtro_hist",
    )
    if filtro_historico.strip():
        alvo = filtro_historico.strip().lower()
        historico = [
            h for h in historico
            if alvo in str(h.get("Chave única", "")).lower()
            or alvo in str(h.get("Empresa", "")).lower()
        ]
        if not historico:
            st.caption("Nenhuma validação encontrada para essa empresa ou chave.")
    colunas_hist = [1.2, 1.35, 1.05, 1.45, 1.0, 0.68, 0.68, 0.35]
    cab = st.columns(colunas_hist)
    for col, titulo in zip(cab, ("Data", "Empresa", "Chave", "Período", "Leads (D/F/A)", "Excel", "Painel", "")):
        col.markdown(f"<span style='font-size:0.72rem; color:{T['texto']}; font-weight:600;'>{titulo}</span>", unsafe_allow_html=True)

    for h in historico:
        rid = h.get("id", "")
        with st.container(border=True):
            c = st.columns(colunas_hist)
            c[0].markdown(f"<span style='font-size:0.78rem;'>{h.get('Data da solicitação', '')}</span>", unsafe_allow_html=True)
            c[1].markdown(f"<span style='font-size:0.78rem;'>{h.get('Empresa', '')}</span>", unsafe_allow_html=True)
            c[2].markdown(f"<span style='font-size:0.78rem;'>{h.get('Chave única', '')}</span>", unsafe_allow_html=True)
            c[3].markdown(f"<span style='font-size:0.78rem;'>{h.get('Período', '')}</span>", unsafe_allow_html=True)
            c[4].markdown(
                f"<span style='font-size:0.78rem;'>{h.get('Leads', '')} "
                f"(<span style='color:#22883A;'>{h.get('Dentro do foco', '')}</span>/"
                f"<span style='color:#D6433F;'>{h.get('Fora do foco', '')}</span>/"
                f"<span style='color:#B4830A;'>{h.get('Aberto', '')}</span>)</span>",
                unsafe_allow_html=True,
            )
            xlsx_salvo = ler_resultado_salvo(rid, "xlsx") if rid else None
            dash_salvo = ler_resultado_salvo(rid, "html") if rid else None
            if xlsx_salvo:
                c[5].download_button("Excel", data=xlsx_salvo, file_name=h.get("xlsx_nome", f"{rid}.xlsx"),
                                      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                      use_container_width=True, key=f"vf_hxlsx_{rid}", help="Baixar Excel")
            else:
                c[5].caption("—")
            if dash_salvo:
                c[6].download_button("Painel", data=dash_salvo, file_name=h.get("dash_nome", f"{rid}.html"),
                                      mime="text/html", use_container_width=True, key=f"vf_hdash_{rid}",
                                      help="Baixar dashboard")
            else:
                c[6].caption("—")
            if rid and c[7].button("✕", key=f"vf_x_{rid}", help="Excluir esta pesquisa"):
                dialogo_excluir_vf(rid, f"{h.get('Empresa', '')} · {h.get('Data da solicitação', '')}")
else:
    st.caption("Nenhuma validação registrada ainda. As próximas aparecerão aqui com data, empresa e resultado.")
