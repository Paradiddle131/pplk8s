/* report-kit dialog. Markup: <button type="button" data-rk-open="ID">...</button> opens
   <dialog class="rk-dialog" id="ID" aria-labelledby="H"> with <div class="rk-dialog-top"><h2 id="H">...</h2>
   <button type="button" class="rk-dialog-close" aria-label="Close">(a cross)</button></div> and its content.
   It opens modal (showModal: the page behind is inert, Tab stays in the dialog and the browser), puts the focus on
   its heading so the reader starts at the top of a long content, and on close (the button, Escape, a click on the
   scrim) gives the focus back to what opened it. API: ReportKit.dialog.open(id), .close(id). */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const openers = new WeakMap();
  function open(id, from) {
    const d = document.getElementById(id);
    if (!d || d.open) return;
    openers.set(d, from || document.activeElement);
    d.showModal();
    const h = d.querySelector(".rk-dialog-top h2");
    if (h) { if (!h.hasAttribute("tabindex")) h.tabIndex = -1; h.focus({ preventScroll: true }); }
  }
  function close(id) { const d = document.getElementById(id); if (d && d.open) d.close(); }
  function init(root) {
    for (const b of root.querySelectorAll("[data-rk-open]")) b.addEventListener("click", () => open(b.dataset.rkOpen, b));
    for (const d of root.querySelectorAll("dialog.rk-dialog")) {
      if (d.dataset.rkDialogOn) continue;
      d.dataset.rkDialogOn = "";
      d.addEventListener("click", e => {
        if (e.target.closest(".rk-dialog-close")) return d.close();
        // a click on the scrim (outside the dialog's box) closes it
        if (e.target === d) { const r = d.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) d.close(); }
      });
      d.addEventListener("close", () => { const o = openers.get(d); if (o && document.contains(o)) o.focus({ preventScroll: true }); });
    }
  }
  RK.dialog = { open, close };
  (RK.inits = RK.inits || []).push(init);
})();
