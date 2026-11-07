/* The Approaches sections' own behaviour over report-kit. The route lifts off when a number sorts the table and comes
   back with the native-to-custom order; the question sets' tables keep one sort between them, so switching sets keeps
   the order the reader chose; a definition the keyboard reaches keeps its bubble through the scroll that brings it
   into view. The kinds grids sort by any kind of question, highest or lowest first. */
(() => {
  function setup() {
    const tables = [...document.querySelectorAll("table.ap-table")];
    const route = t => {
      const home = t.querySelector('th[data-sort="default"]');
      t.dataset.route = home && home.getAttribute("aria-sort") === "ascending" ? "on" : "off";
    };
    for (const t of tables) {
      t.addEventListener("rk:sort", () => {
        const th = [...t.tHead.rows[0].cells].find(h => h.dataset.sort && h.getAttribute("aria-sort") !== "none");
        route(t);
        if (!th) return;
        const dir = th.getAttribute("aria-sort");
        for (const u of tables) {
          if (u === t) continue;
          window.ReportKit.tableSort.sort(u, th.cellIndex, th.dataset.sort, dir);
          for (const h of u.tHead.rows[0].cells) if (h.dataset.sort) h.setAttribute("aria-sort", h.cellIndex === th.cellIndex ? dir : "none");
          route(u);
        }
      });
    }
    // The kinds grids: each kind's head sorts the rows, highest first on the first press, then lowest first, and
    // back; there is no return to the native-to-custom order. The grids of the two question sets keep one sort.
    const grids = [...document.querySelectorAll("table[data-ap-sort]")];
    for (const g of grids) {
      [...g.tBodies[0].rows].forEach((r, i) => { r.dataset.rkOrder = i; });
      const live = document.createElement("p");
      live.className = "rk-sr";
      live.setAttribute("aria-live", "polite");
      g.after(live);
      g._live = live;
    }
    const sortGrids = (col, dir, from) => {
      for (const g of grids) {
        window.ReportKit.tableSort.sort(g, col, "number", dir);
        for (const h of g.tHead.rows[0].cells) if (h.hasAttribute("aria-sort")) h.setAttribute("aria-sort", h.cellIndex === col ? dir : "none");
      }
      const label = from.querySelector(".rk-label").textContent.replace(/\u00ad/g, "").trim();
      const g = from.closest("table");
      g._live.textContent = `Sorted by ${label}, ${dir === "descending" ? "highest first" : "lowest first"}.`;
    };
    for (const g of grids) {
      for (const th of g.tHead.rows[0].cells) {
        const b = th.querySelector("button");
        if (!b) continue;
        b.addEventListener("click", () => sortGrids(th.cellIndex, th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending", b));
      }
    }
    // A definition reached by the keyboard below the fold: the browser scrolls it into view, and the kit's bubble,
    // which closes on any scroll, would close with it. While the keyboard rests on it, the bubble stays on it.
    addEventListener("scroll", () => {
      const a = document.activeElement;
      if (a && a.dataset && a.dataset.tip && a.closest(".ap") && a.matches(":focus-visible")) window.ReportKit.tip.show(a);
    }, { passive: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup); else setup();
})();
