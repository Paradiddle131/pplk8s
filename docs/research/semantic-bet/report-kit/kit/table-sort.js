/* report-kit sortable table. Markup: <table class="rk-table" data-rk-sort> whose header cells carry
   data-sort="default" (the column that restores the page's own order), "number" or "text", each holding one
   <button type="button">; a cell's sort value is its data-v, else its text. Numbers sort highest first on the
   first press, text A to Z; a second press reverses. Ties keep the page's order.
   Options on the table:
     data-rk-sort="toggle"        two states: every press flips its column, and nothing returns to the page's own
                                  order (a default column then flips the page's order too); no column needs to be
                                  the default
     data-rk-sort-group="name"    tables in one group share one sort: sorting one sorts the others the same way
     data-rk-sort-restored="..."  what the live region says when the page's own order comes back
     data-rk-flip                 rows slide to their new places (not under reduced motion)
     data-rk-stack-at="40rem"     with rk-stack: the container width under which rows stack (default 56rem)
   Header labels flow inline, so a wrapped label keeps its column's mark on its first word and the direction mark
   on its last. Event rk:sort {detail: {table, key, dir}} on the table (not on the tables a group sorts with it). */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const MARK = '<svg class="rk-sort-mark" viewBox="0 0 10 14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round" stroke-linejoin="round"><path class="up" d="M1.5 5 5 1.5 8.5 5"/><path class="dn" d="M1.5 9 5 12.5 8.5 9"/></svg>';
  const motion = () => !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const done = new WeakSet();
  function value(row, col, type) {
    const c = row.cells[col];
    const own = n => !(n.classList && n.classList.contains("rk-cell-label"));
    const raw = c ? (c.dataset.v ?? [...c.childNodes].filter(own).map(n => n.textContent).join("").trim()) : "";
    if (type === "text") return raw;
    const n = parseFloat(String(raw).replace(/[^\d.+-]/g, ""));
    return Number.isNaN(n) ? -Infinity : n;
  }
  const heads = table => [...table.tHead.rows[0].cells];
  const toggles = table => table.dataset.rkSort === "toggle";
  // the label's first word keeps the column's mark and its last word keeps the direction mark, on any wrap
  function glue(b) {
    const label = b.querySelector(".rk-label");
    const mark = b.querySelector(":scope > .rk-mark");
    const sortMark = b.querySelector(".rk-sort-mark");
    if (!label || label.children.length) { if (!sortMark) b.insertAdjacentHTML("beforeend", MARK); return; }
    const words = label.textContent.trim().split(/\s+/);
    const nw = () => { const s = document.createElement("span"); s.className = "rk-nw"; return s; };
    const first = nw(), last = words.length > 1 ? nw() : first;
    if (mark) first.append(mark);
    first.append(words[0]);
    label.replaceChildren(first);
    if (words.length > 2) label.append(" " + words.slice(1, -1).join(" "));
    if (last !== first) { label.append(" "); last.append(words[words.length - 1]); label.append(last); }
    if (sortMark) last.append(sortMark); else last.insertAdjacentHTML("beforeend", MARK);
  }
  function setup(table) {
    if (done.has(table)) return;
    done.add(table);
    const hs = heads(table);
    const body = table.tBodies[0];
    [...body.rows].forEach((r, i) => { r.dataset.rkOrder = i; });
    const status = document.createElement("p");
    status.className = "rk-sr";
    status.setAttribute("aria-live", "polite");
    table.after(status);
    table.rkStatus = status;
    const sortable = hs.filter(th => th.dataset.sort);
    const preset = sortable.some(h => h.hasAttribute("aria-sort"));
    for (const th of sortable) {
      const b = th.querySelector("button");
      if (!b) continue;
      glue(b);
      if (!th.hasAttribute("aria-sort")) th.setAttribute("aria-sort", th.dataset.sort === "default" && !preset ? "ascending" : "none");
      b.addEventListener("click", () => {
        const kind = th.dataset.sort;
        const was = th.getAttribute("aria-sort");
        const first = kind === "number" ? "descending" : "ascending";
        const flip = d => (d === "ascending" ? "descending" : "ascending");
        const dir = kind === "default" && !toggles(table) ? "ascending" : was === "none" ? first : toggles(table) ? flip(was) : was === first ? flip(first) : first;
        apply(table, th.cellIndex, kind, dir, true);
        const group = table.dataset.rkSortGroup;
        if (group) for (const t of document.querySelectorAll(`table[data-rk-sort-group="${CSS.escape(group)}"]`)) if (t !== table) apply(t, th.cellIndex, kind, dir, false);
        table.dispatchEvent(new CustomEvent("rk:sort", { bubbles: true, detail: { table, key: labelOf(th), dir } }));
      });
    }
    if (table.classList.contains("rk-stack")) stack(table, hs);
  }
  const labelOf = th => ((th.querySelector(".rk-label") || th).textContent || "").trim();
  // sorts a table and marks its heads; speak: say so in the table's live region
  function apply(table, col, kind, dir, speak) {
    sort(table, col, kind, dir);
    for (const h of heads(table)) if (h.dataset.sort) h.setAttribute("aria-sort", h.cellIndex === col ? dir : "none");
    if (!speak || !table.rkStatus) return;
    const th = heads(table)[col];
    const restored = kind === "default" && dir === "ascending";
    table.rkStatus.textContent = restored ? (table.dataset.rkSortRestored || "Back in the page's own order.")
      : kind === "default" ? "In the page's own order, reversed."
      : `Sorted by ${labelOf(th)}, ${kind === "text" ? (dir === "ascending" ? "A to Z" : "Z to A") : dir === "descending" ? "highest first" : "lowest first"}.`;
  }
  // the stacked layout: each value carries its column's head (its mark and words; the mark alone in rk-stack-compact)
  function stack(table, hs) {
    for (const r of table.tBodies[0].rows) for (const c of r.cells) {
      const h = hs[c.cellIndex];
      if (!h || c.tagName === "TH" || c.classList.contains("rk-wide") || c.querySelector(".rk-cell-label")) continue;
      const lab = document.createElement("span");
      lab.className = "rk-cell-label";
      lab.setAttribute("aria-hidden", "true");
      const mark = h.querySelector(".rk-mark");
      if (mark) lab.append(mark.cloneNode(true));
      const words = document.createElement("span");
      words.className = "rk-cell-words";
      words.textContent = labelOf(h);
      lab.append(words);
      c.prepend(lab);
    }
    const wrap = table.parentElement;
    const at = () => {
      const v = (table.dataset.rkStackAt || "56rem").trim();
      const n = parseFloat(v);
      return /rem$/.test(v) ? n * parseFloat(getComputedStyle(document.documentElement).fontSize) : /em$/.test(v) ? n * parseFloat(getComputedStyle(table).fontSize) : n;
    };
    const fit = () => table.classList.toggle("is-stacked", wrap.clientWidth < at());
    fit();
    if (window.ResizeObserver) new ResizeObserver(fit).observe(wrap);
  }
  function sort(table, col, kind, dir) {
    const body = table.tBodies[0];
    const rows = [...body.rows];
    const animate = table.hasAttribute("data-rk-flip") && motion() && table.offsetParent;
    const before = animate ? new Map(rows.map(r => [r, r.getBoundingClientRect().top])) : null;
    const order = r => Number(r.dataset.rkOrder);
    rows.sort((a, b) => {
      if (kind === "default") return dir === "ascending" ? order(a) - order(b) : order(b) - order(a);
      const va = value(a, col, kind), vb = value(b, col, kind);
      const d = kind === "text" ? String(va).localeCompare(String(vb)) : va - vb;
      return (dir === "ascending" ? d : -d) || order(a) - order(b);
    }).forEach(r => body.appendChild(r));
    if (before) rows.forEach(r => {
      const dy = before.get(r) - r.getBoundingClientRect().top;
      if (dy) r.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 240, easing: "cubic-bezier(.2,.8,.2,1)" });
    });
  }
  function init(root) { for (const t of root.querySelectorAll("table[data-rk-sort]")) setup(t); }
  RK.tableSort = { sort, apply: (table, col, kind, dir) => apply(table, col, kind, dir, false) };
  (RK.inits = RK.inits || []).push(init);
})();
