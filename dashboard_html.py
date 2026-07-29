"""Dashboards HTML autocontidos (para download) — um do validador de foco
(distribuição dos leads recebidos) e um combinado, novo, para a tela de
saúde do cliente (funil completo: perdidos + recebidos)."""
import base64
import re
from datetime import datetime

from nucleo.tema import svg_logo_si

MODELO_DASH = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Validação — __EMPRESA__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; background: __BG_PAGINA__; }
  .tela { max-width: 1180px; margin: 0 auto; background: __BG_TELA__; }
  .nav { display: flex; align-items: center; justify-content: space-between; padding: 18px 36px; background: __BG_NAV__; border-bottom: 1px solid __BORDA_NAV__; }
  .nav .logo { display: flex; align-items: center; gap: 10px; color: __TXT_LOGO__; font-weight: 700; font-size: 14px; }
  .nav .logo .logo-si { flex-shrink: 0; }
  .nav .dir { display: flex; align-items: center; gap: 10px; }
  .nav .baixar { font-size: 12px; color: __BAIXAR_TXT__; background: __BAIXAR_BG__; padding: 8px 16px; border-radius: 20px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; }
  .nav .baixar-imagem { background: transparent; border: 1px solid __SELO_BORDA__; color: __TXT_LOGO__; }
  .hero {
    padding: 24px 36px 20px;
    background: __HERO_OVERLAY__,
      url('https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1900&q=70') center/cover no-repeat;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  }
  .hero h1 { color: __TXT_TITULO__; font-size: 20px; font-weight: 700; margin-bottom: 4px; }
  .hero p { color: __TXT_SUB__; font-size: 12.5px; }
  .selo { background: __SELO_BG__; border: 1px solid __SELO_BORDA__; color: __SELO_TXT__; font-size: 12.5px; padding: 7px 16px; border-radius: 30px; }
  .selo b { font-size: 14px; }
  .corpo { padding: 24px 36px 30px; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
  .kpi { background: __BG_KPI__; border: 1px solid __BORDA_KPI__; border-radius: 14px; padding: 16px 18px; }
  .kpi .lbl { font-size: 11px; color: __TXT_LBL__; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 6px; }
  .kpi .num { font-size: 24px; font-weight: 700; color: __TXT_NUM__; }
  .kpi .num.v { color: #1D9E75; } .kpi .num.r { color: #D85A30; } .kpi .num.a { color: #BA7517; }
  .kpi .sub { font-size: 11px; color: __TXT_LBL__; margin-top: 4px; }
  .linha { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .painel { background: __BG_KPI__; border: 1px solid __BORDA_KPI__; border-radius: 14px; padding: 20px 22px; }
  .painel h2 { color: __TXT_NUM__; font-size: 13.5px; font-weight: 700; margin-bottom: 12px; }
  .painel h2 .pin { font-size: 11px; padding: 2px 8px; border-radius: 20px; vertical-align: middle; margin-left: 6px; font-weight: 600; }
  .pin-verde { background: rgba(29,158,117,0.18); color: #1D9E75; }
  .pin-verm { background: rgba(216,90,48,0.18); color: #D85A30; }
  .grafico { height: 210px; position: relative; }
  .lista-lead { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid __BORDA_LISTA__; font-size: 12.5px; gap: 10px; }
  .lista-lead:last-child { border-bottom: none; }
  .lista-lead .nome { color: __TXT_NOME_LEAD__; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .pin-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .pin-dot-verde { background: #1D9E75; } .pin-dot-verm { background: #D85A30; }
  .lista-lead .email { color: __TXT_EMAIL_LEAD__; font-size: 11.5px; text-align: right; }
  .vazio { color: __TXT_VAZIO__; font-size: 12px; }
  .anuncio-linha { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12.5px; }
  .anuncio-linha .nome { width: 150px; color: __TXT_NOME_LEAD__; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .barra-fundo { flex: 1; height: 8px; background: __BARRA_FUNDO__; border-radius: 5px; overflow: hidden; }
  .barra-cheia { height: 100%; background: #D85A30; border-radius: 5px; }
  .anuncio-linha .qtd { width: 22px; text-align: right; color: __TXT_LBL__; }
  .rodape { text-align: center; color: __TXT_RODAPE__; font-size: 11px; padding: 18px 0 0; }
  @media (max-width: 760px) { .kpis { grid-template-columns: 1fr 1fr; } .linha { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="tela" id="tela-captura">
  <div class="nav">
    <div class="logo">__LOGO_SI__ Validador de Leads</div>
    <div class="dir">
      __BOTAO_EXCEL__
      <button class="baixar baixar-imagem" id="btnBaixarImagem" type="button">Baixar imagem</button>
    </div>
  </div>
  <div id="area-captura">
    <div class="hero">
      <div>
        <h1>__EMPRESA__</h1>
        <p>chave __CHAVE__ &nbsp;·&nbsp; __PERIODO__ &nbsp;·&nbsp; gerado em __GERADO__</p>
      </div>
      <div class="selo"><b>__TOTAL__</b> leads analisados</div>
    </div>

    <div class="corpo">
      <div class="kpis">
        <div class="kpi"><div class="lbl">Total de leads</div><div class="num">__TOTAL__</div><div class="sub">no período</div></div>
        <div class="kpi"><div class="lbl">Dentro do foco</div><div class="num v">__PCT_DENTRO__%</div><div class="sub">__N_DENTRO__ leads</div></div>
        <div class="kpi"><div class="lbl">Fora do foco</div><div class="num r">__PCT_FORA__%</div><div class="sub">__N_FORA__ leads</div></div>
        <div class="kpi"><div class="lbl">Aberto</div><div class="num a">__PCT_ABERTO__%</div><div class="sub">__N_ABERTO__ leads</div></div>
      </div>

      <div class="linha">
        <div class="painel">
          <h2>Distribuição por status</h2>
          <div class="grafico"><canvas id="rosca"></canvas></div>
        </div>
        <div class="painel">
          <h2>Anúncios que mais geraram leads fora do foco</h2>
          __LINHAS_ANUNCIOS__
        </div>
      </div>

      <div class="linha">
        <div class="painel">
          <h2>Melhores leads <span class="pin pin-verde">dentro do foco</span></h2>
          __LINHAS_MELHORES__
        </div>
        <div class="painel">
          <h2>Piores leads <span class="pin pin-verm">fora do foco</span></h2>
          __LINHAS_PIORES__
        </div>
      </div>
    </div>
  </div>
</div>
<p class="rodape">Validador de Leads · Soluções Industriais · uso interno</p>
<script>
new Chart(document.getElementById("rosca"), {
  type: "doughnut",
  data: {
    labels: ["Dentro do foco", "Fora do foco", "Aberto"],
    datasets: [{ data: [__N_DENTRO__, __N_FORA__, __N_ABERTO__], backgroundColor: ["#1D9E75", "#D85A30", "#BA7517"], borderWidth: 0 }]
  },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { color: "__COR_LEGENDA__", font: { size: 12 } } } } }
});

document.getElementById("btnBaixarImagem").addEventListener("click", function () {
  var btn = this;
  btn.textContent = "Gerando imagem...";
  html2canvas(document.getElementById("area-captura"), { backgroundColor: "__BG_TELA__", scale: 2, useCORS: true })
    .then(function (canvas) {
      var link = document.createElement("a");
      link.download = "__NOME_IMAGEM__.jpg";
      link.href = canvas.toDataURL("image/jpeg", 0.92);
      link.click();
      btn.textContent = "Baixar imagem";
    })
    .catch(function () {
      btn.textContent = "Erro ao gerar — tente de novo";
    });
});
</script>
</body>
</html>"""

# Modelo do dashboard combinado (Saúde do cliente): funil de 4 KPIs em vez
# dos 3 do validador isolado — Total no período / Perdidos / Fora de foco /
# Dentro do foco. Reaproveita os mesmos tokens de cor (TEMAS_DASH).
MODELO_DASH_COMBINADO = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saúde do cliente — __EMPRESA__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; background: __BG_PAGINA__; }
  .tela { max-width: 1180px; margin: 0 auto; background: __BG_TELA__; }
  .nav { display: flex; align-items: center; justify-content: space-between; padding: 18px 36px; background: __BG_NAV__; border-bottom: 1px solid __BORDA_NAV__; }
  .nav .logo { display: flex; align-items: center; gap: 10px; color: __TXT_LOGO__; font-weight: 700; font-size: 14px; }
  .nav .dir { display: flex; align-items: center; gap: 10px; }
  .nav .baixar { font-size: 12px; color: __BAIXAR_TXT__; background: __BAIXAR_BG__; padding: 8px 16px; border-radius: 20px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; }
  .hero {
    padding: 24px 36px 20px;
    background: __HERO_OVERLAY__,
      url('https://images.unsplash.com/photo-1513828583688-c52646db42da?w=1900&q=70') center/cover no-repeat;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  }
  .hero h1 { color: __TXT_TITULO__; font-size: 20px; font-weight: 700; margin-bottom: 4px; }
  .hero p { color: __TXT_SUB__; font-size: 12.5px; }
  .selo { background: __SELO_BG__; border: 1px solid __SELO_BORDA__; color: __SELO_TXT__; font-size: 12.5px; padding: 7px 16px; border-radius: 30px; }
  .corpo { padding: 24px 36px 30px; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
  .kpi { background: __BG_KPI__; border: 1px solid __BORDA_KPI__; border-radius: 14px; padding: 16px 18px; }
  .kpi .lbl { font-size: 11px; color: __TXT_LBL__; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 6px; }
  .kpi .num { font-size: 24px; font-weight: 700; color: __TXT_NUM__; }
  .kpi .num.p { color: #D85A30; } .kpi .num.f { color: #BA7517; } .kpi .num.d { color: #1D9E75; }
  .kpi .sub { font-size: 11px; color: __TXT_LBL__; margin-top: 4px; }
  .linha { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .painel { background: __BG_KPI__; border: 1px solid __BORDA_KPI__; border-radius: 14px; padding: 20px 22px; }
  .painel h2 { color: __TXT_NUM__; font-size: 13.5px; font-weight: 700; margin-bottom: 12px; }
  .grafico { height: 210px; position: relative; }
  .anuncio-linha { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12.5px; }
  .anuncio-linha .nome { width: 190px; color: __TXT_NOME_LEAD__; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .barra-fundo { flex: 1; height: 8px; background: __BARRA_FUNDO__; border-radius: 5px; overflow: hidden; }
  .barra-cheia { height: 100%; background: #D85A30; border-radius: 5px; }
  .anuncio-linha .qtd { width: 22px; text-align: right; color: __TXT_LBL__; }
  .vazio { color: __TXT_VAZIO__; font-size: 12px; }
  .rodape { text-align: center; color: __TXT_RODAPE__; font-size: 11px; padding: 18px 0 0; }
  @media (max-width: 760px) { .kpis { grid-template-columns: 1fr 1fr; } .linha { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="tela" id="tela-captura">
  <div class="nav">
    <div class="logo">__LOGO_SI__ Saúde do cliente</div>
    <div class="dir">__BOTAO_EXCEL__</div>
  </div>
  <div id="area-captura">
    <div class="hero">
      <div>
        <h1>__EMPRESA__</h1>
        <p>chave __CHAVE__ &nbsp;·&nbsp; __PERIODO__ &nbsp;·&nbsp; gerado em __GERADO__</p>
      </div>
      <div class="selo"><b>__TOTAL__</b> orçamentos no período</div>
    </div>
    <div class="corpo">
      <div class="kpis">
        <div class="kpi"><div class="lbl">Orçamentos no período</div><div class="num">__TOTAL__</div><div class="sub">recebidos + perdidos</div></div>
        <div class="kpi"><div class="lbl">Perdidos (dentro do foco)</div><div class="num p">__N_PERDIDOS__</div><div class="sub">falta de vínculo</div></div>
        <div class="kpi"><div class="lbl">Recebidos fora de foco</div><div class="num f">__N_FORA__</div><div class="sub">__PCT_FORA__% dos recebidos</div></div>
        <div class="kpi"><div class="lbl">Recebidos dentro do foco</div><div class="num d">__N_DENTRO__</div><div class="sub">__PCT_DENTRO__% dos recebidos</div></div>
      </div>
      <div class="linha">
        <div class="painel">
          <h2>Volume perdido · por produto</h2>
          __LINHAS_PRODUTOS_PERDIDOS__
        </div>
        <div class="painel">
          <h2>Fora de foco · motivo mais comum</h2>
          __LINHAS_MOTIVOS_FORA__
        </div>
      </div>
    </div>
  </div>
</div>
<p class="rodape">Saúde do cliente · Soluções Industriais · uso interno</p>
<script>
document.getElementById("btnBaixarImagem") && document.getElementById("btnBaixarImagem").addEventListener("click", function () {});
</script>
</body>
</html>"""

TEMAS_DASH = {
    "escuro": {
        "BG_PAGINA": "#10161F", "BG_TELA": "#0C1D30",
        "BG_NAV": "rgba(255,255,255,0.05)", "BORDA_NAV": "rgba(255,255,255,0.08)",
        "TXT_LOGO": "#ffffff",
        "HERO_OVERLAY": "linear-gradient(160deg, rgba(6,20,36,0.62), rgba(12,68,124,0.5))",
        "TXT_TITULO": "#ffffff", "TXT_SUB": "#D9EAFB",
        "SELO_BG": "rgba(255,255,255,0.16)", "SELO_BORDA": "rgba(255,255,255,0.32)", "SELO_TXT": "#ffffff",
        "BG_KPI": "rgba(255,255,255,0.08)", "BORDA_KPI": "rgba(255,255,255,0.14)",
        "TXT_LBL": "#AFCBE8", "TXT_NUM": "#ffffff",
        "TXT_NOME_LEAD": "#EAF3FC", "TXT_EMAIL_LEAD": "#7C93AC", "BORDA_LISTA": "rgba(255,255,255,0.08)",
        "TXT_VAZIO": "rgba(234,243,252,0.55)", "BARRA_FUNDO": "rgba(255,255,255,0.12)",
        "BAIXAR_BG": "#ffffff", "BAIXAR_TXT": "#0C447C",
        "TXT_RODAPE": "rgba(234,243,252,0.5)", "COR_LEGENDA": "#EAF3FC",
    },
    "claro": {
        "BG_PAGINA": "#EEF3FA", "BG_TELA": "#EEF3FA",
        "BG_NAV": "rgba(255,255,255,0.75)", "BORDA_NAV": "rgba(24,95,165,0.10)",
        "TXT_LOGO": "#0C2036",
        "HERO_OVERLAY": "linear-gradient(160deg, rgba(230,241,251,0.88), rgba(181,212,244,0.68))",
        "TXT_TITULO": "#0C2036", "TXT_SUB": "#33475C",
        "SELO_BG": "rgba(255,255,255,0.7)", "SELO_BORDA": "rgba(24,95,165,0.2)", "SELO_TXT": "#0C447C",
        "BG_KPI": "rgba(255,255,255,0.72)", "BORDA_KPI": "rgba(255,255,255,0.9)",
        "TXT_LBL": "#5C7089", "TXT_NUM": "#0C2036",
        "TXT_NOME_LEAD": "#0C2036", "TXT_EMAIL_LEAD": "#5C7089", "BORDA_LISTA": "rgba(24,95,165,0.12)",
        "TXT_VAZIO": "#7C8CA1", "BARRA_FUNDO": "rgba(24,95,165,0.12)",
        "BAIXAR_BG": "#0C447C", "BAIXAR_TXT": "#ffffff",
        "TXT_RODAPE": "#7C8CA1", "COR_LEGENDA": "#33475C",
    },
}


def _linhas_leads(lista, cor):
    if not lista:
        return "<p class='vazio'>Nenhum lead nesta categoria.</p>"
    out = ""
    for ld in lista:
        out += (f"<div class='lista-lead'><div class='nome'>"
                f"<span class='pin-dot pin-dot-{cor}'></span>#{ld['id']} · {ld['nome']}</div>"
                f"<div class='email'>{ld['email']}</div></div>")
    return out


def _linhas_barras(lista, rotulo_vazio="Sem dados."):
    if not lista:
        return f"<p class='vazio'>{rotulo_vazio}</p>"
    maior = max(qtd for _, qtd in lista) or 1
    out = ""
    for nome, qtd in lista:
        largura = round(100 * qtd / maior)
        out += (f"<div class='anuncio-linha'><div class='nome'>{nome}</div>"
                f"<div class='barra-fundo'><div class='barra-cheia' style='width:{largura}%'></div></div>"
                f"<div class='qtd'>{qtd}</div></div>")
    return out


def _botao_excel(xlsx_bytes, xlsx_nome):
    if not xlsx_bytes:
        return ""
    b64 = base64.b64encode(xlsx_bytes).decode()
    return (
        f'<a class="baixar" download="{xlsx_nome}" '
        f'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}">'
        f'Baixar Excel</a>'
    )


def _slug(texto):
    return re.sub(r"[^\w\-]+", "-", texto).strip("-").lower() or "dashboard"


def gerar_dashboard_html(empresa, chave, periodo, total, contagem,
                         melhores=None, piores=None, anuncios_ruins=None,
                         tema="escuro", xlsx_bytes=None, xlsx_nome="leads.xlsx"):
    def pct(n):
        return str(round(100 * n / total)) if total else "0"

    cores = TEMAS_DASH.get(tema, TEMAS_DASH["escuro"])
    html = MODELO_DASH
    trocas = {
        "__EMPRESA__": empresa,
        "__CHAVE__": chave,
        "__PERIODO__": periodo,
        "__GERADO__": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "__TOTAL__": str(total),
        "__PCT_DENTRO__": pct(contagem["Dentro do foco"]),
        "__PCT_FORA__": pct(contagem["Fora do foco"]),
        "__PCT_ABERTO__": pct(contagem["Aberto"]),
        "__N_DENTRO__": str(contagem["Dentro do foco"]),
        "__N_FORA__": str(contagem["Fora do foco"]),
        "__N_ABERTO__": str(contagem["Aberto"]),
        "__LINHAS_MELHORES__": _linhas_leads(melhores, "verde"),
        "__LINHAS_PIORES__": _linhas_leads(piores, "verm"),
        "__LINHAS_ANUNCIOS__": _linhas_barras(anuncios_ruins, "Sem dados de anúncio."),
        "__BOTAO_EXCEL__": _botao_excel(xlsx_bytes, xlsx_nome),
        "__NOME_IMAGEM__": _slug(f"dashboard-{empresa}"),
        "__LOGO_SI__": svg_logo_si(cores["TXT_LOGO"], cores["BG_TELA"]),
    }
    for chave_cor, valor_cor in cores.items():
        trocas[f"__{chave_cor}__"] = valor_cor
    for k, v in trocas.items():
        html = html.replace(k, v)
    return html


def gerar_dashboard_combinado(empresa, chave, periodo, total, n_perdidos, n_fora, n_dentro,
                              produtos_perdidos=None, motivos_fora=None,
                              tema="escuro", xlsx_bytes=None, xlsx_nome="saude_cliente.xlsx"):
    """Dashboard da tela 'Saúde do cliente' — funil combinado de volume
    perdido + validação de foco, mesmo visual dos dois relatórios
    individuais (TEMAS_DASH)."""
    recebidos = n_fora + n_dentro

    def pct_recebidos(n):
        return str(round(100 * n / recebidos)) if recebidos else "0"

    cores = TEMAS_DASH.get(tema, TEMAS_DASH["escuro"])
    html = MODELO_DASH_COMBINADO
    trocas = {
        "__EMPRESA__": empresa,
        "__CHAVE__": chave,
        "__PERIODO__": periodo,
        "__GERADO__": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "__TOTAL__": str(total),
        "__N_PERDIDOS__": str(n_perdidos),
        "__N_FORA__": str(n_fora),
        "__N_DENTRO__": str(n_dentro),
        "__PCT_FORA__": pct_recebidos(n_fora),
        "__PCT_DENTRO__": pct_recebidos(n_dentro),
        "__LINHAS_PRODUTOS_PERDIDOS__": _linhas_barras(produtos_perdidos, "Nenhum orçamento perdido encontrado."),
        "__LINHAS_MOTIVOS_FORA__": _linhas_barras(motivos_fora, "Nenhum lead fora de foco encontrado."),
        "__BOTAO_EXCEL__": _botao_excel(xlsx_bytes, xlsx_nome),
        "__LOGO_SI__": svg_logo_si(cores["TXT_LOGO"], cores["BG_TELA"]),
    }
    for chave_cor, valor_cor in cores.items():
        trocas[f"__{chave_cor}__"] = valor_cor
    for k, v in trocas.items():
        html = html.replace(k, v)
    return html
