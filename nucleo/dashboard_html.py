"""Dashboards HTML autocontidos (para download) — um do validador de foco
(distribuição dos leads recebidos) e um combinado, para a tela de saúde do
cliente (funil completo: perdidos + recebidos).

Os dois relatórios são 100% offline: o gráfico de rosca é SVG gerado aqui
(sem depender de CDN como o antigo Chart.js) e a exportação (Baixar imagem /
salvar PDF) usa a lib html2canvas embutida no próprio arquivo — então tudo
abre e funciona igual mesmo sem internet ou em rede que bloqueia CDN.

Os dashboards também são editáveis no próprio arquivo: dá pra ocultar
campos individuais e, no combinado, mostrar/ocultar tudo que é "leads
perdidos" (informação interna que não vai pro cliente). Os controles de
edição nunca aparecem no PDF/imagem exportado."""
import base64
import json
import math
from datetime import datetime
from html import escape as _esc
from pathlib import Path

from nucleo.tema import svg_logo_si

# html2canvas 1.4.1 (MIT) vendorizado ao lado deste módulo, embutido inline em
# cada dashboard pra o "Baixar imagem" funcionar offline.
_HTML2CANVAS_JS = (Path(__file__).with_name("html2canvas.min.js")).read_text(encoding="utf-8")

# JS do botão "Baixar imagem": rasteriza a área do relatório (sem a barra de
# controles) e baixa um JPG. __NOME_IMAGEM__ e __BG_TELA__ são trocados depois.
SCRIPT_IMAGEM = """
(function () {
  var btn = document.getElementById("btn-imagem");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var original = btn.textContent;
    btn.textContent = "Gerando imagem...";
    // Sai do modo de edicao durante a captura pra os ✕ e o contorno tracejado
    // nao aparecerem na imagem. Campos que voce ocultou continuam ocultos, e a
    // visao de leads perdidos e capturada exatamente como esta na tela.
    var estavaEditando = document.body.classList.contains("modo-edicao");
    document.body.classList.remove("modo-edicao");
    function restaurar() { if (estavaEditando) document.body.classList.add("modo-edicao"); }
    html2canvas(document.getElementById("area-captura"), { backgroundColor: "__BG_TELA__", scale: 2, useCORS: true })
      .then(function (canvas) {
        var link = document.createElement("a");
        link.download = "__NOME_IMAGEM__.jpg";
        link.href = canvas.toDataURL("image/jpeg", 0.92);
        link.click();
        restaurar();
        btn.textContent = original;
      })
      .catch(function () { restaurar(); btn.textContent = "Erro ao gerar — tente de novo"; });
  });
})();
"""

# CSS comum aos dois dashboards (barra de edição, botão ocultar campo, etc.)
CSS_EDICAO = """
  .barra-edicao { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 12px 36px; background: __BG_NAV__; border-bottom: 1px solid __BORDA_NAV__; }
  .barra-edicao .be-titulo { font-size: 11px; font-weight: 700; letter-spacing: .4px; text-transform: uppercase; color: __TXT_LBL__; }
  .barra-edicao button { font-size: 12px; font-weight: 600; padding: 7px 14px; border-radius: 20px; border: 1px solid __SELO_BORDA__; background: transparent; color: __TXT_LOGO__; cursor: pointer; }
  .barra-edicao .be-print { background: __BAIXAR_BG__; color: __BAIXAR_TXT__; border: none; }
  .switch { display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; color: __TXT_LOGO__; cursor: pointer; user-select: none; }
  .switch input { width: 16px; height: 16px; accent-color: #1D9E75; cursor: pointer; }
  [data-bloco] { position: relative; }
  .btn-x { display: none; position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border-radius: 50%; border: none; background: #D85A30; color: #fff; cursor: pointer; font-size: 12px; line-height: 1; z-index: 5; }
  body.modo-edicao .btn-x { display: block; }
  body.modo-edicao [data-bloco] { outline: 1px dashed rgba(216,90,48,0.55); outline-offset: 2px; }
  @media print { .no-print { display: none !important; } .btn-x { display: none !important; } body.modo-edicao [data-bloco] { outline: none; } }
"""

# JS comum: modo "ocultar campos" (✕ em cada bloco) + restaurar tudo.
SCRIPT_EDICAO = """
(function () {
  var editando = false;
  var btnE = document.getElementById("btn-editar");
  function marcarBlocos() {
    document.querySelectorAll("[data-bloco]").forEach(function (el) {
      if (el.querySelector(":scope > .btn-x")) return;
      var x = document.createElement("button");
      x.className = "btn-x"; x.type = "button"; x.textContent = "\\u2715";
      x.title = "Ocultar este campo";
      x.addEventListener("click", function (ev) {
        ev.stopPropagation();
        el.style.display = "none";
      });
      el.appendChild(x);
    });
  }
  if (btnE) btnE.addEventListener("click", function () {
    editando = !editando;
    document.body.classList.toggle("modo-edicao", editando);
    btnE.textContent = editando ? "Concluir edicao" : "Ocultar campos";
    if (editando) marcarBlocos();
  });
  var btnR = document.getElementById("btn-restaurar");
  if (btnR) btnR.addEventListener("click", function () {
    document.querySelectorAll("[data-bloco]").forEach(function (el) { el.style.display = ""; });
    document.dispatchEvent(new CustomEvent("restaurar-dash"));
  });
})();
"""

# JS específico do combinado: alterna a visão "com / sem leads perdidos",
# recalculando o total, o selo e o gráfico de rosca.
SCRIPT_PERDIDOS = """
(function () {
  var D = __DADOS_JSON__;
  var chk = document.getElementById("chk-perdidos");
  function desenharRosca(mostrar) {
    var segs = [["Dentro do foco", D.dentro, D.cores.dentro], ["Fora de foco", D.fora, D.cores.fora]];
    if (mostrar) segs.unshift(["Perdidos", D.perdidos, D.cores.perdidos]);
    var total = segs.reduce(function (s, x) { return s + x[1]; }, 0);
    var C = 2 * Math.PI * 54, acc = 0, aneis = "";
    if (total <= 0) {
      aneis = '<circle cx="70" cy="70" r="54" fill="none" stroke="rgba(150,150,150,0.25)" stroke-width="22"/>';
    } else {
      segs.forEach(function (x) {
        if (x[1] <= 0) return;
        var seg = C * x[1] / total;
        aneis += '<circle cx="70" cy="70" r="54" fill="none" stroke="' + x[2] + '" stroke-width="22" stroke-dasharray="' + seg.toFixed(2) + ' ' + (C - seg).toFixed(2) + '" stroke-dashoffset="' + (-acc).toFixed(2) + '"/>';
        acc += seg;
      });
    }
    var leg = "";
    segs.forEach(function (x) {
      leg += '<span class="leg-item" style="color:' + D.corLegenda + '"><span class="leg-dot" style="background:' + x[2] + '"></span>' + x[0] + " (" + x[1] + ")</span>";
    });
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 140" width="170" height="170"><g transform="rotate(-90 70 70)">' + aneis + '</g></svg>';
    var img = '<img src="data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg) + '" width="170" height="170" alt="Grafico de rosca" style="display:block;margin:0 auto;">';
    document.getElementById("grafico-rosca").innerHTML = img + '<div class="legenda">' + leg + "</div>";
  }
  function aplicar(mostrar) {
    document.getElementById("kpi-perdidos").style.display = mostrar ? "" : "none";
    var pp = document.getElementById("painel-perdidos");
    if (pp) pp.style.display = mostrar ? "" : "none";
    var recebidos = D.fora + D.dentro;
    var total = mostrar ? recebidos + D.perdidos : recebidos;
    document.getElementById("kpi-total-num").textContent = total;
    document.getElementById("kpi-total-sub").textContent = mostrar ? "recebidos + perdidos" : "somente recebidos";
    document.getElementById("selo-total").textContent = total;
    document.getElementById("selo-total-lbl").textContent = mostrar ? "orcamentos no periodo" : "leads recebidos";
    desenharRosca(mostrar);
  }
  if (chk) chk.addEventListener("change", function () { aplicar(chk.checked); });
  document.addEventListener("restaurar-dash", function () { if (chk) chk.checked = true; aplicar(true); });
  aplicar(chk ? chk.checked : true);
})();
"""

MODELO_DASH = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Validação — __EMPRESA__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; background: __BG_PAGINA__; }
  .tela { max-width: 1180px; margin: 0 auto; background: __BG_TELA__; }
  .nav { display: flex; align-items: center; justify-content: space-between; padding: 18px 36px; background: __BG_NAV__; border-bottom: 1px solid __BORDA_NAV__; }
  .nav .logo { display: flex; align-items: center; gap: 10px; color: __TXT_LOGO__; font-weight: 700; font-size: 14px; }
  .nav .logo .logo-si { flex-shrink: 0; }
  .nav .dir { display: flex; align-items: center; gap: 10px; }
  .nav .baixar { font-size: 12px; color: __BAIXAR_TXT__; background: __BAIXAR_BG__; padding: 8px 16px; border-radius: 20px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; }
  .hero {
    padding: 24px 36px 20px;
    background: __HERO_OVERLAY__;
    border-bottom: 1px solid __BORDA_KPI__;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  }
  .hero h1 { color: __TXT_TITULO__; font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .hero p { color: __TXT_SUB__; font-size: 12.5px; }
  .selo { background: __SELO_BG__; border: 1px solid __SELO_BORDA__; color: __SELO_TXT__; font-size: 12.5px; padding: 7px 16px; border-radius: 8px; }
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
  .grafico { padding: 6px 0 2px; }
  .legenda { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px; margin-top: 12px; }
  .leg-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
  .leg-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
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
__CSS_EDICAO__
  @media (max-width: 760px) { .kpis { grid-template-columns: 1fr 1fr; } .linha { grid-template-columns: 1fr; } }
  @media print { body { background: #fff; } }
</style>
</head>
<body>
<div class="tela" id="tela-captura">
  <div class="nav">
    <div class="logo">__LOGO_SI__ Validador de Leads</div>
    <div class="dir">__BOTAO_EXCEL__</div>
  </div>
  <div class="barra-edicao no-print">
    <span class="be-titulo">Editar relatório</span>
    <button id="btn-editar" type="button">Ocultar campos</button>
    <button id="btn-restaurar" type="button">Restaurar tudo</button>
    <button class="be-print" id="btn-imagem" type="button">Baixar imagem</button>
    <button type="button" onclick="window.print()">Salvar PDF</button>
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
        <div class="kpi" data-bloco="Total de leads"><div class="lbl">Total de leads</div><div class="num">__TOTAL__</div><div class="sub">no período</div></div>
        <div class="kpi" data-bloco="Dentro do foco"><div class="lbl">Dentro do foco</div><div class="num v">__PCT_DENTRO__%</div><div class="sub">__N_DENTRO__ leads</div></div>
        <div class="kpi" data-bloco="Fora do foco"><div class="lbl">Fora do foco</div><div class="num r">__PCT_FORA__%</div><div class="sub">__N_FORA__ leads</div></div>
        <div class="kpi" data-bloco="Aberto"><div class="lbl">Aberto</div><div class="num a">__PCT_ABERTO__%</div><div class="sub">__N_ABERTO__ leads</div></div>
      </div>

      <div class="linha">
        <div class="painel" data-bloco="Distribuição por status">
          <h2>Distribuição por status</h2>
          <div class="grafico">__GRAFICO_ROSCA__</div>
        </div>
        <div class="painel" data-bloco="Anúncios fora do foco">
          <h2>Anúncios que mais geraram leads fora do foco</h2>
          __LINHAS_ANUNCIOS__
        </div>
      </div>

      <div class="linha">
        <div class="painel" data-bloco="Melhores leads">
          <h2>Melhores leads <span class="pin pin-verde">dentro do foco</span></h2>
          __LINHAS_MELHORES__
        </div>
        <div class="painel" data-bloco="Piores leads">
          <h2>Piores leads <span class="pin pin-verm">fora do foco</span></h2>
          __LINHAS_PIORES__
        </div>
      </div>
    </div>
  </div>
</div>
<p class="rodape">Validador de Leads · Soluções Industriais · uso interno</p>
<script>__HTML2CANVAS__</script>
<script>__SCRIPT_EDICAO__</script>
<script>__SCRIPT_IMAGEM__</script>
</body>
</html>"""

# Modelo do dashboard combinado (Saúde do cliente): funil de 4 KPIs em vez
# dos 3 do validador isolado — Total no período / Perdidos / Fora de foco /
# Dentro do foco. Reaproveita os mesmos tokens de cor (TEMAS_DASH), ganhou o
# gráfico de rosca, o quadro de melhores leads e o botão "leads perdidos".
MODELO_DASH_COMBINADO = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saúde do cliente — __EMPRESA__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; background: __BG_PAGINA__; }
  .tela { max-width: 1180px; margin: 0 auto; background: __BG_TELA__; }
  .nav { display: flex; align-items: center; justify-content: space-between; padding: 18px 36px; background: __BG_NAV__; border-bottom: 1px solid __BORDA_NAV__; }
  .nav .logo { display: flex; align-items: center; gap: 10px; color: __TXT_LOGO__; font-weight: 700; font-size: 14px; }
  .nav .logo .logo-si { flex-shrink: 0; }
  .nav .dir { display: flex; align-items: center; gap: 10px; }
  .nav .baixar { font-size: 12px; color: __BAIXAR_TXT__; background: __BAIXAR_BG__; padding: 8px 16px; border-radius: 20px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; }
  .hero {
    padding: 24px 36px 20px;
    background: __HERO_OVERLAY__;
    border-bottom: 1px solid __BORDA_KPI__;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  }
  .hero h1 { color: __TXT_TITULO__; font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .hero p { color: __TXT_SUB__; font-size: 12.5px; }
  .selo { background: __SELO_BG__; border: 1px solid __SELO_BORDA__; color: __SELO_TXT__; font-size: 12.5px; padding: 7px 16px; border-radius: 8px; }
  .selo b { font-size: 14px; }
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
  .painel h2 .pin { font-size: 11px; padding: 2px 8px; border-radius: 20px; vertical-align: middle; margin-left: 6px; font-weight: 600; }
  .pin-verde { background: rgba(29,158,117,0.18); color: #1D9E75; }
  .grafico { padding: 6px 0 2px; }
  .legenda { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px; margin-top: 12px; }
  .leg-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
  .leg-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
  .lista-lead { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid __BORDA_LISTA__; font-size: 12.5px; gap: 10px; }
  .lista-lead:last-child { border-bottom: none; }
  .lista-lead .nome { color: __TXT_NOME_LEAD__; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .pin-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .pin-dot-verde { background: #1D9E75; }
  .lista-lead .email { color: __TXT_EMAIL_LEAD__; font-size: 11.5px; text-align: right; }
  .anuncio-linha { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12.5px; }
  .anuncio-linha .nome { width: 190px; color: __TXT_NOME_LEAD__; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .barra-fundo { flex: 1; height: 8px; background: __BARRA_FUNDO__; border-radius: 5px; overflow: hidden; }
  .barra-cheia { height: 100%; background: #D85A30; border-radius: 5px; }
  .anuncio-linha .qtd { width: 22px; text-align: right; color: __TXT_LBL__; }
  .vazio { color: __TXT_VAZIO__; font-size: 12px; }
  .rodape { text-align: center; color: __TXT_RODAPE__; font-size: 11px; padding: 18px 0 0; }
__CSS_EDICAO__
  @media (max-width: 760px) { .kpis { grid-template-columns: 1fr 1fr; } .linha { grid-template-columns: 1fr; } }
  @media print { body { background: #fff; } }
</style>
</head>
<body>
<div class="tela" id="tela-captura">
  <div class="nav">
    <div class="logo">__LOGO_SI__ Saúde do cliente</div>
    <div class="dir">__BOTAO_EXCEL__</div>
  </div>
  <div class="barra-edicao no-print">
    <label class="switch"><input type="checkbox" id="chk-perdidos" checked> Mostrar leads perdidos</label>
    <span class="be-titulo">·</span>
    <button id="btn-editar" type="button">Ocultar campos</button>
    <button id="btn-restaurar" type="button">Restaurar tudo</button>
    <button class="be-print" id="btn-imagem" type="button">Baixar imagem</button>
    <button type="button" onclick="window.print()">Salvar PDF</button>
  </div>
  <div id="area-captura">
    <div class="hero">
      <div>
        <h1>__EMPRESA__</h1>
        <p>chave __CHAVE__ &nbsp;·&nbsp; __PERIODO__ &nbsp;·&nbsp; gerado em __GERADO__</p>
      </div>
      <div class="selo"><b id="selo-total">__TOTAL__</b> <span id="selo-total-lbl">orçamentos no período</span></div>
    </div>
    <div class="corpo">
      <div class="kpis">
        <div class="kpi" data-bloco="Orçamentos no período"><div class="lbl">Orçamentos no período</div><div class="num" id="kpi-total-num">__TOTAL__</div><div class="sub" id="kpi-total-sub">recebidos + perdidos</div></div>
        <div class="kpi" id="kpi-perdidos"><div class="lbl">Perdidos (dentro do foco)</div><div class="num p">__N_PERDIDOS__</div><div class="sub">falta de vínculo</div></div>
        <div class="kpi" data-bloco="Recebidos fora de foco"><div class="lbl">Recebidos fora de foco</div><div class="num f">__N_FORA__</div><div class="sub">__PCT_FORA__% dos recebidos</div></div>
        <div class="kpi" data-bloco="Recebidos dentro do foco"><div class="lbl">Recebidos dentro do foco</div><div class="num d">__N_DENTRO__</div><div class="sub">__PCT_DENTRO__% dos recebidos</div></div>
      </div>
      <div class="linha">
        <div class="painel" data-bloco="Distribuição do funil">
          <h2>Distribuição do funil</h2>
          <div class="grafico" id="grafico-rosca">__GRAFICO_ROSCA__</div>
        </div>
        <div class="painel" data-bloco="Melhores leads">
          <h2>Melhores leads <span class="pin pin-verde">dentro do foco</span></h2>
          __LINHAS_MELHORES__
        </div>
      </div>
      <div class="linha">
        <div class="painel" id="painel-perdidos">
          <h2>Volume perdido · por produto</h2>
          __LINHAS_PRODUTOS_PERDIDOS__
        </div>
        <div class="painel" data-bloco="Anúncios fora de foco">
          <h2>Fora de foco · anúncios mais frequentes</h2>
          __LINHAS_ANUNCIOS_FORA__
        </div>
      </div>
    </div>
  </div>
</div>
<p class="rodape">Saúde do cliente · Soluções Industriais · uso interno</p>
<script>__HTML2CANVAS__</script>
<script>__SCRIPT_EDICAO__</script>
<script>__SCRIPT_PERDIDOS__</script>
<script>__SCRIPT_IMAGEM__</script>
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


def _svg_rosca(dados, cor_legenda, tamanho=170):
    """Gráfico de rosca em SVG puro (sem Chart.js), pra o relatório funcionar
    offline. `dados` é uma lista de (rótulo, valor, cor)."""
    total = sum(v for _, v, _ in dados)
    cx = cy = 70
    r = 54
    sw = 22
    circ = 2 * math.pi * r
    aneis = []
    if total <= 0:
        aneis.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="rgba(150,150,150,0.25)" stroke-width="{sw}"/>'
        )
    else:
        acumulado = 0.0
        for _rot, valor, cor in dados:
            if valor <= 0:
                continue
            seg = circ * valor / total
            aneis.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{cor}" '
                f'stroke-width="{sw}" stroke-dasharray="{seg:.2f} {circ - seg:.2f}" '
                f'stroke-dashoffset="{-acumulado:.2f}"/>'
            )
            acumulado += seg
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 140" '
        f'width="{tamanho}" height="{tamanho}">'
        f'<g transform="rotate(-90 {cx} {cy})">{"".join(aneis)}</g></svg>'
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode()
    img = (
        f'<img src="data:image/svg+xml;base64,{b64}" width="{tamanho}" height="{tamanho}" '
        f'alt="Gráfico de rosca" style="display:block; margin:0 auto;">'
    )
    legenda = "<div class='legenda'>"
    for rotulo, valor, cor in dados:
        legenda += (
            f"<span class='leg-item' style='color:{cor_legenda}'>"
            f"<span class='leg-dot' style='background:{cor}'></span>"
            f"{_esc(str(rotulo))} ({valor})</span>"
        )
    legenda += "</div>"
    return img + legenda


def _linhas_leads(lista, cor):
    if not lista:
        return "<p class='vazio'>Nenhum lead nesta categoria.</p>"
    out = ""
    for ld in lista:
        out += (f"<div class='lista-lead'><div class='nome'>"
                f"<span class='pin-dot pin-dot-{cor}'></span>"
                f"#{_esc(str(ld['id']))} · {_esc(str(ld['nome']))}</div>"
                f"<div class='email'>{_esc(str(ld['email']))}</div></div>")
    return out


def _linhas_barras(lista, rotulo_vazio="Sem dados."):
    if not lista:
        return f"<p class='vazio'>{_esc(rotulo_vazio)}</p>"
    maior = max(qtd for _, qtd in lista) or 1
    out = ""
    for nome, qtd in lista:
        largura = round(100 * qtd / maior)
        out += (f"<div class='anuncio-linha'><div class='nome'>{_esc(str(nome))}</div>"
                f"<div class='barra-fundo'><div class='barra-cheia' style='width:{largura}%'></div></div>"
                f"<div class='qtd'>{qtd}</div></div>")
    return out


def _botao_excel(xlsx_bytes, xlsx_nome):
    if not xlsx_bytes:
        return ""
    b64 = base64.b64encode(xlsx_bytes).decode()
    return (
        f'<a class="baixar" download="{_esc(xlsx_nome, quote=True)}" '
        f'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}">'
        f'Baixar Excel</a>'
    )


def _nome_imagem(texto):
    """Nome de arquivo seguro para o JPG do 'Baixar imagem' (sem espaços nem
    símbolos que a JS possa quebrar em atributo download)."""
    limpo = "".join(c if c.isalnum() else "-" for c in texto).strip("-")
    return limpo or "dashboard"


def gerar_dashboard_html(empresa, chave, periodo, total, contagem,
                         melhores=None, piores=None, anuncios_ruins=None,
                         tema="escuro", xlsx_bytes=None, xlsx_nome="leads.xlsx"):
    def pct(n):
        return str(round(100 * n / total)) if total else "0"

    cores = TEMAS_DASH.get(tema, TEMAS_DASH["escuro"])
    rosca = _svg_rosca(
        [("Dentro do foco", contagem["Dentro do foco"], "#1D9E75"),
         ("Fora do foco", contagem["Fora do foco"], "#D85A30"),
         ("Aberto", contagem["Aberto"], "#BA7517")],
        cores["COR_LEGENDA"],
    )
    html = MODELO_DASH
    trocas = {
        "__CSS_EDICAO__": CSS_EDICAO,
        "__HTML2CANVAS__": _HTML2CANVAS_JS,
        "__SCRIPT_EDICAO__": SCRIPT_EDICAO,
        "__SCRIPT_IMAGEM__": SCRIPT_IMAGEM.replace("__NOME_IMAGEM__", _nome_imagem(f"Validacao-{empresa}")),
        "__EMPRESA__": _esc(empresa),
        "__CHAVE__": _esc(chave),
        "__PERIODO__": _esc(periodo),
        "__GERADO__": datetime.now().strftime("%d/%m/%Y"),
        "__TOTAL__": str(total),
        "__PCT_DENTRO__": pct(contagem["Dentro do foco"]),
        "__PCT_FORA__": pct(contagem["Fora do foco"]),
        "__PCT_ABERTO__": pct(contagem["Aberto"]),
        "__N_DENTRO__": str(contagem["Dentro do foco"]),
        "__N_FORA__": str(contagem["Fora do foco"]),
        "__N_ABERTO__": str(contagem["Aberto"]),
        "__GRAFICO_ROSCA__": rosca,
        "__LINHAS_MELHORES__": _linhas_leads(melhores, "verde"),
        "__LINHAS_PIORES__": _linhas_leads(piores, "verm"),
        "__LINHAS_ANUNCIOS__": _linhas_barras(anuncios_ruins, "Sem dados de anúncio."),
        "__BOTAO_EXCEL__": _botao_excel(xlsx_bytes, xlsx_nome),
        "__LOGO_SI__": svg_logo_si(cores["TXT_LOGO"], cores["BG_TELA"]),
    }
    for chave_cor, valor_cor in cores.items():
        trocas[f"__{chave_cor}__"] = valor_cor
    for k, v in trocas.items():
        html = html.replace(k, v)
    return html


def gerar_dashboard_combinado(empresa, chave, periodo, total, n_perdidos, n_fora, n_dentro,
                              produtos_perdidos=None, anuncios_fora=None, melhores=None,
                              tema="escuro", xlsx_bytes=None, xlsx_nome="saude_cliente.xlsx"):
    """Dashboard da tela 'Saúde do cliente' — funil combinado de volume
    perdido + validação de foco, mesmo visual dos dois relatórios
    individuais (TEMAS_DASH). Editável no próprio arquivo: dá pra
    mostrar/ocultar tudo que é leads perdidos e ocultar campos avulsos."""
    recebidos = n_fora + n_dentro

    def pct_recebidos(n):
        return str(round(100 * n / recebidos)) if recebidos else "0"

    cores = TEMAS_DASH.get(tema, TEMAS_DASH["escuro"])
    rosca = _svg_rosca(
        [("Perdidos", n_perdidos, "#D85A30"),
         ("Fora de foco", n_fora, "#BA7517"),
         ("Dentro do foco", n_dentro, "#1D9E75")],
        cores["COR_LEGENDA"],
    )
    dados_js = json.dumps({
        "perdidos": n_perdidos, "fora": n_fora, "dentro": n_dentro,
        "cores": {"perdidos": "#D85A30", "fora": "#BA7517", "dentro": "#1D9E75"},
        "corLegenda": cores["COR_LEGENDA"],
    })
    html = MODELO_DASH_COMBINADO
    trocas = {
        "__CSS_EDICAO__": CSS_EDICAO,
        "__HTML2CANVAS__": _HTML2CANVAS_JS,
        "__SCRIPT_EDICAO__": SCRIPT_EDICAO,
        "__SCRIPT_IMAGEM__": SCRIPT_IMAGEM.replace("__NOME_IMAGEM__", _nome_imagem(f"Saude-cliente-{empresa}")),
        "__SCRIPT_PERDIDOS__": SCRIPT_PERDIDOS.replace("__DADOS_JSON__", dados_js),
        "__EMPRESA__": _esc(empresa),
        "__CHAVE__": _esc(chave),
        "__PERIODO__": _esc(periodo),
        "__GERADO__": datetime.now().strftime("%d/%m/%Y"),
        "__TOTAL__": str(total),
        "__N_PERDIDOS__": str(n_perdidos),
        "__N_FORA__": str(n_fora),
        "__N_DENTRO__": str(n_dentro),
        "__PCT_FORA__": pct_recebidos(n_fora),
        "__PCT_DENTRO__": pct_recebidos(n_dentro),
        "__GRAFICO_ROSCA__": rosca,
        "__LINHAS_MELHORES__": _linhas_leads(melhores, "verde"),
        "__LINHAS_PRODUTOS_PERDIDOS__": _linhas_barras(produtos_perdidos, "Nenhum orçamento perdido encontrado."),
        "__LINHAS_ANUNCIOS_FORA__": _linhas_barras(anuncios_fora, "Nenhum lead fora de foco encontrado."),
        "__BOTAO_EXCEL__": _botao_excel(xlsx_bytes, xlsx_nome),
        "__LOGO_SI__": svg_logo_si(cores["TXT_LOGO"], cores["BG_TELA"]),
    }
    for chave_cor, valor_cor in cores.items():
        trocas[f"__{chave_cor}__"] = valor_cor
    for k, v in trocas.items():
        html = html.replace(k, v)
    return html
