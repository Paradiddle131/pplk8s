/* report-kit filter. Markup: <details class="rk-filter" data-rk-filter> holding <summary> (the button's words, then
   <span class="rk-filter-count"></span>) and <div class="rk-filter-panel"> with fieldsets of
   <label class="rk-check"><input type="checkbox" checked>...</label> and a <div class="rk-filter-foot"> holding
   <button type="button" class="rk-filter-reset">Show all</button>. The count says how many boxes are off ("2 off");
   "Show all" ticks every box and fires one change per box it ticked, so the page's own change handler filters; Escape
   or a click outside closes the panel, focus back on its button. The page filters its rows on the boxes' change
   events: this component only folds the controls away. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  function count(d) {
    const boxes = [...d.querySelectorAll('.rk-filter-panel input[type="checkbox"]')];
    const off = boxes.filter(b => !b.checked).length;
    const c = d.querySelector(".rk-filter-count");
    if (c) c.textContent = off ? `${off} off` : "";
    const r = d.querySelector(".rk-filter-reset");
    if (r) r.disabled = !off;
  }
  function init(root) {
    for (const d of root.querySelectorAll("details[data-rk-filter]")) {
      if (d.dataset.rkFilterOn) continue;
      d.dataset.rkFilterOn = "";
      const sum = d.querySelector("summary");
      d.addEventListener("change", () => count(d));
      // opened, the panel stays inside the viewport: right-aligned under its button, else left-aligned, else shifted
      const panel = d.querySelector(".rk-filter-panel");
      d.addEventListener("toggle", () => {
        if (!d.open || !panel) return;
        panel.style.left = panel.style.right = "";
        const pad = 16, vw = document.documentElement.clientWidth;
        let r = panel.getBoundingClientRect();
        if (r.left < pad) { panel.style.right = "auto"; panel.style.left = "0"; r = panel.getBoundingClientRect(); }
        if (r.right > vw - pad) panel.style.left = `${Math.round(parseFloat(getComputedStyle(panel).left) - (r.right - (vw - pad)))}px`;
      });
      const r = d.querySelector(".rk-filter-reset");
      if (r) r.addEventListener("click", () => {
        for (const b of d.querySelectorAll('.rk-filter-panel input[type="checkbox"]')) {
          if (b.checked) continue;
          b.checked = true;
          b.dispatchEvent(new Event("change", { bubbles: true }));
        }
        count(d);
        // the reset turns itself off once nothing is off; keep the keyboard inside the panel, on the first box
        const first = d.querySelector('.rk-filter-panel input[type="checkbox"]');
        if (first) first.focus();
      });
      // Escape closes from anywhere in the panel, or when focus rests nowhere (the page itself)
      document.addEventListener("keydown", e => {
        if (e.key !== "Escape" || !d.open) return;
        const a = document.activeElement;
        if (a && a !== document.body && !d.contains(a)) return;
        e.stopPropagation(); d.open = false; sum.focus();
      });
      document.addEventListener("click", e => { if (d.open && !d.contains(e.target)) d.open = false; });
      count(d);
    }
  }
  RK.filter = { count };
  (RK.inits = RK.inits || []).push(init);
})();
