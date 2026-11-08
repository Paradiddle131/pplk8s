/* report-kit find. Markup: a <div class="rk-find" data-rk-find="<list id>"> holding a <label class="rk-find-box"> (its
   words, then <input type="search">), an optional <div class="rk-chips" role="group" aria-label="..."> of
   <button type="button" data-value="<type or empty for all>" aria-pressed> chips, each with a <span class="rk-chip-n">,
   and a <p class="rk-find-count" role="status">. The list (the element with the list id) holds items marked
   data-rk-find-item, inside groups marked data-rk-find-group="<type>" (or an item's own data-rk-find-type), and a
   <p class="rk-find-none" hidden> that says nothing matches, with a <button type="button"> that clears the box.
   An item matches when its text (data-rk-find-text, else its own text) holds every word typed, ignoring case and
   accents, and its type is the chosen one; a group with no match hides; each chip counts the matches in its type, so
   the reader sees where the matches are before choosing. data-rk-find-noun="terms" names what is counted. A hash that
   names a hidden item clears what hides it before the tabs scroll to it (ReportKit.find.reveal).
   API: ReportKit.find.reveal(el), .apply(list); event rk:find {detail: {list, shown, total}} on the list. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const norm = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const lists = new Map(); // list element -> state
  const typeOf = it => it.dataset.rkFindType || (it.closest("[data-rk-find-group]") || {}).dataset?.rkFindGroup || "";
  function apply(list) {
    const st = lists.get(list);
    if (!st) return;
    const words = norm(st.input ? st.input.value : "").split(/\s+/).filter(Boolean);
    const hit = it => { const h = norm(it.dataset.rkFindText || it.textContent); return words.every(w => h.includes(w)); };
    const items = [...list.querySelectorAll("[data-rk-find-item]")];
    const hits = new Set(items.filter(hit));
    let shown = 0;
    for (const it of items) { const on = hits.has(it) && (!st.type || typeOf(it) === st.type); it.hidden = !on; if (on) shown++; }
    for (const g of list.querySelectorAll("[data-rk-find-group]")) g.hidden = ![...g.querySelectorAll("[data-rk-find-item]")].some(it => !it.hidden);
    for (const b of st.chips) {
      b.setAttribute("aria-pressed", String((b.dataset.value || "") === st.type));
      const n = b.querySelector(".rk-chip-n");
      if (n) n.textContent = [...hits].filter(it => !b.dataset.value || typeOf(it) === b.dataset.value).length;
    }
    const noun = st.box.dataset.rkFindNoun || "items", narrowed = words.length || st.type;
    if (st.count) st.count.textContent = narrowed ? `${shown} of ${items.length} ${noun} shown` : `${items.length} ${noun}`;
    const none = list.querySelector(".rk-find-none");
    if (none) none.hidden = shown > 0;
    list.dispatchEvent(new CustomEvent("rk:find", { bubbles: true, detail: { list, shown, total: items.length } }));
  }
  function clear(list) {
    const st = lists.get(list);
    if (st.input) st.input.value = "";
    st.type = "";
    apply(list);
  }
  // an item a link or the hash points at comes back, whatever narrowed the list
  function reveal(el) {
    for (const [list, st] of lists) {
      if (!list.contains(el)) continue;
      const it = el.closest("[data-rk-find-item]") || el;
      if (it.hidden || (it.closest("[data-rk-find-group]") || {}).hidden) clear(list);
      return true;
    }
    return false;
  }
  function init(root) {
    for (const box of root.querySelectorAll("[data-rk-find]")) {
      const list = document.getElementById(box.dataset.rkFind);
      if (!list || lists.has(list)) continue;
      const chips = [...box.querySelectorAll(".rk-chips button")];
      const st = { box, input: box.querySelector('input[type="search"]'), chips, count: box.querySelector(".rk-find-count"),
        type: (chips.find(b => b.getAttribute("aria-pressed") === "true") || { dataset: {} }).dataset.value || "" };
      lists.set(list, st);
      if (st.input) st.input.addEventListener("input", () => apply(list));
      for (const b of chips) b.addEventListener("click", () => { st.type = b.dataset.value || ""; apply(list); });
      list.addEventListener("click", e => { if (!e.target.closest(".rk-find-none button")) return; clear(list); if (st.input) st.input.focus(); });
      apply(list);
    }
  }
  RK.find = { reveal, apply };
  (RK.inits = RK.inits || []).push(init);
})();
