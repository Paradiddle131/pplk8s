/* report-kit highlight. A trigger carries data-lit="<mark kind>" (ok, no, warn, bad, info); its scope is the
   nearest ancestor with data-rk-lit-scope (else the nearest table). Pointing at the trigger, or focusing it from
   the keyboard, sets data-rk-lit on the scope; leaving it, blurring it, Escape, or the pointer leaving the
   window resets it. A tap lights nothing, so a sort by touch never leaves marks lit. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  let lit = null;
  function off() { if (lit) { lit.removeAttribute("data-rk-lit"); lit = null; } }
  function on(t) {
    off();
    const scope = t.closest("[data-rk-lit-scope]") || t.closest("table");
    if (!scope) return;
    scope.setAttribute("data-rk-lit", t.dataset.lit);
    lit = scope;
  }
  let global = false;
  function init(root) {
    for (const t of root.querySelectorAll("[data-lit]")) {
      t.addEventListener("pointerenter", e => { if (e.pointerType !== "touch") on(t); });
      t.addEventListener("pointerleave", off);
      t.addEventListener("focus", () => { if (t.matches(":focus-visible")) on(t); });
      t.addEventListener("blur", off);
    }
    if (global) return;
    global = true;
    document.documentElement.addEventListener("pointerleave", off);
    addEventListener("blur", off);
    addEventListener("keydown", e => { if (e.key === "Escape") off(); });
    document.addEventListener("rk:switch", off);
    document.addEventListener("rk:tab", off);
  }
  RK.highlight = { off };
  (RK.inits = RK.inits || []).push(init);
})();
