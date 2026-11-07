/* report-kit chart theme for Observable Plot (inline it with <!-- report-kit:vendor plot -->).
   ReportKit.plotTheme(el) reads the tokens as they stand and returns {ink, paper, line, hair, ok, warn, bad, info,
   viz: [...], font, fontPx, options}; options are Plot defaults in the kit's look (font, ink axes, a light grid,
   series colours, margins scaled to the text size). Plot cannot read CSS variables, which is why the colours are
   resolved values and why a chart is redrawn when the theme changes.
   ReportKit.plot(el, spec) draws spec(theme, width) -> Plot options into el's .rk-chart-plot (or el itself), merged
   over the defaults, and redraws it when the theme flips or its width changes (a chart in a hidden tab is drawn
   once it is shown). */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  function plotTheme(el) {
    // tokens as they reach el: from :root on a whole page, from the scope when the kit runs in part of one
    const root = getComputedStyle(el || document.documentElement);
    const v = n => root.getPropertyValue(n).trim();
    const fontPx = parseFloat(getComputedStyle(el || document.body).fontSize) || 14;
    const t = {
      ink: v("--ink"), paper: v("--paper"), line: v("--line"), ok: v("--ok"), warn: v("--warn"), bad: v("--bad"), info: v("--info"),
      viz: [v("--viz-1"), v("--viz-2"), v("--viz-3"), v("--viz-4")], font: v("--sans"), fontPx,
    };
    t.options = {
      style: { background: "transparent", color: t.ink, fontFamily: t.font, fontSize: fontPx + "px", overflow: "visible" },
      marginTop: Math.round(fontPx * 1.6), marginBottom: Math.round(fontPx * 3.2), marginLeft: Math.round(fontPx * 3), marginRight: Math.round(fontPx),
      color: { range: t.viz },
      x: { labelArrow: "none", tickSize: 4, labelAnchor: "center", labelOffset: Math.round(fontPx * 2.4) },
      y: { labelArrow: "none", tickSize: 0, grid: true },
    };
    return t;
  }
  const charts = new Set();
  function merge(a, b) {
    const out = Object.assign({}, a, b);
    for (const k of ["style", "x", "y", "color"]) if (a[k] && b[k] && typeof b[k] === "object") out[k] = Object.assign({}, a[k], b[k]);
    return out;
  }
  function draw(c) {
    const box = c.el.querySelector(".rk-chart-plot") || c.el;
    const width = Math.floor(box.clientWidth);
    if (!width || !window.Plot) return;
    c.width = width;
    const theme = plotTheme(box);
    const chart = window.Plot.plot(merge(theme.options, Object.assign({ width }, c.spec(theme, width))));
    box.replaceChildren(chart);
  }
  function plot(el, spec) {
    const c = { el, spec, width: 0 };
    charts.add(c);
    const box = el.querySelector(".rk-chart-plot") || el;
    if (window.ResizeObserver) new ResizeObserver(() => { if (Math.floor(box.clientWidth) !== c.width) draw(c); }).observe(box);
    draw(c);
    return { redraw: () => draw(c) };
  }
  const redrawAll = () => charts.forEach(draw);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redrawAll);
  new MutationObserver(redrawAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  RK.plotTheme = plotTheme;
  RK.plot = plot;
})();
