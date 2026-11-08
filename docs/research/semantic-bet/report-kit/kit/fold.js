/* report-kit fold. Markup: inside a .rk-split, <div class="rk-aside"> holding the column's head, then
   <button type="button" class="rk-fold" aria-controls="ID" hidden>Its name<span class="rk-fold-cur"></span></button>,
   then the part it folds (id="ID"); the stage is the split's .rk-stage. Once the stage sits under the column, the
   button shows and the part folds; side by side, the button hides and the part stays open. A click on an element
   marked data-rk-fold-pick inside the part (a choice) folds it again and gives the button the focus.
   ReportKit.fold.current(el, text) names the current choice on the button of the column holding el. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  function init(root) {
    for (const btn of root.querySelectorAll(".rk-aside > .rk-fold")) {
      if (btn.dataset.rkFoldOn) continue;
      btn.dataset.rkFoldOn = "";
      const aside = btn.parentElement, part = document.getElementById(btn.getAttribute("aria-controls"));
      const stage = aside.parentElement.querySelector(":scope > .rk-stage");
      if (!part || !stage) continue;
      let stacked = null;
      const set = (open) => { part.classList.toggle("rk-folded", !open); btn.setAttribute("aria-expanded", String(open)); };
      const sync = () => {
        const s = stage.getBoundingClientRect().top >= aside.getBoundingClientRect().bottom - 1;
        if (s === stacked) return;
        stacked = s; btn.hidden = !s; set(!s);
      };
      btn.addEventListener("click", () => set(part.classList.contains("rk-folded")));
      part.addEventListener("click", (e) => {
        if (stacked && e.target.closest && e.target.closest("[data-rk-fold-pick]")) { set(false); setTimeout(() => btn.focus(), 0); } // after a link's own navigation
      });
      if (window.ResizeObserver) new ResizeObserver(sync).observe(aside.parentElement); else window.addEventListener("resize", sync);
      sync();
    }
  }
  RK.fold = {
    init,
    current(el, text) {
      const a = el && el.closest && el.closest(".rk-aside");
      const c = a && a.querySelector(":scope > .rk-fold .rk-fold-cur");
      if (c) c.textContent = text || "";
    },
  };
  (RK.inits = RK.inits || []).push(init);
})();
