/* report-kit tabs. Markup: a .rk-tabs <nav> holding a [role=tablist] of <a role=tab href="#part" aria-controls="part">,
   and each part a [role=tabpanel] with that id. A part with nothing in it loses its tab; one part left hides
   the strip. The URL's hash names the open part, or an element inside one, which opens its part and comes into
   view (a search or filter that hides it is cleared first: ReportKit.find.reveal); Back and Forward walk the parts; one strip per page (the first in the kit's root). API: ReportKit.tabs.open(id); event rk:tab {detail: id} on document. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  function init(root) {
    const strip = root.querySelector(".rk-tabs");
    if (!strip) return;
    const list = strip.querySelector('[role="tablist"]');
    const panelOf = t => document.getElementById(t.getAttribute("aria-controls"));
    for (const t of [...list.querySelectorAll('[role="tab"]')]) {
      const p = panelOf(t);
      if (!p || !p.textContent.trim()) { t.remove(); if (p) p.remove(); }
    }
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    if (!tabs.length) return;
    strip.hidden = tabs.length < 2;
    const panels = tabs.map(panelOf);
    let current = null;
    function show(p) {
      if (!p || p === current) return;
      current = p;
      panels.forEach((q, i) => {
        const on = q === p;
        q.hidden = !on;
        tabs[i].setAttribute("aria-selected", String(on));
        tabs[i].tabIndex = on ? 0 : -1;
      });
      document.dispatchEvent(new CustomEvent("rk:tab", { detail: p.id }));
    }
    // the hash -> [part, element inside it or null]
    function resolve() {
      let h = location.hash.slice(1);
      try { h = decodeURIComponent(h); } catch (e) { /* keep it raw */ }
      const el = h && document.getElementById(h);
      if (!el) return [panels[0], null];
      if (panels.includes(el)) return [el, null];
      const p = el.closest('[role="tabpanel"]');
      return p && panels.includes(p) ? [p, el] : [current || panels[0], el];
    }
    function route() {
      const [p, el] = resolve();
      show(p);
      if (el) {
        if (RK.find) RK.find.reveal(el); // an entry a search or a type filter hides comes back first
        el.scrollIntoView({ block: "center" });
        el.classList.remove("rk-flash"); void el.offsetWidth; el.classList.add("rk-flash");
      }
    }
    function go(i, replace) {
      const url = "#" + panels[i].id;
      try { history[replace ? "replaceState" : "pushState"](null, "", url); } catch (e) { location.hash = url; }
      show(panels[i]);
      const top = strip.getBoundingClientRect().top;
      if (top < 0) strip.scrollIntoView({ block: "start" });
    }
    list.addEventListener("click", e => {
      const t = e.target.closest('[role="tab"]');
      if (!t || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      go(tabs.indexOf(t), false);
    });
    list.addEventListener("keydown", e => {
      const i = tabs.indexOf(e.target.closest('[role="tab"]'));
      if (i < 0) return;
      const j = { ArrowRight: (i + 1) % tabs.length, ArrowLeft: (i - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 }[e.key];
      if (e.key === " ") { e.preventDefault(); tabs[i].click(); return; }
      if (j === undefined) return;
      e.preventDefault();
      tabs[j].focus();
      go(j, true);
    });
    addEventListener("popstate", route);
    addEventListener("hashchange", route);
    RK.tabs = { open: id => { const i = panels.findIndex(p => p.id === id); if (i >= 0) go(i, false); } };
    route();
  }
  (RK.inits = RK.inits || []).push(init);
})();
