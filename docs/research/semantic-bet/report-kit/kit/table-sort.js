/* report-kit sortable table. Markup: <table class="rk-table" data-rk-sort> whose header cells carry
   data-sort="default" (the column that restores the page's own order), "number" or "text", each holding one
   <button type="button">; a cell's sort value is its data-v, else its text. Numbers sort highest first on the
   first press, text A to Z; a second press reverses. Ties keep the page's order. data-rk-flip slides rows to their
   new places (not under reduced motion). Event rk:sort {detail: {table, key, dir}} on the table. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const MARK = '<svg class="rk-sort-mark" viewBox="0 0 10 14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round" stroke-linejoin="round"><path class="up" d="M1.5 5 5 1.5 8.5 5"/><path class="dn" d="M1.5 9 5 12.5 8.5 9"/></svg>';
  const motion = () => !matchMedia("(prefers-reduced-motion: reduce)").matches;
  function value(row, col, type) {
    const c = row.cells[col];
    const own = n => !(n.classList && n.classList.contains("rk-cell-label"));
    const raw = c ? (c.dataset.v ?? [...c.childNodes].filter(own).map(n => n.textContent).join("").trim()) : "";
    if (type === "text") return raw;
    const n = parseFloat(String(raw).replace(/[^\d.+-]/g, ""));
    return Number.isNaN(n) ? -Infinity : n;
  }
  function setup(table) {
    const heads = [...table.tHead.rows[0].cells];
    const body = table.tBodies[0];
    [...body.rows].forEach((r, i) => { r.dataset.rkOrder = i; });
    const status = document.createElement("p");
    status.className = "rk-sr";
    status.setAttribute("aria-live", "polite");
    table.after(status);
    const sortable = heads.filter(th => th.dataset.sort);
    for (const th of sortable) {
      const b = th.querySelector("button");
      if (!b) continue;
      if (!b.querySelector(".rk-sort-mark")) b.insertAdjacentHTML("beforeend", MARK);
      if (!th.hasAttribute("aria-sort")) th.setAttribute("aria-sort", th.dataset.sort === "default" ? "ascending" : "none");
      b.addEventListener("click", () => {
        const kind = th.dataset.sort;
        const was = th.getAttribute("aria-sort");
        const first = kind === "text" ? "ascending" : "descending";
        const dir = kind === "default" ? "ascending" : was === first ? (first === "ascending" ? "descending" : "ascending") : first;
        sort(table, th.cellIndex, kind, dir);
        for (const h of sortable) h.setAttribute("aria-sort", h === th ? dir : "none");
        const label = (b.querySelector(".rk-label") || b).textContent.trim();
        status.textContent = kind === "default" ? "Back in the page's own order."
          : `Sorted by ${label}, ${kind === "text" ? (dir === "ascending" ? "A to Z" : "Z to A") : dir === "descending" ? "highest first" : "lowest first"}.`;
        table.dispatchEvent(new CustomEvent("rk:sort", { bubbles: true, detail: { table, key: label, dir } }));
      });
    }
    // cell labels for the stacked layout: each value carries its column's head (and its mark, if the head has one)
    if (table.classList.contains("rk-stack")) {
      for (const r of body.rows) for (const c of r.cells) {
        const h = heads[c.cellIndex];
        if (!h || c.tagName === "TH" || c.classList.contains("rk-wide") || c.querySelector(".rk-cell-label")) continue;
        const lab = document.createElement("span");
        lab.className = "rk-cell-label";
        lab.setAttribute("aria-hidden", "true");
        const mark = h.querySelector(".rk-mark");
        if (mark) lab.append(mark.cloneNode(true));
        lab.append(((h.querySelector(".rk-label") || h).textContent || "").trim());
        c.prepend(lab);
      }
    }
  }
  function sort(table, col, kind, dir) {
    const body = table.tBodies[0];
    const rows = [...body.rows];
    const animate = table.hasAttribute("data-rk-flip") && motion() && table.offsetParent;
    const before = animate ? new Map(rows.map(r => [r, r.getBoundingClientRect().top])) : null;
    const order = r => Number(r.dataset.rkOrder);
    rows.sort((a, b) => {
      if (kind === "default") return order(a) - order(b);
      const va = value(a, col, kind), vb = value(b, col, kind);
      const d = kind === "text" ? String(va).localeCompare(String(vb)) : va - vb;
      return (dir === "ascending" ? d : -d) || order(a) - order(b);
    }).forEach(r => body.appendChild(r));
    if (before) rows.forEach(r => {
      const dy = before.get(r) - r.getBoundingClientRect().top;
      if (dy) r.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 240, easing: "cubic-bezier(.2,.8,.2,1)" });
    });
  }
  function init() { for (const t of document.querySelectorAll("table[data-rk-sort]")) setup(t); }
  RK.tableSort = { sort };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
