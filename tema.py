"""Identidade visual única do app — herdada do Validador de Leads v3 (tema
"vidro" claro/escuro), aplicada globalmente para as três páginas terem a
mesma cara. Chamado uma vez em app.py, antes de `pg.run()`."""
import streamlit as st

FOTO_INDUSTRIA = "https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1900&q=70"
NEON_1, NEON_2 = "#2E7BFF", "#00CFFF"

TEMAS_APP = {
    "escuro": {
        "fundo": "#1B2C3D",
        "fundo_grad": "radial-gradient(at 0% 0%, rgba(46,123,255,0.16) 0px, transparent 55%), "
                      "radial-gradient(at 100% 0%, rgba(0,240,255,0.10) 0px, transparent 55%)",
        "hero_overlay": "linear-gradient(90deg, rgba(11,20,28,0.94), rgba(11,20,28,0.55))",
        "label": "#EAF3FC",
        "texto": "#9AA5B8",
        "painel_bg": "rgba(24,32,40,0.45)",
        "painel_borda": "rgba(255,255,255,0.08)",
        "input_bg": "#141C24",
        "input_vidro": "rgba(12, 24, 36, 0.58)",
        "input_borda": "rgba(255,255,255,0.10)",
        "input_txt": "#ffffff",
        "placeholder": "#55698A",
        "popover_bg": "#101820",
        "popover_txt": "#EAF3FC",
        "sec_btn_bg": "transparent",
        "sec_btn_borda": "transparent",
        "sec_btn_txt": "#9AA5B8",
        "hero_titulo": "#ffffff",
        "hero_sub": "#B8C6DA",
        "badge_bg": "rgba(255,255,255,0.06)",
        "badge_borda": "rgba(255,255,255,0.12)",
        "badge_txt": "#ffffff",
        "icone": "#7C8CA3",
        "icone_bg": "rgba(46,123,255,0.14)",
        "acao_primaria": "#3B6D96",
        "acao_primaria_hover": "#315D82",
        "foco": "rgba(109, 173, 225, 0.34)",
    },
    "claro": {
        "fundo": "#EEF3FA",
        "fundo_grad": "radial-gradient(at 0% 0%, rgba(46,123,255,0.08) 0px, transparent 55%), "
                      "radial-gradient(at 100% 0%, rgba(0,180,255,0.06) 0px, transparent 55%)",
        "hero_overlay": "linear-gradient(90deg, rgba(230,241,251,0.95), rgba(181,212,244,0.55))",
        "label": "#0C2036",
        "texto": "#5C7089",
        "painel_bg": "rgba(255,255,255,0.72)",
        "painel_borda": "rgba(255,255,255,0.9)",
        "input_bg": "#ffffff",
        "input_vidro": "rgba(255, 255, 255, 0.58)",
        "input_borda": "rgba(24,95,165,0.16)",
        "input_txt": "#0C2036",
        "placeholder": "#8CA0B8",
        "popover_bg": "#FFFFFF",
        "popover_txt": "#0C2036",
        "sec_btn_bg": "transparent",
        "sec_btn_borda": "transparent",
        "sec_btn_txt": "#0C447C",
        "hero_titulo": "#0C2036",
        "hero_sub": "#33475C",
        "badge_bg": "rgba(255,255,255,0.7)",
        "badge_borda": "rgba(24,95,165,0.18)",
        "badge_txt": "#0C447C",
        "icone": "#7C93AC",
        "icone_bg": "rgba(46,123,255,0.12)",
        "acao_primaria": "#3B78B4",
        "acao_primaria_hover": "#2F659A",
        "foco": "rgba(59, 120, 180, 0.26)",
    },
}


def svg_logo_si(cor, fundo):
    """Marca 'Soluções Industriais' recriada em SVG (skyline + smartphone),
    colorida conforme o tema ativo."""
    return f"""<svg class="logo-si" width="28" height="17" viewBox="0 0 300 180" xmlns="http://www.w3.org/2000/svg">
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
    """Injeta o CSS 'vidro' e a barra de marca no topo — chamar 1x em
    app.py, antes de `pg.run()`, pra todas as páginas herdarem o mesmo
    visual e o mesmo estado de tema (claro/escuro) compartilhado."""
    tema, T = tema_ativo()
    logo = svg_logo_si(T["badge_txt"], T["fundo"])

    st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Geist:wght@400;500&family=JetBrains+Mono:wght@500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1');

  html, body, [data-testid="stAppViewContainer"] {{
    background-color: {T['fundo']};
    background-image: {T['fundo_grad']};
  }}
  [data-testid="stHeader"] {{ background: transparent; }}

  .block-container {{ max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; font-family: 'Geist', sans-serif; }}

  .block-container label, .block-container [data-testid="stWidgetLabel"] p {{
    color: {T['label']} !important; font-weight: 600 !important; font-size: 0.82rem !important;
  }}
  .block-container p, .block-container .stMarkdown {{ color: {T['texto']}; }}

  .topbar-vidro {{ display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 18px; }}
  .topbar-vidro .marca {{
    display: flex; align-items: center; gap: 10px; color: {T['label']};
    font-family: 'Sora', sans-serif; font-weight: 700; font-size: 14px;
  }}
  .topbar-vidro .marca .logo-si {{ flex-shrink: 0; }}

  .hero {{
    background: {T['hero_overlay']}, url('{FOTO_INDUSTRIA}') center/cover no-repeat;
    border-radius: 20px; padding: 34px 40px; margin-bottom: 20px;
  }}
  .hero .badge {{
    display: inline-flex; align-items: center; gap: 7px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; font-weight: 500; letter-spacing: 0.02em;
    color: {T['badge_txt']}; background: {T['badge_bg']}; border: 1px solid {T['badge_borda']};
    padding: 4px 13px; border-radius: 999px; margin-bottom: 12px;
  }}
  .hero .badge::before {{
    content: ""; width: 6px; height: 6px; border-radius: 50%; background: {NEON_1}; flex-shrink: 0;
  }}
  .hero h1 {{
    color: {T['hero_titulo']}; font-family: 'Sora', sans-serif;
    font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 700; margin: 0 0 8px;
  }}
  .hero p {{ color: {T['hero_sub']}; font-size: 0.95rem; line-height: 1.5; max-width: 540px; margin: 0; }}

  .painel-titulo {{ display: flex; align-items: center; gap: 12px; margin-bottom: 22px; }}
  .painel-titulo .icone-titulo {{
    width: 36px; height: 36px; border-radius: 10px; background: {T['icone_bg']}; color: {NEON_1};
    display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0;
  }}
  .painel-titulo h2 {{ font-family: 'Sora', sans-serif; font-size: 1.05rem; font-weight: 700; }}

  div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {T['painel_bg']} !important;
    border: none !important;
    border-radius: 18px !important;
    backdrop-filter: blur(22px) saturate(160%);
    -webkit-backdrop-filter: blur(22px) saturate(160%);
    margin: 0 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.12), 0 12px 32px rgba(10,25,40,0.08) !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    margin: 0 !important;
  }}

  div[data-testid="stTextInput"], div[data-testid="stTextArea"],
  div[data-testid="stDateInput"] > div, div[data-testid="stSelectbox"] > div {{
    background: {T['input_vidro']} !important;
    border: none !important;
    border-radius: 12px !important;
    overflow: hidden;
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16), 0 6px 18px rgba(10,25,40,0.06);
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
    border-color: transparent !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.20), 0 0 0 3px {T['foco']} !important;
  }}
  [data-testid="stTooltipIcon"], [data-testid="stTooltipIcon"] svg,
  [data-testid="stTooltipHoverTarget"] svg {{
    color: {T['texto']} !important; fill: {T['texto']} !important; opacity: 1 !important;
  }}
  div[data-testid="stTooltipContent"] {{
    background: {T['popover_bg']} !important; color: {T['popover_txt']} !important;
    border: 1px solid rgba(120,140,170,0.25) !important; border-radius: 10px !important;
  }}
  div[data-baseweb="popover"] {{
    background: {T['popover_bg']} !important;
    border: 1px solid rgba(120,140,170,0.25) !important;
    border-radius: 14px !important;
  }}
  div[data-baseweb="popover"] * {{ background: transparent !important; color: {T['popover_txt']} !important; }}
  div[data-baseweb="popover"] li:hover,
  div[data-baseweb="popover"] [aria-selected="true"]:not([role="gridcell"]) {{
    background: rgba(120,140,170,0.18) !important;
  }}
  div[data-baseweb="calendar"] {{ background: {T['popover_bg']} !important; }}
  div[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] div {{
    background: {NEON_1} !important; border-radius: 50% !important; color: #ffffff !important;
  }}
  div[data-baseweb="calendar"] [role="gridcell"]:hover div {{ background: rgba(120,140,170,0.18) !important; }}

  .stButton > button, .stDownloadButton > button {{
    border-radius: 10px !important;
    transition: background 140ms ease-out, transform 140ms ease-out;
  }}
  .stButton > button:active, .stDownloadButton > button:active {{ transform: scale(0.97); }}
  .stButton > button[kind="primary"] {{
    background: {T['acao_primaria']} !important; border: 1px solid {T['acao_primaria']} !important;
    font-weight: 700 !important; box-shadow: none !important;
  }}
  .stButton > button[kind="primary"]:hover {{ background: {T['acao_primaria_hover']} !important; box-shadow: none !important; }}
  .stButton > button[kind="primary"] p {{ color: #ffffff !important; }}
  .stDownloadButton > button {{
    background: {T['input_vidro']} !important;
    border: none !important; font-weight: 700 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16), 0 6px 18px rgba(10,25,40,0.06) !important;
  }}
  .stDownloadButton > button:hover {{ background: {T['painel_bg']} !important; }}
  .stDownloadButton > button p {{ color: {T['sec_btn_txt']} !important; }}
  .stButton > button[kind="secondary"] {{
    background: {T['sec_btn_bg']} !important; border: 1px solid {T['sec_btn_borda']} !important;
  }}
  .stButton > button[kind="secondary"]:hover {{ background: {T['painel_bg']} !important; }}
  .stButton > button[kind="secondary"] p {{ color: {T['sec_btn_txt']} !important; }}
  .st-key-btn_tema_escuro .stButton > button, .st-key-btn_tema_claro .stButton > button {{
    min-height: 38px; font-size: 0.82rem !important;
  }}
  .st-key-btn_tema_escuro .stButton > button[kind="secondary"],
  .st-key-btn_tema_claro .stButton > button[kind="secondary"] {{
    background: {T['input_vidro']} !important; border-color: transparent !important;
  }}
  [class*="st-key-conf_"] .stButton > button {{
    background: #C73B3B !important; border-color: #C73B3B !important;
  }}
  [class*="st-key-conf_"] .stButton > button:hover {{ background: #A92F2F !important; }}

  div[data-testid="stMetric"] {{
    background: {T['painel_bg']} !important;
    border: 1px solid {T['painel_borda']} !important;
    border-radius: 16px; padding: 16px 18px; backdrop-filter: blur(14px);
  }}
  div[data-testid="stMetric"] label {{ color: {T['texto']} !important; font-weight: 600 !important; }}
  div[data-testid="stMetricValue"] {{ color: {T['label']} !important; font-weight: 700; }}
  div[data-testid="stMetricDelta"] {{ color: {T['texto']} !important; }}
</style>

<div class="topbar-vidro">
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


def hero(badge: str, titulo: str, subtitulo: str):
    """Bloco 'hero' com foto de fundo — mesmo componente nas três páginas,
    só muda o texto."""
    st.markdown(f"""
<div class="hero">
  <span class="badge">{badge}</span>
  <h1>{titulo}</h1>
  <p>{subtitulo}</p>
</div>
""", unsafe_allow_html=True)


def titulo_painel(icone_material: str, texto: str):
    T = tema_ativo()[1]
    st.markdown(
        f"<div class='painel-titulo'>"
        f"<span class='icone-titulo material-symbols-outlined'>{icone_material}</span>"
        f"<h2 style='margin:0; color:{T['label']};'>{texto}</h2>"
        f"</div>",
        unsafe_allow_html=True,
    )
