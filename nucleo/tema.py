"""Identidade visual única do app — visual "flat", sem depender de fontes
ou ícones externos (o Google Fonts pode estar bloqueado em rede
corporativa), com hierarquia por tamanho/peso de texto em vez de efeito de
vidro em tudo. Aplicado globalmente para as três páginas terem a mesma
cara. Chamado uma vez em app.py, antes de `pg.run()`."""
import streamlit as st

FOTO_HERO = "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1900&q=70"
ACENTO = "#185FA5"  # mesmo primaryColor do .streamlit/config.toml — um azul só em todo canto

TEMAS_APP = {
    "escuro": {
        "fundo": "#0A0E14",
        "label": "#E7EAEE",
        "texto": "#8A93A6",
        "painel_bg": "#12161F",
        "painel_borda": "#1F2530",
        "input_bg": "#12161F",
        "input_borda": "#232A37",
        "input_txt": "#E7EAEE",
        "placeholder": "#5B6472",
        "popover_bg": "#12161F",
        "popover_txt": "#E7EAEE",
        "sec_btn_bg": "transparent",
        "sec_btn_borda": "#232A37",
        "sec_btn_txt": "#8A93A6",
        "hero_titulo": "#F2F4F7",
        "hero_sub": "#8A93A6",
        "icone": ACENTO,
        "icone_bg": "rgba(24,95,165,0.16)",
        "acao_primaria": ACENTO,
        "acao_primaria_hover": "#134B85",
        "foco": "rgba(24,95,165,0.35)",
        "sucesso": "#3FB27F", "aviso": "#D9A441", "perigo": "#DB6A5B",
        "borda_hairline": "#1F2530",
        "hero_tint_1": "rgba(24,95,165,0.7)", "hero_tint_2": "rgba(6,10,16,0.88)",
    },
    "claro": {
        "fundo": "#F7F8FA",
        "label": "#10141C",
        "texto": "#5B6472",
        "painel_bg": "#FFFFFF",
        "painel_borda": "#E4E7EC",
        "input_bg": "#FFFFFF",
        "input_borda": "#DDE1E8",
        "input_txt": "#10141C",
        "placeholder": "#9AA2B1",
        "popover_bg": "#FFFFFF",
        "popover_txt": "#10141C",
        "sec_btn_bg": "transparent",
        "sec_btn_borda": "#DDE1E8",
        "sec_btn_txt": "#10141C",
        "hero_titulo": "#10141C",
        "hero_sub": "#5B6472",
        "icone": ACENTO,
        "icone_bg": "rgba(24,95,165,0.10)",
        "acao_primaria": ACENTO,
        "acao_primaria_hover": "#134B85",
        "foco": "rgba(24,95,165,0.25)",
        "sucesso": "#1F8F5C", "aviso": "#A9791C", "perigo": "#C0392B",
        "borda_hairline": "#E4E7EC",
        "hero_tint_1": "rgba(24,95,165,0.55)", "hero_tint_2": "rgba(247,248,250,0.85)",
    },
}

_ICON_PATHS = {
    "fact_check": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v3H9z"/><path d="M9 12l2 2 4-4"/>',
    "route": '<circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="18" r="2.2"/><path d="M6 8.2v3a4 4 0 0 0 4 4h4"/>',
    "trending_down": '<polyline points="4 7 10 13 13 10 20 17"/><polyline points="20 10 20 17 13 17"/>',
    "filter_alt": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
}


def icon_svg(nome: str, tamanho: int = 18) -> str:
    """Ícone outline autocontido (sem depender de fonte externa) — o mesmo
    conjunto usado nos títulos de painel das três páginas."""
    caminho = _ICON_PATHS.get(nome, _ICON_PATHS["fact_check"])
    return (
        f'<svg viewBox="0 0 24 24" width="{tamanho}" height="{tamanho}" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{caminho}</svg>'
    )


def svg_logo_si(cor, fundo):
    """Marca 'Soluções Industriais' recriada em SVG (skyline + smartphone),
    colorida conforme o tema ativo."""
    return f"""<svg class="logo-si" width="26" height="16" viewBox="0 0 300 180" xmlns="http://www.w3.org/2000/svg">
  <path d="M0 150 L40 95 L60 118 L92 72 L112 100 L132 62 L150 100 L150 150 Z" fill="{cor}"/>
  <path d="M300 150 L260 95 L240 118 L208 72 L188 100 L168 62 L150 100 L150 150 Z" fill="{cor}"/>
  <rect x="16" y="126" width="13" height="10" fill="{cor}"/>
  <rect x="58" y="126" width="13" height="10" fill="{cor}"/>
  <rect x="229" y="126" width="13" height="10" fill="{cor}"/>
  <rect x="271" y="126" width="13" height="10" fill="{cor}"/>
  <path d="M228 60 q10 -8 4 -20" stroke="{cor}" stroke-width="4" fill="none" stroke-linecap="round"/>
  <rect x="112" y="16" width="76" height="140" rx="20" fill="{cor}"/>
  <rect x="126" y="30" width="48" height="94" rx="7" fill="{fundo}"/>
  <circle cx="150" cy="62" r="13" fill="{fundo}"/>
  <circle cx="150" cy="62" r="5.5" fill="{cor}"/>
  <circle cx="150" cy="146" r="6" fill="{fundo}"/>
</svg>"""


def tema_ativo():
    """Nome do tema ('escuro'/'claro') e seus tokens de cor, da sessão atual."""
    nome = st.session_state.get("tema", "escuro")
    return nome, TEMAS_APP[nome]


def aplicar_estilo_global():
    """Injeta o CSS e a barra de marca no topo — chamar 1x em app.py, antes
    de `pg.run()`, pra todas as páginas herdarem o mesmo visual e o mesmo
    estado de tema (claro/escuro) compartilhado.

    Usa só a fonte do sistema (nenhum @import externo) — em rede corporativa
    com Google Fonts bloqueado, o app continua com a aparência prevista em
    vez de cair para texto sem estilo."""
    tema, T = tema_ativo()
    logo = svg_logo_si(T["label"], T["fundo"])
    fonte = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif"

    st.markdown(f"""
<style>
  html, body, [data-testid="stAppViewContainer"] {{
    background-color: {T['fundo']};
  }}
  [data-testid="stHeader"] {{ background: transparent; }}

  .block-container {{ max-width: 1080px; padding-top: 1.2rem; padding-bottom: 3rem; font-family: {fonte}; }}

  .block-container label, .block-container [data-testid="stWidgetLabel"] p {{
    color: {T['label']} !important; font-weight: 500 !important; font-size: 0.82rem !important;
  }}
  .block-container p, .block-container .stMarkdown {{ color: {T['texto']}; }}

  .topbar {{ display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 20px; }}
  .topbar .marca {{
    display: flex; align-items: center; gap: 9px; color: {T['label']};
    font-family: {fonte}; font-weight: 600; font-size: 13.5px;
  }}
  .topbar .marca .logo-si {{ flex-shrink: 0; }}

  .hero {{
    position: relative; overflow: hidden; border-radius: 14px;
    padding: 30px 34px; margin-bottom: 22px; isolation: isolate;
  }}
  .hero::before {{
    content: ""; position: absolute; inset: 0; z-index: 0;
    background: url('{FOTO_HERO}') center/cover no-repeat;
    filter: grayscale(1) brightness(0.5);
  }}
  .hero::after {{
    content: ""; position: absolute; inset: 0; z-index: 0;
    background: linear-gradient(135deg, {T['hero_tint_1']}, {T['hero_tint_2']});
    mix-blend-mode: color;
  }}
  .hero > * {{ position: relative; z-index: 1; }}
  .hero .kicker {{
    font-family: {fonte}; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #ffffff; margin: 0 0 8px; opacity: 0.85;
  }}
  .hero h1 {{
    color: #ffffff; font-family: {fonte};
    font-size: 1.6rem; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.01em;
  }}
  .hero p {{ color: rgba(255,255,255,0.82); font-size: 0.92rem; line-height: 1.55; max-width: 620px; margin: 0; }}

  .painel-titulo {{ display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }}
  .painel-titulo .icone-titulo {{
    width: 30px; height: 30px; border-radius: 8px; background: {T['icone_bg']}; color: {T['icone']};
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }}
  .painel-titulo h2 {{ font-family: {fonte}; font-size: 0.98rem; font-weight: 600; }}

  div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {T['painel_bg']} !important;
    border: 1px solid {T['painel_borda']} !important;
    border-radius: 12px !important;
    margin: 0 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    margin: 0 !important;
  }}

  div[data-testid="stTextInput"], div[data-testid="stTextArea"],
  div[data-testid="stDateInput"] > div, div[data-testid="stSelectbox"] > div {{
    background: {T['input_bg']} !important;
    border: 1px solid {T['input_borda']} !important;
    border-radius: 8px !important;
    overflow: hidden;
  }}
  div[data-testid="stTextInput"] div, div[data-testid="stTextArea"] div,
  div[data-testid="stDateInput"] div, div[data-testid="stSelectbox"] div,
  div[data-baseweb="input"], div[data-baseweb="base-input"],
  div[data-baseweb="textarea"], div[data-baseweb="select"] > div {{
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
  }}
  div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea,
  div[data-testid="stDateInput"] input, div[data-testid="stSelectbox"] *,
  div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {{
    background: transparent !important; color: {T['input_txt']} !important;
  }}
  div[data-testid="stTextInput"] input::placeholder,
  div[data-testid="stTextArea"] textarea::placeholder {{
    color: {T['placeholder']} !important;
  }}
  div[data-testid="stTextInput"]:focus-within, div[data-testid="stTextArea"]:focus-within,
  div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{
    border-color: {T['icone']} !important;
    box-shadow: 0 0 0 3px {T['foco']} !important;
  }}
  [data-testid="stTooltipIcon"], [data-testid="stTooltipIcon"] svg,
  [data-testid="stTooltipHoverTarget"] svg {{
    color: {T['texto']} !important; fill: {T['texto']} !important; opacity: 1 !important;
  }}
  div[data-testid="stTooltipContent"] {{
    background: {T['popover_bg']} !important; color: {T['popover_txt']} !important;
    border: 1px solid {T['painel_borda']} !important; border-radius: 8px !important;
  }}
  div[data-baseweb="popover"] {{
    background: {T['popover_bg']} !important;
    border: 1px solid {T['painel_borda']} !important;
    border-radius: 10px !important;
  }}
  div[data-baseweb="popover"] * {{ background: transparent !important; color: {T['popover_txt']} !important; }}
  div[data-baseweb="popover"] li:hover,
  div[data-baseweb="popover"] [aria-selected="true"]:not([role="gridcell"]) {{
    background: {T['painel_bg']} !important;
  }}
  div[data-baseweb="calendar"] {{ background: {T['popover_bg']} !important; }}
  div[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] div {{
    background: {T['icone']} !important; border-radius: 6px !important; color: #ffffff !important;
  }}
  div[data-baseweb="calendar"] [role="gridcell"]:hover div {{ background: {T['painel_bg']} !important; }}

  .stButton > button, .stDownloadButton > button {{
    border-radius: 8px !important;
    transition: background 120ms ease-out, border-color 120ms ease-out;
  }}
  .stButton > button:active, .stDownloadButton > button:active {{ transform: scale(0.98); }}
  .stButton > button[kind="primary"] {{
    background: {T['acao_primaria']} !important; border: 1px solid {T['acao_primaria']} !important;
    font-weight: 600 !important; box-shadow: none !important;
  }}
  .stButton > button[kind="primary"]:hover {{ background: {T['acao_primaria_hover']} !important; }}
  .stButton > button[kind="primary"] p {{ color: #ffffff !important; }}
  .stDownloadButton > button {{
    background: {T['painel_bg']} !important;
    border: 1px solid {T['painel_borda']} !important; font-weight: 600 !important;
    box-shadow: none !important;
  }}
  .stDownloadButton > button:hover {{ border-color: {T['icone']} !important; }}
  .stDownloadButton > button p {{ color: {T['sec_btn_txt']} !important; }}
  .stButton > button[kind="secondary"] {{
    background: {T['sec_btn_bg']} !important; border: 1px solid {T['sec_btn_borda']} !important;
  }}
  .stButton > button[kind="secondary"]:hover {{ border-color: {T['icone']} !important; }}
  .stButton > button[kind="secondary"] p {{ color: {T['sec_btn_txt']} !important; }}
  [class*="st-key-conf_"] .stButton > button {{
    background: {T['perigo']} !important; border-color: {T['perigo']} !important;
  }}

  div[data-testid="stMetric"] {{
    background: {T['painel_bg']} !important;
    border: 1px solid {T['painel_borda']} !important;
    border-radius: 10px; padding: 14px 16px;
  }}
  div[data-testid="stMetric"] label {{ color: {T['texto']} !important; font-weight: 500 !important; }}
  div[data-testid="stMetricValue"] {{ color: {T['label']} !important; font-weight: 600; }}
  div[data-testid="stMetricDelta"] {{ color: {T['texto']} !important; }}
</style>

<div class="topbar">
  <div class="marca">{logo} Soluções Industriais · Auditoria de Cliente</div>
</div>
""", unsafe_allow_html=True)


def seletor_tema():
    """Botões Escuro/Claro no topo de cada página — troca fica só na
    sessão (não persiste entre acessos diferentes, mantém simples)."""
    tema, _T = tema_ativo()
    col_vazio, col_esc, col_cla = st.columns([5, 1, 1])
    with col_esc:
        if st.button("Escuro", use_container_width=True, key="btn_tema_escuro",
                     type=("primary" if tema == "escuro" else "secondary")):
            st.session_state["tema"] = "escuro"
            st.rerun()
    with col_cla:
        if st.button("Claro", use_container_width=True, key="btn_tema_claro",
                     type=("primary" if tema == "claro" else "secondary")):
            st.session_state["tema"] = "claro"
            st.rerun()


def hero(kicker: str, titulo: str, subtitulo: str):
    """Cabeçalho de página — texto só, sem foto de fundo (mesmo componente
    nas três páginas, só muda o texto e diferencia pelo próprio conteúdo)."""
    st.markdown(f"""
<div class="hero">
  <p class="kicker">{kicker}</p>
  <h1>{titulo}</h1>
  <p>{subtitulo}</p>
</div>
""", unsafe_allow_html=True)


def titulo_painel(icone: str, texto: str):
    T = tema_ativo()[1]
    st.markdown(
        f"<div class='painel-titulo'>"
        f"<span class='icone-titulo'>{icon_svg(icone, 16)}</span>"
        f"<h2 style='margin:0; color:{T['label']};'>{texto}</h2>"
        f"</div>",
        unsafe_allow_html=True,
    )
